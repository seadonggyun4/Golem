"""Role enrollment, immutable assessments and completion using real C QA."""
import copy
import json
import unittest
from execution_change_integration import Changes
from completion_integration import Completion
from discovery_integration import SOURCE


class Roles(Changes):
    def template(self, name):
        return self.cli("role", "template", name)

    def role(self, op="assess", ok=True, approval=None, **fields):
        request = dict(schema_version=1, operation=op, selection_id="selection", **fields)
        if op != "status":
            request.setdefault("key", "assessment-1")
            request.setdefault("expected_generation", self.generation)
            if op != "enroll":
                request.setdefault("review", None)
        args = ["role", "call", self.work, self.write("role-request.json", request)]
        if approval:
            args += ["--approve-contract", approval]
        return self.cli(*args, ok=ok)

    def enroll(self, contract=None, ok=True, approve=True):
        contract = contract or self.template("implementer")
        digest = self.cli("role", "validate", self.write("role-contract.json", contract))["contract_digest"]
        return self.role("enroll", key="enroll", contract=contract,
                         approval=digest if approve else None, ok=ok)

    def ready_roles(self, names=("implementer", "qa"), changed=True):
        self.configure(version=5, mode="real")
        contract = self.template(names[0])
        contract["rules"] = [self.template(name)["rules"][0] for name in names]
        self.enroll(contract)
        if not changed:
            (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.prepare()
        if changed:
            (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.finish()
        self.qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="role-qa")
        self.result("qa-result", self.qa)
        self.managed("completion")

    def finalize_roles(self, key="roles-done", ok=True):
        return self.cli("completion", "call", self.work, self.write("role-completion.json", dict(
            schema_version=2, operation="finalize", selection_id="selection", key=key,
            expected_generation=self.generation, issues=[])), ok=ok)

    def review(self):
        manifest = self.inputs("completion")
        return dict(document=dict(document_id="completion", revision=self.docs["completion"]["revision"],
                                  digest=self.docs["completion"]["manifest_digest"]),
                    targets=[{k: d[k] for k in ("document_id", "revision", "digest")}
                             for d in manifest["documents"]], decision="ACCEPT", findings=[],
                    qa_receipt=getattr(self, "qa", {}).get("receipt_digest", ""))

    def test_strict_contracts_and_templates(self):
        for name in ("implementer", "qa", "reviewer", "researcher", "doc-only", "no-change"):
            c = self.template(name)
            self.cli("role", "validate", self.write("contract.json", c))
        c = self.template("qa")
        for field, value in (("stage", "ux"), ("predicate", "script:exit 0"), ("role", "admin"),
                             ("independent_review", True)):
            bad = copy.deepcopy(c)
            bad["rules"][0][field] = value
            self.cli("role", "validate", self.write("bad.json", bad), ok=False)
        for field, value in (("schema_version", 2), ("allowed_effects", "ALL"),
                             ("max_assessments", 0), ("mode", "documents"), ("rules", [])):
            self.cli("role", "validate", self.write("bad.json", {**c, field: value}), ok=False)
        c["rules"] *= 2
        self.cli("role", "validate", self.write("duplicate.json", c), ok=False)
        self.cli("role", "validate", self.write("duplicate-key.json", '{"id":"a","id":"b"}'), ok=False)

    def test_enrollment_approval_missing_and_sticky(self):
        self.setup_work()
        self.register_selection()
        self.enroll(approve=False, ok=False)
        first = self.enroll()
        self.assertEqual(first, self.enroll())
        c = self.template("qa")
        self.enroll(c, ok=False)
        a = self.role()["event"]["assessment"]
        self.assertEqual(a["rules"][0]["state"], "MISSING")
        self.assertEqual(a["target_kind"], "development-result")
        self.finalize_roles(ok=False)

    def test_real_evidence_completion_recovery_idempotency(self):
        self.ready_roles()
        self.assertEqual(self.next()["action"], "ASSESS_DELIVERABLES")
        self.finalize_roles(ok=False)
        r = self.role()
        self.assertEqual(r, self.role())
        a = r["event"]["assessment"]
        self.assertEqual(a["state"], "SATISFIED")
        self.assertTrue(all(len(row["input_digest"]) == 64 for row in a["rules"]))
        self.finalize(ok=False)  # old predicate cannot bypass an enrolled contract
        done = self.finalize_roles()
        assessment = done["record"]["record"]["assessment"]
        self.assertEqual(assessment["policy"]["predicate"], "golem.completion.roles.v1")
        self.assertEqual(assessment["deliverable_receipt"], r["receipt_digest"])
        self.assertEqual(done, self.finalize_roles())
        self.assertEqual(self.completion()["action"], "RECOVER_REPORT")
        self.assertIn("Role-contract completion", self.project())
        self.assertEqual(self.completion()["action"], "DONE")
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_live_change_blocks_completion_but_history_replays(self):
        self.ready_roles()
        old = self.role()
        self.finalize_roles()
        self.project()
        (self.repo / "late.c").write_text("/* new source */\n")
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        self.finalize_roles("late", ok=False)
        current = self.role("evaluate")
        self.assertEqual(current["state"], "UNSATISFIED")
        failure = self.role(key="late-assessment")
        self.assertEqual(failure["event"]["assessment"], current)
        (self.repo / "late.c").unlink()
        self.assertEqual(self.role("status"), failure["event"])
        self.assertEqual(self.role(), old)
        self.finalize_roles("without-new-assessment", ok=False)
        self.assertEqual(self.role(key="reassessed")["event"]["assessment"]["state"], "SATISFIED")

    def test_fake_markdown_is_not_execution(self):
        self.setup_work()
        self.register_selection()
        c = self.template("qa")
        self.enroll(c)
        for kind in ("planning", "development-plan", "development-result", "qa-plan", "qa-result", "completion"):
            self.managed(kind)
        a = self.role()["event"]["assessment"]
        self.assertEqual(a["state"], "UNSATISFIED")
        self.assertEqual({d["document_id"] for d in a["affected"]}, {"qa-result", "completion"})
        self.assertEqual(self.next()["action"], "REVISE_DOCUMENT")
        self.assertEqual(self.next()["deliverable_feedback"], a)
        self.finalize_roles(ok=False)

    def test_document_only_completion_does_not_claim_qa_execution(self):
        self.setup_work(mode="documents")
        self.register_selection()
        self.enroll(self.template("doc-only"))
        for kind in ("planning", "development-plan", "qa-plan", "qa-result", "completion"):
            self.managed(kind)
        receipt = self.role()
        self.assertEqual(receipt["event"]["assessment"]["state"], "SATISFIED")
        # A CAS object without its committed event is not an assessment.
        event = sorted((self.work / "events").glob("*.evt"))[-1]
        frame = event.read_bytes()
        event.unlink()
        self.finalize_roles(ok=False)
        event.write_bytes(frame)
        done = self.finalize_roles()
        self.assertEqual(done["record"]["record"]["assessment"]["assurance"],
                         "DOCUMENT_CONTRACT_ONLY_NO_EXECUTION_CLAIM")
        self.project()
        self.assertEqual(self.completion()["action"], "DONE")

    def test_review_requires_exact_closure_and_nonblocking_decision(self):
        self.ready_roles(names=("reviewer",))
        self.assertEqual(self.role()["event"]["assessment"]["state"], "UNSATISFIED")
        v = self.review()
        v["targets"][0]["digest"] = "f" * 64
        self.assertEqual(self.role("evaluate", review=v)["state"], "UNSATISFIED")
        v = self.review()
        v["qa_receipt"] = "e" * 64
        self.assertEqual(self.role("evaluate", review=v)["state"], "UNSATISFIED")
        v = self.review()
        v["findings"] = [dict(id="fix", blocking=True, description="Requires a correction")]
        self.assertEqual(self.role("evaluate", review=v)["state"], "UNSATISFIED")
        r = self.role(key="reviewed", review=self.review())
        self.assertEqual(r["event"]["assessment"]["state"], "SATISFIED")
        self.finalize_roles()

    def test_independent_identity_unknown_fails_closed(self):
        self.configure(version=5)
        c = self.template("reviewer")
        c["rules"][0]["independent_review"] = True
        self.enroll(c)
        self.prepare()
        self.finish()
        self.qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa")
        self.result("qa-result", self.qa)
        self.managed("completion")
        a = self.role(review=self.review())["event"]["assessment"]
        self.assertEqual(a["rules"][0]["state"], "BLOCKED")
        self.finalize_roles(ok=False)

    def test_no_change_means_observed_baseline_equal(self):
        self.ready_roles(names=("no-change",), changed=False)
        self.assertEqual(self.role()["event"]["assessment"]["state"], "SATISFIED")
        self.finalize_roles()

    def test_no_change_rejects_actual_change(self):
        self.ready_roles(names=("no-change",))
        self.assertEqual(self.role()["event"]["assessment"]["state"], "UNSATISFIED")
        self.finalize_roles(ok=False)

    def test_assessment_limit_and_read_only_evaluate(self):
        self.setup_work()
        self.register_selection()
        c = self.template("implementer")
        c["max_assessments"] = 1
        self.enroll(c)
        for kind in ("planning", "development-plan", "development-result", "qa-plan", "qa-result", "completion"):
            self.managed(kind)
        self.role()
        self.assertEqual(self.next()["action"], "BLOCKED")
        self.assertEqual(self.next()["reason"], "ROLE_ASSESSMENT_BUDGET_EXHAUSTED")
        self.role(key="extra", ok=False)
        before = sorted((self.work / "events").iterdir())
        self.role("evaluate")
        self.assertEqual(before, sorted((self.work / "events").iterdir()))

    def test_tampered_markdown_fails_closed(self):
        self.ready_roles()
        self.role()
        path = self.work / "documents/development-result/r0001.md"
        path.chmod(0o600)
        path.write_text("claimed PASS without original evidence")
        self.role("evaluate", ok=False)
        self.finalize_roles(ok=False)

    def test_legacy_completion_migrates_without_rewriting_history(self):
        Completion.ready(self)
        historical = self.finalize()
        markdown = self.project()
        self.enroll(self.template("qa"))
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        self.finalize(key="legacy-bypass", ok=False)
        self.role()
        self.finalize_roles()
        self.assertEqual(self.finalize(), historical)
        self.assertEqual(self.project(), markdown)
        self.project(2)
        self.assertEqual(self.completion()["action"], "DONE")

    def test_stale_parent_and_current_generation(self):
        self.setup_work(mode="documents")
        self.register_selection()
        c = self.template("doc-only")
        c["rules"][0].update(stage="development", kind="development-plan")
        self.enroll(c)
        self.managed("planning")
        self.managed("development-plan")
        self.assertEqual(self.role()["event"]["assessment"]["state"], "SATISFIED")
        self.managed("planning")
        self.role(key="wrong-generation", expected_generation=self.generation-1, ok=False)
        stale = self.role(key="stale")["event"]["assessment"]
        self.assertEqual(stale["rules"][0]["state"], "STALE")
        self.assertEqual(stale["next_action"], "REVISE_DOCUMENT")
        self.assertEqual({d["document_id"] for d in stale["affected"]}, {"development-plan"})
        self.finalize_roles(ok=False)

    def test_deny_and_ask_cannot_be_overridden_by_role(self):
        for permission in ("DENY", "ASK_ALWAYS"):
            spec = json.loads((SOURCE / "samples/documents/work.json").read_text())
            spec["permission"] = permission
            self.work = self.root / permission
            self.generation = 1
            self.cli("work", "start", self.work, self.write("denied-spec.json", spec))
            before = sorted((self.work / "events").glob("*.evt"))
            error = self.enroll(approve=True, ok=False)
            self.assertIn("policy denied" if permission == "DENY" else "approval required",
                          error.stderr.decode().lower())
            self.assertEqual(sorted((self.work / "events").glob("*.evt")), before)

    def test_dropped_assessment_cas_is_not_empty_success(self):
        self.setup_work(mode="documents")
        self.register_selection()
        self.enroll(self.template("researcher"))
        self.managed("planning")
        r = self.role()
        key = r["receipt_digest"]
        self.object_path(key).unlink()
        self.role("status", ok=False)
        self.finalize_roles(ok=False)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Roles(n) for n in Roles.__dict__ if n.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
