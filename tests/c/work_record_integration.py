"""Consolidation is lossless for metadata and never changes Work authority."""
import copy
import hashlib
import json
import subprocess
import sys
import unittest
import workflow_integration as fixture


class Record(unittest.TestCase):
    for name in ("setUp", "tearDown", "write", "cli", "validate", "answered", "confirmed",
                 "metadata", "publish", "setup_work", "register_selection", "body", "inputs", "managed"):
        locals()[name] = getattr(fixture.Workflow, name)

    def prepare(self):
        self.setup_work()
        self.request = dict(schema_version=1, work_id="example-work", byte_budget=32 * 1024 * 1024,
                            document_head="", agent_head="")

    def record(self, ok=True):
        return self.cli("work", "record", self.work, self.write("record.json", self.request), ok=ok)

    def inventory(self):
        return {str(p.relative_to(self.work)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.work.rglob("*") if p.is_file()}

    def test_interning_reconstructs_legacy_metadata_without_writing(self):
        self.prepare()
        second = self.metadata("scope", version=2)
        second["assessment"] = self.a
        self.publish(second)
        before = self.inventory()
        result = self.record()
        self.assertEqual(result, self.record())
        self.assertEqual(before, self.inventory())
        self.assertEqual(len(result["assessments"]), 1)
        self.assertEqual(len(result["documents"]), 2)
        self.assertEqual([d["freshness"] for d in result["documents"]], ["SUPERSEDED", "CURRENT"])
        for doc in result["documents"]:
            reconstructed = {**doc["metadata"], "assessment": result["assessments"][doc["assessment_ref"]]}
            original = self.cli("document", "inspect", self.work, doc["document_id"], doc["revision"])
            self.assertEqual(reconstructed, original["metadata"])
            self.assertEqual(doc["digest"], original["manifest_digest"])
            self.assertEqual(doc["event_digest"], original["event_digest"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["acceptance_verified"])

    def test_status_and_history_match_existing_queries(self):
        self.prepare()
        self.register_selection()
        self.cli("session", "call", self.work, self.write("start.json", dict(
            schema_version=1, operation="start", work_id="example-work", key="start",
            expected_sequence=0, selection_id="selection")))
        result = self.record()
        status = self.cli("session", "call", self.work, self.write("status.json", dict(
            schema_version=1, operation="status", work_id="example-work")))
        self.assertEqual(result["status"], status)
        events, after = [], 0
        while True:
            history = self.cli("work", "history", self.work, self.write("history.json", dict(
                schema_version=1, work_id="example-work", after=after, limit=1,
                document_head=result["document_head"], agent_head=result["agent_head"])))
            events.extend(history["events"])
            if not history["has_more"]:
                break
            self.assertGreater(history["next_after"], after)
            after = history["next_after"]
        self.assertEqual(result["journal"], events)

    def test_changed_document_or_agent_head_rejects_stale_request(self):
        self.prepare()
        self.register_selection()
        result = self.record()
        self.request.update(document_head=result["document_head"], agent_head=result["agent_head"])
        self.assertEqual(result, self.record())
        self.cli("session", "call", self.work, self.write("start.json", dict(
            schema_version=1, operation="start", work_id="example-work", key="start",
            expected_sequence=0, selection_id="selection")))
        self.assertEqual(self.record(ok=False).stdout, b"")
        self.request.update(document_head="", agent_head="")
        result = self.record()
        self.request.update(document_head=result["document_head"], agent_head=result["agent_head"])
        self.managed("planning")
        self.assertEqual(self.record(ok=False).stdout, b"")

    def test_changed_assessment_is_not_semantically_merged(self):
        self.prepare()
        modified = copy.deepcopy(self.a)
        modified["references"][0]["limitations"] = "A distinct uncertainty, preserved verbatim."
        m = self.metadata("scope", version=2)
        m["assessment"] = modified
        self.publish(m)
        result = self.record()
        self.assertEqual(len(result["assessments"]), 2)
        self.assertNotEqual(*[d["assessment_ref"] for d in result["documents"]])

    def test_budget_unknown_contract_and_wrong_work_fail_without_output(self):
        self.prepare()
        for change in ({"byte_budget": 1}, {"byte_budget": True}, {"schema_version": 2},
                       {"extra": "ignored?"}, {"work_id": "other"}, {"agent_head": "a" * 64}):
            original = self.request.copy()
            self.request.update(change)
            self.assertEqual(self.record(ok=False).stdout, b"")
            self.request = original

    def test_corrupt_original_blocks_record(self):
        self.prepare()
        digest = self.docs["scope"]["body_digest"]
        path, = self.work.rglob(digest[2:])
        path.chmod(0o600)
        path.write_bytes(b"corrupt original")
        self.assertEqual(self.record(ok=False).stdout, b"")

    def test_public_api_failure_preserves_output_and_clock_failure_has_no_events(self):
        self.prepare()
        before = self.inventory()
        helper = fixture.CLI.parent / "tests/c/golem_work_record_helper"
        result = subprocess.run([str(helper), str(self.work)], capture_output=True, env=fixture.ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.inventory())


if __name__ == "__main__":
    unittest.main(argv=[__file__, *sys.argv[1:]])
