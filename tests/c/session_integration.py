"""Cooperating external clients; no provider execution or semantic QA claims."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import workflow_integration as fixture

CLIENT = Path(sys.argv.pop(1)).resolve()


class Session(unittest.TestCase):
    setUp = fixture.Workflow.setUp
    tearDown = fixture.Workflow.tearDown
    write = fixture.Workflow.write
    cli = fixture.Workflow.cli
    validate = fixture.Workflow.validate
    answered = fixture.Workflow.answered
    confirmed = fixture.Workflow.confirmed
    body = fixture.Workflow.body
    metadata = fixture.Workflow.metadata
    publish = fixture.Workflow.publish
    setup_work = fixture.Workflow.setup_work
    register_selection = fixture.Workflow.register_selection

    def setup_session(self, actual=False):
        self.setup_work()
        self.register_selection()
        self.now, self.boot, self.seq, self.key = 1000, 1, 0, 0
        self.actual = actual
        self.request("start", selection_id="selection")

    def raw(self, r, ok=True):
        path = self.write("request.json", r)
        args = ([str(fixture.CLI), "session", "call", str(self.work), str(path)] if self.actual else
                [str(CLIENT), str(self.work), str(path), str(self.now), str(self.boot)])
        p = subprocess.run(args, capture_output=True, env=fixture.ENV, timeout=90)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr.decode())
            return json.loads(p.stdout)
        self.assertNotEqual(p.returncode, 0, p.stdout.decode())
        return p

    def request(self, op, ok=True, **fields):
        r = {"schema_version": 1, "operation": op, "work_id": "example-work"}
        if op not in ("status", "next", "context"):
            self.key += 1
            r.update(key=f"request-{self.key}", expected_sequence=self.seq)
        r.update(fields)
        result = self.raw(r, ok)
        if ok and result.get("committed"):
            self.seq = result["sequence"]
        self.last_request = r
        return result

    def claim(self, session="agent-a", ok=True):
        r = self.request("claim", ok=ok, session_id=session, expected_generation=self.generation,
                         source_snapshot=self.source, byte_budget=1048576, ttl_ms=10000)
        if ok:
            self.active = r["state"]["active"]
            self.token = {k: self.active[k] for k in ("epoch", "attempt_id", "session_id")}
        return r

    def begin(self):
        return self.request("begin", token=self.token, input_digest=self.active["manifest_digest"])

    def output(self):
        context = self.request("context", token=self.token, max_bytes=33554432)
        m = self.metadata(self.active["kind"], parents=context["manifest"]["direct"], version=4)
        m["producer_attempt"] = self.active["attempt_id"]
        m["input_manifest"] = context["manifest"]
        receipt = self.publish(m)
        self.ref = {"document_id": m["document_id"], "revision": m["revision"], "digest": receipt["manifest_digest"]}
        self.evidence = self.cli("evidence", "put", self.work, self.write("observation.txt", "Agent-reported fixture observation.\n"))["digest"]

    def submit(self, ok=True):
        return self.request("submit", ok=ok, token=self.token, input_digest=self.active["manifest_digest"],
                            source_snapshot=self.source, output=self.ref, evidence=[self.evidence])

    def test_actual_cli_document_handoff(self):
        self.setup_session(actual=True)
        for kind in ("planning", "development-plan", "development-result", "qa-plan", "qa-result", "completion"):
            next_action = self.request("next")
            self.assertEqual(next_action["action"], "NEXT_ACTION")
            self.assertGreaterEqual(len(next_action["required_documents"]), 2)
            self.assertEqual(next_action["requirements"][0]["id"], "REQ-1")
            self.claim()
            self.assertEqual(self.active["kind"], kind)
            self.begin()
            self.output()
            r = self.submit()
            self.assertFalse(r["acceptance_verified"])
        self.assertEqual(self.request("next")["reason"], "CALL_COMPLETION_FINALIZE")

    def test_claim_race_exactly_one_winner(self):
        self.setup_session()
        requests = []
        for i in range(2):
            r = dict(schema_version=1, operation="claim", work_id="example-work", key=f"race-{i}",
                     expected_sequence=self.seq, session_id=f"agent-{i}", expected_generation=self.generation,
                     source_snapshot=self.source, byte_budget=1048576, ttl_ms=10000)
            path = self.write(f"race-{i}.json", r)
            requests.append(subprocess.Popen([str(CLIENT), str(self.work), str(path), str(self.now), str(self.boot)],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=fixture.ENV))
        outputs = [p.communicate(timeout=90) for p in requests]
        self.assertEqual(sum(p.returncode == 0 for p in requests), 1, outputs)

    def test_claim_and_submit_idempotency_conflicts(self):
        self.setup_session()
        claimed = self.claim()
        original = copy.deepcopy(self.last_request)
        self.assertEqual(self.raw(original), claimed)
        conflict = copy.deepcopy(original)
        conflict["session_id"] = "different"
        self.raw(conflict, ok=False)
        self.begin()
        self.output()
        receipt = self.submit()
        original = copy.deepcopy(self.last_request)
        self.now += 100000
        self.assertEqual(self.raw(original), receipt)
        original["source_snapshot"] = "f" * 64
        self.raw(original, ok=False)

    def test_resume_claimed_revokes_old_token(self):
        self.setup_session()
        self.claim()
        old = copy.deepcopy(self.token)
        self.request("resume", session_id="other", ttl_ms=10000, ok=False)
        self.now += 10000
        self.request("begin", token=old, input_digest=self.active["manifest_digest"], ok=False)
        self.request("resume", session_id="other", ttl_ms=10000)
        self.claim("other")
        self.request("begin", token=old, input_digest=self.active["manifest_digest"], ok=False)
        self.begin()

    def test_running_resume_requires_reconciliation(self):
        self.setup_session()
        self.claim()
        self.begin()
        self.now += 10000
        self.assertEqual(self.request("next")["reason"], "RESUME_REQUIRED")
        r = self.request("resume", session_id="agent-b", ttl_ms=10000)
        self.assertEqual(r["state"]["active"]["state"], "RECOVERY_REQUIRED")
        self.claim("agent-b", ok=False)
        self.token = {k: r["state"]["active"][k] for k in ("epoch", "attempt_id", "session_id")}
        c = self.request("context", token=self.token, max_bytes=33554432)
        self.assertTrue(c["historical_recovery_context"])
        evidence = self.cli("evidence", "put", self.work, self.write("reconcile.txt", "Inspected workspace; no effects observed by fixture."))["digest"]
        self.request("reconcile", token=self.token, input_digest=self.active["manifest_digest"],
                     source_snapshot=self.source, output=None, evidence=[evidence], resolution="NO_EFFECTS")
        self.claim("agent-b")

    def test_interrupted_document_submission_adopts_without_rerun(self):
        self.setup_session()
        self.claim()
        self.begin()
        self.output()
        old = copy.deepcopy(self.token)
        self.now += 10000
        r = self.request("resume", session_id="agent-b", ttl_ms=10000)
        self.token = {k: r["state"]["active"][k] for k in ("epoch", "attempt_id", "session_id")}
        self.request("submit", token=old, input_digest=self.active["manifest_digest"], source_snapshot=self.source,
                     output=self.ref, evidence=[self.evidence], ok=False)
        self.request("reconcile", token=self.token, input_digest=self.active["manifest_digest"],
                     source_snapshot=self.source, output=None, evidence=[self.evidence], resolution="NO_EFFECTS", ok=False)
        self.request("reconcile", token=self.token, input_digest=self.active["manifest_digest"],
                     source_snapshot=self.source, output=self.ref, evidence=[self.evidence], resolution="ADOPT_OUTPUT")
        self.assertEqual(self.request("next")["document_action"]["target_kind"], "development-plan")
        self.assertEqual(len(list((self.work / "documents/planning").glob("*.md"))), 1)

    def test_clock_rollback_and_reboot_fail_closed(self):
        self.setup_session()
        self.claim()
        self.now -= 1
        self.request("begin", token=self.token, input_digest=self.active["manifest_digest"], ok=False)
        self.boot += 1
        self.request("begin", token=self.token, input_digest=self.active["manifest_digest"], ok=False)
        self.request("resume", session_id="after-reboot", ttl_ms=10000)
        self.claim("after-reboot")
        self.begin()

    def test_heartbeat_expiry_and_context_budget(self):
        self.setup_session()
        self.claim()
        self.now += 9999
        self.request("heartbeat", token=self.token, ttl_ms=10000)
        self.now += 2
        self.request("context", token=self.token, max_bytes=1, ok=False)
        c = self.request("context", token=self.token, max_bytes=33554432)
        self.assertEqual(len(c["documents"]), 2)
        self.assertIn("## Scope", c["documents"][0]["markdown"])
        self.now += 9998
        self.request("heartbeat", token=self.token, ttl_ms=10000, ok=False)

    def test_wrong_input_scope_attempt_and_missing_evidence(self):
        self.setup_session()
        self.claim()
        self.request("begin", token=self.token, input_digest="f" * 64, ok=False)
        self.begin()
        self.output()
        self.request("submit", token=self.token, input_digest=self.active["manifest_digest"], source_snapshot="f" * 64,
                     output=self.ref, evidence=[self.evidence], ok=False)
        good = dict(token=self.token, input_digest=self.active["manifest_digest"], source_snapshot=self.source, output=self.ref)
        self.request("submit", **good, evidence=["f" * 64], ok=False)
        self.request("submit", **good, evidence=[], ok=False)
        self.submit()

    def test_parent_change_blocks_begin(self):
        self.setup_session()
        self.claim()
        m = self.metadata("scope", version=2)
        m["assessment"] = self.a
        self.publish(m)
        self.request("begin", token=self.token, input_digest=self.active["manifest_digest"], ok=False)

    def test_corrupt_and_missing_session_journal(self):
        self.setup_session()
        self.claim()
        path = self.work / "agent-events/00000001.evt"
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(original[:30])
        self.request("status", ok=False)
        path.write_bytes(original)
        path.unlink()
        self.request("status", ok=False)

    def test_unknown_request_fields_are_rejected(self):
        self.setup_session()
        self.request("status", unexpected="value", ok=False)

    def test_no_receipt_without_claim_and_no_policy_escalation(self):
        self.setup_session()
        self.request("claim", session_id="a", expected_generation=self.generation, source_snapshot=self.source,
                     byte_budget=1048576, ttl_ms=0, ok=False)
        self.claim()
        self.output()
        self.submit(ok=False)
        self.request("begin", token=self.token, input_digest=self.active["manifest_digest"], ok=False)
        spec = json.loads((fixture.SOURCE / "samples/documents/work.json").read_text())
        spec["permission"] = "DENY"
        self.work = self.root / "denied"
        self.cli("work", "start", self.work, self.write("deny.json", spec))
        self.seq = 0
        self.request("start", selection_id="selection", ok=False)
        self.assertIsNone(self.request("status")["state"])

    def test_unreceipted_documents_do_not_advance(self):
        self.setup_session()
        manifest = self.cli("workflow", "inputs", self.work, "selection", "planning", self.source, 1048576)
        m = self.metadata("planning", parents=manifest["direct"], version=4)
        m["input_manifest"] = manifest
        self.publish(m)
        self.assertEqual(self.request("next")["reason"], "UNRECEIPTED_OUTPUT")
        self.claim(ok=False)


if __name__ == "__main__":
    unittest.main()
