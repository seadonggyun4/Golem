"""Mechanical observations must not invent successful execution or provenance."""
import ast
from concurrent.futures import ThreadPoolExecutor
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import execution_record as record


class Records(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        record.git(self.source, "init", "-q")
        record.git(self.source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                   "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "fixture")

    def invoke(self, code="print('hello')", name="result", **kwargs):
        directory = record.private_directory(self.root / name)
        result = record.capture([sys.executable, "-c", code], directory,
                                kwargs.pop("timeout", 10), self.source, **kwargs)
        return directory, result

    def read(self, directory, name):
        return json.loads((directory / "execution" / name).read_bytes())

    def test_automatic_success_records_observation_not_acceptance(self):
        path, result = self.invoke()
        start = self.read(path, "started.json")
        finish = self.read(path, "result.json")
        self.assertEqual(start["argv"], [sys.executable, "-c", "print('hello')"])
        self.assertEqual(start["cwd"], str(self.source))
        self.assertEqual(start["executable"]["sha256"], record.digest(Path(sys.executable)))
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["recording"], "RECORDED")
        self.assertTrue(finish["source_unchanged"])
        self.assertFalse(finish["product_acceptance"])
        self.assertEqual(record.check(path)["integrity"], "PASS")
        self.assertEqual((path / "execution").stat().st_mode & 0o777, 0o700)
        for p in path.rglob("*"):
            if p.is_file():
                self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_nonzero_signal_timeout_and_limit_are_preserved(self):
        cases = [("raise SystemExit(7)", "EXIT", 7, {}),
                 ("import os,signal; os.kill(os.getpid(),signal.SIGTERM)", "EXIT", -15, {}),
                 ("import time; time.sleep(10)", "TIMEOUT", None, {"timeout": .1}),
                 ("print('x'*2048)", "OUTPUT_LIMIT", None, {"limit": 16})]
        for i, (code, reason, rc, options) in enumerate(cases):
            path, result = self.invoke(code, str(i), **options)
            self.assertEqual(result["reason"], reason)
            if rc is not None:
                self.assertEqual(result["returncode"], rc)
            self.assertEqual(record.check(path)["process"]["reason"], reason)

    def test_launch_failure_is_finalized_without_retry(self):
        path = record.private_directory(self.root / "missing")
        with self.assertRaises(FileNotFoundError):
            record.capture([str(self.root / "no-program")], path, 10, self.source)
        observed = record.check(path)["process"]
        self.assertEqual(observed["reason"], "LAUNCH_ERROR")
        self.assertIsNone(observed["returncode"])

    def test_start_record_failure_prevents_effects(self):
        marker = self.root / "effect"
        with patch.object(record, "save", side_effect=OSError(errno.ENOSPC, "full")):
            with self.assertRaises(OSError):
                self.invoke(f"from pathlib import Path; Path({str(marker)!r}).touch()")
        self.assertFalse(marker.exists())

    def test_record_fsync_does_not_change_legacy_report_writer(self):
        import verify_agent
        with patch.object(record.os, "fsync") as sync:
            verify_agent.save(self.root / "legacy-report", b"report")
            sync.assert_not_called()
            record.save(self.root / "durable-record", b"record")
            self.assertEqual(sync.call_count, 2)

    def test_finish_record_failure_preserves_process_result_no_retry(self):
        marker = self.root / "effect"
        original = record.save
        def fail(path, data):
            if path.name == "result.json":
                raise OSError(errno.ENOSPC, "full")
            return original(path, data)
        with patch.object(record, "save", side_effect=fail):
            path, result = self.invoke(f"from pathlib import Path; Path({str(marker)!r}).write_text('once')")
        self.assertEqual(marker.read_text(), "once")
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["reason"], "RECORDING_ERROR")
        self.assertEqual(result["process_reason"], "EXIT")
        self.assertEqual(result["recording"], "INCOMPLETE")
        with self.assertRaises(OSError):
            record.check(path)

    def test_changed_dirty_untracked_source_is_detected(self):
        path, _ = self.invoke("from pathlib import Path; Path('new.txt').write_text('changed')")
        self.assertFalse(self.read(path, "result.json")["source_unchanged"])
        self.assertIn("new.txt", self.read(path, "source-after.json")["files"])

    def test_no_git_is_unavailable_not_clean(self):
        path, _ = self.invoke(source=self.root)
        self.assertEqual(self.read(path, "source-before.json")["status"], "UNAVAILABLE")
        self.assertIsNone(self.read(path, "result.json")["source_unchanged"])

    def test_binary_change_has_separate_observed_status(self):
        binary = self.root / "fixture"
        binary.write_text("#!/bin/sh\nprintf '\\n' >> \"$0\"\n")
        binary.chmod(0o700)
        directory = record.private_directory(self.root / "binary")
        result = record.capture([binary], directory, 10, self.source)
        self.assertEqual(result["returncode"], 0)
        self.assertFalse(self.read(directory, "result.json")["executable_unchanged"])

    def test_log_corruption_and_symlinks_rejected(self):
        path, _ = self.invoke()
        (path / "stdout.log").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            record.check(path)
        (path / "stdout.log").unlink()
        (path / "stdout.log").symlink_to(self.source / "absent")
        with self.assertRaises(ValueError):
            record.check(path)

    def test_record_reuse_and_existing_logs_refused(self):
        path, _ = self.invoke()
        with self.assertRaises(FileExistsError):
            record.capture([sys.executable, "-c", "pass"], path, 10, self.source)
        self.assertEqual(record.check(path)["integrity"], "PASS")

    def test_no_environment_values_are_dumped(self):
        with patch.dict(os.environ, {"SYNTHETIC_SECRET": "never-include-this-value"}):
            path, _ = self.invoke()
        self.assertNotIn(b"never-include-this-value", b"".join(
            p.read_bytes() for p in (path / "execution").iterdir()))

    def test_concurrent_independent_records_have_unique_ids(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda i: self.invoke(name=str(i)), range(3)))
        self.assertEqual(len({self.read(p, "started.json")["invocation_id"] for p, _ in results}), 3)
        for p, _ in results:
            self.assertEqual(record.check(p)["integrity"], "PASS")

    def test_killed_recorder_never_has_verified_completion(self):
        path = record.private_directory(self.root / "killed")
        marker = self.root / "spawned"
        child_code = f"from pathlib import Path; import time; Path({str(marker)!r}).touch(); time.sleep(.3)"
        command = ("import execution_record as r; from pathlib import Path; import sys; "
                   f"r.capture([sys.executable,'-c',{child_code!r}],Path({str(path)!r}),10,Path({str(self.source)!r}))")
        process = subprocess.Popen([sys.executable, "-c", command], cwd=Path(record.__file__).parent)
        try:
            deadline = time.monotonic() + 10
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(marker.exists())
            process.kill()
            process.wait(timeout=5)
            self.assertTrue((path / "execution/started.json").exists())
            with self.assertRaises(OSError):
                record.check(path)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            time.sleep(.35)  # The inert test child exits itself; no orphan effects.

    def test_checked_adapter_retains_failed_logs(self):
        path = self.root / "adapter"
        with self.assertRaises(subprocess.CalledProcessError) as error:
            record.run([sys.executable, "-c", "print('failure'); raise SystemExit(4)"],
                       destination=path, cwd=self.source)
        self.assertEqual(error.exception.returncode, 4)
        self.assertEqual(error.exception.stdout, b"failure\n")
        self.assertEqual(record.check(path)["process"]["returncode"], 4)


class Coverage(unittest.TestCase):
    def test_owned_python_launches_use_recording_boundary(self):
        root = Path(record.__file__).resolve().parents[1]
        allowed = {("tools/execution_record.py", "git"), ("tools/execution_record.py", "capture"),
                   ("tools/agent_entrypoint.py", "git"), ("tools/instruction_bundle.py", "boundary"),
                   ("bench/benchmark.py", "cpu_name")}
        found = set()
        paths = list((root / "tools").glob("*.py")) + [root / "bench/benchmark.py"]
        for path in paths:
            if path.name.startswith("test_") or not path.exists():
                continue
            tree = ast.parse(path.read_text())
            parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"
                        and node.func.attr in {"run", "Popen", "check_call", "check_output", "call"}):
                    parent = node
                    while parent in parents and not isinstance(parent, ast.FunctionDef):
                        parent = parents[parent]
                    found.add((path.relative_to(root).as_posix(), getattr(parent, "name", "<module>")))
        self.assertFalse(found - allowed, "Unreviewed execution bypass: " + str(found - allowed))


if __name__ == "__main__":
    unittest.main()
