"""D2 real stdio clients and native candidate renderer, on disposable Works only.

Optional gate: install tools/requirements-mcp.txt, then pass CLI and source root.
Not part of dependency-free native consumers or the core CMake test set.
"""
import asyncio
import base64
import copy
import json
from pathlib import Path
import sys
import subprocess
import unittest

import integration_read_backend as fixture

import integration_contract as c
import integration_service as service
import integration_transfer as transfer
import integration_mcp as branding


class D2(fixture.ReadBackend):
    def test_verified_evidence_and_completion_preserve_native_files(self):
        path, digest = self.make_policy()
        api = service.Service(transfer.Transfer(path, digest, approve_data_transfer=True))
        args = {"project_id": "project", "work_id": "example-work"}
        record = api.call("work_inspect", {**args, "view": "record"})["result"]
        document = record["documents"][0]
        orphan_file = self.root / "unregistered.txt"
        orphan_file.write_bytes(b"not registered as Work evidence")
        orphan = self.cli("evidence", "put", self.work, orphan_file)
        before = self.inventory()
        for key in (document["digest"], document["body_digest"], record["journal"][0]["payload_digest"]):
            result = api.call("evidence_read", {**args, "digest": key, "max_bytes": 1048576})
            raw = base64.b64decode(result["result"]["data"], validate=True)
            self.assertEqual(c.sha(raw), key)
            self.assertEqual(len(raw), result["result"]["size"])
            self.assertTrue(result["references"])
            self.assertEqual(result["verification"], "SHA256_INTEGRITY_NOT_CONTENT_TRUTH")
        for key in (orphan["digest"], "f" * 64, document["event_digest"]):
            with self.assertRaises(c.IntegrationError) as caught:
                api.call("evidence_read", {**args, "digest": key, "max_bytes": 1048576})
            self.assertEqual(caught.exception.code, "EVIDENCE_NOT_REFERENCED")
        with self.assertRaises(c.IntegrationError):
            api.call("evidence_read", {**args, "digest": document["digest"], "max_bytes": 1})
        result = api.call("completion_check", {**args, "selection_id": "selection"})
        expected = self.cli("completion", "check", self.work, self.write("check.json", {
            "schema_version": 1, "operation": "resume", "selection_id": "selection"}))
        self.assertEqual(result["result"], expected)
        self.assertFalse(result["result"]["acceptance_verified"])
        with self.assertRaises(c.IntegrationError):
            api.call("completion_check", {**args, "selection_id": "missing"})
        self.assertEqual(before, self.inventory())

    def test_native_evidence_bytes_empty_bounds_and_corruption(self):
        for content in (b"", b"\x00\xff\xfe\n", b"x" * 1048576):
            file = self.root / "bytes.bin"
            file.write_bytes(content)
            put = self.cli("evidence", "put", self.work, file)
            before = self.inventory()
            result = self.cli("evidence", "read", self.work, put["digest"], 1048576)
            self.assertEqual(base64.b64decode(result["data"]), content)
            for limit in ("0", "-1", "true", "1048577", "9999999999999999999999", ""):
                self.cli("evidence", "read", self.work, put["digest"], limit, ok=False)
            self.assertEqual(before, self.inventory())
        # Corrupt only this disposable unregistered object, never product evidence.
        objects = [p for p in self.work.rglob("*") if p.is_file() and p.read_bytes() == content]
        self.assertEqual(len(objects), 1)
        objects[0].chmod(0o600)
        objects[0].write_bytes(b"corrupt")
        before = self.inventory()
        self.cli("evidence", "read", self.work, put["digest"], 1048576, ok=False)
        self.assertEqual(before, self.inventory())

    def make_policy(self, client="client-a", generation=1):
        recipient = "client-b" if client == "client-a" and len(self.enrollment["grants"]) > 1 else "client-a"
        policy = {"schema": "golem.integration-transfer.v1", "registry": str(self.registry.root),
            "registry_identity": self.registry.root_identity, "destination": "MODEL_SERVICE",
            "destination_id": client, "max_result_bytes": 8388608,
            "data_class": "APPROVED_WORK_CONTENT",
            "scopes": [{"binding": {**self.query("status")["binding"], "client_id": client,
                                    "generation": generation},
                        "work_ids": ["example-work"], "tools": list(transfer.NAMES),
                        "recipients": [{**self.query("status")["binding"], "generation": generation,
                                        "client_id": recipient}]}],
            "producer": transfer.producer()}
        path = self.root / (client + "-policy.json")
        path.write_bytes(c.encoded(policy))
        path.chmod(0o600)
        return path, c.sha(path.read_bytes())

    def context_args(self):
        return {"project_id": "project", "work_id": "example-work", "selection_id": "selection",
                "source_snapshot": self.source, "target_kind": "planning", "recipe": "current-v1"}

    def test_transfer_schema_with_independent_validator(self):
        from jsonschema import Draft202012Validator, ValidationError
        path, _ = self.make_policy()
        policy = c.decode(path.read_bytes())
        Draft202012Validator.check_schema(transfer.POLICY)
        for schema in service.SCHEMAS.values():
            Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(transfer.POLICY)
        validator.validate(policy)
        for fields in ((), ("producer",), ("scopes", 0), ("scopes", 0, "binding")):
            current = policy
            for field in fields:
                current = current[field]
            for key in current:
                value = copy.deepcopy(policy)
                target = value
                for field in fields:
                    target = target[field]
                del target[key]
                with self.assertRaises(ValidationError):
                    validator.validate(value)
        for value in ({**policy, "extra": True}, {**policy, "max_result_bytes": True},
                      {**policy, "producer": None}):
            with self.assertRaises(ValidationError):
                validator.validate(value)

    def test_complete_context_and_handoff_do_not_change_native_work(self):
        path, digest = self.make_policy()
        api = service.Service(transfer.Transfer(path, digest, approve_data_transfer=True))
        before = self.inventory()
        for recipe in ("current-v1", "original-v1"):
            for tool in ("context_get", "handoff_prepare"):
                args = {**self.context_args(), "recipe": recipe}
                if tool == "handoff_prepare":
                    args["recipient_client_id"] = "client-a"
                result = api.call(tool, args)
                self.assertEqual(result["state_scope"], "DELIVERY_ONLY")
                self.assertFalse(result["work_completion_inferred"])
                payload = result["payload"]
                self.assertEqual(c.sha(payload["candidate_json"].encode()), payload["projection_digest"])
                self.assertEqual(payload["provider_budget"], "UNKNOWN")
                self.assertFalse(payload["execution_ready"])
                self.assertFalse(payload["ownership_transferred"])
                self.assertEqual(payload["context_role"], "READING_AID")
                self.assertEqual(before, self.inventory())

    def test_stale_source_and_unknown_selection_fail_without_native_writes(self):
        path, digest = self.make_policy()
        api = service.Service(transfer.Transfer(path, digest, approve_data_transfer=True))
        before = self.inventory()
        for change, code in (({"source_snapshot": "f" * 64}, "SOURCE_SNAPSHOT_MISMATCH"),
                             ({"selection_id": "missing"}, "NATIVE_FAILURE")):
            with self.assertRaises(c.IntegrationError) as caught:
                api.call("context_get", {**self.context_args(), **change})
            self.assertEqual(caught.exception.code, code)
            self.assertFalse(service.blocked(caught.exception)["automatic_retry_allowed"])
        self.assertEqual(before, self.inventory())

    def test_live_foreign_owner_is_not_resumed_or_taken_over(self):
        native = self.cli("session", "call", self.work, self.write("foreign-claim.json", {
            "schema_version": 1, "operation": "claim", "work_id": "example-work", "key": "foreign-claim",
            "expected_sequence": 1, "session_id": "foreign-owner", "expected_generation": self.generation,
            "source_snapshot": self.source, "byte_budget": 1048576, "ttl_ms": 3600000}))
        path, digest = self.make_policy()
        api = service.Service(transfer.Transfer(path, digest, approve_data_transfer=True))
        before = self.inventory()
        result = api.call("handoff_prepare", {**self.context_args(), "recipient_client_id": "client-a"})
        status = result["payload"]["preflight"]["status"]
        self.assertEqual(status["state"]["active"]["session_id"], "foreign-owner")
        self.assertTrue(status["resume_preflight"]["lease_live"])
        self.assertFalse(result["payload"]["execution_ready"])
        self.assertEqual(before, self.inventory())

    def test_malformed_and_oversized_wire_frames_launch_no_native_reads(self):
        path, digest = self.make_policy()
        command = [sys.executable, str(fixture.fixture.SOURCE / "tools/integration_mcp.py"),
                   "--policy", str(path), "--reviewed-policy-sha256", digest, "--approve-data-transfer"]
        before = self.inventory()
        for data in (b'{"jsonrpc":"2.0","id":1,"id":2,"method":"tools/list"}\n',
                     b" " * 524289 + b"\n", b'{"x":NaN}\n', b'{"x":"\\ud800"}\n'):
            result = subprocess.run(command, input=data, capture_output=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"BLOCKED", result.stderr)
        self.assertEqual(list(self.registry.root.glob("read-*")), [])
        self.assertEqual(before, self.inventory())

    def test_real_stdio_modern_and_legacy_clients_and_revocation(self):
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters
        from mcp.types import Implementation
        # Distinct owner-reviewed clients; a clientInfo label confers no rights.
        second = copy.deepcopy(self.enrollment["grants"][0])
        second["client_id"] = "client-b"
        self.enrollment["grants"].append(second)
        plan = self.registry.plan(self.enrollment)
        self.registry.apply(self.enrollment, plan["plan_sha256"], approve_local_owner=True)
        policies = [self.make_policy(client, 2) for client in ("client-a", "client-b")]
        before = self.inventory()

        async def exercise():
            params = [StdioServerParameters(command=sys.executable,
                args=[str(fixture.fixture.SOURCE / "tools/integration_mcp.py"), "--policy", str(path),
                      "--reviewed-policy-sha256", digest, "--approve-data-transfer"],
                cwd=str(self.root)) for path, digest in policies]
            async with Client(params[0], mode="auto", read_timeout_seconds=120) as modern:
                async with Client(params[1], mode="legacy", read_timeout_seconds=120,
                                  client_info=Implementation(name="client-a-forged", version="1")) as legacy:
                    self.assertEqual(modern.protocol_version, "2026-07-28")
                    self.assertEqual(legacy.protocol_version, "2025-11-25")
                    for client in (modern, legacy):
                        listed = await client.list_tools()
                        self.assertIsNotNone(client.server_info)
                        self.assertEqual(c.sha(client.server_info.icons[0].src.encode()),
                                         c.sha(branding.server_icons()[0].src.encode()))
                        self.assertEqual({t.name for t in listed.tools}, {"golem_" + n for n in transfer.NAMES})
                        result = await client.call_tool("golem_context_get", self.context_args())
                        self.assertFalse(result.is_error)
                        value = json.loads(result.content[0].text)
                        self.assertFalse(value["execution_authorized"])
                        completion = await client.call_tool("golem_completion_check", {
                            "project_id": "project", "work_id": "example-work", "selection_id": "selection"})
                        self.assertFalse(completion.is_error)
                        record = await client.call_tool("golem_work_inspect", {
                            "project_id": "project", "work_id": "example-work", "view": "record"})
                        key = json.loads(record.content[0].text)["result"]["documents"][0]["body_digest"]
                        evidence = await client.call_tool("golem_evidence_read", {
                            "project_id": "project", "work_id": "example-work", "digest": key,
                            "max_bytes": 1048576})
                        self.assertFalse(evidence.is_error)
                        self.assertEqual(c.sha(base64.b64decode(json.loads(evidence.content[0].text)
                                                               ["result"]["data"])), key)
                        forged = await client.call_tool("golem_work_inspect", {
                            "project_id": "project", "work_id": "example-work", "view": "status",
                            "principal_id": "owner"})
                        self.assertTrue(forged.is_error)
                        missing = await client.call_tool("golem_work_inspect", {
                            "project_id": "foreign", "work_id": "example-work", "view": "status"})
                        self.assertTrue(missing.is_error)
                    addressed = await modern.call_tool("golem_handoff_prepare", {
                        **self.context_args(), "recipient_client_id": "client-b"})
                    self.assertFalse(addressed.is_error)
                    payload = json.loads(addressed.content[0].text)["payload"]
                    self.assertEqual(payload["recipient_binding"]["client_id"], "client-b")
                    received = await legacy.call_tool("golem_context_get", self.context_args())
                    self.assertFalse(received.is_error)
                    receiver = json.loads(received.content[0].text)["payload"]
                    self.assertEqual(receiver["projection_digest"], payload["projection_digest"])
                    self.assertEqual(receiver["binding"]["client_id"], "client-b")
                    plan = self.registry.plan(self.enrollment, "revoke")
                    self.registry.apply(self.enrollment, plan["plan_sha256"], action="revoke", approve_local_owner=True)
                    for client in (modern, legacy):
                        denied = await client.call_tool("golem_work_inspect", {
                            "project_id": "project", "work_id": "example-work", "view": "status"})
                        self.assertTrue(denied.is_error)
        asyncio.run(asyncio.wait_for(exercise(), timeout=240))
        self.assertEqual(before, self.inventory())


if __name__ == "__main__":
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName("D2." + name, sys.modules[__name__])
        for name in D2.__dict__ if name.startswith("test_"))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
