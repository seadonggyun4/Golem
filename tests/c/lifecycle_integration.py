"""Three-phase orchestration with a real native document mutation."""
import json
import subprocess
import sys
import unittest
import workflow_integration as fixture

sys.path.insert(0, str(fixture.SOURCE / "tools"))
import agent_lifecycle as life


class Lifecycle(fixture.Workflow):
    def setup_lifecycle(self):
        self.setup_work(mode="documents")
        repo = self.root / "repo"
        repo.mkdir()
        life.records.git(repo, "init", "-q")
        life.records.git(repo, "-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                         "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "fixture")
        metadata = self.metadata("stage-selection", "selection", [self.selection["scope"]], 3)
        metadata["selection"] = self.selection
        meta = self.write("selection-meta.json", metadata)
        body = self.write("selection-body.md", self.body("stage-selection", metadata["parents"]))
        commands = {
            "prepare": (["workflow", "select", str(self.work), "scope", "1", "documents"], "mode", "documents"),
            "execute": (["document", "submit", str(self.work), str(meta), str(body), "lifecycle-submit"], "committed", True),
            "finalize": (["workflow", "next", str(self.work), "selection"], "target_kind", "planning"),
        }
        self.plan = {"schema": life.SCHEMA, "run_id": "native-1", "cwd": str(repo),
                     "inputs": {str(p): life.records.digest(p) for p in (meta, body)}, "phases": {}}
        for phase, (argv, key, expected) in commands.items():
            self.plan["phases"][phase] = [{"id": phase, "argv": [str(fixture.CLI), "--output-mode", "full", *argv],
                "timeout": 30, "executable_sha256": life.records.digest(fixture.CLI),
                "expect": [{"path": [key], "equals": expected}]}]
        self.store = self.root / "lifecycle"

    def test_real_native_lifecycle_and_duplicate(self):
        self.setup_lifecycle()
        request = self.write("lifecycle-plan.json", self.plan)
        command = [sys.executable, str(fixture.SOURCE / "tools/agent_lifecycle.py"), "run", str(request),
                   "--store", str(self.store), "--reviewed-plan", life.io.identity(self.plan)]
        first = subprocess.run(command, capture_output=True, timeout=90)
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        result = json.loads(first.stdout)
        self.assertEqual(result["status"], "FINISHED")
        self.assertFalse(result["product_acceptance"])
        before = {str(p): life.records.digest(p) for p in self.work.rglob("*") if p.is_file()}
        second = subprocess.run(command, capture_output=True, timeout=90)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout), result)
        self.assertEqual(before, {str(p): life.records.digest(p) for p in self.work.rglob("*") if p.is_file()})
        self.assertEqual(self.next()["target_kind"], "planning")

    def test_native_rejection_stops_before_registration(self):
        self.setup_lifecycle()
        self.plan["phases"]["prepare"][0]["argv"][-2] = "2"
        before = {str(p): life.records.digest(p) for p in self.work.rglob("*") if p.is_file()}
        result = life.run(self.plan, self.store, life.io.identity(self.plan))
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual(result["steps"][1]["status"], "NOT_RUN")
        self.assertEqual(before, {str(p): life.records.digest(p) for p in self.work.rglob("*") if p.is_file()})


if __name__ == "__main__":
    names = [name for name in Lifecycle.__dict__ if name.startswith("test_")]
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(Lifecycle(name) for name in names)).wasSuccessful())
