"""Actual TLS/resource-server/MCP/native D6 tests. Ephemeral keys and Works only."""
import asyncio
import copy
from contextlib import asynccontextmanager
from pathlib import Path
import socket
import ssl
import threading
import unittest
from unittest.mock import patch
import sys

import integration_d4_mutations as d4
import integration_contract as c
import integration_registry as r
import integration_gateway as gateway
import integration_gateway_contract as contract
import integration_mutations as mutations
import integration_lifecycle as life
import test_integration_gateway as support


class Remote:
    def inventory(self):
        return {str(p.relative_to(self.work)): (p.stat().st_mode, c.sha(p.read_bytes()) if p.is_file() else None)
                for p in self.work.rglob("*")}

    def count(self):
        path = self.repo / "invoked"
        return len(path.read_text()) if path.exists() else 0

    @asynccontextmanager
    async def running(self, *, mutate=False, second=False):
        import uvicorn
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(16)
        listener.setblocking(False)
        url = "https://127.0.0.1:" + str(listener.getsockname()[1]) + "/mcp"
        self.value, self.signing = support.credentials(self.root, r.file_pin(self.transfer_path), "fixture",
            mutation_pin=r.file_pin(self.policy_path) if mutate else None, resource=url)
        if mutate and isinstance(self, QA):
            self.value["delegates"][0]["tools"] = ["work_inspect", "execution_request"]
        if second:
            second_grant = copy.deepcopy(self.enrollment["grants"][0])
            second_grant["client_id"] = "client-b"
            self.enrollment["grants"].append(second_grant)
            plan = self.registry.plan(self.enrollment)
            self.registry.apply(self.enrollment, plan["plan_sha256"], approve_local_owner=True)
            self.value["delegates"][0]["transfer_policy"] = r.file_pin(self.make_policy(client="client-a", generation=2)[0])
            self.value["delegates"][0]["destination_id"] = "client-a"
            second_pin = r.file_pin(self.make_policy(client="client-b", generation=2)[0])
            self.value["delegates"].append({**self.value["delegates"][0], "delegate_id": "remote-b",
                "subject": "user-b", "oauth_client_id": "oauth-b", "destination_id": "client-b", "transfer_policy": second_pin})
        self.remote_pin = support.private(self.root, "gateway.json", self.value)
        policy = contract.Policy(Path(self.remote_pin["path"]), self.remote_pin["sha256"], approve_remote_gateway=True)
        gateway.tls(policy)
        self.remote = gateway.Gateway(policy, approve_remote_mutations=mutate)
        self.bearer = support.token(self.signing, self.value)
        self.url = url
        self.context = ssl.create_default_context(cafile=self.value["tls_cert"]["path"])
        config = uvicorn.Config(self.remote.app(), host="127.0.0.1", port=0, log_config=None, log_level="error",
            access_log=False, proxy_headers=False, ssl_certfile=self.value["tls_cert"]["path"],
            ssl_keyfile=self.value["tls_key"]["path"], timeout_keep_alive=1)
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            for _ in range(200):
                if server.started or task.done():
                    break
                await asyncio.sleep(.025)
            self.assertTrue(server.started)
            yield
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, 120)
            listener.close()

    @asynccontextmanager
    async def client(self, *, bearer=None, mode="auto"):
        import httpx2
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        async with httpx2.AsyncClient(verify=self.context, trust_env=False, timeout=120,
            headers={"Authorization": "Bearer " + (bearer or self.bearer)}) as http:
            async with Client(streamable_http_client(self.url, http_client=http), mode=mode, read_timeout_seconds=120) as client:
                yield client

    async def rpc_call(self, client, name, args):
        result = await client.call_tool("golem_" + name, args)
        value = c.decode(result.content[0].text.encode(), c.MAX_NATIVE)
        return result, value


