"""Real CLI observations, without provider calls or semantic savings claims."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import unittest

import workflow_integration as fixture

sys.path.insert(0, str(fixture.SOURCE / "tools"))
import agent_io

parser = argparse.ArgumentParser()
parser.add_argument("--evidence-root", type=Path)
options = parser.parse_args()
EVIDENCE = agent_io.private_directory(options.evidence_root) if options.evidence_root else None


class Observation(fixture.Workflow):
    # Only this integration case, not inherited workflow cases, is loaded below.
    def test_live_cli_observation_and_delta(self):
        self.setup_work()
        self.register_selection()
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True, env=fixture.ENV)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c",
                        "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture"],
                       check=True, env=fixture.ENV)
        scope = {"cli": str(fixture.CLI), "work": str(self.work), "work_id": "example-work", "selection": "selection"}
        bundles = []
        initial_work = {str(p.relative_to(self.work)): agent_io.digest(p)
                        for p in self.work.rglob("*") if p.is_file()}
        for i in range(4):
            if i == 2:
                self.cli("session", "call", self.work, self.write("start.json", {
                    "schema_version": 1, "operation": "start", "work_id": "example-work",
                    "key": "start", "expected_sequence": 0, "selection_id": "selection"}))
                initial_work = {str(p.relative_to(self.work)): agent_io.digest(p)
                                for p in self.work.rglob("*") if p.is_file()}
            output = agent_io.private_directory((EVIDENCE or self.root) / f"observation-{i}")
            plan = agent_io.observe_plan(fixture.CLI, self.work, "example-work", "selection", output, "code")
            agent_io.run(plan, repo, output, scope)
            value = agent_io.view(output)
            self.assertEqual(value["status"], "RECORDED", value)
            self.assertFalse(value["product_acceptance"])
            self.assertEqual(value["steps"][1]["observed"]["fields"]["action"],
                             "BLOCKED" if i < 2 else "NEXT_ACTION")
            self.assertEqual(value["steps"][1]["observed"]["fields"]["reason"],
                             "START_REQUIRED" if i < 2 else "CLAIM_REQUIRED")
            for step in value["steps"]:
                original = json.loads((output / step["id"] / "stdout.log").read_bytes())
                for key, field in step["observed"]["fields"].items():
                    self.assertEqual(original[key] if key in original else original["status"][key], field)
            consolidated = agent_io.work_record(output)
            self.assertEqual(len(consolidated["value"]["assessments"]), 1)
            self.assertEqual(agent_io.work_record(output, "status")["value"],
                             consolidated["value"]["status"])
            bundles.append(output)
            self.assertEqual(initial_work, {str(p.relative_to(self.work)): agent_io.digest(p)
                                            for p in self.work.rglob("*") if p.is_file()})
        revision = agent_io.digest(bundles[0] / "record.json")
        delta = agent_io.view(bundles[1], bundles[0], revision)
        self.assertEqual(delta["mode"], "DELTA")
        self.assertEqual(delta["steps"], [])
        changed = agent_io.view(bundles[2], bundles[1], agent_io.digest(bundles[1] / "record.json"))
        self.assertEqual(changed["mode"], "DELTA")
        self.assertIn("next", [step["id"] for step in changed["steps"]])
        self.assertEqual(agent_io.view(bundles[3], bundles[2],
                                      agent_io.digest(bundles[2] / "record.json"))["steps"], [])
        measurements = {"fixture": "real CLI, synthetic Work, not a model evaluation",
                        "full": agent_io.measure(bundles[1]),
                        "delta": agent_io.measure(bundles[1], bundles[0], revision),
                        "next_action_full": agent_io.measure(bundles[3]),
                        "next_action_delta": agent_io.measure(bundles[3], bundles[2],
                                                              agent_io.digest(bundles[2] / "record.json"))}
        if EVIDENCE:
            agent_io.save(EVIDENCE / "measurements.json", agent_io.encoded(measurements))
        print(json.dumps(measurements, sort_keys=True))


if __name__ == "__main__":
    suite = unittest.TestSuite([Observation("test_live_cli_observation_and_delta")])
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
