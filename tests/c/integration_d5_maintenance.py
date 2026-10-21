"""Actual native D5 update/recovery and optional modern/legacy SDK reload probes."""
import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import integration_d4_mutations as d4
from discovery_integration import CLI, SOURCE

import execution_record as records
import integration_contract as c
import integration_registry as r
import integration_lifecycle as life
import integration_recovery as recovery
import integration_reload_probe as reload_probe
import integration_update as update
import integration_transfer as transfer
import integration_mutation_contract as mutations_contract
import integration_mutations as mutations


class Maintenance:
    def manager_setup(self):
        self.manager = update.Manager(self.registry)
        self.stopped = [{"principal_id": g["principal_id"], "client_id": g["client_id"], "state": "STOPPED_OWNER_ATTESTED"}
                        for g in self.enrollment["grants"]]

    def do(self, operation, request):
        if operation == "restore" and "effect_review" not in request:
            enrollment, _ = self.manager.enrollment("project")
            state, _ = life.current(self.registry, "project")
            evidence = self.private("restore-inspection.json", c.encoded({"inspection": "synthetic fixture effects inspected"}))
            review = self.private("restore-review.json", c.encoded({"schema": "golem.integration-restore-review.v1",
                "project_id": "project", "freeze_id": state["freeze_id"], "enrollment_sha256": c.sha(c.encoded(enrollment)),
                "effects": "NONE_SINCE_SWITCH_OWNER_ATTESTED", "evidence": [r.file_pin(evidence)], "reason": "fixture-reviewed"}))
            request = {**request, "effect_review": r.file_pin(review)}
        plan = self.manager.plan(operation, {"project_id": "project", **request})
        return self.manager.apply(plan, c.sha(c.encoded(plan)), approve_maintenance=True)

    def freeze(self):
        return self.do("freeze", {"freeze_id": "native-maintenance"})

    def verified(self):
        self.freeze()
        artifacts = [{"name": name, "role": role, "source": r.file_pin(path), "mode": mode} for name, role, path, mode in (
            ("engine", "ENGINE", CLI, "EXECUTE"),
            ("sdk", "SDK", SOURCE / "samples/agent-session/status.json", "READ"),
            ("integration", "INTEGRATION", SOURCE / "tools/integration_lifecycle.py", "READ"),
            ("mcp", "MCP", SOURCE / "tools/requirements-mcp.txt", "READ"),
            ("instructions", "INSTRUCTIONS", SOURCE / "samples/agent-session/AGENTS.minimal.md", "READ"))]
        stage = self.do("stage", {"destination": str(self.root / "staged"), "artifacts": artifacts})
        desired = copy.deepcopy(self.enrollment)
        desired["project"]["cli"] = r.file_pin(self.root / "staged/engine")
        desired["project"]["sdk_pins"] = [r.file_pin(self.root / "staged/sdk")]
        verified = self.do("verify", {"bundle": stage["bundle"], "enrollment": desired})
        return verified["verification"], desired

    def review(self, evidence_id):
        evidence = self.private("external-inspection.json", c.encoded({"review": "synthetic owner inspected fixture effects"}))
        review = self.private("effect-review.json", c.encoded({"schema": "golem.integration-effect-review.v1",
            "disposition": "EFFECTS_RECONCILED", "processes": "STOPPED_OWNER_ATTESTED", "reason": "fixture-reviewed",
            "evidence": [r.file_pin(evidence)]}))
        return {"project_id": "project", "work_id": "example-work", "evidence_id": evidence_id,
            "binding": self.transfer_binding(), "owner_review": r.file_pin(review), "stopped": self.stopped}

    def transfer_binding(self):
        record, _ = self.registry._load("project")
        return {"schema": "golem.integration-client-binding.v1", "project_id": "project", "generation": record["generation"],
            "principal_id": "owner", "client_id": "client-a", "assurance": "LOCAL_COOPERATIVE"}

    def clearance(self, evidence_id):
        request = self.review(evidence_id)
        plan = recovery.plan(self.manager, request)
        return recovery.apply(self.manager, plan, c.sha(c.encoded(plan)), approve_recovery=True)


