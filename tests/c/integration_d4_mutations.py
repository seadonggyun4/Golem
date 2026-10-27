"""D4 native and optional real MCP gates on synthetic disposable Works only."""
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

import integration_d2_mcp as fixture
import execution_integration as execution
HOST = Path(sys.argv.pop(1)).resolve()
WITH_MCP = "--mcp" in sys.argv
if WITH_MCP:
    sys.argv.remove("--mcp")

import execution_record as records
import integration_contract as c
import integration_registry as registry
import integration_transfer as transfer
import integration_mutation_contract as contract
import integration_mutations as mutations


class Actions:
    def init_d4(self, project, *, move=False):
        if move:
            target = project / ".golem/works/test"
            target.parent.mkdir(parents=True)
            self.work.rename(target)
            self.work = target
            self.registry = registry.Registry.create(self.root / "registry", approve_local_owner=True)
            self.enrollment = {"schema": "golem.integration-enrollment.v1",
                "project": registry.describe("project", project, fixture.fixture.fixture.CLI,
                    [fixture.fixture.fixture.SOURCE / "samples/agent-session/status.json"], [("example-work", self.work)]),
                "grants": [{"schema": "golem.integration-grant.v1", "principal_id": "owner", "client_id": "client-a",
                    "operations": ["status", "next", "record", "history"], "work_ids": ["example-work"],
                    "destination": "LOCAL_HOST", "assurance": "LOCAL_COOPERATIVE"}]}
            plan = self.registry.plan(self.enrollment)
            self.registry.apply(self.enrollment, plan["plan_sha256"], approve_local_owner=True)
        policy = {"schema": "golem.integration-transfer.v1", "registry": str(self.registry.root),
            "registry_identity": self.registry.root_identity, "destination": "MODEL_SERVICE", "destination_id": "fixture",
            "max_result_bytes": 8388608, "data_class": "APPROVED_WORK_CONTENT",
            "scopes": [{"binding": {"schema": "golem.integration-client-binding.v1", "project_id": "project",
                "generation": 1, "principal_id": "owner", "client_id": "client-a", "assurance": "LOCAL_COOPERATIVE"},
                "work_ids": ["example-work"], "tools": list(transfer.NAMES), "recipients": []}], "producer": transfer.producer()}
        self.transfer_path = self.private("transfer.json", c.encoded(policy))
        self.entries = []

    def private(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        path.chmod(0o600)
        return path

    def stage(self, name, native, *, action_id=None, owner="mapped-owner", body="", context="", count="", approval=None):
        action_id = action_id or "action-" + str(len(self.entries))
        action = {"schema": "golem.integration-native-action.v1", "native_json": json.dumps(native) + "\n",
                  "body": body, "context_json": context, "count_json": count, "approval": approval}
        path = self.private(action_id + ".json", c.encoded(action))
        entry = {"action_id": action_id, "project_id": "project", "work_id": "example-work", "tool": name,
                 "session_id": owner, "native_binding_id": "", "action": registry.file_pin(path)}
        self.entries.append(entry)
        policy = {"schema": "golem.integration-mutations.v1", "transfer_policy": registry.file_pin(self.transfer_path),
                  "actions": self.entries, "producer": contract.producer()}
        self.policy_path = self.private("mutations.json", c.encoded(policy))
        self.policy_digest = c.sha(self.policy_path.read_bytes())
        self.api = mutations.Service(contract.Policy(self.policy_path, self.policy_digest, approve_mutations=True))
        self.args = {"project_id": "project", "work_id": "example-work", "action_id": action_id,
                     "request_id": action_id}
        return self.args

    def invoke(self, name):
        return self.api.call(name, self.args)

    def claim(self, sequence=1, source=None):
        request = {"schema_version": 1, "operation": "claim", "work_id": "example-work", "key": "d4-claim",
            "expected_sequence": sequence, "session_id": "mapped-owner", "expected_generation": self.generation,
            "source_snapshot": source or self.source, "byte_budget": 1048576, "ttl_ms": 3600000}
        self.stage("session_claim", request)
        return self.invoke("session_claim")

    def resume_inputs(self):
        request = {"schema_version": 1, "renderer_version": 2, "recipe": "current-v1", "selection_id": "selection",
            "source_snapshot": self.source, "target_kind": "planning", "byte_budget": 2097152, "excerpt_bytes": 0,
            "token_budget": 100000, "tokenizer_id": "fixture-count-only", "agent_note": ""}
        candidate = self.cli("context", "candidate", self.work, self.write("context.json", request))
        count = {"schema_version": 1, "tokenizer_id": request["tokenizer_id"],
                 "projection_digest": candidate["projection_digest"], "input_tokens": 100}
        return json.dumps(request), json.dumps(count)


class D4(Actions, fixture.D2):
    def setUp(self):
        super().setUp()
        self.init_d4(self.project)

    def test_claim_begin_document_and_session_submission_use_native_receipts(self):
        claim = self.claim()
        self.assertEqual(claim["state"], "NATIVE_RESULT_RECORDED")
        self.assertEqual(self.invoke("session_claim"), claim)
        active = claim["native_reply"]["state"]["active"]
        token = {k: active[k] for k in ("epoch", "attempt_id", "session_id")}
        self.stage("session_begin", {"schema_version": 1, "operation": "begin", "work_id": "example-work",
            "key": "begin", "expected_sequence": 2, "token": token, "input_digest": active["manifest_digest"]})
        self.assertEqual(self.invoke("session_begin")["state"], "NATIVE_RESULT_RECORDED")
        manifest = self.inputs("planning", budget=1048576)
        meta = self.metadata("planning", parents=manifest["direct"], version=4)
        meta.update(input_manifest=manifest, producer_attempt=token["attempt_id"])
        self.stage("document_submit", meta, body=self.body("planning", manifest["direct"]))
        document = self.invoke("document_submit")
        self.assertEqual(document["state"], "NATIVE_RESULT_RECORDED", document)
        output = document["native_reply"]
        self.stage("session_submit", {"schema_version": 1, "operation": "submit", "work_id": "example-work",
            "key": "submit", "expected_sequence": 3, "token": token, "input_digest": active["manifest_digest"],
            "source_snapshot": self.source, "output": {"document_id": "planning", "revision": output["revision"],
                "digest": output["manifest_digest"]}, "evidence": [output["body_digest"]]})
        submitted = self.invoke("session_submit")
        self.assertEqual(submitted["native_reply"]["sequence"], 4, submitted)
        self.assertFalse(submitted["acceptance_verified"])

    def test_native_stale_source_rejected_and_unknown_never_retried(self):
        before = self.inventory()
        result = self.claim(source="f" * 64)
        self.assertEqual(result["state"], "COMMIT_UNKNOWN")
        self.assertEqual(before, self.inventory())
        self.assertEqual(self.invoke("session_claim"), result)
        with self.assertRaises(c.IntegrationError):
            self.api.call("session_claim", {**self.args, "request_id": "replacement"})

    def test_response_loss_after_native_commit_is_not_reexecuted(self):
        original = records.capture
        def lost(*args, **kwargs):
            result = original(*args, **kwargs)
            if (args[1] / "dispatch-intent.json").exists():
                self.assertEqual(result["returncode"], 0)
                raise OSError("synthetic lost native response")
            return result
        with patch.object(records, "capture", lost):
            result = self.claim()
        self.assertEqual(result["state"], "COMMIT_UNKNOWN")
        after = self.inventory()
        self.assertEqual(self.invoke("session_claim"), result)
        self.assertEqual(after, self.inventory())
        status = self.cli("session", "call", self.work, self.write("status.json", {
            "schema_version": 1, "operation": "status", "work_id": "example-work"}))
        self.assertEqual(status["sequence"], 2)

    def test_concurrent_admission_never_dispatches_twice(self):
        request = {"schema_version": 1, "operation": "claim", "work_id": "example-work", "key": "concurrent",
            "expected_sequence": 1, "session_id": "mapped-owner", "expected_generation": self.generation,
            "source_snapshot": self.source, "byte_budget": 1048576, "ttl_ms": 3600000}
        self.stage("session_claim", request)
        second = mutations.Service(contract.Policy(self.policy_path, self.policy_digest, approve_mutations=True))
        def call(api):
            try:
                return api.call("session_claim", self.args)
            except c.IntegrationError as error:
                return {"state": error.code}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(call, (self.api, second)))
        self.assertGreaterEqual(sum(r["state"] == "NATIVE_RESULT_RECORDED" for r in results), 1, results)
        self.assertEqual(len(list(self.registry.root.glob("mutation-*/dispatch-intent.json"))), 1)
        status = self.cli("session", "call", self.work, self.write("concurrent-status.json", {
            "schema_version": 1, "operation": "status", "work_id": "example-work"}))
        self.assertEqual(status["sequence"], 2)

    def test_running_resume_requires_explicit_reconcile_without_reexecution(self):
        claim = self.claim()["native_reply"]
        active = claim["state"]["active"]
        token = {k: active[k] for k in ("epoch", "attempt_id", "session_id")}
        self.stage("session_begin", {"schema_version": 1, "operation": "begin", "work_id": "example-work", "key": "begin",
            "expected_sequence": 2, "token": token, "input_digest": active["manifest_digest"]})
        self.invoke("session_begin")
        context, count = self.resume_inputs()
        self.stage("session_resume", {"schema_version": 1, "operation": "resume", "work_id": "example-work", "key": "resume",
            "expected_sequence": 3, "session_id": "mapped-owner", "ttl_ms": 3600000}, context=context, count=count)
        result = self.invoke("session_resume")
        self.assertEqual(result["state"], "NATIVE_RESULT_RECORDED", result)
        reply = result["native_reply"]
        self.assertTrue(reply["budget_verified"])
        active = reply["receipt"]["state"]["active"]
        self.assertEqual(active["state"], "RECOVERY_REQUIRED")
        token = {k: active[k] for k in ("epoch", "attempt_id", "session_id")}
        # Use an existing CAS body digest, never an arbitrary guessed hash.
        evidence = self.docs["scope"]["body_digest"]
        self.stage("session_reconcile", {"schema_version": 1, "operation": "reconcile", "work_id": "example-work",
            "key": "explicit-no-effects", "expected_sequence": 4, "token": token,
            "input_digest": active["manifest_digest"], "source_snapshot": self.source,
            "resolution": "NO_EFFECTS", "output": None, "evidence": [evidence]})
        result = self.invoke("session_reconcile")
        self.assertEqual(result["state"], "NATIVE_RESULT_RECORDED", result)
        self.assertIsNone(result["native_reply"]["state"]["active"])

    def test_live_foreign_owner_resume_is_read_only_blocked(self):
        self.claim()
        context, count = self.resume_inputs()
        self.stage("session_resume", {"schema_version": 1, "operation": "resume", "work_id": "example-work", "key": "takeover",
            "expected_sequence": 2, "session_id": "different-owner", "ttl_ms": 3600000},
            owner="different-owner", context=context, count=count)
        before = self.inventory()
        result = self.invoke("session_resume")
        self.assertEqual((result["state"], result["code"]), ("NOT_DISPATCHED", "LIVE_OWNER_WAIT"))
        self.assertEqual(before, self.inventory())

    def test_corrupt_evidence_preflight_never_attempts_a_mutation_or_repair(self):
        victim = self.committed_body()
        victim.chmod(0o600)
        victim.write_bytes(b"synthetic damaged CAS")
        before = self.inventory()
        result = self.claim()
        self.assertEqual(result["state"], "NOT_DISPATCHED")
        self.assertEqual(before, self.inventory())
        self.assertEqual(list(self.registry.root.glob("mutation-*/dispatch-intent.json")), [])

    def test_real_mcp_modern_and_legacy_typed_scope(self):
        if not WITH_MCP:
            self.skipTest("optional actual SDK gate")
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        request = {"schema_version": 1, "operation": "claim", "work_id": "example-work", "key": "wire-claim",
            "expected_sequence": 1, "session_id": "mapped-owner", "expected_generation": self.generation,
            "source_snapshot": self.source, "byte_budget": 1048576, "ttl_ms": 3600000}
        self.stage("session_claim", request)
        async def exercise():
            for mode in ("auto", "legacy"):
                params = StdioServerParameters(command=sys.executable, cwd=str(self.root), args=[
                    str(fixture.fixture.fixture.SOURCE / "tools/integration_mutation_mcp.py"),
                    "--policy", str(self.policy_path), "--reviewed-policy-sha256", self.policy_digest, "--approve-mutations"])
                async with Client(params, mode=mode, read_timeout_seconds=120) as client:
                    tools = (await client.list_tools()).tools
                    names = {t.name for t in tools}
                    historical = next(t for t in tools if t.name == 'golem_execution_read')
                    self.assertTrue(historical.annotations.read_only_hint)
                    self.assertTrue(historical.annotations.idempotent_hint)
                    self.assertFalse(historical.annotations.destructive_hint)
                    self.assertFalse(historical.annotations.open_world_hint)
                    import integration_mcp as branding
                    self.assertIsNotNone(client.server_info)
                    self.assertEqual(c.sha(client.server_info.icons[0].src.encode()),
                                     c.sha(branding.server_icons()[0].src.encode()))
                    self.assertIn("golem_session_claim", names)
                    self.assertNotIn("golem_session_resume", names)
                    forged = await client.call_tool("golem_session_claim", {**self.args, "approve": True})
                    self.assertTrue(forged.is_error)
                    reply = await client.call_tool("golem_session_claim", self.args)
                    self.assertFalse(reply.is_error)
                    self.assertEqual(json.loads(reply.content[0].text)["state"], "NATIVE_RESULT_RECORDED")
        asyncio.run(asyncio.wait_for(exercise(), timeout=240))


