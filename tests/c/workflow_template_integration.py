"""Template proposals, immutable registration and non-bypass integration."""
import copy
import unittest
from workflow_integration import Workflow
from role_integration import Roles
from reentry_integration import Reentry


class Templates(Workflow):
    role = Roles.role
    enroll = Roles.enroll
    finalize_roles = Roles.finalize_roles
    review = Roles.review

    def preset(self, name):
        return self.cli("workflow", "template", "show", name)

    def instantiate(self, template):
        return self.cli("workflow", "template", "instantiate", self.work, "scope", 1,
                        self.write("template.json", template))

    def inputs(self, kind, ok=True, budget=1048576):
        return super().inputs(kind, ok=ok, budget=budget)

    def test_builtin_strict_codec_and_floor(self):
        self.assertEqual(self.cli("workflow", "template", "list"), ["feature", "bugfix", "review", "research"])
        for name in ("feature", "bugfix", "review", "research"):
            t = self.preset(name)
            # validate emits a digest, not a JSON document.
            import subprocess
            from discovery_integration import CLI, ENV
            p = subprocess.run([str(CLI), "workflow", "template", "validate", str(self.write("t.json", t))],
                               capture_output=True, env=ENV)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(len(p.stdout.strip()), 64)
            for field, value in (("schema_version", 2), ("version", True), ("shell", "exit 0")):
                bad = {**t, field: value}
                self.cli("workflow", "template", "validate", self.write("bad.json", bad), ok=False)
            bad = copy.deepcopy(t)
            bad["stages"][0]["after"] = "audit"
            self.cli("workflow", "template", "validate", self.write("bad.json", bad), ok=False)
            bad = copy.deepcopy(t)
            bad["role_contract"]["rules"] = bad["role_contract"]["rules"][:1]
            self.cli("workflow", "template", "validate", self.write("bad.json", bad), ok=False)

    def test_scope_selection_and_immutable_pin(self):
        self.setup_work(ui=True)
        t = self.preset("feature")
        selection = self.instantiate(t)
        self.assertEqual(selection, self.instantiate(t))
        self.assertTrue(all(d["status"] == "REQUIRED" for d in selection["decisions"]))
        bad = copy.deepcopy(selection)
        bad["decisions"][1]["status"] = "NOT_APPLICABLE"
        self.register_selection(bad, ok=False)
        self.selection = selection
        self.register_selection()
        self.inputs("planning", ok=False)
        self.enroll(t["role_contract"], approve=False, ok=False)
        self.enroll(t["role_contract"])
        self.inputs("planning", budget=1048577, ok=False)
        self.inputs("planning")
        t["stages"][0]["reason"] = "Edited local file cannot mutate the registered revision."
        self.write("template.json", t)
        self.assertEqual(self.inputs("planning")["selection"]["digest"], self.docs["selection"]["manifest_digest"])

    def test_documents_templates_do_not_create_execution_pass(self):
        self.setup_work(mode="documents")
        t = self.preset("research")
        self.selection = self.instantiate(t)
        self.register_selection()
        self.finalize_roles(ok=False)
        self.enroll(t["role_contract"])
        for kind in ("planning", "development-plan", "qa-plan", "qa-result", "completion"):
            self.managed(kind)
        self.inputs("development-result", ok=False)
        assessment = self.role(review=self.review())["event"]["assessment"]
        self.assertEqual(assessment["state"], "SATISFIED")
        self.assertFalse(any(r["predicate"] == "QA_PASS" for r in t["role_contract"]["rules"]))
        self.finalize_roles()

    def test_revision_no_downgrade_or_renamed_selection(self):
        self.setup_work()
        t = self.preset("feature")
        self.selection = self.instantiate(t)
        self.register_selection()
        legacy = self.cli("workflow", "select", self.work, "scope", 1, "development")
        self.register_selection(legacy, ok=False)
        metadata = self.metadata("stage-selection", "other", [self.selection["scope"]], 3)
        metadata["selection"] = self.selection
        self.publish(metadata, ok=False)
        changed = copy.deepcopy(t)
        changed["budget"]["max_reentries"] += 1
        self.register_selection(self.instantiate(changed), ok=False)
        changed = copy.deepcopy(t)
        changed["version"] = 2
        changed["budget"]["context_bytes"] //= 2
        self.selection = self.instantiate(changed)
        self.register_selection()
        self.enroll(t["role_contract"])
        self.inputs("planning", budget=524288)
        self.inputs("planning", budget=524289, ok=False)

    def test_digest_tampering_and_mismatched_role_rejected(self):
        self.setup_work()
        t = self.preset("bugfix")
        self.selection = self.instantiate(t)
        bad = copy.deepcopy(self.selection)
        bad["template_instance"]["definition"]["budget"]["max_reentries"] = 20
        self.register_selection(bad, ok=False)
        self.register_selection()
        weak = copy.deepcopy(t["role_contract"])
        weak["rules"] = weak["rules"][:1]
        self.enroll(weak, ok=False)
        self.inputs("planning", ok=False)


