"""29C latest-state and episode measures over actual QA-backed 29B records."""
import unittest
from outcome_integration import Outcome


class OutcomeMetrics(Outcome):
    def metrics(self, *args):
        return self.cli("research", "metrics", self.work, *args)

    def test_latest_cases_and_episode_denominators(self):
        self.enroll()
        empty = self.metrics()
        self.assertEqual(empty["required_case_coverage"]["unassessed_required_case_count"], 2)
        self.assertEqual(empty["counts"]["latest_unassessed_enrollment_count"], 1)
        previous = ""
        for i, status in enumerate(("SKIPPED", "SKIPPED", "PASS", "PASS", "FAIL")):
            r = self.research("adjudicate", self.decision(status, supersedes=previous), f"a{i}")
            previous = r["record_digest"]
        m = self.metrics()
        self.assertEqual(m["counts"]["adjudication_revision_count"], 5)
        self.assertEqual(m["counts"]["ineligible_adjudication_revision_count"], 3)
        self.assertEqual(m["counts"]["latest_assessed_case_count"], 1)
        self.assertEqual(m["counts"]["latest_eligible_case_count"], 0)
        self.assertEqual(m["latest_normalized_status_counts"], {"FAIL": 1})
        self.assertEqual(m["required_case_coverage"]["fail_count"], 2)
        self.assertEqual(m["required_case_coverage"]["skipped_count"], 0)
        self.assertEqual(m["adjudication_recovery"]["episode_count"], 2)
        self.assertEqual(m["adjudication_recovery"]["recovered_episode_count"], 1)
        self.assertEqual(m["adjudication_recovery"]["open_episode_count"], 1)
        self.assertEqual(m["adjudication_recovery"]["rate_denominator"], 2)
        self.assertEqual(m["cases"][0]["latest_adjudication_digest"], previous)
        self.assertFalse(m["acceptance_verified"])

    def test_history_not_live_completion_or_external_probe(self):
        self.enroll()
        r = self.research("adjudicate", self.decision(), "pass")
        self.finalize()
        self.project()
        m = self.metrics()
        self.assertEqual(m["work_history"]["ever_recorded_completed_work_count"], 1)
        self.assertEqual(m["work_history"]["recorded_completion_count"], 1)
        self.assertFalse(m["acceptance_verified"])
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a-b; }\n")
        self.assertEqual(m, self.metrics())
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        d = self.decision(supersedes=r["record_digest"])
        d["open_blockers"] = ["review"]
        self.research("adjudicate", d, "blocked")
        latest = self.metrics()
        self.assertEqual(latest["work_history"], m["work_history"])
        self.assertEqual(latest["counts"]["latest_not_eligible_case_count"], 1)
        self.assertEqual(latest["latest_normalized_status_counts"], {"PASS": 1})
        self.assertEqual(latest["counts"]["pass_but_ineligible_revision_count"], 1)
        self.assertIsNone(latest["unavailable"]["false_completion_prevented_count"]["value"])

    def test_cross_case_recovery_never_paired(self):
        self.enroll()
        self.research("adjudicate", self.decision("ERROR", "ENVIRONMENT"), "failed")
        c = dict(self.case["event"]["request"]["record"], case_id="case-2")
        case2 = self.research("case-create", c, "case-2")
        p = dict(self.policy, case_id="case-2", case_digest=case2["record_digest"])
        policy2 = self.research("outcome-enroll", p, "policy-2")
        d = dict(self.decision(), case_id="case-2", case_digest=case2["record_digest"], policy_digest=policy2["record_digest"])
        self.research("adjudicate", d, "pass-2")
        m = self.metrics()
        self.assertEqual(m["counts"]["case_count"], 2)
        self.assertEqual(m["adjudication_recovery"]["episode_count"], 1)
        self.assertEqual(m["adjudication_recovery"]["recovered_episode_count"], 0)
        self.assertEqual(m["required_case_coverage"]["required_case_count"], 4)
        self.assertEqual(m["required_case_coverage"]["environment_failure_count"], 2)
        only = self.metrics("--case", "case-2")
        self.assertEqual(only["counts"]["case_count"], 1)
        self.assertFalse(only["adjudication_recovery"]["rate_defined"])
        self.assertEqual(only["work_history"]["work_count"], 1)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(OutcomeMetrics(n) for n in OutcomeMetrics.__dict__ if n.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
