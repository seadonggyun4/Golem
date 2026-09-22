"""Observed C regression -> classified impact -> revised plan -> repaired QA."""
import copy
import json
import unittest
from execution_integration import Execution


class Reentry(Execution):
    def setup_work(self):
        Execution.setup_work(self, ui=getattr(self, "ui", False))

    def managed(self, kind, doc_id=None):
        if kind == "development-plan" and getattr(self, "ui", False) and "ux" not in self.docs:
            Execution.managed(self, "ux")
            Execution.managed(self, "publishing")
        return Execution.managed(self, kind, doc_id)

    def setup_failure(self, mode="real", sessions=False):
        self.setup_execution(mode=mode, sessions=sessions)
        self.prepare()
        self.finish()
        if sessions:
            self.begin_claim()
        self.failure = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="first")
        self.result("qa-result", self.failure)

    def request(self, classification="IMPLEMENTATION", **changes):
        return {"schema_version": 1, "operation": "decide", "key": "decision-1", "expected_sequence": 0,
                "failure_receipt": self.failure["receipt_digest"], "classification": classification,
                "hypothesis": "The observed addition result suggests an implementation defect.",
                "confidence": "HIGH", "verification": "Keep both pinned C assertions and rerun after repair.",
                "affected_requirements": ["REQ-1"], "evidence_refs": [self.failure["receipt_digest"]],
                "policy": {"max_total": 8, "max_stage": 3, "max_no_progress": 1, "max_elapsed_ms": 900000},
                **changes}

    def decide(self, request=None, ok=True):
        return self.cli("reentry", "call", self.work, self.write("decision.json", request or self.request()), ok=ok)

    def reprepare(self):
        d = self.docs["development-plan"]
        self.contract["development_plan"] = {"document_id": "development-plan", "revision": d["revision"],
                                               "digest": d["manifest_digest"]}
        self.approval = self.raw("execution", "validate", self.write("contract.json", self.contract)).strip()
        return self.prepare()

    def test_repair_revision_and_historical_evidence(self):
        self.setup_failure()
        old_plan = self.docs["planning"].copy()
        old_qa = (self.work / "documents/qa-result/r0001.md").read_bytes()
        decision = self.decide()
        record = decision["record"]["decision"]
        self.assertEqual([v["document_id"] for v in record["invalidated"]],
                         ["development-plan", "development-result", "qa-plan", "qa-result"])
        self.assertEqual([v["document_id"] for v in record["reused"]], ["planning"])
        report = self.raw("reentry", "report", self.work, 1)
        self.assertIn("Hypothesis", report)
        self.assertIn("Overall QA: **FAIL**", report)
        self.assertIn(self.failure["receipt_digest"], report)
        self.assertEqual((self.work / "failures/r0001.md").read_text(), report)
        self.assertEqual(self.next()["target_kind"], "development-plan")
        inputs = self.inputs("development-plan")
        self.assertEqual(inputs["schema_version"], 2)
        self.assertEqual(inputs["reentry"]["decision_digest"], decision["decision_digest"])
        self.inputs("qa-result", ok=False)
        self.managed("development-plan")
        self.assertEqual(self.docs["planning"], old_plan)
        self.reprepare()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.finish()
        passed = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="second")
        self.assertEqual(passed["record"]["status"], "PASS")
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="unauthorized-extra", ok=False)
        self.result("qa-result", passed)
        self.assertEqual((self.work / "documents/qa-result/r0001.md").read_bytes(), old_qa)
        self.assertEqual(self.next()["target_kind"], "completion")
        self.assertEqual(self.inputs("completion")["reentry"]["failure_receipt"], self.failure["receipt_digest"])
        self.assertEqual(self.decide(), decision)  # same request, restart-safe adoption

    def test_classification_routes_and_non_applicable(self):
        routes = {"REQUIREMENTS": ("REVISE_DOCUMENT", "planning"),
                  "TEST_DEFECT": ("REVISE_DOCUMENT", "qa-plan"),
                  "ENVIRONMENT": ("BLOCKED", ""), "PERMISSION": ("BLOCKED", ""),
                  "BUDGET": ("BLOCKED", ""), "LEASE": ("BLOCKED", ""),
                  "UNKNOWN": ("INVESTIGATE", ""), "EXTERNAL_EFFECT_UNKNOWN": ("RECONCILE", "")}
        for category, expected in routes.items():
            with self.subTest(category=category):
                self.tearDown()
                self.setUp()
                self.setup_failure()
                for absent in ("UX", "PUBLISHING"):
                    self.decide(self.request(absent), ok=False)
                d = self.decide(self.request(category))["record"]["decision"]
                self.assertEqual((d["action"], d["target_kind"]), expected)
                self.assertEqual(self.next()["action"], expected[0])
                if expected[0] != "REVISE_DOCUMENT":
                    self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="blocked", ok=False)

    def test_no_progress_and_immutable_policy(self):
        self.setup_failure()
        self.decide()
        self.managed("development-plan")
        self.reprepare()
        self.finish()  # changed prose/revisions are not observed source progress
        self.failure = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="second")
        self.result("qa-result", self.failure)
        self.assertEqual(self.next()["action"], "CLASSIFY_FAILURE")
        request = self.request(key="decision-2", expected_sequence=1)
        changed = copy.deepcopy(request)
        changed["policy"]["max_no_progress"] = 8
        self.decide(changed, ok=False)
        d = self.decide(request)["record"]["decision"]
        self.assertEqual((d["action"], d["reason"]), ("BLOCKED", "NO_OBSERVED_PROGRESS"))
        self.inputs("development-plan", ok=False)
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="third", ok=False)

    def test_changed_source_still_obeys_attempt_budget(self):
        self.setup_failure()
        policy = {"max_total": 1, "max_stage": 1, "max_no_progress": 8, "max_elapsed_ms": 900000}
        self.decide(self.request(policy=policy))
        self.managed("development-plan")
        self.reprepare()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a-b; } /* still broken */\n")
        self.finish()
        self.failure = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="still-broken")
        self.result("qa-result", self.failure)
        d = self.decide(self.request(key="decision-2", expected_sequence=1, policy=policy))["record"]["decision"]
        self.assertEqual(d["reason"], "ATTEMPT_BUDGET_EXHAUSTED")
        self.assertEqual(self.next()["action"], "BLOCKED")

    def test_session_context_contains_failure_report(self):
        self.setup_failure(sessions=True)
        self.decide()
        self.begin_claim()
        request = {"schema_version": 1, "operation": "context", "work_id": "example-work",
                   "token": self.token, "max_bytes": 1048576}
        r = self.cli("session", "call", self.work, self.write("context.json", request))
        self.assertIn(self.failure["receipt_digest"], r["failure_markdown"])
        self.assertEqual(r["manifest"]["target_kind"], "development-plan")
        self.decide(self.request(key="during-claim"), ok=False)
        m = self.metadata("development-plan", parents=r["manifest"]["direct"], version=4)
        m.update(input_manifest=r["manifest"], producer_attempt=self.token["attempt_id"])
        self.publish(m)
        self.session_submit("development-plan")
        self.reprepare()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.finish()
        self.begin_claim()
        passed = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="session-retry")
        self.assertEqual(passed["record"]["status"], "PASS")
        self.result("qa-result", passed)

    def test_applicable_ui_routes(self):
        self.ui = True
        for category, target, reused in (("UX", "ux", ["planning"]),
                                          ("PUBLISHING", "publishing", ["planning", "ux"])):
            with self.subTest(category=category):
                self.tearDown()
                self.setUp()
                self.setup_failure()
                d = self.decide(self.request(category))["record"]["decision"]
                self.assertEqual(d["target_kind"], target)
                self.assertEqual([r["document_id"] for r in d["reused"]], reused)
                self.assertEqual(self.next()["target_kind"], target)

    def test_deadline_does_not_grant_another_dispatch(self):
        self.setup_failure()
        request = self.request()
        request["policy"]["max_elapsed_ms"] = 1
        self.decide(request)
        self.inputs("development-plan", ok=False)
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="late", ok=False)

    def test_investigation_reclassification_requires_new_evidence(self):
        self.setup_failure()
        first = self.decide(self.request("UNKNOWN"))
        request = self.request(key="decision-2", expected_sequence=1, previous_decision=first["decision_digest"])
        self.decide(request, ok=False)
        evidence = self.cli("evidence", "put", self.work, self.write("review.txt", "Independent diagnosis: inspect the subtraction operator.\n"))
        request["evidence_refs"].append(evidence["digest"])
        second = self.decide(request)
        self.assertEqual(second["record"]["decision"]["action"], "REVISE_DOCUMENT")
        self.assertEqual(self.next()["target_kind"], "development-plan")

    def test_errors_cannot_masquerade_as_product_failure(self):
        self.setup_failure(mode="empty")
        d = self.decide()["record"]["decision"]
        self.assertEqual(d["action"], "INVESTIGATE")
        self.assertEqual(d["invalidated"], [])
        self.assertIn("Overall QA: **ERROR**", self.raw("reentry", "report", self.work, 1))

    def test_gate_relaxation_and_bad_inputs(self):
        self.setup_failure()
        for change in ({"affected_requirements": ["OUT-OF-SCOPE"]}, {"affected_requirements": [123]}, {"classification": "audit"},
                       {"confidence": "CERTAIN"}, {"expected_sequence": 1}, {"evidence_refs": []},
                       {"extra": True}):
            self.decide(self.request(**change), ok=False)
        self.decide()
        self.managed("development-plan")
        self.contract["gates"][0]["cases"].pop()
        d = self.docs["development-plan"]
        self.contract["development_plan"].update(revision=d["revision"], digest=d["manifest_digest"])
        self.approval = self.raw("execution", "validate", self.write("relaxed.json", self.contract)).strip()
        self.call("prepare", contract=self.contract, ok=False)

    def test_corrupt_missing_event_and_projection(self):
        self.setup_failure()
        self.decide()
        self.raw("reentry", "report", self.work, 1)
        path = self.work / "failures/r0001.md"
        path.chmod(0o600)
        path.write_text("altered report")
        self.raw("reentry", "report", self.work, 1, ok=False)
        events = sorted((self.work / "events").glob("*.evt"))
        events[-2].unlink()
        self.cli("reentry", "call", self.work,
                 self.write("status.json", {"schema_version": 1, "operation": "status"}), ok=False)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Reentry(name) for name in Reentry.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
