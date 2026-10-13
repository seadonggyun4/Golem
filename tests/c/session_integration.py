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
        args = ([str(fixture.CLI), "--output-mode", "full", "session", "call", str(self.work), str(path)] if self.actual else
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

    def work_bytes(self):
        return {str(p.relative_to(self.work)): p.read_bytes()
                for p in self.work.rglob("*") if p.is_file()}

    def test_idle_reboot_preflight_is_read_only_and_requires_resume(self):
        self.setup_session()
        self.boot += 1
        before = self.work_bytes()
        status = self.request("status")
        hint = status["resume_preflight"]
        self.assertEqual(hint["reason"], "BOOT_CHANGED")
        self.assertEqual(hint["next_operation"], "SESSION_RESUME")
        self.assertTrue(hint["resume_required"])
        self.assertFalse(hint["reconciliation_required"])
        self.assertEqual(hint["expected_sequence"], self.seq)
        self.assertFalse(hint["execution_authorized"])
        self.assertEqual(self.request("next")["reason"], "RESUME_REQUIRED")
        self.assertEqual(before, self.work_bytes())
        self.claim(ok=False)  # Query does not bypass the original storage fence.
        self.assertEqual(self.request("status")["sequence"], self.seq)
        self.request("resume", session_id="after-reboot", ttl_ms=10000)
        self.assertFalse(self.request("status")["resume_preflight"]["resume_required"])
        self.assertEqual(self.request("next")["reason"], "CLAIM_REQUIRED")
        self.claim("after-reboot")
        self.begin()

    def test_idle_clock_rollback_requires_explicit_resume(self):
        self.setup_session()
        self.now -= 1
        before = self.work_bytes()
        hint = self.request("next")["resume_preflight"]
        self.assertEqual(hint["reason"], "CLOCK_REGRESSED")
        self.assertFalse(hint["boot_changed"])
        self.assertTrue(hint["clock_regressed"])
        self.assertEqual(before, self.work_bytes())
        self.claim(ok=False)
        self.request("resume", session_id="after-clock", ttl_ms=10000)
        self.claim("after-clock")

    def test_preflight_running_expiry_and_recovery_are_distinct(self):
        self.setup_session()
        self.claim()
        self.begin()
        live = self.request("status")["resume_preflight"]
        self.assertEqual(live["next_operation"], "OWNER_CONTINUE_OR_RESUME")
        self.assertEqual(live["owner_session_id"], "agent-a")
        self.request("resume", session_id="intruder", ttl_ms=10000, ok=False)
        self.now += 10000  # equality is expired
        expired = self.request("next")["resume_preflight"]
        self.assertEqual(expired["reason"], "LEASE_EXPIRED")
        self.assertTrue(expired["reconciliation_required"])
        self.assertEqual(expired["next_operation"], "SESSION_RESUME")
        self.request("resume", session_id="recovery", ttl_ms=10000)
        before = self.work_bytes()
        recovering = self.request("next")["resume_preflight"]
        self.assertEqual(recovering["next_operation"], "CONTEXT_THEN_RECONCILE")
        self.assertFalse(recovering["resume_required"])
        self.assertEqual(before, self.work_bytes())
        self.claim("recovery", ok=False)
        self.now += 10000
        self.assertEqual(self.request("next")["resume_preflight"]["next_operation"], "SESSION_RESUME")

    def test_preflight_fresh_and_unstarted_sessions(self):
        self.setup_work()
        self.now, self.boot, self.seq, self.key, self.actual = 1000, 1, 0, 0, False
        before = self.work_bytes()
        hint = self.request("status")["resume_preflight"]
        self.assertEqual(hint["next_operation"], "SESSION_START")
        self.assertFalse(hint["resume_required"])
        self.assertEqual(before, self.work_bytes())
        self.register_selection()
        self.request("start", selection_id="selection")
        self.assertEqual(self.request("status")["resume_preflight"]["next_operation"], "READ_NEXT")

    def test_resume_live_foreign_owner_is_rejected_before_any_write(self):
        self.setup_session()
        self.claim()
        before = self.work_bytes()
        rejected = self.request("resume", session_id="intruder", ttl_ms=10000, ok=False)
        self.assertIn(b"session.resume_preflight.LIVE_OWNER.WAIT", rejected.stderr)
        self.assertEqual(before, self.work_bytes())

    def test_preflight_observation_does_not_authorize_stale_resume(self):
        self.setup_session()
        observed = self.request("status")["resume_preflight"]["expected_sequence"]
        self.claim()
        before = self.work_bytes()
        rejected = self.request("resume", expected_sequence=observed,
                                session_id="agent-a", ttl_ms=10000, ok=False)
        self.assertIn(b"session.expected_sequence", rejected.stderr)
        self.assertEqual(before, self.work_bytes())

    def test_completed_session_reboot_does_not_request_mutation(self):
        self.setup_work(mode="documents")
        self.register_selection()
        self.now, self.boot, self.seq, self.key, self.actual = 1000, 1, 0, 0, False
        self.request("start", selection_id="selection")
        for kind in ("planning", "development-plan", "qa-plan", "qa-result", "completion"):
            self.claim()
            self.begin()
            self.output()
            self.submit()
        contract = self.cli("role", "template", "doc-only")
        digest = self.cli("role", "validate", self.write("role-contract.json", contract))["contract_digest"]
        enroll = dict(schema_version=1, operation="enroll", selection_id="selection", key="enroll",
                      expected_generation=self.generation, contract=contract)
        self.cli("role", "call", self.work, self.write("enroll.json", enroll), "--approve-contract", digest)
        self.cli("role", "call", self.work, self.write("assess.json", dict(
            schema_version=1, operation="assess", selection_id="selection", key="assess",
            expected_generation=self.generation, review=None)))
        self.cli("completion", "call", self.work, self.write("finalize.json", dict(
            schema_version=2, operation="finalize", selection_id="selection", key="done",
            expected_generation=self.generation, issues=[])))
        report = subprocess.run([str(fixture.CLI), "--output-mode", "full", "completion",
                                 "report", str(self.work), "1"], capture_output=True,
                                env=fixture.ENV, timeout=90)
        self.assertEqual(report.returncode, 0, report.stderr.decode())
        self.boot += 1
        before = self.work_bytes()
        self.assertEqual(self.request("next")["action"], "DONE")
        hint = self.request("status")["resume_preflight"]
        self.assertEqual(hint["next_operation"], "NONE")
        self.assertEqual(hint["reason"], "DONE")
        self.assertTrue(hint["boot_changed"])
        self.assertFalse(hint["resume_required"])
        self.assertEqual(before, self.work_bytes())
        rejected = self.request("resume", session_id="unnecessary", ttl_ms=10000, ok=False)
        self.assertIn(b"session.resume_preflight.DONE.READ_NEXT", rejected.stderr)
        self.assertEqual(before, self.work_bytes())

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

    def test_expired_resume_race_has_one_owner(self):
        self.setup_session()
        self.claim()
        self.begin()
        self.now += 10000
        processes = []
        for i in range(2):
            request = dict(schema_version=1, operation="resume", work_id="example-work",
                           key=f"resume-race-{i}", expected_sequence=self.seq,
                           session_id=f"recovery-{i}", ttl_ms=10000)
            path = self.write(f"resume-race-{i}.json", request)
            processes.append(subprocess.Popen(
                [str(CLIENT), str(self.work), str(path), str(self.now), str(self.boot)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=fixture.ENV))
        outputs = [p.communicate(timeout=90) for p in processes]
        self.assertEqual(sum(p.returncode == 0 for p in processes), 1, outputs)
        status = self.request("status")
        self.assertEqual(status["sequence"], self.seq + 1)
        self.assertEqual(status["state"]["active"]["state"], "RECOVERY_REQUIRED")
        self.assertEqual(status["resume_preflight"]["next_operation"], "CONTEXT_THEN_RECONCILE")

    def test_duplicate_resume_is_historical_not_new_permission(self):
        self.setup_session()
        self.claim()
        receipt = self.request("resume", session_id="agent-a", ttl_ms=10000)
        original = copy.deepcopy(self.last_request)
        self.claim()
        self.now += 10000
        before = self.work_bytes()
        self.assertEqual(self.raw(original), receipt)
        self.assertEqual(before, self.work_bytes())
        self.assertFalse(self.request("status")["lease_live"])

    def test_actual_cli_resume_reports_live_owner_before_write(self):
        self.setup_session(actual=True)
        self.claim()
        before = self.work_bytes()
        rejected = self.request("resume", session_id="intruder", ttl_ms=10000, ok=False)
        errors = [json.loads(line) for line in rejected.stderr.decode().splitlines()
                  if line.startswith("{")]
        self.assertTrue(any(e.get("diagnostic") == "session.resume_preflight.LIVE_OWNER.WAIT"
                            for e in errors))
        self.assertEqual(before, self.work_bytes())

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
        denied = self.request("status")
        self.assertIsNone(denied["state"])
        self.assertEqual(denied["resume_preflight"]["next_operation"], "REVIEW_POLICY")

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
