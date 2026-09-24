"""31A: real execution, private log retention and read-only bundle verification."""
import copy
import hashlib
import json
import unittest
from execution_integration import Execution


class Bundle(Execution):
    def setup_bundle(self, mode="REDACTED_CAPTURE", cap=16384, required=False, script=None, timeout=None):
        self.setup_execution(mode="pass")
        if script is not None:
            runner = self.repo / "runner.py"
            runner.write_text(script)
        self.contract.update(schema_version=2, log_retention={
            "mode": mode, "max_bytes": cap if mode == "REDACTED_CAPTURE" else 0,
            "redactor": "mask-bytes-v1" if mode == "REDACTED_CAPTURE" else "none",
            "require_complete": required})
        if timeout is not None:
            self.contract["gates"][0]["timeout_ms"] = timeout
        self.approval = self.raw("execution", "validate", self.write("contract.json", self.contract)).strip()
        self.prepare()
        self.finish()

    def run_bundle(self, attempt="qa-bundle"):
        receipt = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id=attempt)
        def inventory():
            return {str(p.relative_to(self.work)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.work.rglob("*") if p.is_file()}
        before = inventory()
        bundle = self.cli("execution", "bundle", "inspect", self.work, receipt["receipt_digest"])
        self.cli("execution", "bundle", "verify", self.work, self.write("bundle.json", bundle))
        self.assertEqual(before, inventory())
        return receipt, bundle

    def object_path(self, digest):
        return self.work / "objects/sha256" / digest[:2] / digest[2:]

    def test_capture_bundle_and_markdown(self):
        secret = "fixture-secret-not-for-cas"
        script = ("import sys,json\n"
                  "from pathlib import Path\nPath('invoked').write_text('x')\n"
                  f"sys.stderr.buffer.write({secret.encode()!r}+bytes([0,255,195]))\n"
                  "print(json.dumps({'schema_version':1,'cases':"
                  "[{'id':'fix','status':'PASS'},{'id':'regression','status':'PASS'}]}))\n")
        self.setup_bundle(required=True, script=script)
        r, b = self.run_bundle()
        self.assertEqual(r["record"]["schema_version"], 2)
        self.assertEqual(b["status"], "PASS")
        self.assertFalse(b["acceptance_verified"])
        logs = b["gates"][0]["logs"]
        for log in logs:
            self.assertEqual(log["state"], "COMPLETE")
            self.assertTrue(log["eof"])
            wire = self.object_path(log["retained_receipt"]).read_bytes()
            retained = self.object_path(wire[-32:].hex()).read_bytes()
            self.assertEqual(retained, b"*" * log["retained_bytes"])
        for p in (self.work / "objects/sha256").glob("*/*"):
            self.assertNotIn(secret.encode(), p.read_bytes())
        body = self.result("qa-result", r)
        self.assertIn("Verification bundle:", body)
        self.assertIn("mask-bytes-v1", body)
        self.assertNotIn(secret, body)
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_discard_and_historical(self):
        self.setup_bundle(mode="DISCARD")
        r, b = self.run_bundle()
        self.assertEqual(b["status"], "PASS")
        for log in b["gates"][0]["logs"]:
            self.assertEqual(log["state"], "DISCARDED")
            self.assertNotIn("retained_receipt", log)
        self.tearDown()
        self.setUp()
        self.setup_execution(mode="pass")
        self.prepare()
        self.finish()
        _, b = self.run_bundle()
        self.assertEqual(b["log_availability"], "HISTORICAL_DISCARDED_COMPLETENESS_UNKNOWN")

    def test_required_truncation_blocks_completion(self):
        self.setup_bundle(cap=1, required=True)
        r, b = self.run_bundle()
        self.assertEqual(b["status"], "ERROR")
        self.assertEqual(b["gates"][0]["reason"], "EVIDENCE_INCOMPLETE")
        self.assertEqual(b["gates"][0]["logs"][0]["state"], "TRUNCATED")
        self.result("qa-result", r)
        self.inputs("completion", ok=False)

    def test_tamper_missing_log_and_idempotency(self):
        self.setup_bundle()
        r, b = self.run_bundle()
        for field in ("work_id", "attempt_id", "source_snapshot", "input_manifest", "qa_receipt", "status"):
            changed = copy.deepcopy(b)
            changed[field] = "0" * 64
            self.cli("execution", "bundle", "verify", self.work,
                     self.write("tampered.json", changed), ok=False)
        changed = copy.deepcopy(b)
        changed["extra"] = True
        self.cli("execution", "bundle", "verify", self.work, self.write("tampered.json", changed), ok=False)
        duplicate = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa-bundle")
        self.assertEqual(duplicate, r)
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        log = b["gates"][0]["logs"][0]
        self.object_path(log["retained_receipt"]).unlink()
        self.cli("execution", "bundle", "inspect", self.work, r["receipt_digest"], ok=False)
        self.call("verify", receipt=r["receipt_digest"], ok=False)
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa-bundle", ok=False)
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_policy_denial(self):
        self.setup_execution(mode="pass")
        self.contract["schema_version"] = 2
        for mode, cap, redactor, required in [
                ("RAW", 100, "none", False),
                ("DISCARD", 0, "none", True),
                ("REDACTED_CAPTURE", 16385, "mask-bytes-v1", False),
                ("REDACTED_CAPTURE", 20, "unknown", False)]:
            self.contract["log_retention"] = dict(mode=mode, max_bytes=cap,
                                                  redactor=redactor, require_complete=required)
            self.raw("execution", "validate", self.write("bad.json", self.contract), ok=False)
        self.assertFalse((self.repo / "invoked").exists())

    def test_missing_bundle_blocks_receipt_without_reexecution(self):
        self.setup_bundle()
        r, b = self.run_bundle()
        encoded = json.dumps(b, separators=(",", ":"), ensure_ascii=False).encode()
        self.object_path(hashlib.sha256(encoded).hexdigest()).unlink()
        self.cli("execution", "bundle", "inspect", self.work, r["receipt_digest"], ok=False)
        # Retrying the same completed attempt republishes only missing metadata.
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa-bundle")
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_case_inventory_and_timeout(self):
        cases = [{"id": "fix", "status": "PASS"}, {"id": "regression", "status": "PASS"}]
        fixtures = [([], "ERROR"), ([cases[0], cases[0]], "ERROR"),
                    (list(reversed(cases)), "ERROR"),
                    ([{**cases[0], "status": "SKIPPED"}, cases[1]], "ERROR"),
                    ([{**cases[0], "status": "ERROR"}, cases[1]], "ERROR"),
                    ([{**cases[0], "status": "FAIL"}, cases[1]], "FAIL")]
        for observed, expected in fixtures:
            with self.subTest(cases=observed):
                self.tearDown()
                self.setUp()
                script = "print(" + repr(json.dumps({"schema_version": 1, "cases": observed})) + ")\n"
                self.setup_bundle(script=script)
                r, b = self.run_bundle()
                self.assertEqual(b["status"], expected)
                self.result("qa-result", r)
                self.inputs("completion", ok=False)

    def test_overflow_prefix_never_complete(self):
        self.setup_bundle(script="import sys\nsys.stdout.buffer.write(b'x'*1000000)\n")
        r, b = self.run_bundle()
        self.assertEqual(b["status"], "ERROR")
        log = b["gates"][0]["logs"][0]
        self.assertEqual(log["state"], "TRUNCATED")
        self.assertLessEqual(log["retained_bytes"], 16384)
        self.assertGreater(log["dropped_observed_bytes"], 0)
        self.assertEqual(b["gates"][0]["reason"], "LOG_LIMIT")

    def test_capture_publication_failure_keeps_started_attempt(self):
        self.setup_bundle(cap=1)
        target = self.object_path(hashlib.sha256(b"*").hexdigest())
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(b"corrupt existing CAS object")
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="uncertain", ok=False)
        self.assertTrue((self.work / "execution-attempts/uncertain.started").exists())
        self.assertFalse((self.work / "execution-attempts/uncertain.done").exists())
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="uncertain", ok=False)
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_timeout_never_passes_even_with_complete_empty_log(self):
        self.setup_bundle(script="import time\ntime.sleep(3)\n", timeout=150)
        _, b = self.run_bundle()
        self.assertEqual(b["status"], "ERROR")
        self.assertTrue(b["gates"][0]["timed_out"])
        self.assertEqual(b["gates"][0]["reason"], "TIMEOUT")


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Bundle(name) for name in Bundle.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