class D5(Maintenance, d4.D4):
    def setUp(self):
        super().setUp()
        self.manager_setup()

    def test_staged_switch_and_restore_preserve_every_native_file(self):
        before = self.inventory()
        verification, desired = self.verified()
        self.assertEqual(before, self.inventory())
        switched = self.do("switch", {"verification": verification, "stopped": self.stopped})
        self.assertEqual(switched["phase"], "RELOAD_REQUIRED")
        self.assertEqual(before, self.inventory())
        restored = self.do("restore", {"stopped": self.stopped})
        self.assertEqual(restored["phase"], "RELOAD_REQUIRED")
        self.assertEqual(self.registry._load("project")[0]["generation"], 3)
        self.assertEqual(before, self.inventory())

    def test_live_owner_and_direct_new_event_block_update_or_restore(self):
        self.claim()
        self.freeze()
        with self.assertRaises(c.IntegrationError) as error:
            self.manager.observe(self.enrollment["project"])
        self.assertEqual(error.exception.code, "NATIVE_OWNER_OR_RECOVERY_REQUIRED")

    def test_live_participant_requires_stop_and_old_client_cannot_write(self):
        with life.participation(self.registry, [self.transfer_binding()]):
            self.freeze()
            with self.assertRaises(c.IntegrationError) as error:
                self.manager.quiet(self.enrollment)
            self.assertEqual(error.exception.code, "PARTICIPANT_OR_WRITER_LIVE")
        self.manager.quiet(self.enrollment)
        before = self.inventory()
        with self.assertRaises(c.IntegrationError) as error:
            self.claim()
        self.assertEqual(error.exception.code, "PROJECT_MAINTENANCE")
        self.assertEqual(before, self.inventory())

    def test_committed_lost_claim_needs_native_reconciliation_before_clearance(self):
        original_capture = records.capture
        def lost(*args, **kwargs):
            result = original_capture(*args, **kwargs)
            if (args[1] / "dispatch-intent.json").exists():
                raise OSError("synthetic lost claim reply after native commit")
            return result
        with patch.object(records, "capture", lost):
            result = self.claim()
        self.assertEqual(result["state"], "COMMIT_UNKNOWN")
        path = self.registry.root / result["local_evidence_id"]
        original = (path / "result.json").read_bytes()
        self.freeze()
        with self.assertRaises(c.IntegrationError) as error:
            recovery.plan(self.manager, self.review(path.name))
        self.assertEqual(error.exception.code, "NATIVE_OWNER_OR_RECOVERY_REQUIRED")
        # Explicit fixture owner uses original native API, never the D5 manager.
        self.cli("session", "call", self.work, self.write("owner-resume.json", {
            "schema_version": 1, "operation": "resume", "work_id": "example-work", "key": "owner-unused-claim-release",
            "expected_sequence": 2, "session_id": "mapped-owner", "ttl_ms": 3600000}))
        before = self.inventory()
        cleared = self.clearance(path.name)
        self.assertFalse(cleared["native_result_promoted"])
        self.assertEqual(before, self.inventory())
        self.assertEqual((path / "result.json").read_bytes(), original)
        self.do("thaw", {"stopped": self.stopped})
        self.assertEqual(self.invoke("session_claim"), result)
        with self.assertRaises(c.IntegrationError) as error:
            self.api.call("session_claim", {**self.args, "request_id": "unsafe-replacement"})
        self.assertEqual(error.exception.code, "RESOLVED_ACTION_REUSE_FORBIDDEN")
        request = c.decode((path / "request.json").read_bytes())
        request.update(key="owner-reviewed-fresh-claim", expected_sequence=3)
        self.stage("session_claim", request)
        self.assertEqual(self.invoke("session_claim")["state"], "NATIVE_RESULT_RECORDED")

    def test_post_switch_native_event_prevents_automatic_downgrade(self):
        verification, _ = self.verified()
        self.do("switch", {"verification": verification, "stopped": self.stopped})
        self.cli("session", "call", self.work, self.write("outside-direct-native.json", {
            "schema_version": 1, "operation": "resume", "work_id": "example-work", "key": "explicit-native-change",
            "expected_sequence": 1, "session_id": "owner-direct", "ttl_ms": 3600000}))
        before = self.inventory()
        with self.assertRaises(c.IntegrationError) as error:
            self.do("restore", {"stopped": self.stopped})
        self.assertEqual(error.exception.code, "POST_SWITCH_NATIVE_CHANGE")
        self.assertEqual(before, self.inventory())

    def test_actual_two_client_modern_legacy_reload_is_read_only(self):
        if not d4.WITH_MCP:
            self.skipTest("separate actual SDK gate")
        second = copy.deepcopy(self.enrollment["grants"][0])
        second["client_id"] = "client-b"
        self.enrollment["grants"].append(second)
        plan = self.registry.plan(self.enrollment)
        self.registry.apply(self.enrollment, plan["plan_sha256"], approve_local_owner=True)
        self.manager_setup()
        before = self.inventory()
        verification, _ = self.verified()
        self.do("switch", {"verification": verification, "stopped": self.stopped})
        acknowledgements = []
        for client, mode in (("client-a", "auto"), ("client-b", "legacy")):
            path, digest = self.make_policy(client=client, generation=3)
            probe = reload_probe.probe({"path": str(path), "sha256": digest}, "project", mode,
                self.root / (client + "-reload"), approve_reload_probe=True)
            self.assertEqual(c.decode(Path(probe["path"]).read_bytes())["protocol"],
                "2026-07-28" if mode == "auto" else "2025-11-25")
            acknowledgements.append({"principal_id": "owner", "client_id": client,
                "state": "RELOADED_OWNER_ATTESTED", "probe": probe})
        ready = self.do("ready", {"reloads": acknowledgements})
        self.assertEqual(ready["phase"], "OPEN")
        self.assertEqual(ready["body"]["reload_assurance"], "SDK_READ_OBSERVED_OWNER_RELOAD_REPORTED")
        self.assertEqual(before, self.inventory())


