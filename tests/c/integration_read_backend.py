"""Real native read adapter on disposable stores, with complete no-write checks."""
import copy
import os
from pathlib import Path
import sys
import unittest

import workflow_integration as fixture

sys.path.insert(0, str(fixture.SOURCE / "tools"))
import integration_backend as backend
import integration_contract as c
import integration_registry as registry


class ReadBackend(fixture.Workflow):
    # Do not inherit the workflow tests a second time.
    def setUp(self):
        super().setUp()
        self.setup_work()
        self.register_selection()
        self.cli("session", "call", self.work, self.write("start.json", {
            "schema_version": 1, "operation": "start", "work_id": "example-work",
            "selection_id": "selection", "key": "start", "expected_sequence": 0}))
        self.project = self.root / "project"
        target = self.project / ".golem/works/work"
        target.parent.mkdir(parents=True)
        self.work.rename(target)
        self.work = target
        self.registry = registry.Registry.create(self.root / "registry", approve_local_owner=True)
        self.enrollment = {"schema": "golem.integration-enrollment.v1",
            "project": registry.describe("project", self.project, fixture.CLI,
                [fixture.SOURCE / "samples/agent-session/status.json"], [("example-work", self.work)]),
            "grants": [{"schema": "golem.integration-grant.v1", "principal_id": "owner", "client_id": "client-a",
                "operations": ["status", "next", "record", "history"], "work_ids": ["example-work"],
                "destination": "LOCAL_HOST", "assurance": "LOCAL_COOPERATIVE"}]}
        plan = self.registry.plan(self.enrollment)
        self.registry.apply(self.enrollment, plan["plan_sha256"], approve_local_owner=True)

    def query(self, operation):
        return {"schema": "golem.integration-read.v1", "binding": {
            "schema": "golem.integration-client-binding.v1", "project_id": "project", "generation": 1,
            "principal_id": "owner", "client_id": "client-a", "assurance": "LOCAL_COOPERATIVE"},
            "work_id": "example-work", "operation": operation, "limit": 1, "cursor": None}

    def inventory(self):
        return {str(p.relative_to(self.work)): (p.stat().st_mode, c.sha(p.read_bytes()) if p.is_file() else None)
                for p in self.work.rglob("*")}

    def test_real_native_status_next_record_history_preserve_all_bytes_and_modes(self):
        before = self.inventory()
        for operation in ("status", "next", "record", "history"):
            observed = backend.read(self.registry, self.query(operation))
            self.assertEqual(observed["state"], "OBSERVED")
            self.assertFalse(observed["native_state_changed"])
            self.assertFalse(observed["execution_authorized"])
            self.assertEqual(before, self.inventory())
        query = self.query("history")
        pages = 0
        while True:
            result = backend.read(self.registry, query)["result"]
            pages += 1
            self.assertLess(pages, 32)
            if not result["has_more"]:
                break
            query["cursor"] = result["cursor"]
        self.assertEqual(before, self.inventory())

    def test_claimed_work_and_changed_sequence_remain_native_owned(self):
        before = backend.read(self.registry, self.query("status"))["result"]
        native = self.cli("session", "call", self.work, self.write("claim.json", {
            "schema_version": 1, "operation": "claim", "work_id": "example-work", "key": "claim",
            "expected_sequence": before["sequence"], "session_id": "other-owner",
            "expected_generation": self.generation, "source_snapshot": self.source,
            "byte_budget": 1048576, "ttl_ms": 3600000}))
        inventory = self.inventory()
        observed = backend.read(self.registry, self.query("status"))["result"]
        self.assertGreater(observed["sequence"], before["sequence"])
        self.assertEqual(observed["state"]["active"]["session_id"], "other-owner")
        self.assertTrue(observed["resume_preflight"]["lease_live"])
        self.assertEqual(inventory, self.inventory())
        query = self.query("status")
        query["operation"] = "resume"
        with self.assertRaises(c.IntegrationError):
            backend.read(self.registry, query)
        self.assertEqual(inventory, self.inventory())

    def test_native_corrupt_store_error_is_retained_not_repaired(self):
        candidates = list((self.work / "objects").rglob("*"))
        victim = next(p for p in candidates if p.is_file())
        victim.chmod(0o600)
        victim.write_bytes(b"corrupt synthetic object")
        before = self.inventory()
        with self.assertRaises(c.IntegrationError) as error:
            backend.read(self.registry, self.query("status"))
        self.assertEqual(error.exception.code, "NATIVE_FAILURE")
        spool = next(self.registry.root.glob("read-*"))
        self.assertTrue((spool / "record/stderr.log").is_file())
        self.assertTrue((spool / "failure.json").is_file())
        self.assertEqual(before, self.inventory())


if __name__ == "__main__":
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(
        "ReadBackend." + name, sys.modules[__name__]) for name in (
            "test_real_native_status_next_record_history_preserve_all_bytes_and_modes",
            "test_claimed_work_and_changed_sequence_remain_native_owned",
            "test_native_corrupt_store_error_is_retained_not_repaired"))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