class D6(Remote, d4.D4):
    def test_actual_tls_two_clients_modern_legacy_and_native_read_only(self):
        async def check():
            async with self.running(second=True):
                before = self.inventory()
                for mode, subject, oauth in (("auto", "user-a", "oauth-a"), ("legacy", "user-b", "oauth-b")):
                    bearer = support.token(self.signing, self.value, sub=subject, client_id=oauth, scope="golem.read")
                    async with self.client(bearer=bearer, mode=mode) as client:
                        self.assertIn("golem_work_inspect", [t.name for t in (await client.list_tools()).tools])
                        for view in ("status", "next", "record"):
                            result, value = await self.rpc_call(client, "work_inspect", {"project_id": "project",
                                "work_id": "example-work", "view": view})
                            self.assertFalse(result.is_error)
                            self.assertFalse(value["native_state_changed"])
                        result, value = await self.rpc_call(client, "context_get", self.context_args())
                        self.assertFalse(result.is_error, value)
                        result, value = await self.rpc_call(client, "handoff_prepare", {**self.context_args(),
                            "recipient_client_id": "client-b" if subject == "user-a" else "client-a"})
                        self.assertFalse(result.is_error, value)
                        self.assertFalse(value["ownership_transferred"])
                self.assertEqual(before, self.inventory())
        asyncio.run(check())

    def test_http_challenge_host_origin_proxy_bearer_and_live_revocation(self):
        import httpx2
        async def check():
            async with self.running():
                before = self.inventory()
                async with httpx2.AsyncClient(verify=self.context, trust_env=False) as http:
                    reply = await http.post(self.url, json={})
                    self.assertEqual(reply.status_code, 401)
                    self.assertIn("resource_metadata", reply.headers["www-authenticate"])
                    reply = await http.get(self.url.rsplit("/", 1)[0] + "/.well-known/oauth-protected-resource/mcp")
                    self.assertEqual(reply.status_code, 200)
                    self.assertEqual(reply.json()["resource"], self.url)
                    with self.assertRaises(httpx2.RequestError):
                        async with httpx2.AsyncClient(trust_env=False) as untrusted:
                            await untrusted.get(self.url)
                    for extra in ({"Origin": "https://evil.example"}, {"Host": "evil.example"}, {"X-Forwarded-Proto": "https"}):
                        reply = await http.post(self.url, json={}, headers={"Authorization": "Bearer " + self.bearer, **extra})
                        self.assertEqual(reply.status_code, 403)
                    bad = support.token(self.signing, self.value, aud="https://provider.example/api")
                    reply = await http.post(self.url, json={}, headers={"Authorization": "Bearer " + bad})
                    self.assertEqual(reply.status_code, 401)
                    revoked = c.decode(Path(self.value["revocation_file"]).read_bytes())
                    support.private(self.root, "revocations.json", {**revoked, "epoch": 2, "revoked_jtis": ["token-a"]})
                    reply = await http.post(self.url, json={}, headers={"Authorization": "Bearer " + self.bearer})
                    self.assertEqual(reply.status_code, 401)
                self.assertEqual(before, self.inventory())
        asyncio.run(check())

    def test_remote_claim_exact_replay_native_receipt_and_maintenance_fence(self):
        self.stage_claim()
        async def check():
            async with self.running(mutate=True):
                async with self.client() as client:
                    result, first = await self.rpc_call(client, "session_claim", self.args)
                    self.assertFalse(result.is_error)
                    self.assertEqual(first["state"], "NATIVE_RESULT_RECORDED")
                    before = self.inventory()
                    _, repeated = await self.rpc_call(client, "session_claim", self.args)
                    self.assertEqual(first, repeated)
                    self.assertEqual(before, self.inventory())
                    with self.registry.locked(exclusive=True):
                        life.publish(self.registry, "project", "FROZEN", "maintenance", {})
                    result, blocked = await self.rpc_call(client, "session_claim", {**self.args, "request_id": "new-request"})
                    self.assertTrue(result.is_error)
                    self.assertEqual(blocked["code"], "PROJECT_MAINTENANCE")
                    with self.assertRaises(c.IntegrationError):
                        life.quiet(self.registry, "project")
                    self.assertEqual(before, self.inventory())
        asyncio.run(check())

    def test_lost_native_reply_stays_unknown_and_does_not_redispatch(self):
        self.stage_claim()
        original = mutations.records.capture
        def lost(*args, **kwargs):
            result = original(*args, **kwargs)
            if (args[1] / "dispatch-intent.json").exists():
                raise OSError("synthetic lost reply after committed native claim")
            return result
        async def check():
            async with self.running(mutate=True):
                async with self.client() as client:
                    with patch.object(mutations.records, "capture", lost):
                        _, first = await self.rpc_call(client, "session_claim", self.args)
                    self.assertEqual(first["state"], "COMMIT_UNKNOWN")
                    before = self.inventory()
                    _, replayed = await self.rpc_call(client, "session_claim", self.args)
                    self.assertEqual(first, replayed)
                    _, blocked = await self.rpc_call(client, "session_claim", {**self.args, "request_id": "bypass"})
                    self.assertEqual(blocked["code"], "WORK_MUTATION_UNRESOLVED")
                    self.assertEqual(before, self.inventory())
        asyncio.run(check())

    def stage_claim(self):
        self.stage("session_claim", {"schema_version": 1, "operation": "claim", "work_id": "example-work",
            "key": "remote-claim", "expected_sequence": 1, "session_id": "mapped-owner", "expected_generation": self.generation,
            "source_snapshot": self.source, "byte_budget": 1048576, "ttl_ms": 3600000}, owner="mapped-owner")


