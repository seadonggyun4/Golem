"""Portable orchestration tests; real ptrace tests are a separate Linux command."""
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import execution_record as record
import syscall_record as trace


class Contract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_unsupported_never_launches_target(self):
        with patch.object(trace.platform, "system", return_value="Darwin"), patch.object(record, "capture") as run:
            result = trace.capture([sys.executable, "-c", "raise SystemExit(99)"], self.root / "out")
        run.assert_not_called()
        self.assertFalse(result["target_attempted"])
        self.assertEqual(result["diagnostic"], "trace.platform_unsupported")
        self.assertTrue((self.root / "out/trace.json").is_file())

    def test_invalid_deadline_does_not_create_output(self):
        for timeout in (float("nan"), float("inf"), 0, -1):
            with self.assertRaises(ValueError):
                trace.capture([sys.executable], self.root / "out", timeout=timeout)
        self.assertFalse((self.root / "out").exists())

    def test_probe_failure_never_retries_or_launches_target(self):
        def failed(argv, destination, *args, **kwargs):
            self.assertIn("--kill-on-exit", argv)
            self.assertEqual(argv[-1], "/bin/true")
            return {"reason": "EXIT", "returncode": 1, "recording": "RECORDED"}
        with patch.object(trace.platform, "system", return_value="Linux"), patch.object(record, "capture", side_effect=failed) as run:
            result = trace.capture([sys.executable], self.root / "out", tracer=sys.executable)
        self.assertEqual(run.call_count, 1)
        self.assertFalse(result["target_attempted"])
        self.assertEqual(result["diagnostic"], "trace.probe_failed")

    def test_raw_capture_keeps_failure_separate(self):
        calls = []
        def observed(argv, destination, *args, **kwargs):
            calls.append(argv)
            (destination / "syscalls.log").write_text("fixture syscall observation\n")
            self.assertEqual(kwargs["extra_logs"], ("syscalls.log",))
            return {"reason": "EXIT", "returncode": 0 if len(calls) == 1 else 7, "recording": "RECORDED"}
        with patch.object(trace.platform, "system", return_value="Linux"), patch.object(record, "capture", side_effect=observed), patch.object(record, "check"):
            result = trace.capture([sys.executable, "-c", "raise SystemExit(7)"], self.root / "out", tracer=sys.executable)
        self.assertEqual(len(calls), 2)
        self.assertIn("raw=all", calls[1])
        self.assertNotIn("-p", calls[1])
        self.assertEqual(result["state"], "OBSERVED")
        self.assertEqual(result["process"]["returncode"], 7)
        self.assertFalse(result["product_acceptance"])


class LinuxIntegration(unittest.TestCase):
    def setUp(self):
        self.assertEqual(platform.system(), "Linux", "This suite requires Linux, not a mocked backend")
        if os.environ.get("GOLEM_TRACE_TEST_OUTPUT"):
            self.root = Path(os.environ["GOLEM_TRACE_TEST_OUTPUT"]).resolve() / self._testMethodName
            self.root.mkdir(mode=0o700, parents=True)
            return
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_child_failures_and_manifest(self):
        program = """import os
pid = os.fork()
if pid == 0:
    try: os.open('/golem-trace-intentionally-missing', os.O_RDONLY)
    except FileNotFoundError: pass
    print(os.getpid(), flush=True)
    os._exit(0)
os.waitpid(pid, 0)
"""
        out = self.root / "out"
        result = trace.capture([sys.executable, "-c", program], out, source=self.root)
        self.assertEqual(result["state"], "OBSERVED", result)
        self.assertEqual(result["process"]["returncode"], 0)
        raw = (out / "run/syscalls.log").read_text()
        child = (out / "run/stdout.log").read_text().strip()
        self.assertTrue(child.isdigit())
        self.assertIn(child, raw)
        self.assertIn("ENOENT", raw)
        self.assertNotIn("golem-trace-intentionally-missing", raw)
        self.assertEqual(record.check(out / "run")["integrity"], "PASS")

    def test_timeout_kills_descendant_that_changes_session(self):
        pidfile = self.root / "pid"
        program = f"""import os, time
if os.fork() == 0:
    os.setsid()
    open({str(pidfile)!r}, 'w').write(str(os.getpid()))
    time.sleep(60)
else:
    time.sleep(60)
"""
        result = trace.capture([sys.executable, "-c", program], self.root / "out", timeout=2, source=self.root)
        self.assertEqual(result["state"], "INCOMPLETE", result)
        self.assertEqual(result["process"]["reason"], "TIMEOUT")
        pid = int(pidfile.read_text())
        for _ in range(100):
            state = Path(f"/proc/{pid}/stat")
            if not state.exists() or state.read_text().split(") ", 1)[1].startswith("Z"):
                break
            time.sleep(0.01)
        else:
            os.kill(pid, 9)
            self.fail("traced descendant survived tracer exit")


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromTestCase(Contract)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        LinuxIntegration if sys.argv[1:] == ["--linux-integration"] else Contract)
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
