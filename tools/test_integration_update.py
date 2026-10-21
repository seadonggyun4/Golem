"""D5 owner plans, stale/crash boundaries and clearance; native gates are separate."""
import copy
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import execution_record as records
import integration_contract as c
import integration_registry as r
import integration_lifecycle as life
import integration_recovery as recovery
import integration_update as update
import test_integration_mutations as fixture


class D5(unittest.TestCase):
    for name in ("repin", "api", "invoke", "capture", "preflight", "approve", "query", "expect", "inventory", "save_policy", "adapter"):
        locals()[name] = getattr(fixture.D4, name)

    def setUp(self):
        fixture.D4.setUp(self)
        self.manager = update.Manager(self.registry)
        self.mock_observe = patch.object(self.manager, "observe", side_effect=self.observed)
        self.mock_observe.start()
        self.addCleanup(self.mock_observe.stop)
        self.stopped = [{"principal_id": "owner", "client_id": "client-a", "state": "STOPPED_OWNER_ATTESTED"}]

    def observed(self, project):
        r.check_project(project)
        return {w["work_id"]: {"inventory": update.inventory(Path(w["path"])), "sequence": 1,
                "document_head": "0" * 64, "agent_head": "1" * 64} for w in project["works"]}

    def private(self, name, value):
        path = self.root / name
        path.write_bytes(c.encoded(value))
        path.chmod(0o600)
        return r.file_pin(path)

    def do(self, operation, request):
        if operation == "restore" and "effect_review" not in request:
            enrollment, _ = self.manager.enrollment("p")
            state, _ = life.current(self.registry, "p")
            request = {**request, "effect_review": self.private("restore-review.json", {
                "schema": "golem.integration-restore-review.v1", "project_id": "p", "freeze_id": state["freeze_id"],
                "enrollment_sha256": c.sha(c.encoded(enrollment)), "effects": "NONE_SINCE_SWITCH_OWNER_ATTESTED",
                "evidence": [self.private("restore-inspection.json", {"inspection": "synthetic fixture"})], "reason": "reviewed"})}
        plan = self.manager.plan(operation, {"project_id": "p", **request})
        return self.manager.apply(plan, c.sha(c.encoded(plan)), approve_maintenance=True)

    def freeze(self):
        return self.do("freeze", {"freeze_id": "maintenance-1"})

    def stage_request(self):
        return {"project_id": "p", "destination": str(self.root / "stage"), "artifacts": [
            {"name": role.lower(), "role": role, "source": r.file_pin(self.cli if role == "ENGINE" else self.sdk),
             "mode": "EXECUTE" if role == "ENGINE" else "READ"}
            for role in ("ENGINE", "SDK", "INTEGRATION", "MCP", "INSTRUCTIONS")]}

    def verified(self):
        self.freeze()
        request = self.stage_request()
        staged = self.do("stage", request)
        desired = copy.deepcopy(self.enrollment)
        desired["project"]["cli"] = r.file_pin(self.root / "stage/engine")
        desired["project"]["sdk_pins"] = [r.file_pin(self.root / "stage/sdk")]
        verified = self.do("verify", {"bundle": staged["bundle"], "enrollment": desired})
        return verified["verification"], desired

    def unknown(self):
        original = self.invoke(capture=lambda *a, **k: (_ for _ in ()).throw(OSError("synthetic lost reply")))
        self.assertEqual(original["state"], "COMMIT_UNKNOWN")
        return original

    def review(self, evidence_id):
        evidence = self.private("effects.json", {"inspection": "synthetic owner observation"})
        review = self.private("review.json", {"schema": "golem.integration-effect-review.v1",
            "disposition": "NO_EFFECTS_CONFIRMED", "processes": "STOPPED_OWNER_ATTESTED", "reason": "reviewed",
            "evidence": [evidence]})
        return {"project_id": "p", "work_id": "a", "evidence_id": evidence_id, "binding": self.query()["binding"],
                "owner_review": review, "stopped": self.stopped}

    def test_owner_intent_closed_requests_and_stale_plans(self):
        plan = self.manager.plan("freeze", {"project_id": "p", "freeze_id": "f"})
        self.expect("OWNER_MAINTENANCE_APPROVAL_REQUIRED", lambda: self.manager.apply(plan, c.sha(c.encoded(plan))))
        self.expect("SCHEMA", lambda: self.manager.plan("freeze", {"project_id": "p", "freeze_id": "f", "approve": True}))
        self.approve()
        self.expect("MAINTENANCE_PLAN_STALE", lambda: self.manager.apply(plan, c.sha(c.encoded(plan)), approve_maintenance=True))

    def test_freeze_fences_new_mutations_without_native_or_evidence_changes(self):
        before = self.inventory()
        self.freeze()
        self.expect("PROJECT_MAINTENANCE", lambda: self.invoke())
        self.assertEqual(before, self.inventory())
        self.assertEqual(life.current(self.registry, "p")[0]["phase"], "FROZEN")

    def test_live_participant_and_writer_are_not_pid_killed(self):
        with life.participation(self.registry, [self.query()["binding"]]):
            self.freeze()
            self.expect("PARTICIPANT_OR_WRITER_LIVE", lambda: self.manager.quiet(self.enrollment))
        self.manager.quiet(self.enrollment)

    def test_stage_pins_all_roles_and_preserves_source_and_original_work(self):
        self.freeze()
        before = self.inventory()
        result = self.do("stage", self.stage_request())
        self.assertEqual(result["state"], "STAGED")
        self.assertEqual(len(self.manager.bundle(result["bundle"])["artifacts"]), 5)
        self.assertEqual(before, self.inventory())
        self.assertEqual((self.root / "stage/engine").stat().st_mode & 0o777, 0o500)

    def test_staging_refuses_symlinks_unknown_roles_and_source_drift(self):
        self.freeze()
        request = self.stage_request()
        plan = self.manager.plan("stage", request)
        self.sdk.write_bytes(b"changed SDK")
        self.expect("PIN_MISMATCH", lambda: self.manager.apply(plan, c.sha(c.encoded(plan)), approve_maintenance=True))
        self.sdk.write_text("Synthetic SDK\n")
        link = self.root / "link"
        link.symlink_to(self.root / "not-created")
        self.expect("PATH", lambda: self.manager.plan("stage", {**request, "destination": str(link)}))
        self.expect("BUNDLE_INCOMPLETE", lambda: self.manager.plan("stage", {**request, "artifacts": request["artifacts"][:-1]}))
        duplicate = {**request["artifacts"][0], "name": "second-engine", "mode": "READ"}
        self.expect("BUNDLE_ENGINE", lambda: self.manager.plan("stage", {**request, "artifacts": request["artifacts"] + [duplicate]}))
        self.assertFalse((self.root / "stage").exists())

    def test_partial_stage_repairs_only_missing_exact_approved_artifacts(self):
        self.freeze()
        request = self.stage_request()
        plan = self.manager.plan("stage", request)
        pin = self.private("stage-plan.json", plan)
        original = records.save
        def fail(path, data, **kwargs):
            if Path(path).name == "integration":
                raise OSError("synthetic interrupted stage")
            return original(path, data, **kwargs)
        with patch.object(records, "save", fail), self.assertRaises(OSError):
            self.manager.apply(plan, c.sha(c.encoded(plan)), approve_maintenance=True)
        self.assertFalse((self.root / "stage/bundle.json").exists())
        result = self.do("stage-repair", {"original_plan": pin})
        self.assertEqual(result["state"], "STAGED")

    def test_partial_stage_drift_is_not_overwritten_or_deleted(self):
        self.freeze()
        request = self.stage_request()
        plan = self.manager.plan("stage", request)
        pin = self.private("stage-plan.json", plan)
        (self.root / "stage").mkdir(mode=0o700)
        (self.root / "stage/engine").write_bytes(b"partial conflicting bytes")
        self.expect("STAGE_DRIFT", lambda: self.manager.plan("stage-repair", {"project_id": "p", "original_plan": pin}))
        self.assertEqual((self.root / "stage/engine").read_bytes(), b"partial conflicting bytes")

    def test_switch_requires_all_clients_and_read_only_verification(self):
        verification, desired = self.verified()
        self.expect("ALL_CLIENT_ACKNOWLEDGEMENTS_REQUIRED", lambda: self.manager.plan("switch", {
            "project_id": "p", "verification": verification, "stopped": [{**self.stopped[0], "client_id": "forged"}]}))
        result = self.do("switch", {"verification": verification, "stopped": self.stopped})
        self.assertEqual(result["phase"], "RELOAD_REQUIRED")
        self.assertEqual(self.registry._load("p")[0]["enrollment"], desired)
        self.expect("GRANT_STALE", lambda: self.invoke())

    def test_switch_plan_rejects_work_changes_after_review(self):
        verification, _ = self.verified()
        plan = self.manager.plan("switch", {"project_id": "p", "verification": verification, "stopped": self.stopped})
        (self.work / "external-change").write_bytes(b"synthetic direct native or external change")
        self.expect("VERIFICATION_STALE", lambda: self.manager.apply(plan, c.sha(c.encoded(plan)), approve_maintenance=True))

    def test_post_switch_change_blocks_restore_and_keeps_evidence(self):
        verification, _ = self.verified()
        self.do("switch", {"verification": verification, "stopped": self.stopped})
        changed = self.work / "new-event-like-evidence"
        changed.write_bytes(b"not actual journal fixture; inventory boundary test")
        self.expect("POST_SWITCH_NATIVE_CHANGE", lambda: self.do("restore", {"stopped": self.stopped}))
        self.assertTrue(changed.exists())

    def test_restore_without_events_uses_new_generation_not_old_pointer(self):
        verification, _ = self.verified()
        self.do("switch", {"verification": verification, "stopped": self.stopped})
        restored = self.do("restore", {"stopped": self.stopped})
        record, _ = self.registry._load("p")
        self.assertEqual(record["generation"], 3)
        self.assertEqual(record["enrollment"], self.enrollment)
        self.assertEqual(restored["phase"], "RELOAD_REQUIRED")

    def test_switch_crash_after_d1_commit_repairs_forward_without_reapplying(self):
        verification, desired = self.verified()
        original = self.registry.apply
        def crash(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError("synthetic crash after D1 pointer commit")
        with patch.object(self.registry, "apply", crash), self.assertRaises(OSError):
            self.do("switch", {"verification": verification, "stopped": self.stopped})
        self.assertEqual(life.current(self.registry, "p")[0]["phase"], "SWITCH_INTENT")
        with patch.object(self.registry, "apply", side_effect=AssertionError("no D1 rewrite")):
            result = self.do("repair-switch", {"stopped": self.stopped})
        self.assertEqual(result["phase"], "RELOAD_REQUIRED")
        self.assertEqual(self.registry._load("p")[0]["enrollment"], desired)

    def test_switch_crash_before_d1_commit_returns_frozen_not_automatic_retry(self):
        verification, _ = self.verified()
        with patch.object(self.registry, "apply", side_effect=OSError("not committed")), self.assertRaises(OSError):
            self.do("switch", {"verification": verification, "stopped": self.stopped})
        result = self.do("repair-switch", {"stopped": self.stopped})
        self.assertEqual(result["phase"], "FROZEN")
        self.assertEqual(self.registry._load("p")[0]["generation"], 1)

    def test_unknown_clearance_preserves_original_result_and_retires_action(self):
        original = self.unknown()
        output = self.registry.root / original["local_evidence_id"]
        before = (output / "result.json").read_bytes()
        self.freeze()
        request = self.review(output.name)
        plan = recovery.plan(self.manager, request)
        self.expect("OWNER_RECOVERY_APPROVAL_REQUIRED", lambda: recovery.apply(self.manager, plan, c.sha(c.encoded(plan))))
        result = recovery.apply(self.manager, plan, c.sha(c.encoded(plan)), approve_recovery=True)
        self.assertEqual(result["state"], "QUARANTINE_CLEARED_ORIGINAL_RESULT_UNCHANGED")
        self.assertEqual((output / "result.json").read_bytes(), before)
        self.do("thaw", {"stopped": self.stopped})
        self.assertEqual(self.invoke(), original)
        self.expect("RESOLVED_ACTION_REUSE_FORBIDDEN", lambda: self.api().call("session_claim", {**self.args, "request_id": "replacement"}))
        self.action_path = self.root / "fresh-action.json"
        self.entry["action_id"] = "fresh"
        self.native["key"] = "fresh-native-key"
        self.action["native_json"] = c.encoded(self.native).decode()
        self.repin()
        self.args.update(action_id="fresh", request_id="new-request")
        self.assertEqual(self.invoke()["state"], "NATIVE_RESULT_RECORDED")

    def test_recovery_rejects_stale_review_original_input_and_cross_work(self):
        original = self.unknown()
        self.freeze()
        request = self.review(original["local_evidence_id"])
        plan = recovery.plan(self.manager, request)
        review_path = Path(request["owner_review"]["path"])
        review_path.write_bytes(review_path.read_bytes() + b" ")
        self.expect("PIN_MISMATCH", lambda: recovery.apply(self.manager, plan, c.sha(c.encoded(plan)), approve_recovery=True))
        self.expect("GRANT_SCOPE", lambda: recovery.plan(self.manager, {**request, "work_id": "foreign"}))

    def test_partial_clearance_publication_can_finish_without_overwrite(self):
        original = self.unknown()
        self.freeze()
        request = self.review(original["local_evidence_id"])
        plan = recovery.plan(self.manager, request)
        save = records.save
        def crash(path, data, **kwargs):
            if Path(path).name == "d5-resolution-ref.json":
                raise OSError("synthetic partial certificate publication")
            return save(path, data, **kwargs)
        with patch.object(records, "save", crash), self.assertRaises(OSError):
            recovery.apply(self.manager, plan, c.sha(c.encoded(plan)), approve_recovery=True)
        certificate = self.registry.root / original["local_evidence_id"] / "d5-resolution.json"
        before = certificate.read_bytes()
        recovery.apply(self.manager, plan, c.sha(c.encoded(plan)), approve_recovery=True)
        self.assertEqual(certificate.read_bytes(), before)

    def test_clearance_ref_corruption_never_releases_quarantine(self):
        original = self.unknown()
        self.freeze()
        request = self.review(original["local_evidence_id"])
        plan = recovery.plan(self.manager, request)
        recovery.apply(self.manager, plan, c.sha(c.encoded(plan)), approve_recovery=True)
        ref = self.registry.root / original["local_evidence_id"] / "d5-resolution-ref.json"
        ref.write_bytes(c.encoded({"sha256": "0" * 64}))
        self.expect("RESOLUTION_CORRUPT", lambda: self.do("thaw", {"stopped": self.stopped}))

    def test_live_writer_blocks_quiescence_without_deleting_intent(self):
        original = self.unknown()
        path = self.registry.root / original["local_evidence_id"] / "writer.lock"
        fd = life.lock(path)
        try:
            self.freeze()
            self.expect("PARTICIPANT_OR_WRITER_LIVE", lambda: self.manager.quiet(self.enrollment))
            self.assertTrue(path.exists())
        finally:
            os.close(fd)
        self.manager.quiet(self.enrollment)

    def test_cleared_quarantine_rechecks_retained_original_evidence(self):
        original = self.unknown()
        self.freeze()
        plan = recovery.plan(self.manager, self.review(original["local_evidence_id"]))
        recovery.apply(self.manager, plan, c.sha(c.encoded(plan)), approve_recovery=True)
        path = self.registry.root / original["local_evidence_id"] / "request.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.expect("RESOLUTION_CORRUPT", lambda: self.do("thaw", {"stopped": self.stopped}))

    def test_lifecycle_history_corruption_is_not_treated_as_open(self):
        self.freeze()
        first, digest = life.current(self.registry, "p")
        with self.registry.locked(exclusive=True):
            life.publish(self.registry, "p", "OPEN", first["freeze_id"], first["body"])
        (self.registry.root / ("d5-state-" + digest + ".json")).write_bytes(b"corrupt")
        self.expect("LIFECYCLE_CORRUPT", lambda: life.fence(self.registry, "p"))

    def test_reload_ack_alone_or_fabricated_report_cannot_open_project(self):
        verification, _ = self.verified()
        self.do("switch", {"verification": verification, "stopped": self.stopped})
        ack = {"principal_id": "owner", "client_id": "client-a", "state": "RELOADED_OWNER_ATTESTED"}
        self.expect("SCHEMA", lambda: self.manager.plan("ready", {"project_id": "p", "reloads": [ack]}))
        pin = self.private("fake-probe.json", {"state": "READ_OBSERVED"})
        with self.assertRaises((c.IntegrationError, OSError)):
            self.manager.plan("ready", {"project_id": "p", "reloads": [{**ack, "probe": pin}]})
        self.assertEqual(life.current(self.registry, "p")[0]["phase"], "RELOAD_REQUIRED")

    def test_restore_needs_explicit_bound_external_effect_review(self):
        verification, _ = self.verified()
        self.do("switch", {"verification": verification, "stopped": self.stopped})
        self.expect("SCHEMA", lambda: self.manager.plan("restore", {"project_id": "p", "stopped": self.stopped}))
        review = self.private("wrong-restore.json", {
            "schema": "golem.integration-restore-review.v1", "project_id": "p", "freeze_id": "foreign",
            "enrollment_sha256": "0" * 64, "effects": "NONE_SINCE_SWITCH_OWNER_ATTESTED",
            "evidence": [self.private("inspection.json", {"fixture": True})], "reason": "reviewed"})
        self.expect("RESTORE_REVIEW_STALE", lambda: self.manager.plan("restore", {
            "project_id": "p", "stopped": self.stopped, "effect_review": review}))


if __name__ == "__main__":
    unittest.main()
