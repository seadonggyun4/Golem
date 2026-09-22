"""Completion acceptance and crash-boundary recovery, with real C QA."""
import copy
import hashlib
import json
import time
import unittest
from reentry_integration import Reentry


class Completion(Reentry):
    def completion(self, operation="resume", ok=True, **kw):
        req = dict(schema_version=1, operation=operation, selection_id="selection", **kw)
        return self.cli("completion", "call", self.work, self.write("completion.json", req), ok=ok)

    def finalize(self, key="done-1", ok=True, issues=None):
        return self.completion("finalize", key=key, expected_generation=self.generation,
                               issues=issues or [], ok=ok)

    def ready(self, sessions=False):
        self.setup_execution(sessions=sessions)
        self.prepare()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.finish()
        if sessions:
            self.begin_claim()
        self.qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="final-qa")
        self.result("qa-result", self.qa)
        self.managed("completion")

    def project(self, seq=1, ok=True):
        return self.raw("completion", "report", self.work, seq, ok=ok)

    def events(self):
        return sorted((self.work / "events").glob("*.evt"))

    def test_complete_recover_and_idempotency(self):
        self.ready(sessions=True)
        self.assertEqual(self.completion()["action"], "VERIFY_COMPLETION")
        r = self.finalize()
        self.assertEqual(r, self.finalize())
        self.assertEqual(self.completion()["action"], "RECOVER_REPORT")
        report = self.project()
        self.assertIn("Independent review: **not established**", report)
        self.assertEqual(self.completion()["action"], "DONE")
        self.assertTrue(self.next()["acceptance_verified"])
        session_next = self.cli("session", "call", self.work, self.write("session-next.json", {
            "schema_version": 1, "operation": "next", "work_id": "example-work"}))
        self.assertEqual(session_next["action"], "DONE")
        self.assertTrue(session_next["acceptance_verified"])
        n = len(self.events())
        for _ in range(2):
            self.assertEqual(self.project(), report)
            self.assertEqual(self.completion()["action"], "DONE")
        self.assertEqual(len(self.events()), n)
        self.finalize(key="duplicate-with-another-key", ok=False)
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        (self.work / "completions/r0001/completion.md").unlink()
        (self.work / "documents/planning/r0001.md").unlink()
        self.assertEqual(self.completion()["action"], "RECOVER_REPORT")
        self.assertEqual(self.project(), report)
        self.assertEqual(self.completion()["action"], "DONE")
        self.assertEqual((self.repo / "user.txt").read_text(), "preexisting uncommitted user work\n")

    def test_changed_code_and_documents_preserve_history(self):
        self.ready()
        r = self.finalize()
        report = self.project()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a-b; }\n")
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        self.finalize(key="not-current", ok=False)
        self.assertEqual(self.finalize(), r)  # history, never a fresh success claim
        self.assertEqual(self.project(), report)
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.managed("planning")
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        self.finalize(key="stale-plan", ok=False)
        self.assertEqual(self.project(), report)

    def test_failure_repair_reaches_completion(self):
        Reentry.test_repair_revision_and_historical_evidence(self)
        self.managed("completion")
        receipt = self.finalize()
        self.assertEqual(receipt["record"]["record"]["assessment"]["reentry_count"], 1)
        self.project()
        self.assertEqual(self.completion()["action"], "DONE")
        self.assertEqual(self.next()["action"], "DONE")

    def test_missing_noop_failed_and_active_rejected(self):
        self.setup_execution(sessions=True)
        self.finalize(ok=False)
        self.prepare()
        self.assertEqual(self.completion()["action"], "WAIT")
        self.finalize(ok=False)
        self.finish()
        self.begin_claim()
        q = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="bad")
        self.result("qa-result", q)
        self.finalize(ok=False)
        self.assertEqual(self.completion()["action"], "CLASSIFY_FAILURE")

    def test_noop_documents_are_not_real_completion(self):
        self.setup_work()
        self.register_selection()
        for k in ("planning", "development-plan", "development-result", "qa-plan", "qa-result", "completion"):
            self.managed(k)
        self.finalize(ok=False)

    def test_issues_unknown_fields_and_key_conflict(self):
        self.ready()
        issue = dict(id="LIMIT-1", blocking=True, description="Known limitation",
                     evidence_digest=self.docs["planning"]["body_digest"])
        self.finalize(issues=[issue], ok=False)
        issue["blocking"] = False
        r = self.finalize(issues=[issue])
        self.assertEqual(len(r["record"]["record"]["assessment"]["unresolved_nonblocking_items"]), 1)
        self.finalize(ok=False)
        self.completion("resume", extra=True, ok=False)
        bad = copy.deepcopy(issue)
        bad["evidence_digest"] = "f" * 64
        self.finalize(key="missing-evidence", issues=[bad], ok=False)

    def test_uncertain_or_unsubmitted_attempt_blocks(self):
        self.ready()
        done = self.work / "execution-attempts/final-qa.done"
        original = done.read_bytes()
        done.unlink()
        self.assertEqual(self.completion()["action"], "RECONCILE_EXECUTION")
        self.finalize(ok=False)
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        done.write_bytes(original)
        other = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="unsubmitted")
        self.assertEqual(other["record"]["status"], "PASS")
        self.finalize(ok=False)
        self.assertEqual(self.completion()["action"], "RECONCILE_EXECUTION")

    def test_commit_boundary_orphans_and_corruption(self):
        self.ready()
        self.finalize()
        committed = self.events()[-1]
        frame = committed.read_bytes()
        committed.unlink()  # CAS persisted, event not committed: an orphan is not completion
        self.assertEqual(self.completion()["action"], "VERIFY_COMPLETION")
        committed.write_bytes(frame)
        self.assertEqual(self.completion()["action"], "RECOVER_REPORT")
        self.project()
        path = self.work / "completions/r0001/completion.md"
        path.chmod(0o600)
        path.write_text("forged DONE")
        self.completion(ok=False)
        self.project(ok=False)
        self.assertEqual(path.read_text(), "forged DONE")
        path.unlink()
        self.project()
        committed.write_bytes(frame[:-1])
        self.completion(ok=False)

    def test_missing_cas_and_unknown_event(self):
        self.ready()
        r = self.finalize()
        report = r["record"]["report_digest"]
        obj = self.work / "objects/sha256" / report[:2] / report[2:]
        data = obj.read_bytes()
        obj.unlink()
        self.completion(ok=False)
        obj.write_bytes(data)
        # No edits to the actual project are needed for recovery.
        self.project()
        events = self.events()
        frame = events[-1].read_bytes()
        payload = json.dumps({"schema_version": 999, "type": "completion"}).encode()
        key = hashlib.sha256(payload).hexdigest()
        path = self.work / "objects/sha256" / key[:2] / key[2:]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(payload)
        events[-1].chmod(0o600)
        events[-1].write_bytes(frame[:48] + bytes.fromhex(key))
        self.completion(ok=False)
        events[-1].write_bytes(frame)
        events[-2].unlink()
        self.completion(ok=False)

    def test_lost_side_journal_cannot_look_empty(self):
        self.ready(sessions=True)
        self.finalize()
        self.project()
        for directory in ("agent-events", "execution-attempts"):
            src = self.work / directory
            saved = self.root / (directory + "-saved")
            src.rename(saved)
            self.completion(ok=False)
            saved.rename(src)
        self.assertEqual(self.completion()["action"], "DONE")

    def test_expired_claim_is_not_restored_by_completion(self):
        self.setup_execution(sessions=True)
        self.session("claim", session_id="old-agent", expected_generation=self.generation,
                     source_snapshot=self.source, byte_budget=1048576, ttl_ms=5000)
        time.sleep(5.1)
        events = list((self.work / "agent-events").glob("*.evt"))
        state = self.completion()
        self.assertEqual(state["action"], "RECONCILE_SESSION")
        self.assertEqual(state["boundary"]["session"]["active"]["session_id"], "old-agent")
        self.assertEqual(len(list((self.work / "agent-events").glob("*.evt"))), len(events))
        self.finalize(ok=False)

    def test_session_cannot_skip_output_submission(self):
        self.ready()
        self.seq = 0
        self.session("start", selection_id="selection")
        self.assertEqual(self.completion()["action"], "RECONCILE_SESSION")
        self.finalize(ok=False)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Completion(n) for n in Completion.__dict__ if n.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
