"""Synthetic trusted host, real local command effects and persistent receipts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import execution_integration as base

HELPER = Path(sys.argv.pop(1)).resolve()


class Approval(unittest.TestCase):
    setUp = base.Execution.setUp
    tearDown = base.Execution.tearDown
    write = base.Execution.write
    cli = base.Execution.cli
    raw = base.Execution.raw
    validate = base.Execution.validate
    answered = base.Execution.answered
    confirmed = base.Execution.confirmed
    body = base.Execution.body
    metadata = base.Execution.metadata
    publish = base.Execution.publish
    setup_work = base.Execution.setup_work
    register_selection = base.Execution.register_selection
    inputs = base.Execution.inputs
    managed = base.Execution.managed
    git = base.Execution.git
    setup_execution = base.Execution.setup_execution
    prepare = base.Execution.prepare
    finish = base.Execution.finish
    result = base.Execution.result
    call = base.Execution.call
    session = base.Execution.session
    begin_claim = base.Execution.begin_claim
    session_submit = base.Execution.session_submit

    def setup_qa(self):
        self.setup_execution(mode="pass")
        self.prepare()
        self.finish()
        self.req = dict(schema_version=1, operation="run", checkpoint=self.cp["receipt_digest"], attempt_id="approved-qa")
        self.key = 0

    def host_call(self, kind, request, mode="host", receipt="-", now=0, boot=0, ok=True):
        p = subprocess.run([str(HELPER), kind, str(self.work), str(self.write("approval-client.json", request)),
                            mode, receipt, str(now), str(boot)], capture_output=True, env=base.ENV, timeout=90)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr.decode())
            return json.loads(p.stdout)
        self.assertNotEqual(p.returncode, 0, p.stdout.decode())
        return p

    def enroll(self, ttl=60000, now=0, boot=0):
        self.scope = self.host_call("describe", self.req)["action"]
        self.key += 1
        self.creation = dict(schema_version=1, operation="request", key=f"request-{self.key}", action=self.scope, ttl_ms=ttl)
        self.receipt = self.host_call("call", self.creation, now=now, boot=boot)["receipt_digest"]
        return self.receipt

    def decide(self, op="approve", **kwargs):
        self.key += 1
        r = dict(schema_version=1, operation=op, key=f"decision-{self.key}", request_receipt=self.receipt, reason="fixture-review")
        return self.host_call("call", r, **kwargs)

    def status(self, op="status", **kwargs):
        return self.host_call("call", dict(schema_version=1, operation=op, request_receipt=self.receipt), **kwargs)

    def execute(self, **kwargs):
        return self.host_call("execute", self.req, receipt=self.receipt, now=self.approval, **kwargs)

    def test_one_use_and_readonly_result_recovery(self):
        self.setup_qa(); self.enroll(); self.decide()
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="legacy-bypass", ok=False)
        result = self.execute()
        self.assertEqual(result["record"]["status"], "PASS")
        self.execute(ok=False)
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        self.assertEqual(self.status("recover")["result"], result)
        self.assertEqual(self.status()["state"], "RECORDED")

    def test_expiry_rollback_boot_change_and_no_auto_approval(self):
        self.setup_qa(); self.enroll(ttl=100, now=1000, boot=1)
        self.assertEqual(self.status(now=1100, boot=1)["state"], "EXPIRED")
        self.decide(now=1100, boot=1, ok=False)
        self.assertEqual(self.status(now=999, boot=1)["state"], "EXPIRED")
        self.assertEqual(self.status(now=1001, boot=2)["state"], "EXPIRED")
        self.decide("expire", now=1100, boot=1)
        self.decide(now=1000, boot=1, ok=False)

    def test_forged_approval_and_revocation(self):
        self.setup_qa(); self.enroll()
        self.decide(mode="no-host", ok=False)
        self.decide()
        self.execute(mode="revoked", ok=False)
        self.assertEqual(self.status()["state"], "APPROVED")
        self.decide("revoke")
        self.execute(ok=False)
        self.assertFalse((self.repo / "invoked").exists())

    def test_changed_source_or_attempt_cannot_consume(self):
        self.setup_qa(); self.enroll(); self.decide()
        self.req["attempt_id"] = "different"
        self.execute(ok=False)
        self.req["attempt_id"] = "approved-qa"
        (self.repo / "logic.c").write_text("int add(int a,int b){return a+b;}\n")
        self.execute(ok=False)
        self.assertEqual(self.status()["state"], "APPROVED")
        self.assertFalse((self.repo / "invoked").exists())

    def test_consume_crash_never_redispatches(self):
        self.setup_qa(); self.enroll(); self.decide()
        p = self.execute(mode="crash", ok=False)
        self.assertEqual(p.returncode, 86)
        self.assertEqual(self.status("recover")["dispatch"], "UNCERTAIN")
        self.execute(ok=False)
        self.assertFalse((self.repo / "invoked").exists())

    def test_deny_duplicate_and_key_conflict(self):
        self.setup_qa(); self.enroll()
        self.assertEqual(self.host_call("call", self.creation)["receipt_digest"], self.receipt)
        conflict = copy.deepcopy(self.creation); conflict["ttl_ms"] += 1
        self.host_call("call", conflict, ok=False)
        self.decide("deny")
        self.decide(ok=False)
        self.execute(ok=False)
        self.assertEqual(self.status()["state"], "DENIED")

    def test_concurrent_consumption_exactly_one_dispatch(self):
        self.setup_qa(); self.enroll(); self.decide()
        path = self.write("concurrent-execution.json", self.req)
        args = [str(HELPER), "execute", str(self.work), str(path), "host", self.receipt, self.approval, "0"]
        processes = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=base.ENV) for _ in range(2)]
        outputs = [p.communicate(timeout=90) for p in processes]
        self.assertEqual(sum(p.returncode == 0 for p in processes), 1, outputs)
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_cli_cannot_issue_host_decision(self):
        self.setup_qa()
        r = self.cli("approval", "describe", self.work, self.write("describe.json", self.req))
        self.assertEqual(r["action"]["operation"], "run")
        self.enroll()
        forged = dict(schema_version=1, operation="approve", key="forged", request_receipt=self.receipt, reason="self-report")
        self.cli("approval", "call", self.work, self.write("forged.json", forged), ok=False)

    def test_post_consume_revocation_blocks_dispatch(self):
        self.setup_qa(); self.enroll(); self.decide()
        self.execute(mode="late-deny", ok=False)
        self.assertEqual(self.status()["dispatch"], "UNCERTAIN")
        self.assertFalse((self.repo / "invoked").exists())
        self.execute(ok=False)

    def test_session_fence_is_part_of_scope(self):
        self.setup_execution(mode="pass", sessions=True)
        self.prepare(); self.finish(); self.begin_claim()
        self.req = dict(schema_version=1, operation="run", checkpoint=self.cp["receipt_digest"],
                        attempt_id="approved-qa", token=copy.deepcopy(self.token))
        self.key = 0
        self.enroll(); self.decide()
        self.req["token"]["epoch"] += 1
        self.execute(ok=False)
        self.assertEqual(self.status()["state"], "APPROVED")
        self.req["token"] = self.token
        self.assertEqual(self.execute()["record"]["status"], "PASS")

    def test_strict_schema_and_pending_bound(self):
        self.setup_qa(); self.enroll()
        for changes in ({"ttl_ms": 0}, {"ttl_ms": 3600001}, {"extra": True},
                        {"schema_version": 2}):
            bad = {**self.creation, "key": "invalid", **changes}
            self.host_call("call", bad, ok=False)
        for i in range(1, 32):
            self.host_call("call", {**self.creation, "key": f"bounded-{i}"})
        self.host_call("call", {**self.creation, "key": "overflow"}, ok=False)
        self.decide("deny")
        self.host_call("call", {**self.creation, "key": "after-denial"})


if __name__ == "__main__":
    unittest.main()