class TemplateExecution(Roles):
    def inputs(self, kind, ok=True, budget=1048576):
        return Workflow.inputs(self, kind, ok=ok, budget=budget)

    def register_selection(self):
        t = self.cli("workflow", "template", "show", getattr(self, "preset_name", "feature"))
        t["budget"]["max_reentries"] = getattr(self, "reentry_cap", 4)
        self.selection = self.cli("workflow", "template", "instantiate", self.work, "scope", 1,
                                  self.write("template.json", t))
        Workflow.register_selection(self)
        self.enroll(t["role_contract"])

    def test_real_execution_requires_qa_and_review(self):
        self.configure(version=5, mode="real")
        self.prepare()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.finish()
        self.qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="template-qa")
        self.assertEqual(self.qa["record"]["status"], "PASS")
        self.result("qa-result", self.qa)
        self.managed("completion")
        self.finalize_roles(ok=False)
        self.assertEqual(self.role()["event"]["assessment"]["state"], "UNSATISFIED")
        self.assertEqual(self.role(key="reviewed", review=self.review())["event"]["assessment"]["state"],
                         "SATISFIED")
        self.finalize_roles()

    def test_bugfix_requires_reproduction_case(self):
        self.preset_name = "bugfix"
        self.configure(version=5, mode="real")
        self.call("prepare", contract=self.contract, ok=False)
        self.assertFalse((self.repo / "invoked").exists())

    def test_execution_approval_not_granted_by_template(self):
        self.configure(version=5, mode="real")
        self.call("prepare", contract=self.contract, approval=False, ok=False)
        self.assertFalse((self.repo / "invoked").exists())

    request = Reentry.request
    decide = Reentry.decide
    reprepare = Reentry.reprepare

    def test_template_caps_reentry_even_with_larger_policy(self):
        self.reentry_cap = 1
        self.configure(version=5, mode="real")
        self.prepare()
        self.finish()
        self.failure = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="first")
        self.result("qa-result", self.failure)
        policy = dict(max_total=8, max_stage=8, max_no_progress=8, max_elapsed_ms=900000)
        self.decide(self.request(policy=policy))
        self.managed("development-plan")
        self.reprepare()
        self.finish()
        self.failure = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="second")
        self.result("qa-result", self.failure)
        decision = self.decide(self.request(key="decision-2", expected_sequence=1,
                                            policy=policy))["record"]["decision"]
        self.assertEqual((decision["action"], decision["reason"]),
                         ("BLOCKED", "ATTEMPT_BUDGET_EXHAUSTED"))


def load_tests(loader, _tests, _pattern):
    return unittest.TestSuite(cls(name) for cls in (Templates, TemplateExecution)
                              for name in sorted(cls.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
