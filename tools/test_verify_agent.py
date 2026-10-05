"""The conformance harness must not turn skipped or invented evidence into PASS."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import verify_agent as gate


class ConformanceToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.cli = Path(sys.executable).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def output(self, name="out"):
        return gate.private_directory(self.root / name)

    def test_private_no_overwrite_or_symlink(self):
        path = self.output()
        self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        gate.save(path / "data", b"original")
        self.assertEqual((path / "data").stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            gate.save(path / "data", b"replacement")
        with self.assertRaises(FileExistsError):
            gate.private_directory(path)
        (self.root / "link").symlink_to(path)
        with self.assertRaises(ValueError):
            gate.private_directory(self.root / "link/child")
        self.assertEqual((path / "data").read_bytes(), b"original")

    def test_json_limits_and_duplicate_keys(self):
        for value in (b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b" " * (gate.LIMIT + 1)):
            with self.assertRaises(ValueError):
                gate.strict_json(value)

    def test_capture_failure_and_timeout(self):
        r = gate.capture([self.cli, "-c", "raise SystemExit(3)"], self.output(), 10)
        self.assertEqual(r["returncode"], 3)
        r = gate.capture([self.cli, "-c", "import time; time.sleep(20)"], self.output("timed"), 1)
        self.assertEqual(r["reason"], "TIMEOUT")
        self.assertNotEqual(r["returncode"], 0)

    def test_completed_launcher_cannot_leave_child_running(self):
        marker = self.root / "late"
        child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()"
        launcher = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}])"
        r = gate.capture([self.cli, "-c", launcher], self.output(), 10)
        self.assertEqual(r["returncode"], 0)
        time.sleep(1.2)
        self.assertFalse(marker.exists())

    def test_capture_output_limit_is_failure_even_with_exit_zero(self):
        # Isolate output accounting from platform-specific process-group cleanup.
        # This child creates no descendants and capture still waits for its exit.
        with patch.object(gate, "LIMIT", 32), patch.object(
                gate.os, "killpg", side_effect=ProcessLookupError):
            r = gate.capture([self.cli, "-c", "print('x' * 256)"], self.output(), 10)
        self.assertEqual(r["returncode"], 0)
        self.assertEqual(r["reason"], "OUTPUT_LIMIT")

    def test_cleanup_denied_preserved_when_output_exceeds_limit(self):
        with patch.object(gate, "LIMIT", 32), patch.object(
                gate.os, "killpg", side_effect=PermissionError("denied")):
            r = gate.capture([self.cli, "-c", "print('x' * 256)"], self.output(), 10)
        self.assertEqual(r["reason"], "CLEANUP_DENIED")

    def test_cleanup_denied_never_becomes_success(self):
        with patch.object(gate.os, "killpg", side_effect=PermissionError("denied")):
            r = gate.capture([self.cli, "-c", "pass"], self.output(), 10)
        self.assertEqual(r["returncode"], 0)
        self.assertEqual(r["reason"], "CLEANUP_DENIED")

    def test_fixture_rejects_empty_skipped_and_partial(self):
        src = self.root / "src/tests/c"
        src.mkdir(parents=True)
        (src / "conformance_integration.py").write_text("# synthetic suite")
        valid = "\n".join(f"test_e{i:02d}_case (Fixture) ... ok" for i in range(1, 9))
        valid += "\n\nRan 8 tests in 1.0s\n\nOK\n"
        for i, log in enumerate(("", "Ran 0 tests in 0s\n\nOK\n", valid.replace("... ok", "... skipped", 1), valid)):
            out = self.output(str(i))
            (out / "stderr.log").write_text(log)
            with patch.object(gate, "capture", return_value={"returncode": 0, "reason": "EXIT"}):
                r = gate.fixture(self.cli, self.root / "src", self.cli, out, 10)
            self.assertEqual(r["status"], "PASS" if i == 3 else "FAIL")
            self.assertFalse(r["actual_agent_verified"])
            self.assertFalse(r["release_ready"])

    def observed(self, state, name="out"):
        out = self.output(name)
        work = self.root / "work"
        work.mkdir(exist_ok=True)
        (out / "stdout.log").write_text(json.dumps(state))
        with patch.object(gate, "capture", return_value={"returncode": 0, "reason": "EXIT"}) as run:
            result = gate.observe(self.cli, work, "selection", out, 10)
        self.assertEqual(run.call_args.args[0][1:5], ["--output-mode", "full", "completion", "call"])
        request = json.loads((out / "request.json").read_text())
        self.assertEqual(request["operation"], "resume")
        return result

    def test_observation_is_not_agent_authentication(self):
        state = {"schema_version": 1, "action": "DONE", "acceptance_verified": True,
                 "execution_authorized": False, "receipt_digest": "a" * 64,
                 "completion": {"record": {"evidence_root": "b" * 64}},
                 "private": "synthetic-private-do-not-export"}
        r = self.observed(state)
        self.assertEqual(r["status"], "PASS")
        self.assertFalse(r["actual_agent_verified"])
        self.assertFalse(r["release_ready"])
        self.assertIsNone(r["usage"])
        self.assertNotIn(state["private"], json.dumps(r))
        state["action"] = "RECOVER_REPORT"
        self.assertEqual(self.observed(state, "missing")["status"], "BLOCKED")
        state["action"], state["acceptance_verified"] = "DONE", "true"
        self.assertEqual(self.observed(state, "fake-bool")["status"], "BLOCKED")

    def test_observation_requires_receipt_and_outside_store(self):
        with self.assertRaises(ValueError):
            self.observed({"schema_version": 1, "action": "DONE", "acceptance_verified": True,
                           "execution_authorized": False})
        work = self.root / "store"
        work.mkdir()
        with self.assertRaises(ValueError):
            gate.observe(self.cli, work, "selection", self.output("store/output"), 10)

    def test_observation_rejects_unsupported_schema_and_shapes(self):
        for i, state in enumerate(([], {"schema_version": True}, {"schema_version": 2},
                                   {"schema_version": 1, "completion": []})):
            with self.assertRaises(ValueError):
                self.observed(state, str(i))

    def test_markdown_and_summary_do_not_contain_raw_logs(self):
        out = self.output()
        r = gate.base(self.cli, "FIXTURE_CONFORMANCE")
        r["status"] = "FAIL"
        gate.write_report(out, r, report_at="requested")
        self.assertIn("Actual agent verified: false", (out / "report.md").read_text())
        self.assertFalse(json.loads((out / "report.json").read_text())["release_ready"])

    def test_default_defers_narrative_and_explicit_report_never_captures(self):
        out = self.output()
        r = gate.base(self.cli, "FIXTURE_CONFORMANCE")
        r["status"] = "FAIL"
        gate.write_report(out, r)
        before = {p.name: p.read_bytes() for p in out.iterdir()}
        self.assertNotIn("report.md", before)
        with patch.object(gate, "capture", side_effect=AssertionError("must not execute")):
            with patch("builtins.print") as printed:
                self.assertEqual(gate.main(["report", "--output", str(out)]), 0)
                self.assertIn("Status: FAIL", printed.call_args.args[0])
        self.assertEqual(before, {p.name: p.read_bytes() for p in out.iterdir()})
        self.assertEqual(gate.render_report(before["report.json"]), gate.render_report(before["report.json"]))

    def test_boundary_and_render_failure_preserve_observation(self):
        r = gate.base(self.cli, "WORK_OBSERVATION")
        r["status"] = "BLOCKED"
        for boundary in ("handoff", "completion"):
            out = self.output(boundary)
            gate.write_report(out, r, report_at=boundary)
            self.assertIn("Status: BLOCKED", (out / "report.md").read_text())
        out = self.output("failed-render")
        with patch.object(gate, "render_report", side_effect=ValueError("render failed")):
            with self.assertRaises(ValueError):
                gate.write_report(out, r, report_at="requested")
        self.assertEqual(json.loads((out / "report.json").read_bytes())["status"], "BLOCKED")

    def test_projection_rejects_fabricated_authority_and_escapes_prose(self):
        r = gate.base(self.cli, "WORK_OBSERVATION")
        r.update(status="PASS", limitations=["\n# injected\n<script>"])
        rendered = gate.render_report(json.dumps(r).encode())
        self.assertNotIn("\n# injected", rendered)
        r["release_ready"] = True
        with self.assertRaises(ValueError):
            gate.render_report(json.dumps(r).encode())


if __name__ == "__main__":
    unittest.main()
