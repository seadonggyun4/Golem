"""Fact/delta integration using actual subprocess observations."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest

import agent_io as io
import judgment_record as jr
import test_agent_io


class Judgments(unittest.TestCase):
    setUp = test_agent_io.AgentIO.setUp
    git = test_agent_io.AgentIO.git
    plan = test_agent_io.AgentIO.plan
    run_plan = test_agent_io.AgentIO.run_plan
    work = {"project_id": "project", "work_id": "work"}

    def delta(self, bundle, text="Investigate the recorded result"):
        ids = list(jr.fact_ids(jr.facts(bundle, self.work)))
        return {"schema": jr.DELTA, "actor": "agent", "set": {
            "decision": {"text": text, "fact_ids": ids}}, "remove": []}

    def write(self, bundle, delta=None, baseline=None, revision=None, name="judgment"):
        return jr.write(bundle, self.work, delta or self.delta(bundle), self.root / name,
                        baseline, revision)

    def test_ordinary_task_has_no_research_fields(self):
        bundle = self.run_plan()
        view = self.write(bundle)
        self.assertEqual(view["judgments"]["decision"]["verification"], "DECLARED_NOT_VERIFIED")
        self.assertFalse(view["product_acceptance"])
        self.assertFalse(view["native_work_updated"])
        self.assertFalse((self.root / "judgment/report.md").exists())
        self.assertNotIn("hypothesis", io.encoded(view).decode())

    def test_no_change_marks_prior_judgment_historical(self):
        first = self.write(self.run_plan())
        delta = {"schema": jr.DELTA, "actor": "agent", "set": {}, "remove": []}
        second = self.write(self.run_plan(), delta, self.root / "judgment",
                            first["revision"], "second")
        self.assertEqual(second["judgments"]["decision"]["freshness"], "HISTORICAL_REQUIRES_REVIEW")
        self.assertEqual(second["changes"], delta)

    def test_update_and_remove_replay(self):
        first = self.write(self.run_plan())
        bundle = self.run_plan()
        second = self.write(bundle, self.delta(bundle, "Changed decision"), self.root / "judgment",
                            first["revision"], "second")
        delta = {"schema": jr.DELTA, "actor": "human", "set": {}, "remove": ["decision"]}
        third = self.write(bundle, delta, self.root / "second", second["revision"], "third")
        self.assertEqual(third["judgments"], {})

    def test_failed_and_not_run_facts_are_not_hidden(self):
        plan = self.plan("raise SystemExit(7)")
        plan["commands"].append({"id": "later", "argv": [sys.executable, "-c", "print(1)"], "timeout": 5})
        view = self.write(self.run_plan(plan))
        self.assertEqual(view["execution"]["status"], "FAILED")
        self.assertEqual({f["status"] for f in view["execution"]["facts"].values()}, {"FAILED", "NOT_RUN"})

    def test_unknown_evidence_rejected_before_publication(self):
        bundle = self.run_plan()
        delta = self.delta(bundle)
        delta["set"]["decision"]["fact_ids"] = ["0" * 64]
        with self.assertRaises(jr.ContractError):
            self.write(bundle, delta)
        self.assertFalse((self.root / "judgment").exists())

    def test_wrong_or_missing_parent_rejected(self):
        bundle = self.run_plan()
        self.write(bundle)
        for baseline, revision in ((self.root / "judgment", None),
                                   (self.root / "judgment", "0" * 64), (None, "0" * 64)):
            with self.subTest(revision=revision), self.assertRaises(jr.ContractError):
                self.write(bundle, baseline=baseline, revision=revision, name="second")

    def test_work_mismatch_rejected(self):
        bundle = self.run_plan(scope={"work_id": "other"})
        with self.assertRaises(jr.ContractError):
            self.write(bundle)

    def test_tampered_raw_and_judgment_rejected(self):
        bundle = self.run_plan()
        self.write(bundle)
        (bundle / "check/stdout.log").write_text("tampered")
        with self.assertRaises(io.ObservationError):
            jr.facts(bundle, self.work)
        (self.root / "judgment/record.json").write_text("{}")
        with self.assertRaises(jr.ContractError):
            jr.view(self.root / "judgment")

    def test_embedded_snapshot_revision_checked_on_replay(self):
        self.write(self.run_plan())
        record, _ = jr.load(self.root / "judgment")
        changed = copy.deepcopy(record)
        changed["entries"][0]["observation"]["record"]["status"] = "invented"
        with self.assertRaises(jr.ContractError):
            jr.replay(changed)

    def test_no_overwrite_and_overlap(self):
        bundle = self.run_plan()
        self.write(bundle)
        with self.assertRaises(FileExistsError):
            self.write(bundle)
        with self.assertRaises(jr.ContractError):
            jr.write(bundle, self.work, self.delta(bundle), bundle / "child")

    def test_bounds_and_invalid_removal(self):
        bundle = self.run_plan()
        for delta in ({"schema": jr.DELTA, "actor": "agent", "set": {}, "remove": ["missing"]},
                      {**self.delta(bundle), "actor": ""}):
            with self.assertRaises(jr.ContractError):
                self.write(bundle, delta)

    def test_cli_facts_and_view(self):
        bundle = self.run_plan()
        self.write(bundle)
        for argv in (["judgment-facts", str(bundle), "--project-id", "project", "--work-id", "work"],
                     ["judgment-view", str(self.root / "judgment")]):
            result = subprocess.run([sys.executable, str(Path(io.__file__)), *argv], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(io.strict_json(result.stdout)["product_acceptance"])

    def test_cli_write_and_exact_parent(self):
        bundle = self.run_plan()
        delta = self.root / "delta.json"
        io.save(delta, io.encoded(self.delta(bundle)))
        argv = [sys.executable, str(Path(io.__file__)), "judgment-write", str(bundle),
                "--project-id", "project", "--work-id", "work", "--delta", str(delta),
                "--output", str(self.root / "cli-output")]
        result = subprocess.run(argv, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(argv + ["--since", str(self.root / "cli-output"),
                                       "--revision", "0" * 64], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(io.strict_json(result.stderr)["code"], "JUDGMENT_CONTRACT")

    def test_timeout_is_execution_fact_not_qa_failure_classification(self):
        plan = self.plan("import time; time.sleep(30)")
        plan["commands"][0]["timeout"] = 1
        view = self.write(self.run_plan(plan))
        fact = next(iter(view["execution"]["facts"].values()))
        self.assertEqual(fact["reason"], "TIMEOUT")
        self.assertFalse(view["product_acceptance"])

    def test_chain_limit_and_parent_links(self):
        self.write(self.run_plan())
        record, _ = jr.load(self.root / "judgment")
        with self.assertRaises(jr.ContractError):
            jr.replay({**record, "entries": record["entries"] * (jr.MAX_ENTRIES + 1)})
        changed = copy.deepcopy(record)
        changed["entries"][0]["parent"] = "0" * 64
        with self.assertRaises(jr.ContractError):
            jr.replay(changed)

    def test_output_inside_source_rejected(self):
        bundle = self.run_plan()
        with self.assertRaises(jr.ContractError):
            jr.write(bundle, self.work, self.delta(bundle), self.source / "derived")


if __name__ == "__main__":
    unittest.main()
