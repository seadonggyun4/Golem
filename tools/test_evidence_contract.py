"""No upgrade from hashes or declarations to truth, execution or independent review."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest

import agent_io as io
import evidence_adapters as adapters
import evidence_contract as ec
import judgment_record as jr
import revision_status as rs
import test_agent_io


class Evidence(unittest.TestCase):
    setUp = test_agent_io.AgentIO.setUp
    git = test_agent_io.AgentIO.git
    plan = test_agent_io.AgentIO.plan
    run_plan = test_agent_io.AgentIO.run_plan
    work = {"project_id": "project", "work_id": "work"}

    def observation(self, script="print('a false assertion')"):
        bundle = self.run_plan(self.plan(script), self.work)
        return bundle, adapters.observation(bundle, io.digest(bundle / "record.json"), "check", self.work)

    def review(self, **changes):
        raw = b"artifact"
        payload = {"schema": "golem.evidence-review.v1", "subject_sha256": ec.sha256(raw),
                   "binding": self.work, "author": "author", "reviewer": "reviewer",
                   "scope": "logic-correctness", "decision": "APPROVE", **changes}
        return adapters.review(raw, payload, payload["subject_sha256"], self.work)

    def test_unknown_dimensions_are_explicit(self):
        value = ec.assessment("a" * 64, "ARTIFACT")
        self.assertTrue(all(c["state"].startswith("NOT_") for c in value["checks"].values()))
        self.assertEqual(value["content_truth"], "NOT_ESTABLISHED")

    def test_hash_and_exit_zero_never_establish_truth_or_review(self):
        _, value = self.observation()
        self.assertEqual(value["checks"]["integrity"]["state"], "MATCH")
        self.assertEqual(value["checks"]["execution"]["state"], "OBSERVED")
        self.assertEqual(value["checks"]["independent_review"]["state"], "NOT_OBSERVED")
        self.assertEqual(value["content_truth"], "NOT_ESTABLISHED")
        self.assertFalse(value["acceptance_authorized"])

    def test_execution_does_not_claim_stdout_was_parsed(self):
        _, value = self.observation("print('not json')")
        self.assertEqual(value["checks"]["parser"]["scope"], "RECORDER_ENVELOPE_NOT_STDOUT_CONTENT")

    def test_failed_exit_is_still_observed_execution(self):
        _, value = self.observation("raise SystemExit(7)")
        self.assertEqual(value["checks"]["execution"]["state"], "OBSERVED")
        self.assertEqual(value["content_truth"], "NOT_ESTABLISHED")

    def test_timeout_is_incomplete_not_absent(self):
        plan = self.plan("import time; time.sleep(30)")
        plan["commands"][0]["timeout"] = 1
        bundle = self.run_plan(plan, self.work)
        value = adapters.observation(bundle, io.digest(bundle / "record.json"), "check", self.work)
        self.assertEqual(value["checks"]["execution"]["state"], "INCOMPLETE")

    def test_not_run_has_no_execution_claim(self):
        plan = self.plan("raise SystemExit(7)")
        plan["commands"].append({"id": "later", "argv": [sys.executable, "-c", "print(1)"], "timeout": 5})
        bundle = self.run_plan(plan, self.work)
        value = adapters.observation(bundle, io.digest(bundle / "record.json"), "later", self.work)
        self.assertEqual(value["checks"]["execution"]["state"], "NOT_OBSERVED")

    def test_self_hash_not_integrity_check(self):
        value = adapters.declaration(b"I passed", "user", self.work)
        self.assertEqual(value["checks"]["statement"]["state"], "DECLARED")
        self.assertEqual(value["checks"]["integrity"]["state"], "NOT_CHECKED")
        self.assertEqual(value["checks"]["execution"]["state"], "NOT_OBSERVED")

    def test_distinct_review_ids_not_authenticated_independence(self):
        value = self.review()
        self.assertEqual(value["checks"]["independent_review"]["state"], "DECLARED")
        self.assertEqual(value["checks"]["authenticity"]["state"], "NOT_VERIFIED")
        self.assertFalse(value["acceptance_authorized"])

    def test_self_review_is_rejected(self):
        self.assertEqual(self.review(reviewer="author")["checks"]["independent_review"]["state"], "REJECTED")

    def test_wrong_review_artifact_is_mismatch(self):
        value = self.review(subject_sha256="f" * 64)
        self.assertEqual(value["checks"]["integrity"]["state"], "MISMATCH")
        self.assertEqual(value["checks"]["independent_review"]["state"], "REJECTED")

    def test_cross_work_review_rejected(self):
        with self.assertRaises(ValueError):
            self.review(binding={"project_id": "project", "work_id": "different"})

    def test_forged_truth_authenticity_or_missing_axis_rejected(self):
        value = ec.assessment("a" * 64, "ARTIFACT")
        for change in (lambda v: v.update(content_truth="TRUE"),
                       lambda v: v.update(acceptance_authorized=True),
                       lambda v: v["checks"]["authenticity"].update(state="VERIFIED"),
                       lambda v: v["checks"].pop("independent_review")):
            forged = copy.deepcopy(value)
            change(forged)
            with self.assertRaises(ValueError):
                ec.validate(forged)

    def test_check_requires_scope_method_and_references(self):
        value = ec.assessment("a" * 64, "ARTIFACT")
        with self.assertRaises(ValueError):
            ec.set_check(value, "parser", "VALID", "NONE", "NONE")
        self.assertEqual(value["checks"]["parser"]["state"], "NOT_RUN")

    def test_reference_limits_and_duplicates(self):
        value = ec.assessment("a" * 64, "ARTIFACT")
        for refs in (["b" * 64] * 2, [f"{i:064x}" for i in range(33)]):
            with self.assertRaises(ValueError):
                ec.set_check(value, "parser", "VALID", "shape", "parser", refs=refs)

    def test_legacy_research_pass_is_declared_not_observed(self):
        item = {"id": "case", "status": "PASS", "failure_domain": "NONE", "evidence_digest": "a" * 64}
        value = adapters.research_outcome({"observations": [item]}, "author", self.work)[0]["verification"]
        self.assertEqual(value["checks"]["statement"]["state"], "DECLARED")
        self.assertEqual(value["checks"]["integrity"]["state"], "NOT_CHECKED")
        self.assertEqual(value["checks"]["execution"]["state"], "NOT_OBSERVED")

    def test_legacy_unknown_and_inconsistent_fail_closed(self):
        item = {"id": "case", "status": "UNKNOWN", "failure_domain": "UNKNOWN", "evidence_digest": "a" * 64}
        self.assertEqual(adapters.research_outcome({"observations": [item]}, "author")[0]["declared_status"], "UNKNOWN")
        with self.assertRaises(ValueError):
            adapters.research_outcome({"observations": [{**item, "status": "PASS"}]}, "author")

    def test_judgment_view_has_statement_not_execution(self):
        bundle, _ = self.observation()
        ids = list(jr.fact_ids(jr.facts(bundle, self.work)))
        view = jr.write(bundle, self.work, {"schema": jr.DELTA, "actor": "agent",
            "set": {"decision": {"text": "Investigate", "fact_ids": ids}}, "remove": []}, self.root / "judgment")
        value = view["judgments"]["decision"]["evidence_verification"]
        self.assertEqual(value["checks"]["statement"]["state"], "DECLARED")
        self.assertEqual(value["checks"]["execution"]["state"], "NOT_OBSERVED")

    def test_status_adapter_parser_independent_of_domain_pass(self):
        bundle, _ = self.observation("print(\"<testsuite><testcase><failure/></testcase></testsuite>\")")
        entry = {"id": "qa", "channel": "local_qa", "adapter": "junit.v1", "bundle": str(bundle),
                 "revision": io.digest(bundle / "record.json"), "step": "check", "scope": "suite"}
        index = {"binding": self.work, "repository": "owner/repo"}
        target = {k: v for k, v in rs.records.source_identity(self.source).items() if k != "files"}
        result = rs.evidence(entry, index, target)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["verification"]["checks"]["parser"]["state"], "VALID")
        self.assertEqual(result["verification"]["content_truth"], "NOT_ESTABLISHED")

    def test_cli_observation_and_declaration(self):
        bundle, _ = self.observation()
        text = self.root / "claim.txt"
        io.save(text, b"a declared claim")
        for args in (["observation", str(bundle), "--revision", io.digest(bundle / "record.json"), "--step", "check"],
                     ["declaration", str(text), "--actor", "user"]):
            result = subprocess.run([sys.executable, adapters.__file__, *args,
                                     "--project-id", "project", "--work-id", "work"], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            ec.validate(io.strict_json(result.stdout))

    def test_invalid_parser_keeps_integrity_and_execution_dimensions(self):
        bundle, _ = self.observation("print('not XML')")
        entry = {"id": "qa", "channel": "local_qa", "adapter": "junit.v1", "bundle": str(bundle),
                 "revision": io.digest(bundle / "record.json"), "step": "check", "scope": "suite"}
        target = {k: v for k, v in rs.records.source_identity(self.source).items() if k != "files"}
        result = rs.evidence(entry, {"binding": self.work}, target)
        checks = result["verification"]["checks"]
        self.assertEqual(result["status"], "INVALID")
        self.assertEqual(checks["integrity"]["state"], "MATCH")
        self.assertEqual(checks["parser"]["state"], "INVALID")
        self.assertEqual(checks["execution"]["state"], "OBSERVED")

    def test_corrupt_bundle_cannot_claim_parser_or_execution(self):
        bundle, _ = self.observation()
        revision = io.digest(bundle / "record.json")
        (bundle / "check/stdout.log").write_text("tampered")
        entry = {"id": "qa", "channel": "local_qa", "adapter": "command.v1", "bundle": str(bundle),
                 "revision": revision, "step": "check", "scope": "suite"}
        result = rs.evidence(entry, {"binding": self.work}, {})
        checks = result["verification"]["checks"]
        self.assertEqual(checks["integrity"]["state"], "MISMATCH")
        self.assertEqual(checks["parser"]["state"], "NOT_RUN")
        self.assertEqual(checks["execution"]["state"], "NOT_OBSERVED")

    def test_cross_work_execution_is_not_accepted(self):
        bundle, _ = self.observation()
        with self.assertRaises(ValueError):
            adapters.observation(bundle, io.digest(bundle / "record.json"), "check",
                                 {**self.work, "work_id": "other"})

    def test_cli_review_decision_is_not_verification_status(self):
        artifact = self.root / "artifact.txt"
        io.save(artifact, b"artifact")
        digest = ec.sha256(b"artifact")
        statement = self.root / "review.json"
        io.save(statement, io.encoded({"schema": "golem.evidence-review.v1", "subject_sha256": digest,
            "binding": self.work, "author": "author", "reviewer": "reviewer",
            "scope": "correctness", "decision": "REJECT"}))
        result = subprocess.run([sys.executable, adapters.__file__, "review", str(artifact),
            "--statement", str(statement), "--sha256", digest, "--project-id", "project",
            "--work-id", "work"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        view = io.strict_json(result.stdout)
        self.assertEqual(view["declared_decision"], "REJECT")
        self.assertEqual(view["verification"]["checks"]["independent_review"]["state"], "DECLARED")
        self.assertEqual(view["verification"]["content_truth"], "NOT_ESTABLISHED")


if __name__ == "__main__":
    unittest.main()
