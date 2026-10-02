"""Real native selection, immutable proposals and retained failures."""
import json
import subprocess
import sys
import unittest

import workflow_integration as fixture

sys.path.insert(0, str(fixture.SOURCE / "tools"))
import agent_io as io


class Procedure(fixture.Workflow):
    def capture(self, activities, bad_digest=False, revision=1):
        repo = self.root / "repo"
        if not repo.exists():
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c",
                            "user.email=test@example.invalid", "commit", "--allow-empty", "-qm", "fixture"], check=True)
        scope = dict(self.selection["scope"])
        scope["revision"] = revision
        if bad_digest:
            scope["digest"] = "f" * 64
        request = {"schema": "golem.procedure-intent.v1", "activities": activities, "scope": scope}
        output = self.root / ("bundle-" + "-".join(activities) + str(revision) + str(bad_digest))
        completed = subprocess.run([sys.executable, str(fixture.SOURCE / "tools/agent_io.py"), "procedure",
            "--cwd", str(repo), "--output", str(output), "--cli", str(fixture.CLI), "--work", str(self.work),
            "--intent", str(self.write("intent.json", request))], capture_output=True, timeout=90)
        return completed, output

    def test_routes_are_native_proposals_not_effects(self):
        self.setup_work(ui=True)
        before = {str(p): io.digest(p) for p in self.work.rglob("*") if p.is_file()}
        for activities in (["docs"], ["docs", "code"], ["docs", "deploy"]):
            completed, output = self.capture(activities)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result, io.procedure_view(output))
            self.assertEqual(result["mode"], "documents" if activities == ["docs"] else "development")
            self.assertTrue(all(d["status"] == "REQUIRED" for d in result["selection"]["decisions"]))
            self.assertFalse(result["execution_authorized"])
            self.assertTrue(all(step["state"] == "NOT_EVALUATED" for step in result["procedure"]))
            if "deploy" in activities:
                self.assertEqual(result["deployment"], "BLOCKED_PENDING_SCOPED_HOST_INTEGRATION")
            self.assertEqual(before, {str(p): io.digest(p) for p in self.work.rglob("*") if p.is_file()})

    def test_scope_digest_mismatch_retains_evidence(self):
        self.setup_work()
        completed, output = self.capture(["code"], bad_digest=True)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(json.loads(completed.stderr)["code"], "PROCEDURE_EVIDENCE")
        io.load_bundle(output)
        with self.assertRaises(io.ObservationError):
            io.procedure_view(output)

    def test_missing_revision_never_becomes_proposal(self):
        self.setup_work()
        completed, output = self.capture(["code"], revision=2)
        self.assertEqual(completed.returncode, 2)
        record, _ = io.load_bundle(output)
        self.assertEqual(record["status"], "FAILED")
        self.assertTrue((output / "selection/stderr.log").exists())

    def test_superseded_scope_never_becomes_proposal(self):
        self.setup_work()
        metadata = self.metadata("scope", version=2)
        metadata["assessment"] = self.a
        self.publish(metadata)
        completed, output = self.capture(["code"])
        self.assertEqual(completed.returncode, 2)
        record, _ = io.load_bundle(output)
        self.assertEqual(record["status"], "FAILED")

    def test_proposal_registers_without_fabricating_development(self):
        self.setup_work()
        completed, output = self.capture(["docs"])
        self.assertEqual(completed.returncode, 0, completed.stderr)
        proposal = io.procedure_view(output)
        self.register_selection(p=proposal["selection"])
        self.managed("planning")
        self.managed("development-plan")
        self.assertEqual(self.next()["target_kind"], "qa-plan")
        self.inputs("development-result", ok=False)
        (output / "procedure-route.json").write_text("{}")
        with self.assertRaises(io.ObservationError):
            io.procedure_view(output)


if __name__ == "__main__":
    names = [name for name in Procedure.__dict__ if name.startswith("test_")]
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(
        unittest.TestSuite(Procedure(name) for name in names)).wasSuccessful())