class QA(Actions, execution.Execution):
    def setUp(self):
        super().setUp()
        mode = {"test_qa_fail_is_recorded_not_promoted_to_acceptance": "real",
                "test_live_registry_revocation_cancels_approved_qa": "lease"}.get(self._testMethodName, "pass")
        self.setup_execution(mode=mode)
        if self._testMethodName != "test_receipted_prepare_and_finish_reuse_existing_core":
            self.prepare()
            self.finish()
        self.init_d4(self.repo, move=True)

    def approve_qa(self, attempt="owner-qa", *, record_decision=True, request=None):
        request = request or {"schema_version": 1, "operation": "run", "checkpoint": self.cp["receipt_digest"], "attempt_id": attempt}
        description = self.cli("approval", "describe", self.work, self.write("describe.json", request))
        creation = {"schema_version": 1, "operation": "request", "key": attempt + "-request",
                    "action": description["action"], "ttl_ms": 3600000}
        receipt = self.cli("approval", "call", self.work, self.write("approval-request.json", creation))["receipt_digest"]
        decision = {"schema": "golem.integration-local-decision.v1", "action_digest": description["action_digest"],
                    "issuer": "1" * 64, "policy_epoch": 1, "operation": "approve"}
        permit = self.private(attempt + "-decision.json", c.encoded(decision))
        native = self.private(attempt + "-approve.json", c.encoded({"schema_version": 1, "operation": "approve", "key": attempt + "-approve",
            "request_receipt": receipt, "reason": "synthetic-owner-reviewed"}))
        output = self.root / (attempt + "-decision-record")
        output.mkdir(mode=0o700)
        if record_decision:
            result = records.capture([str(HOST), "approve", str(self.work), str(native), str(permit), c.sha(permit.read_bytes()),
                                      "-", "-", "-", "-", "-"], output,
                                      env=mutations.backend.ENVIRONMENT, timeout=60, observe_source=False)
            self.assertEqual(result["returncode"], 0, (output / "stderr.log").read_text())
        approval = {"host": registry.file_pin(HOST), "decision": registry.file_pin(permit),
                    "request_receipt": receipt, "contract": self.approval, "shell_contract": ""}
        self.stage("execution_request", request, approval=approval)
        return permit

    def test_receipted_qa_pass_and_historical_response_do_not_rerun(self):
        self.approve_qa()
        result = self.invoke("execution_request")
        self.assertEqual(result["state"], "NATIVE_RESULT_RECORDED", result)
        self.assertEqual(result["native_reply"]["record"]["status"], "PASS")
        self.assertEqual(self.invoke("execution_request"), result)
        self.assertEqual((self.repo / "invoked").read_text(), "x")

        before = {str(p): c.sha(p.read_bytes()) for p in self.work.rglob('*') if p.is_file()}
        with patch.object(records, 'capture', side_effect=AssertionError('historical read cannot launch native')):
            reply = self.api.call('execution_read', {**self.args, 'operation': 'stored_result'})
        self.assertEqual(reply['result'], result)
        self.assertFalse(reply['native_state_changed'])
        self.assertFalse(reply['native_dispatch_performed'])
        self.assertEqual(before, {str(p): c.sha(p.read_bytes()) for p in self.work.rglob('*') if p.is_file()})
        self.assertEqual((self.repo / 'invoked').read_text(), 'x')

    def test_receipted_prepare_and_finish_reuse_existing_core(self):
        self.approve_qa("owner-prepare", request={"schema_version": 1, "operation": "prepare", "contract": self.contract})
        prepared = self.invoke("execution_request")
        self.assertEqual(prepared["state"], "NATIVE_RESULT_RECORDED", prepared)
        checkpoint = prepared["native_reply"]["receipt_digest"]
        self.approve_qa("owner-finish", request={"schema_version": 1, "operation": "finish", "checkpoint": checkpoint})
        finished = self.invoke("execution_request")
        self.assertEqual(finished["state"], "NATIVE_RESULT_RECORDED", finished)
        self.assertFalse((self.repo / "invoked").exists())

    def test_changed_or_removed_owner_decision_cannot_dispatch(self):
        permit = self.approve_qa()
        permit.unlink()
        with self.assertRaises((OSError, c.IntegrationError)):
            self.invoke("execution_request")
        self.assertFalse((self.repo / "invoked").exists())

    def test_qa_fail_is_recorded_not_promoted_to_acceptance(self):
        self.approve_qa()
        # The real compiler fixture starts with add(a,b)=a-b and must fail.
        result = self.invoke("execution_request")
        self.assertEqual(result["state"], "NATIVE_RESULT_RECORDED", result)
        self.assertIn(result["native_reply"]["record"]["status"], ("FAIL", "ERROR"))
        self.assertFalse(result["acceptance_verified"])

    def test_pending_native_approval_never_auto_approves(self):
        self.approve_qa(record_decision=False)
        before = {str(p.relative_to(self.work)): (p.stat().st_mode, c.sha(p.read_bytes()) if p.is_file() else None)
                  for p in self.work.rglob("*")}
        result = self.invoke("execution_request")
        self.assertEqual((result["state"], result["code"]), ("PENDING_APPROVAL", "PENDING_APPROVAL"))
        self.assertFalse((self.repo / "invoked").exists())
        after = {str(p.relative_to(self.work)): (p.stat().st_mode, c.sha(p.read_bytes()) if p.is_file() else None)
                 for p in self.work.rglob("*")}
        self.assertEqual(before, after)

    def test_protected_file_change_does_not_relax_original_approval(self):
        self.approve_qa()
        original = (self.repo / "runner.py").read_bytes()
        (self.repo / "runner.py").write_bytes(original + b"\n# synthetic protected-file change\n")
        result = self.invoke("execution_request")
        self.assertEqual(result["state"], "COMMIT_UNKNOWN")
        self.assertFalse((self.repo / "invoked").exists())
        self.assertTrue((self.work / "execution-policies").is_dir())

    def test_live_registry_revocation_cancels_approved_qa(self):
        self.approve_qa()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.invoke, "execution_request")
            deadline = time.monotonic() + 30
            while not (self.repo / "invoked").exists() and not future.done() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue((self.repo / "invoked").exists())
            plan = self.registry.plan(self.enrollment, "revoke")
            self.registry.apply(self.enrollment, plan["plan_sha256"], action="revoke", approve_local_owner=True)
            result = future.result(timeout=8)
        self.assertEqual(result["state"], "COMMIT_UNKNOWN")
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        # Existing native approval recovery remains authoritative and read-only.
        request_receipt = c.decode((self.root / "action-0.json").read_bytes())["approval"]["request_receipt"]
        status = self.cli("approval", "call", self.work, self.write("recover.json", {
            "schema_version": 1, "operation": "recover", "request_receipt": request_receipt}))
        if status["dispatch"] == "NOT_REDISPATCHED":
            self.assertEqual(status["state"], "RECORDED")
            self.assertEqual(status["result"]["record"]["status"], "ERROR")
        else:
            self.assertEqual(status["dispatch"], "UNCERTAIN")


if __name__ == "__main__":
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(cls.__name__ + "." + name, sys.modules[__name__])
        for cls in (D4, QA) for name in cls.__dict__ if name.startswith("test_"))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
