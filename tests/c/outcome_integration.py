"""29B semantic gates against real C execution receipts and journal replay."""
import copy
import hashlib
import json
import unittest
from completion_integration import Completion


class Outcome(Completion):
    def research(self, op, record, key, ok=True):
        req = dict(schema_version=1, operation=op, record=record, key=key)
        return self.cli("research", "call", self.work, self.write("research.json", req), ok=ok)

    def enroll(self, passing=True):
        if passing:
            self.ready()
        else:
            self.setup_execution()
            self.prepare()
            self.finish()
            self.qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="failed-native")
        case = dict(schema_version=1, work_id="example-work", case_id="case-1", project_id="fixture",
                    case_type="REGRESSION_CANARY", privacy_level="PRIVATE", unit_of_analysis="Declared required cases",
                    research_questions=[dict(id="RQ-1", question="Can a skipped case appear complete?")],
                    context=dict(product="fixture", environment="local", tool="test", runner="C", constraints="Synthetic"),
                    pre_registered_plan_digest="")
        self.case = self.research("case-create", case, "case")
        self.policy = dict(schema_version=1, work_id="example-work", case_id="case-1",
                           case_digest=self.case["record_digest"], selection_id="selection", gate_id="regression",
                           adjudication_rule="golem.required-cases.v1",
                           required_cases=[dict(id="fix", requirement_id="REQ-1"),
                                           dict(id="regression", requirement_id="REQ-1")])
        self.enrollment = self.cli("research", "outcome", "enroll", self.work,
                                   self.write("policy.json", self.policy), "enroll")

    def decision(self, status="PASS", domain=None, supersedes=""):
        return dict(schema_version=1, work_id="example-work", case_id="case-1",
                    case_digest=self.case["record_digest"], policy_digest=self.enrollment["record_digest"],
                    qa_receipt=self.qa["receipt_digest"], supersedes=supersedes,
                    raw_status="Synthetic normalized report", rationale="Bounded regression observation",
                    open_blockers=[], observations=[dict(id=c["id"], status=status,
                        failure_domain=domain or ("NONE" if status == "PASS" else "UNKNOWN"),
                        evidence_digest=self.qa["receipt_digest"]) for c in self.policy["required_cases"]])

    def test_missing_adjudication_blocks_then_pass(self):
        self.enroll()
        self.finalize(ok=False)
        d = self.decision()
        receipt = self.cli("research", "outcome", "adjudicate", self.work, self.write("d.json", d), "a1")
        self.assertTrue(receipt["adjudicated"])
        self.assertFalse(receipt["execution_authorized"])
        self.assertTrue(receipt["event"]["assessment"]["completion_eligible"])
        self.assertEqual(receipt, self.research("adjudicate", d, "a1"))
        self.assertEqual(receipt, self.cli("research", "inspect", self.work, 3))
        md = self.raw("research", "report", self.work, 3)
        self.assertIn("Derived Assessment", md)
        final = self.finalize()
        self.assertEqual(final["record"]["record"]["assessment"]["outcome_adjudications"][0]["adjudication_digest"], receipt["record_digest"])
        self.assertIn("Outcome Adjudications", self.project())
        self.assertEqual(self.completion()["action"], "DONE")

    def test_status_matrix_and_revisions(self):
        self.enroll()
        previous = ""
        for status in ("SKIPPED", "NOT_EXECUTED", "UNKNOWN", "ERROR", "FAIL", "PASS"):
            d = self.decision(status, supersedes=previous)
            r = self.research("adjudicate", d, status)
            a = r["event"]["assessment"]
            self.assertEqual(a["normalized_status"], status)
            self.assertEqual(a["completion_eligible"], status == "PASS")
            self.assertEqual(a["required_case_complete"], status in ("FAIL", "PASS"))
            self.assertEqual(a["work_outcome"], "PASS" if status == "PASS" else "NOT_DONE")
            if status != "PASS":
                self.finalize(ok=False)
            previous = r["record_digest"]
        self.finalize()

    def test_missing_cases_and_domains(self):
        self.enroll()
        d = self.decision()
        d["observations"] = []
        r = self.research("adjudicate", d, "missing")
        self.assertEqual(r["event"]["assessment"]["not_executed_count"], 2)
        self.finalize(ok=False)
        for domain in ("PRODUCT", "HARNESS", "ENVIRONMENT"):
            d = self.decision("FAIL", domain, r["record_digest"])
            r = self.research("adjudicate", d, domain)
            self.assertEqual(r["event"]["assessment"][domain.lower() + "_failure_count"], 2)
            self.finalize(ok=False)

    def test_late_blocker_invalidates_done_and_new_revision_recovers(self):
        self.enroll()
        r = self.research("adjudicate", self.decision(), "pass")
        first = self.finalize()
        historical = self.project()
        d = self.decision(supersedes=r["record_digest"])
        d["open_blockers"] = ["unresolved-review"]
        blocked = self.research("adjudicate", d, "block")
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        self.assertFalse(self.next()["acceptance_verified"])
        self.finalize(key="blocked", ok=False)
        self.assertEqual(first, self.finalize())
        self.assertEqual(historical, self.project())
        self.research("adjudicate", self.decision(supersedes=blocked["record_digest"]), "resolved")
        self.finalize(key="done-2")
        self.project(2)
        self.assertEqual(self.completion()["action"], "DONE")
        self.finalize(key="duplicate", ok=False)

    def test_enrollment_immutable_and_bad_models(self):
        self.enroll()
        self.research("outcome-enroll", self.policy, "duplicate", ok=False)
        self.research("outcome-enroll", dict(self.policy, required_cases=self.policy["required_cases"][:1]), "weaken", ok=False)
        d = self.decision()
        for change in ({"policy_digest": "0" * 64}, {"qa_receipt": self.case["record_digest"]},
                       {"case_digest": "0" * 64}, {"work_id": "other"}, {"supersedes": "f" * 64},
                       {"completion_eligible": True}, {"observations": d["observations"] * 2},
                       {"open_blockers": ["x", "x"]}, {"rationale": " "}, {"schema_version": 2}):
            with self.subTest(change=change):
                self.research("adjudicate", dict(d, **change), "bad", ok=False)
        for status, domain in (("DONE", "NONE"), ("PASS", "PRODUCT"), ("FAIL", "NONE"), ("SKIPPED", "PRODUCT")):
            self.research("adjudicate", self.decision(status, domain), "bad", ok=False)
        d["observations"][0]["id"] = "undeclared"
        self.research("adjudicate", d, "bad", ok=False)
        d = self.decision()
        d["observations"][0]["evidence_digest"] = "0" * 64
        self.research("adjudicate", d, "bad", ok=False)

    def test_rehashed_forged_assessment_rejected_on_replay(self):
        self.enroll()
        r = self.research("adjudicate", self.decision("SKIPPED"), "skip")
        event = copy.deepcopy(r["event"])
        event["assessment"]["completion_eligible"] = True
        data = json.dumps(event).encode()
        digest = hashlib.sha256(data).hexdigest()
        path = self.work / "objects/sha256" / digest[:2] / digest[2:]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        last = self.events()[-1]
        frame = last.read_bytes()
        last.chmod(0o600)
        last.write_bytes(frame[:48] + bytes.fromhex(digest))
        self.cli("research", "status", self.work, ok=False)
        self.completion(ok=False)

    def test_supersedes_and_source_staleness(self):
        self.enroll()
        r = self.research("adjudicate", self.decision(), "first")
        self.research("adjudicate", self.decision(), "branch", ok=False)
        self.finalize()
        self.project()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a-b; }\n")
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        self.finalize(key="stale", ok=False)
        self.assertEqual(r, self.research("adjudicate", self.decision(), "first"))

    def test_native_failure_cannot_be_overridden(self):
        self.enroll(passing=False)
        self.assertNotEqual(self.qa["record"]["status"], "PASS")
        r = self.research("adjudicate", self.decision(), "declared-pass")
        self.assertEqual(r["event"]["assessment"]["normalized_status"], "PASS")
        self.assertFalse(r["event"]["assessment"]["native_qa_pass"])
        self.assertFalse(r["event"]["assessment"]["completion_eligible"])
        self.finalize(ok=False)

    def test_new_qa_requires_new_adjudication(self):
        self.enroll()
        old = self.research("adjudicate", self.decision(), "old")
        self.qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="new-qa")
        self.result("qa-result", self.qa)
        self.managed("completion")
        self.finalize(ok=False)
        self.research("adjudicate", self.decision(supersedes=old["record_digest"]), "current")
        self.finalize()

    def test_late_enrollment_and_unrelated_case(self):
        self.enroll()
        r = self.research("adjudicate", self.decision(), "first")
        self.finalize()
        self.project()
        case = copy.deepcopy(self.case["event"]["request"]["record"])
        case["case_id"] = "case-2"
        c = self.research("case-create", case, "case-2")
        self.assertEqual(self.completion()["action"], "DONE")
        p = dict(self.policy, case_id="case-2", case_digest=c["record_digest"])
        self.research("outcome-enroll", p, "enroll-2")
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        self.finalize(key="missing-new-case", ok=False)
        self.assertEqual(r, self.research("adjudicate", self.decision(), "first"))

    def test_observation_evidence_corruption_rejected(self):
        self.enroll()
        data = b"Synthetic independent report data, not real product evidence."
        digest = hashlib.sha256(data).hexdigest()
        path = self.work / "objects/sha256" / digest[:2] / digest[2:]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        d = self.decision()
        d["observations"][0]["evidence_digest"] = digest
        self.research("adjudicate", d, "a1")
        path.write_bytes(b"altered")
        self.completion(ok=False)
        self.cli("research", "status", self.work, ok=False)

    def test_enrollment_validation_limits(self):
        self.enroll()
        for update in ({"adjudication_rule": "golem.unknown.v2"}, {"required_cases": []},
                       {"required_cases": self.policy["required_cases"] * 2},
                       {"selection_id": "missing"}, {"required_cases": [dict(id="x", requirement_id="missing")]}):
            policy = dict(self.policy, **update)
            request = dict(schema_version=1, operation="outcome-enroll", key="invalid", record=policy)
            # The call also enforces enrollment uniqueness; validate separately
            # for malformed/version cases so the test exercises that boundary.
            if "selection_id" not in update and update != {"required_cases": [dict(id="x", requirement_id="missing")]}:
                self.cli("research", "validate", self.write("validate.json", request), ok=False)
            self.research("outcome-enroll", policy, "invalid", ok=False)
        for op, name in (("outcome-enroll", "outcome-enroll-request.json"), ("adjudicate", "adjudication-request.json")):
            from discovery_integration import SOURCE
            self.raw("research", "validate", SOURCE / "samples/research" / name)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Outcome(n) for n in Outcome.__dict__ if n.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