class QA(Maintenance, d4.QA):
    def setUp(self):
        super().setUp()
        self.manager_setup()

    def test_qa_lost_reply_clearance_does_not_rerun_or_promote_original_result(self):
        self.approve_qa()
        original_capture = records.capture
        def lost(*args, **kwargs):
            result = original_capture(*args, **kwargs)
            if (args[1] / "dispatch-intent.json").exists():
                raise OSError("synthetic lost QA reply after execution")
            return result
        with patch.object(records, "capture", lost):
            result = self.invoke("execution_request")
        self.assertEqual(result["state"], "COMMIT_UNKNOWN")
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        self.freeze()
        path = self.registry.root / result["local_evidence_id"]
        before = {str(p.relative_to(self.work)): c.sha(p.read_bytes()) for p in self.work.rglob("*") if p.is_file()}
        cleared = self.clearance(path.name)
        self.assertFalse(cleared["native_result_promoted"])
        after = {str(p.relative_to(self.work)): c.sha(p.read_bytes()) for p in self.work.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.do("thaw", {"stopped": self.stopped})
        self.assertEqual(self.invoke("execution_request"), result)
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        with self.assertRaises(c.IntegrationError) as error:
            self.api.call("execution_request", {**self.args, "request_id": "do-not-rerun"})
        self.assertEqual(error.exception.code, "RESOLVED_ACTION_REUSE_FORBIDDEN")

    def test_pending_approval_is_not_silently_cancelled_or_cleared(self):
        self.approve_qa(record_decision=False)
        with self.registry.locked(exclusive=True):
            _, _, _, _, _, output, _ = self.api._admit("execution_request", self.args)
        self.freeze()
        with self.assertRaises(c.IntegrationError) as error:
            recovery.plan(self.manager, self.review(output.name))
        self.assertEqual(error.exception.code, "APPROVAL_STILL_DISPATCHABLE")


if __name__ == "__main__":
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(cls.__name__ + "." + name, sys.modules[__name__])
        for cls in (D5, QA) for name in cls.__dict__ if name.startswith("test_"))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
