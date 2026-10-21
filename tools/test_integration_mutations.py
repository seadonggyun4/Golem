"""D4 admission/uncertainty regressions; no native or external effects."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

import integration_contract as c
import integration_mutation_contract as contract
import integration_mutations as mutations
import test_integration_d2 as fixture


class D4(unittest.TestCase):
    for name in ("approve", "query", "expect", "inventory", "save_policy", "adapter"):
        locals()[name] = getattr(fixture.D2, name)

    def setUp(self):
        fixture.D2.setUp(self)
        self.action_path = self.root / "action.json"
        self.entry = {"action_id": "claim", "project_id": "p", "work_id": "a", "tool": "session_claim",
                      "session_id": "owner-session", "native_binding_id": "", "action": {}}
        self.native = {"schema_version": 1, "operation": "claim", "work_id": "a", "key": "native-key",
            "expected_sequence": 1, "session_id": "owner-session", "expected_generation": 2,
            "source_snapshot": "0" * 64, "byte_budget": 1048576, "ttl_ms": 60000}
        self.action = {"schema": "golem.integration-native-action.v1", "native_json": c.encoded(self.native).decode(),
            "body": "", "context_json": "", "count_json": "", "approval": None}
        self.mutation_path = self.root / "mutations.json"
        self.args = {"project_id": "p", "work_id": "a", "action_id": "claim", "request_id": "request-1"}
        self.repin()

    def repin(self):
        self.action_path.write_bytes(c.encoded(self.action))
        self.action_path.chmod(0o600)
        self.entry["action"] = {"path": str(self.action_path), "sha256": c.sha(self.action_path.read_bytes())}
        self.mutation_policy = {"schema": "golem.integration-mutations.v1",
            "transfer_policy": {"path": str(self.policy_path), "sha256": self.digest},
            "actions": [self.entry], "producer": contract.producer()}
        self.mutation_path.write_bytes(c.encoded(self.mutation_policy))
        self.mutation_path.chmod(0o600)
        self.mutation_digest = c.sha(self.mutation_path.read_bytes())

    def api(self):
        return mutations.Service(contract.Policy(self.mutation_path, self.mutation_digest, approve_mutations=True))

    def preflight(self, *args):
        return {"status": {"sequence": 1}, "next": {"sequence": 1}}

    def capture(self, argv, output, *args, **kwargs):
        self.assertTrue((output / "dispatch-intent.json").is_file())
        self.assertEqual((output / "request.json").read_bytes(), self.action["native_json"].encode())
        self.assertEqual(kwargs["env"], mutations.backend.ENVIRONMENT)
        (output / "stdout.log").write_bytes(c.encoded({"sequence": 2, "committed": True}))
        (output / "stdout.log").chmod(0o600)
        return {"returncode": 0, "reason": "EXIT", "recording": "RECORDED"}

    def invoke(self, api=None, capture=None):
        api = api or self.api()
        with patch.object(api, "_preflight", self.preflight), patch.object(mutations.records, "capture", capture or self.capture):
            return api.call("session_claim", self.args)

    def test_requires_owner_intent_and_exact_closed_policy(self):
        self.expect("OWNER_MUTATION_APPROVAL_REQUIRED", lambda: contract.Policy(self.mutation_path, self.mutation_digest))
        for key in self.mutation_policy:
            bad = copy.deepcopy(self.mutation_policy)
            del bad[key]
            self.expect("SCHEMA", lambda: contract.validate(bad))
        self.expect("SCHEMA", lambda: contract.validate({**self.mutation_policy, "approve": True}))

    def test_tools_and_model_arguments_cannot_supply_authority(self):
        api = self.api()
        self.assertIn("session_claim", api.tools())
        self.assertNotIn("session_begin", api.tools())
        for key in ("native_json", "path", "argv", "principal_id", "session_id", "approve", "binding"):
            self.expect("SCHEMA", lambda: api.call("session_claim", {**self.args, key: "untrusted"}))
        self.expect("MUTATION_SCOPE", lambda: api.call("session_begin", self.args))
        self.expect("MUTATION_SCOPE", lambda: api.call("session_claim", {**self.args, "work_id": "foreign"}))
        self.assertEqual(list(self.registry.root.glob("mutation-*")), [])

    def test_exact_response_replay_never_dispatches_or_renews(self):
        before, api = self.inventory(), self.api()
        with patch.object(api, "_preflight", self.preflight), patch.object(mutations.records, "capture", side_effect=self.capture) as launch:
            result = api.call("session_claim", self.args)
            self.assertEqual(result["state"], "NATIVE_RESULT_RECORDED")
            self.assertEqual(api.call("session_claim", self.args), result)
            self.assertEqual(launch.call_count, 1)
        self.assertEqual(before, self.inventory())

    def test_same_request_different_bytes_conflicts(self):
        self.invoke()
        self.action["native_json"] += " "
        self.repin()
        self.expect("REQUEST_CONFLICT", lambda: self.invoke())

    def test_uncertain_result_blocks_other_request_ids_and_never_retries(self):
        api = self.api()
        result = self.invoke(api, lambda *a, **k: (_ for _ in ()).throw(OSError("lost response")))
        self.assertEqual(result["state"], "COMMIT_UNKNOWN")
        self.assertEqual(result["native_state_changed"], "UNKNOWN")
        self.assertEqual(self.invoke(api), result)
        self.expect("WORK_MUTATION_UNRESOLVED", lambda: api.call("session_claim", {**self.args, "request_id": "new-id"}))

    def test_missing_final_record_after_intent_is_unknown_not_empty_success(self):
        api = self.api()
        with self.registry.locked(exclusive=True):
            _, _, _, _, _, output, _ = api._admit("session_claim", self.args)
        self.assertFalse((output / "result.json").exists())
        with patch.object(mutations.records, "capture", side_effect=AssertionError("no launch")):
            self.assertEqual(api.call("session_claim", self.args)["state"], "COMMIT_UNKNOWN")

    def test_changed_action_or_native_owner_is_not_dispatched(self):
        api = self.api()
        self.action_path.write_bytes(self.action_path.read_bytes() + b" ")
        self.expect("ACTION_CHANGED", lambda: api.call("session_claim", self.args))
        self.native["session_id"] = "foreign-owner"
        self.action["native_json"] = c.encoded(self.native).decode()
        self.repin()
        self.expect("SCHEMA", lambda: self.api().call("session_claim", self.args))

    def test_revocation_or_policy_change_blocks_existing_service(self):
        api = self.api()
        self.approve("revoke")
        self.assertNotIn("session_claim", api.tools())
        self.expect("PROJECT_APPROVAL_REQUIRED", lambda: api.call("session_claim", self.args))

    def test_preflight_failures_are_not_dispatched(self):
        api = self.api()
        with patch.object(api, "_preflight", side_effect=c.IntegrationError("OBSERVATION_STALE")), \
             patch.object(mutations.records, "capture", side_effect=AssertionError("no launch")):
            result = api.call("session_claim", self.args)
        self.assertEqual(result["state"], "NOT_DISPATCHED")
        self.assertFalse(result["native_state_changed"])

    def test_success_without_audit_completion_is_uncertain(self):
        api = self.api()
        with patch.object(api, "_publish", side_effect=OSError("disk full")):
            result = self.invoke(api)
        self.assertEqual(result["state"], "COMMIT_UNKNOWN")
        self.assertEqual(self.invoke(api)["state"], "COMMIT_UNKNOWN")

    def test_unfinished_intent_excludes_other_service_instances(self):
        first, second = self.api(), self.api()
        with self.registry.locked(exclusive=True):
            first._admit("session_claim", self.args)
        self.expect("WORK_MUTATION_UNRESOLVED", lambda: second.call("session_claim", {**self.args, "request_id": "second"}))

    def test_tampered_historical_response_never_replays(self):
        result = self.invoke()
        output = self.registry.root / result["local_evidence_id"]
        (output / "result.json").write_bytes(c.encoded({"state": "PASS"}))
        self.assertEqual(self.invoke()["state"], "COMMIT_UNKNOWN")
        self.expect("WORK_MUTATION_UNRESOLVED", lambda: self.api().call("session_claim", {**self.args, "request_id": "new"}))

    def test_future_schema_duplicate_json_and_unreviewed_context_rejected(self):
        for text in ('{"operation":"claim","operation":"begin"}', '{"x":NaN}', '{"x":"\\ud800"}'):
            action = {**self.action, "native_json": text}
            with self.assertRaises(c.IntegrationError):
                contract.native_action(self.entry, action)
        self.expect("ACTION_CONTEXT_SCOPE", lambda: contract.native_action(self.entry,
            {**self.action, "context_json": "{}"}))

    def test_native_v2_binding_is_fixed_and_legacy_cannot_downgrade(self):
        entry = {**self.entry, "native_binding_id": "owner-bound-id"}
        self.expect("SCHEMA", lambda: contract.native_action(entry, self.action))
        request = {**self.native, "schema_version": 2, "binding_id": "owner-bound-id"}
        action = {**self.action, "native_json": c.encoded(request).decode()}
        self.assertEqual(contract.native_action(entry, action), request)
        request["binding_id"] = "forged"
        self.expect("SCHEMA", lambda: contract.native_action(entry, {**action, "native_json": c.encoded(request).decode()}))

    def test_missing_result_reference_cannot_release_work_quarantine(self):
        result = self.invoke()
        output = self.registry.root / result["local_evidence_id"]
        (output / "result-ref.json").unlink()
        self.assertEqual(self.invoke()["state"], "COMMIT_UNKNOWN")
        self.expect("WORK_MUTATION_UNRESOLVED", lambda: self.api().call("session_claim", {**self.args, "request_id": "new"}))

    def test_busy_service_and_registry_never_wait_or_dispatch(self):
        api = self.api()
        api._lock.acquire()
        try:
            self.expect("SERVICE_BUSY", lambda: api.call("session_claim", self.args))
        finally:
            api._lock.release()

    def test_unrelated_owner_reviewed_action_does_not_redispatch_historical_request(self):
        result = self.invoke()
        self.mutation_policy["actions"].append({**self.entry, "action_id": "unrelated"})
        self.mutation_path.write_bytes(c.encoded(self.mutation_policy))
        self.mutation_digest = c.sha(self.mutation_path.read_bytes())
        with patch.object(mutations.records, "capture", side_effect=AssertionError("no redispatch")):
            self.assertEqual(self.api().call("session_claim", self.args), result)

    def test_short_dispatch_serializes_registry_revocation_until_native_returns(self):
        def capture(*args, **kwargs):
            self.expect("REGISTRY_BUSY", lambda: self.approve("revoke"))
            return self.capture(*args, **kwargs)
        self.assertEqual(self.invoke(capture=capture)["state"], "NATIVE_RESULT_RECORDED")

    def test_resume_requires_complete_renderer_and_positive_token_budget(self):
        entry = {**self.entry, "tool": "session_resume"}
        request = {k: v for k, v in self.native.items() if k not in ("expected_generation", "source_snapshot", "byte_budget")}
        request["operation"] = "resume"
        context = {"renderer_version": 2, "recipe": "current-v1", "excerpt_bytes": 0, "token_budget": 100}
        action = {**self.action, "native_json": c.encoded(request).decode(), "context_json": c.encoded(context).decode(),
                  "count_json": "{}"}
        self.assertEqual(contract.native_action(entry, action), request)
        for change in ({"recipe": "extractive-v1"}, {"renderer_version": 1}, {"renderer_version": 2.0},
                       {"token_budget": True}, {"excerpt_bytes": 1}, {"excerpt_bytes": False}):
            bad = {**action, "context_json": c.encoded({**context, **change}).decode()}
            self.expect("RESUME_COUNT_REQUIRED", lambda: contract.native_action(entry, bad))


if __name__ == "__main__":
    unittest.main()
