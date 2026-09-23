"""Read-only 29C replay projections. No metric numbers submitted by the agent."""
import hashlib
import json
import unittest
from research_integration import Research, SOURCE


class Metrics(Research):
    def metrics(self, *args, **kwargs):
        return self.run_cli("research", "metrics", self.work, *args, **kwargs)

    def fingerprint(self):
        return {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).digest())
                for p in self.work.rglob("*") if p.is_file()}

    def check_digest(self, metrics):
        payload = dict(metrics)
        digest = payload.pop("projection_digest")
        self.assertEqual(digest, hashlib.sha256(json.dumps(payload, ensure_ascii=False,
                          separators=(",", ":")).encode()).hexdigest())

    def test_empty_golden_and_undefined_measurements(self):
        before = self.fingerprint()
        m = self.metrics()
        expected = dict(research_record_count=0, case_count=0, attempt_plan_count=0, attempt_count_total=0,
                        linked_plan_attempt_count=0, retrospective_attempt_count=0, unobserved_plan_count=0,
                        outcome_enrollment_count=0, adjudication_revision_count=0, latest_assessed_case_count=0,
                        ineligible_adjudication_revision_count=0, pass_but_ineligible_revision_count=0,
                        latest_unassessed_enrollment_count=0, latest_eligible_case_count=0, latest_not_eligible_case_count=0)
        self.assertEqual(m["counts"], expected)
        self.assertEqual(m["work_history"]["work_count"], 1)
        self.assertEqual(m["cases"], [])
        self.assertEqual(m["source_records"], [])
        self.assertFalse(m["adjudication_recovery"]["rate_defined"])
        self.assertIsNone(m["declared_attempt_duration"]["min_ms"])
        for metric in m["unavailable"].values():
            self.assertIsNone(metric["value"])
            self.assertTrue(metric["reason"])
        self.assertFalse(m["acceptance_verified"])
        self.assertFalse(m["execution_authorized"])
        self.check_digest(m)
        self.assertEqual(m, self.metrics())
        self.metrics("--format", "markdown", raw=True)
        self.assertEqual(before, self.fingerprint())

    def test_declared_counts_not_promoted_and_retry_not_counted(self):
        case = self.create()
        plan = self.attempt(case)
        receipt = self.call("attempt-plan", plan, "plan")
        result = self.result(plan, receipt["record_digest"])
        result["classification"] = "FALSE_COMPLETION_PREVENTED"
        result["observations"][0]["counts"] = [dict(name="false_completion_prevented_count", value=2**63-1)]
        self.call("attempt-record", result, "observed")
        first = self.metrics()
        self.assertEqual(first["counts"]["attempt_count_total"], 1)
        self.assertEqual(first["counts"]["linked_plan_attempt_count"], 1)
        self.assertEqual(first["counts"]["unobserved_plan_count"], 0)
        self.assertEqual(first["declared_classification_counts"], {"FALSE_COMPLETION_PREVENTED": 1})
        self.assertIsNone(first["unavailable"]["false_completion_prevented_count"]["value"])
        self.assertEqual(first["declared_attempt_duration"]["sum_ms"], 100)
        self.call("attempt-record", dict(reversed(list(result.items()))), "observed")
        self.assertEqual(first, self.metrics())
        self.check_digest(first)

    def test_case_filter_and_unobserved_plan(self):
        first = self.create()
        self.call("attempt-plan", self.attempt(first), "unobserved")
        case2 = dict(self.case, case_id="second")
        second = self.call("case-create", case2, "second")
        r = self.result(self.attempt(second))
        r["case_id"] = "second"
        r["actor_kind"] = "HUMAN_OPERATOR"
        r["classification"] = "ENVIRONMENT_LIMITATION"
        self.call("attempt-record", r, "retrospective")
        all_cases = self.metrics()
        a = self.metrics("--case", self.case["case_id"])
        b = self.metrics("--case", "second")
        self.assertEqual(all_cases["counts"]["case_count"], 2)
        self.assertEqual(a["counts"]["attempt_count_total"], 0)
        self.assertEqual(a["counts"]["unobserved_plan_count"], 1)
        self.assertEqual(b["counts"]["retrospective_attempt_count"], 1)
        self.assertEqual(b["declared_actor_counts"], {"HUMAN_OPERATOR": 1})
        self.assertIsNone(b["unavailable"]["manual_intervention_count"]["value"])
        self.assertEqual(a["boundary"], b["boundary"])
        self.assertEqual([v["research_sequence"] for v in a["source_records"]], [1, 2])
        self.assertEqual([v["research_sequence"] for v in b["source_records"]], [3, 4])

    def test_cli_invalid_filters_and_flags(self):
        for args in (("--case", ""), ("--case", "missing"), ("--case", "../x"),
                     ("--case", "a", "--case", "b"), ("--format", "csv"), ("--format",),
                     ("--format", "json", "--format", "json"), ("--output", "file"), ("trailing",)):
            self.metrics(*args, ok=False)

    def test_private_prose_not_projected_and_markdown_deterministic(self):
        self.case["unit_of_analysis"] = "PRIVATE-NARRATIVE <script>do-not-export</script>"
        self.create()
        before = self.fingerprint()
        md = self.metrics("--format", "markdown", raw=True)
        js = self.metrics(raw=True)
        self.assertNotIn(b"PRIVATE-NARRATIVE", md + js)
        self.assertNotIn(b"<script>", md)
        self.assertIn(b"undefined", md)
        self.assertEqual(md, self.metrics("--format", "markdown", raw=True))
        self.assertEqual(before, self.fingerprint())

    def test_large_declared_duration_does_not_overflow(self):
        case = self.create()
        previous = ""
        limit = 253402300799999
        for i in range(3):
            r = self.result(self.attempt(case, f"a{i}", previous))
            r.update(started_at=0, ended_at=limit)
            previous = self.call("attempt-record", r, f"a{i}")["record_digest"]
        d = self.metrics()["declared_attempt_duration"]
        self.assertEqual(d["sum_ms"], limit * 3)
        self.assertEqual(d["min_ms"], limit)
        self.assertEqual(d["max_ms"], limit)

    def test_replay_corruption_rejected(self):
        case = self.create()
        self.metrics()
        path = self.cas_path(case["record_digest"])
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(b"corrupt")
        self.metrics(ok=False)
        path.write_bytes(original)
        self.assertEqual(self.metrics()["counts"]["case_count"], 1)

    def test_pending_orphan_and_interleaved_documents(self):
        self.create()
        before = self.metrics()
        (self.work / "events/.pending-metrics-test").write_bytes(b"not committed")
        self.assertEqual(before, self.metrics())
        samples = SOURCE / "samples/documents"
        self.run_cli("document", "submit", self.work, samples / "planning.json", samples / "planning.md", "planning")
        after = self.metrics()
        self.assertEqual(before["counts"], after["counts"])
        self.assertNotEqual(before["boundary"]["work_head"], after["boundary"]["work_head"])
        self.assertNotEqual(before["projection_digest"], after["projection_digest"])

    def test_maximum_case_population_fits_json_and_markdown(self):
        for i in range(256):
            self.call("case-create", dict(self.case, case_id=f"c{i}"), f"k{i}")
        m = self.metrics()
        self.assertEqual(m["counts"]["case_count"], 256)
        self.assertEqual(len(m["cases"]), 256)
        self.assertEqual(len(m["source_records"]), 256)
        self.check_digest(m)
        self.assertLess(len(self.metrics(raw=True)), 262144)
        self.assertLess(len(self.metrics("--format", "markdown", raw=True)), 1048576)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Metrics(n) for n in Metrics.__dict__ if n.startswith("test_"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
