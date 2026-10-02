"""Disposable project rollout: exact user-rule preservation and fail-closed drift."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import agent_entrypoint as entry


class Entrypoint(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.git("init", "-q")
        (self.project / ".gitignore").write_text(".golem/\n")
        self.sdk = self.root / "sdk with spaces"
        (self.sdk / "docs").mkdir(parents=True)
        (self.sdk / "samples/agent-session").mkdir(parents=True)
        (self.sdk / "tools").mkdir()
        source = Path(entry.__file__).resolve().parents[1]
        for name in ("AGENTS.minimal.md", "AGENTS.minimal.ko.md"):
            shutil.copyfile(source / "samples/agent-session" / name, self.sdk / "samples/agent-session" / name)
        for name in entry.DOCS:
            (self.sdk / "docs" / name).write_text("# " + name + "\n")
        shutil.copyfile(entry.__file__, self.sdk / "tools/agent_entrypoint.py")
        shutil.copyfile(source / "tools/verify_agent.py", self.sdk / "tools/verify_agent.py")
        shutil.copyfile(source / "tools/execution_record.py", self.sdk / "tools/execution_record.py")
        self.cli = self.root / "golem"
        self.cli.write_text("#!/bin/sh\nprintf '0.1.0\\n'\n")
        self.cli.chmod(0o755)
        self.config = {"schema": entry.SCHEMA, "language": "en", "sdk": str(self.sdk),
                       "cli": str(self.cli), "work_root": ".golem/workspace/works", "repositories": ["."]}
        self.write_config()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.project), *args], capture_output=True, check=True).stdout

    def write_config(self):
        (self.project / ".golem-agent.json").write_bytes(entry.encoded(self.config))

    def apply(self):
        return entry.apply(self.project, entry.plan_identity(entry.plan(self.project)))

    def expect_code(self, code, call):
        with self.assertRaises(entry.EntryError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_plan_is_readonly_and_resolves_all_placeholders(self):
        value = entry.plan(self.project)
        self.assertEqual(value["before"], "absent")
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / ".golem").exists())
        self.assertNotIn(b"<GOLEM_", value["new"])
        self.assertIn(b"sdk with spaces", value["new"])
        self.assertIn(b"check --project .", value["new"])

    def test_apply_both_languages_and_probe(self):
        for language in ("en", "ko"):
            self.config["language"] = language
            self.write_config()
            result = self.apply()
            self.assertEqual(result["status"], "READY")
            self.assertFalse(result["model_instruction_loading_verified"])
            self.assertFalse(result["product_acceptance"])
            self.assertLessEqual(result["managed_bytes"], entry.MAX_BLOCK)
            self.assertEqual(entry.check(self.project, probe=True)["cli_probe"], "PASS")

    def test_probe_requires_actual_version_shape(self):
        for output, accepted in (("golem 0.1.0", True), ("golem unrelated text", False),
                                 ("0.1.0 extra", False)):
            self.cli.write_text("#!/bin/sh\nprintf '%s\\n' '" + output + "'\n")
            self.apply()
            if accepted:
                self.assertEqual(entry.check(self.project, probe=True)["cli_probe"], "PASS")
            else:
                self.expect_code("CLI_PROBE", lambda: entry.check(self.project, probe=True))

    def test_preserves_unmanaged_bytes_and_backup(self):
        original = "# Local rules\r\n보안 규칙 유지.\r\nDo not deploy.".encode()
        path = self.project / "AGENTS.md"
        path.write_bytes(original)
        path.chmod(0o640)
        self.apply()
        self.assertTrue(path.read_bytes().startswith(original))
        state = json.loads((self.project / ".golem/entrypoints/state.json").read_bytes())
        self.assertEqual(Path(state["backup"]).read_bytes(), original)
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_preserves_prefix_suffix_on_update(self):
        first = entry.plan(self.project)["block"]
        path = self.project / "AGENTS.md"
        path.write_bytes(b"# Before\n" + first + b"# After\nNever upload credentials.\n")
        self.config["language"] = "ko"
        self.write_config()
        self.apply()
        self.assertTrue(path.read_bytes().startswith(b"# Before\n"))
        self.assertTrue(path.read_bytes().endswith(b"# After\nNever upload credentials.\n"))
        self.assertEqual(path.read_bytes().count(entry.BEGIN), 1)

    def test_repeat_is_idempotent(self):
        self.apply()
        path = self.project / "AGENTS.md"
        state = self.project / ".golem/entrypoints/state.json"
        before = path.read_bytes(), state.read_bytes(), path.stat().st_mtime_ns
        files = sorted((self.project / ".golem").rglob("*"))
        self.apply()
        self.assertEqual(before, (path.read_bytes(), state.read_bytes(), path.stat().st_mtime_ns))
        self.assertEqual(files, sorted((self.project / ".golem").rglob("*")))

    def test_stale_expected_hash_never_overwrites(self):
        self.expect_code("STALE", lambda: entry.apply(self.project, "0" * 64))
        self.assertFalse((self.project / "AGENTS.md").exists())
        (self.project / "AGENTS.md").write_text("# New rules\n")
        self.expect_code("STALE", lambda: entry.apply(self.project, "absent"))
        self.assertEqual((self.project / "AGENTS.md").read_text(), "# New rules\n")

    def test_reviewed_plan_binds_config_and_sdk_not_only_agents(self):
        reviewed = entry.plan_identity(entry.plan(self.project))
        self.config["language"] = "ko"
        self.write_config()
        self.expect_code("STALE", lambda: entry.apply(self.project, reviewed))
        reviewed = entry.plan_identity(entry.plan(self.project))
        (self.sdk / "docs/completion.md").write_text("# changed completion\n")
        self.expect_code("STALE", lambda: entry.apply(self.project, reviewed))
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_unmanaged_golem_refused_not_deleted(self):
        path = self.project / "AGENTS.md"
        path.write_text("# Project\n## Golem Work Rules\nExisting rules.\n")
        before = path.read_bytes()
        self.expect_code("UNMANAGED_GOLEM", lambda: entry.plan(self.project))
        self.assertEqual(path.read_bytes(), before)

    def test_duplicate_incomplete_reversed_and_inline_markers(self):
        for data in (entry.BEGIN, entry.END, entry.BEGIN + entry.END + entry.BEGIN + entry.END,
                     entry.END + entry.BEGIN, b"text" + entry.BEGIN + entry.END):
            (self.project / "AGENTS.md").write_bytes(data)
            self.expect_code("MARKERS", lambda: entry.plan(self.project))

    def test_symlink_hardlink_runtime_symlink_refused(self):
        target = self.root / "real.md"
        target.write_text("# Keep\n")
        path = self.project / "AGENTS.md"
        path.symlink_to(target)
        self.expect_code("SYMLINK", lambda: entry.plan(self.project))
        path.unlink()
        os.link(target, path)
        self.expect_code("UNSAFE_FILE", lambda: entry.plan(self.project))
        path.unlink()
        (self.project / ".golem").symlink_to(self.root)
        self.expect_code("SYMLINK", lambda: entry.plan(self.project))

    def test_override_blocks_application(self):
        path = self.project / "AGENTS.override.md"
        path.write_text("# Override\n")
        self.expect_code("OVERRIDE", lambda: entry.plan(self.project))
        path.write_text("")
        self.apply()

    def test_required_document_and_binary_missing(self):
        path = self.sdk / "docs/completion.md"
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            entry.plan(self.project)
        path.write_text("# completion\n")
        self.cli.unlink()
        self.expect_code("CLI_MISSING", lambda: entry.plan(self.project))

    def test_sdk_tool_mismatch_is_not_a_valid_entry_command(self):
        (self.sdk / "tools/agent_entrypoint.py").write_text("# different revision\n")
        self.expect_code("SDK_TOOL_MISMATCH", lambda: entry.plan(self.project))

    def test_rendered_entry_command_really_runs_from_target_root(self):
        self.apply()
        result = subprocess.run([sys.executable, str(self.sdk / "tools/agent_entrypoint.py"),
                                 "check", "--project", "."], cwd=self.project, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "READY")

    def test_missing_ignore_or_tracked_private_state_refused(self):
        (self.project / ".gitignore").write_text("")
        with self.assertRaises(subprocess.CalledProcessError):
            entry.plan(self.project)
        (self.project / ".gitignore").write_text(".golem/\n")
        (self.project / ".golem").mkdir()
        (self.project / ".golem/private").write_text("private")
        self.git("add", "-f", ".golem/private")
        self.expect_code("TRACKED_RUNTIME", lambda: entry.plan(self.project))

    def test_each_private_path_must_be_ignored(self):
        (self.project / ".gitignore").write_text(".golem/entrypoints/\n")
        with self.assertRaises(subprocess.CalledProcessError):
            entry.plan(self.project)

    def test_drift_binary_documents_config_and_user_rules(self):
        self.apply()
        paths = [self.cli, self.sdk / "docs/execution.md", self.project / "AGENTS.md"]
        for path in paths:
            before = path.read_bytes()
            path.write_bytes(before + b"\nchanged\n")
            self.expect_code("DRIFT", lambda: entry.check(self.project))
            path.write_bytes(before)
        self.config["language"] = "ko"
        self.write_config()
        self.expect_code("DRIFT", lambda: entry.check(self.project))

    def test_removed_completion_guard_detected(self):
        self.apply()
        path = self.project / "AGENTS.md"
        path.write_bytes(path.read_bytes().replace(b"DONE", b"done"))
        self.expect_code("DRIFT", lambda: entry.check(self.project))

    def test_budget_never_truncates_user_rules(self):
        path = self.project / "AGENTS.md"
        original = b"# Rules\n" + b"x" * entry.MAX_TOTAL
        path.write_bytes(original)
        self.expect_code("TOTAL_BUDGET", lambda: entry.plan(self.project))
        self.assertEqual(path.read_bytes(), original)

    def test_bad_config_duplicate_keys_and_path_injection(self):
        path = self.project / ".golem-agent.json"
        path.write_text('{"schema":1,"schema":2}')
        with self.assertRaises(ValueError):
            entry.plan(self.project)
        self.config["cli"] = "bad`command"
        self.write_config()
        self.expect_code("PATH", lambda: entry.plan(self.project))

    def test_work_root_cannot_escape_or_overlap_metadata(self):
        for value in (str(self.root), ".golem", ".golem/entrypoints", ".golem/entrypoints/works"):
            self.config["work_root"] = value
            self.write_config()
            self.expect_code("WORK_ROOT", lambda: entry.plan(self.project))

    def test_lock_conflict_does_not_remove_existing_lock(self):
        directory = self.project / ".golem/entrypoints"
        directory.mkdir(parents=True)
        lock = directory / "apply.lock"
        lock.write_text("other process")
        self.expect_code("BUSY", self.apply)
        self.assertEqual(lock.read_text(), "other process")

    def test_failed_publish_preserves_backup_and_can_repair(self):
        path = self.project / "AGENTS.md"
        path.write_text("# Existing\n")
        original = path.read_bytes()
        write = entry.atomic_write
        def fail_state(target, data, mode=0o600):
            if target.name == "state.json":
                raise OSError("injected metadata failure")
            return write(target, data, mode)
        with patch.object(entry, "atomic_write", side_effect=fail_state), self.assertRaises(OSError):
            self.apply()
        backup = self.project / ".golem/entrypoints" / (entry.sha(original) + ".before.md")
        self.assertEqual(backup.read_bytes(), original)
        with self.assertRaises(FileNotFoundError):
            entry.check(self.project)
        self.assertEqual(self.apply()["status"], "READY")

    def test_probe_failure_does_not_assert_readiness(self):
        self.cli.write_text("#!/bin/sh\nexit 7\n")
        self.apply()
        self.expect_code("CLI_PROBE", lambda: entry.check(self.project, probe=True))

    def test_cli_plan_apply_check_roundtrip(self):
        script = Path(entry.__file__).resolve()
        def call(*args):
            return subprocess.run([sys.executable, str(script), *args, "--project", str(self.project)],
                                  capture_output=True, text=True)
        result = call("plan")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        before = json.loads(result.stdout)["plan_sha256"]
        self.assertEqual(call("apply", "--expected", before).returncode, 0)
        self.assertEqual(json.loads(call("check", "--probe").stdout)["cli_probe"], "PASS")


if __name__ == "__main__":
    unittest.main()
