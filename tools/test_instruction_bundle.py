import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import instruction_bundle as bundle
from agent_entrypoint import EntryError, encoded, sha


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="instruction workspace ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "child").mkdir()
        subprocess.run(["git", "init", "-q", str(self.root / "child")], check=True)
        (self.root / ".golem/bin").mkdir(parents=True)
        (self.root / ".golem/bin/golem").write_text("fixture executable\n")
        (self.root / "AGENTS.md").write_bytes(b"Original rules\r\n")
        (self.root / "CLAUDE.md").write_text("Original pointer\n")
        self.value = {"schema": bundle.SCHEMA, "project": str(self.root), "repositories": ["child"],
                      "cli": ".golem/bin/golem", "pins": {".golem/bin/golem": sha(b"fixture executable\n")},
                      "files": {name: {"before": sha((self.root / name).read_bytes()), "text": text}
                                for name, text in (("AGENTS.md", "Reviewed safety and completion rules\n"),
                                                   ("CLAUDE.md", "Read AGENTS.md\n"))}}
        self.value["files"][bundle.HOME + "/policies/work.md"] = {"before": None, "text": "Exact detailed rules\n"}

    def install(self):
        key = bundle.identity(bundle.plan(self.value))
        return bundle.apply(self.value, key), key

    def test_install_backup_idempotency_and_executable_check(self):
        result, key = self.install()
        self.assertEqual(result["status"], "READY")
        self.assertFalse(result["model_instruction_loading_verified"])
        self.assertFalse(result["token_savings_verified"])
        backup = self.root / bundle.HOME / (self.value["files"]["AGENTS.md"]["before"] + ".before")
        self.assertEqual(backup.read_bytes(), b"Original rules\r\n")
        state = self.root / bundle.HOME / "state.json"
        old_stat = state.stat().st_mtime_ns
        self.assertEqual(bundle.apply(self.value, key), result)
        self.assertEqual(state.stat().st_mtime_ns, old_stat)
        process = subprocess.run([sys.executable, str(self.root / bundle.HOME / "instruction_bundle.py"),
                                  "check", "--project", "."], cwd=self.root, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stdout)

    def test_readonly_plan_and_wrong_hash(self):
        bundle.plan(self.value)
        self.assertFalse((self.root / bundle.HOME).exists())
        with self.assertRaisesRegex(EntryError, "STALE"):
            bundle.apply(self.value, "0" * 64)
        self.assertFalse((self.root / bundle.HOME).exists())

    def test_source_drift(self):
        key = bundle.identity(bundle.plan(self.value))
        (self.root / "AGENTS.md").write_text("User changes\n")
        with self.assertRaisesRegex(EntryError, "STALE"):
            bundle.apply(self.value, key)
        self.assertEqual((self.root / "AGENTS.md").read_text(), "User changes\n")

    def test_dependency_drift(self):
        self.install()
        (self.root / ".golem/bin/golem").write_text("new binary")
        with self.assertRaisesRegex(EntryError, "DEPENDENCY_DRIFT"):
            bundle.check(self.root)

    def test_instruction_and_tool_drift(self):
        self.install()
        for name in ("AGENTS.md", bundle.HOME + "/policies/work.md", bundle.HOME + "/verify_agent.py"):
            path = self.root / name
            original = path.read_bytes()
            path.write_bytes(original + b"tampered")
            with self.assertRaisesRegex(EntryError, "DRIFT"):
                bundle.check(self.root)
            path.write_bytes(original)

    def test_scope_and_path_escape(self):
        for name in ("child/AGENTS.md", "../AGENTS.md", "/tmp/AGENTS.md", ".golem/project.json",
                     bundle.HOME + "/policies/../../escape"):
            value = copy.deepcopy(self.value)
            value["files"][name] = {"before": None, "text": "not allowed"}
            with self.assertRaises(EntryError):
                bundle.plan(value)

    def test_git_parent_rejected(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        with self.assertRaisesRegex(EntryError, "WORKSPACE"):
            bundle.plan(self.value)

    def test_symlink_and_override(self):
        override = self.root / "AGENTS.override.md"
        override.write_text("override")
        with self.assertRaisesRegex(EntryError, "OVERRIDE"):
            bundle.plan(self.value)
        override.unlink()
        (self.root / "AGENTS.md").unlink()
        (self.root / "AGENTS.md").symlink_to(self.root / "CLAUDE.md")
        with self.assertRaisesRegex(EntryError, "SYMLINK"):
            bundle.plan(self.value)

    def test_interruption_retains_originals_and_blocks(self):
        real = bundle.atomic_write
        def interrupted(path, data, *args):
            if path.name == "state.json":
                raise OSError("injected interruption")
            real(path, data, *args)
        with patch.object(bundle, "atomic_write", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.install()
        backup = self.root / bundle.HOME / (self.value["files"]["AGENTS.md"]["before"] + ".before")
        self.assertEqual(backup.read_bytes(), b"Original rules\r\n")
        with self.assertRaises(FileNotFoundError):
            bundle.check(self.root)
        with self.assertRaisesRegex(EntryError, "STALE"):
            bundle.plan(self.value)

    def test_busy_preserves_files(self):
        key = bundle.identity(bundle.plan(self.value))
        lock = self.root / ".golem/entrypoints/apply.lock"
        lock.parent.mkdir(parents=True)
        lock.write_text("busy")
        with self.assertRaisesRegex(EntryError, "BUSY"):
            bundle.apply(self.value, key)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), b"Original rules\r\n")

    def test_budget_never_truncates(self):
        self.value["files"]["AGENTS.md"]["text"] = "x" * 8193
        with self.assertRaisesRegex(EntryError, "BUDGET"):
            bundle.plan(self.value)

    def test_duplicate_json_cli_blocked(self):
        path = self.root / "manifest.json"
        path.write_text('{"schema":1,"schema":2}')
        process = subprocess.run([sys.executable, bundle.__file__, "plan", "--manifest", str(path)],
                                 capture_output=True)
        self.assertEqual(process.returncode, 1)
        self.assertIn(b"BLOCKED", process.stdout)

    def test_symlink_retarget_same_content_blocks(self):
        binary = self.root / ".golem/bin/golem"
        content = binary.read_bytes()
        binary.unlink()
        first, second = binary.parent / "first", binary.parent / "second"
        first.write_bytes(content)
        second.write_bytes(content)
        binary.symlink_to(first)
        self.install()
        binary.unlink()
        binary.symlink_to(second)
        with self.assertRaisesRegex(EntryError, "DEPENDENCY_DRIFT"):
            bundle.check(self.root)

    def test_new_override_after_install_blocks(self):
        self.install()
        (self.root / "AGENTS.override.md").write_text("new override")
        with self.assertRaisesRegex(EntryError, "OVERRIDE"):
            bundle.check(self.root)

    def test_no_implicit_replacement(self):
        self.install()
        self.value["files"]["AGENTS.md"]["text"] = "Different policy\n"
        with self.assertRaisesRegex(EntryError, "INSTALLED"):
            bundle.apply(self.value, "0" * 64)

    def test_private_symlink_and_external_repository(self):
        self.value["repositories"] = ["../external"]
        with self.assertRaises(EntryError):
            bundle.plan(self.value)
        self.value["repositories"] = ["child"]
        directory = self.root / ".golem/entrypoints"
        directory.symlink_to(self.root / "child", target_is_directory=True)
        with self.assertRaisesRegex(EntryError, "SYMLINK"):
            bundle.plan(self.value)


if __name__ == "__main__":
    unittest.main()
