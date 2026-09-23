"""Bundle projection of real local C QA receipts without exporting raw logs."""
import json
import unittest
from outcome_integration import Outcome


class OutcomeBundle(Outcome):
    def test_qa_inventory_revision_history_and_completion_boundary(self):
        self.enroll()
        first = self.research("adjudicate", self.decision("SKIPPED"), "skipped")
        self.research("adjudicate", self.decision(supersedes=first["record_digest"]), "passed")
        before = len(self.events())
        directory = self.work.parent / "review-bundle"
        policy = self.write("redact.json", dict(schema_version=1, profile="LINKABLE", acknowledge_linkability=True))
        self.cli("research", "export", self.work, "--case", "case-1", "--output", directory, "--redact", policy)
        self.assertEqual(len(self.events()), before)
        self.cli("research", "bundle-verify", directory)
        outcomes = [json.loads(line) for line in (directory / "outcome-adjudications.jsonl").read_text().splitlines()]
        self.assertEqual([r.get("normalized_status") for r in outcomes], [None, "SKIPPED", "PASS"])
        inventory = json.loads((directory / "evidence-inventory.json").read_text())
        self.assertIn(self.qa["receipt_digest"], [r["source_sha256"] for r in inventory["items"]])
        self.assertFalse(json.loads((directory / "manifest.json").read_text())["acceptance_verified"])
        self.assertNotEqual(self.completion()["action"], "DONE")
        self.finalize()
        self.project()
        self.assertEqual(self.completion()["action"], "DONE")


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(OutcomeBundle(n) for n in OutcomeBundle.__dict__ if n.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
