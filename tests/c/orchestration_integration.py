"""Cross-subsystem recovery: real C QA, template, reentry, roles and completion."""
import copy
import unittest
from workflow_template_integration import TemplateExecution


class Orchestration(TemplateExecution):
    def test_failure_revision_pass_review_completion_restart(self):
        self.configure(version=5, mode="real")
        self.prepare()
        self.finish()
        self.failure = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="first")
        self.assertEqual(self.failure["record"]["status"], "FAIL")
        self.result("qa-result", self.failure)
        self.finalize_roles(ok=False)
        decision = self.decide()
        self.assertEqual(decision, self.decide())  # new CLI process, same persisted request
        self.managed("development-plan")
        self.reprepare()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.finish()
        self.qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="repaired")
        self.assertEqual(self.qa["record"]["status"], "PASS")
        self.assertEqual(self.qa, self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="repaired"))
        self.assertEqual((self.repo / "invoked").read_text(), "xx")
        self.result("qa-result", self.qa)
        self.managed("completion")
        self.finalize_roles(ok=False)
        self.assertEqual(self.role(review=self.review())["event"]["assessment"]["state"], "SATISFIED")
        final = self.finalize_roles()
        self.assertEqual(final, self.finalize_roles())
        self.assertEqual(self.completion()["action"], "RECOVER_REPORT")
        self.project()
        self.assertEqual(self.completion()["action"], "DONE")
        self.assertEqual((self.repo / "invoked").read_text(), "xx")
        (self.repo / "late.c").write_text("/* not reviewed */\n")
        self.finalize_roles(key="late-completion", ok=False)
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")

    def test_unknown_selection_revision_does_not_mutate_store(self):
        self.setup_work()
        self.register_selection()
        before = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        newer = copy.deepcopy(self.selection)
        newer["schema_version"] = 999
        from workflow_integration import Workflow
        Workflow.register_selection(self, newer, ok=False)
        self.assertEqual(before, {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()})


def load_tests(loader, _tests, _pattern):
    return unittest.TestSuite(Orchestration(name) for name in sorted(Orchestration.__dict__)
                              if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