class QA(Remote, d4.QA):
    def test_tls_response_loss_preserves_native_result_without_automatic_retry(self):
        self.approve_qa()
        async def check():
            async with self.running(mutate=True):
                ready, release = threading.Event(), threading.Event()
                original = self.remote.call
                def hold(*args):
                    value = original(*args)
                    ready.set()
                    release.wait(30)
                    return value
                async with self.client() as client:
                    with patch.object(self.remote, "call", hold):
                        request = asyncio.create_task(self.rpc_call(client, "execution_request", self.args))
                        try:
                            for _ in range(1000):
                                if ready.is_set() or request.done():
                                    break
                                await asyncio.sleep(.02)
                            self.assertTrue(ready.is_set())
                            request.cancel()
                            try:
                                await request
                            except asyncio.CancelledError:
                                pass
                        finally:
                            release.set()
                before = self.inventory()
                async with self.client() as client:
                    _, value = await self.rpc_call(client, "execution_request", self.args)
                    self.assertEqual(value["state"], "NATIVE_RESULT_RECORDED")
                self.assertEqual(self.count(), 1)
                self.assertEqual(before, self.inventory())
        asyncio.run(check())

    def test_remote_authentication_cannot_approve_pending_qa(self):
        self.approve_qa(record_decision=False)
        async def check():
            async with self.running(mutate=True):
                async with self.client() as client:
                    result, value = await self.rpc_call(client, "execution_request", self.args)
                    self.assertTrue(result.is_error)
                    self.assertEqual(value["state"], "PENDING_APPROVAL")
                    self.assertEqual(self.count(), 0)
        asyncio.run(check())

    def test_remote_qa_reuses_owner_decision_and_native_one_use_receipt(self):
        self.approve_qa()
        async def check():
            async with self.running(mutate=True):
                async with self.client() as client:
                    result, value = await self.rpc_call(client, "execution_request", self.args)
                    self.assertFalse(result.is_error)
                    self.assertEqual(value["state"], "NATIVE_RESULT_RECORDED")
                    self.assertEqual(self.count(), 1)
                    before = self.inventory()
                    _, replayed = await self.rpc_call(client, "execution_request", self.args)
                    self.assertEqual(replayed, value)
                    self.assertEqual(self.count(), 1)
                    self.assertEqual(before, self.inventory())
        asyncio.run(check())


if __name__ == "__main__":
    names = {D6: [n for n in D6.__dict__ if n.startswith("test_")], QA: [n for n in QA.__dict__ if n.startswith("test_")]}
    suite = unittest.TestSuite(cls(name) for cls, tests in names.items() for name in tests)
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
