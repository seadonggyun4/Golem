"""Native D3 no-write tests, optionally real pinned client lifecycle fixtures."""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import unittest
import uuid

ARGUMENTS = sys.argv[1:]
import integration_d2_mcp as fixture
import integration_contract as c
import integration_hook_contract as h
import integration_hooks as hooks

CLIENTS = {}


class D3(fixture.D2):
    def make_profile(self, client="codex-cli", binary=None):
        policy, digest = self.make_policy()
        if binary is None:
            binary = self.root / "synthetic-client"
            version = "codex-cli 0.141.0" if client == "codex-cli" else "2.1.196 (Claude Code)"
            binary.write_text("#!/bin/sh\nprintf '%s\\n' '" + version + "'\n")
            binary.chmod(0o700)
        elif binary.stat().st_nlink != 1:
            # A private test-only snapshot, never rewrite an installed hardlink.
            staged = self.root / "reviewed-native-client"
            shutil.copyfile(binary, staged)
            staged.chmod(stat.S_IMODE(binary.stat().st_mode))
            binary = staged
        value = {"schema": "golem.integration-hook-profile.v1", "client": client, "client_version": h.VERSIONS[client],
            "client_pin": h.executable_pin(binary), "python_pin": h.executable_pin(Path(sys.executable).resolve()),
            "transfer_policy": {"path": str(policy), "sha256": digest}, "context": self.context_args(),
            "sources": list(h.SOURCES), "mcp_server": "golem", "delivery": "SCOPED_MCP_NOTICE", "producer": h.producer()}
        value = h.plan(value)
        path = self.root / "hook-profile.json"
        path.write_bytes(c.encoded(value))
        path.chmod(0o600)
        return h.Profile(path, c.sha(path.read_bytes()), approve_hooks=True)

    def hook(self, profile, source):
        command = h.fragment(profile)["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        value = {"session_id": "fixture-host", "cwd": str(self.project), "hook_event_name": "SessionStart", "source": source}
        result = subprocess.run(shlex.split(command), input=c.encoded(value), capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(c.decode(result.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_native_startup_resume_compact_clear_preserve_all_work_bytes(self):
        profile = self.make_profile()
        before = self.inventory()
        for source in h.SOURCES:
            notice = self.hook(profile, source)
            self.assertEqual(notice["context_state"], "AVAILABLE_FOR_EXPLICIT_FETCH")
            self.assertFalse(notice["execution_authorized"])
            self.assertFalse(notice["complete_context_delivered"])
            self.assertEqual(before, self.inventory())

    def test_stale_context_and_revocation_are_visible_without_resume(self):
        profile = self.make_profile()
        value = {**profile.value, "context": {**profile.value["context"], "source_snapshot": "f" * 64}}
        profile.path.write_bytes(c.encoded(value))
        profile = h.Profile(profile.path, c.sha(profile.path.read_bytes()), approve_hooks=True)
        before = self.inventory()
        notice = self.hook(profile, "resume")
        self.assertEqual(notice["context_state"], "BLOCKED")
        self.assertEqual(notice["code"], "NATIVE_FAILURE")
        self.assertIn("resume_preflight", notice)
        plan = self.registry.plan(self.enrollment, "revoke")
        self.registry.apply(self.enrollment, plan["plan_sha256"], action="revoke", approve_local_owner=True)
        # Do not recheck the revoked profile to obtain the original command.
        command = [sys.executable, str(fixture.fixture.fixture.SOURCE / "tools/integration_hooks.py"),
                   "--profile", str(profile.path), "--reviewed-profile-sha256", profile.digest, "--approve-hooks"]
        result = subprocess.run(command, input=b"{}", capture_output=True, timeout=30)
        self.assertIn(b"PROJECT_APPROVAL_REQUIRED", result.stdout)
        self.assertEqual(before, self.inventory())

    def test_live_owner_is_reported_not_taken_over(self):
        self.cli("session", "call", self.work, self.write("d3-claim.json", {
            "schema_version": 1, "operation": "claim", "work_id": "example-work", "key": "d3-claim",
            "expected_sequence": 1, "session_id": "foreign-owner", "expected_generation": self.generation,
            "source_snapshot": self.source, "byte_budget": 1048576, "ttl_ms": 3600000}))
        profile = self.make_profile()
        before = self.inventory()
        notice = self.hook(profile, "resume")
        self.assertEqual(notice["resume_preflight"]["reason"], "ACTIVE_CLAIM")
        self.assertTrue(notice["resume_preflight"]["lease_live"])
        self.assertFalse(notice["execution_authorized"])
        self.assertEqual(before, self.inventory())

    def test_corrupt_native_evidence_is_not_repaired_or_hidden(self):
        profile = self.make_profile()
        victim = next(p for p in (self.work / "objects").rglob("*") if p.is_file())
        victim.chmod(0o600)
        victim.write_bytes(b"synthetic corrupt object")
        before = self.inventory()
        notice = self.hook(profile, "resume")
        self.assertEqual(notice["context_state"], "BLOCKED")
        self.assertEqual(notice["code"], "NATIVE_FAILURE")
        self.assertEqual(before, self.inventory())

    def test_concurrent_hooks_do_not_change_work_or_retry_busy_reads(self):
        profile = self.make_profile()
        before = self.inventory()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.hook, profile, source) for source in ("startup", "resume")]
            for future in futures:
                notice = future.result(timeout=90)
                self.assertIn(notice["context_state"], ("AVAILABLE_FOR_EXPLICIT_FETCH", "BLOCKED"))
                self.assertFalse(notice["execution_authorized"])
                if notice["context_state"] == "BLOCKED":
                    self.assertFalse(notice["automatic_retry_allowed"])
        self.assertEqual(before, self.inventory())

    def test_npm_native_resolution_is_layout_independent_and_rejects_ambiguity(self):
        import hook_client_fixture as client
        prefix = self.root / "npm-fixture"
        packages = prefix / "node_modules"
        codex_root = packages / "@openai" / ("codex-" + client.npm_target())
        codex = codex_root / "vendor/fixture/bin/codex"
        claude = packages / "@anthropic-ai" / ("claude-code-" + client.npm_target()) / "claude"
        for path in (codex, claude):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic native filename fixture")
        self.assertEqual(client.npm_clients(prefix), {"codex-cli": codex, "claude-code": claude})
        duplicate = codex_root / "vendor/fixture/codex/codex"
        duplicate.parent.mkdir(parents=True)
        duplicate.write_bytes(b"duplicate")
        with self.assertRaises(ValueError):
            client.npm_clients(prefix)

    def test_real_codex_startup_resume_and_failure_without_trust_bypass(self):
        import hook_client_fixture as client
        binary = CLIENTS["codex-cli"]
        profile = self.make_profile("codex-cli", binary)
        binary = Path(profile.value["client_pin"]["path"])
        home = self.root / "codex-home"
        home.mkdir(mode=0o700)
        (home / "hooks.json").write_bytes(c.encoded(h.fragment(profile)))
        before = self.inventory()
        with client.provider() as (url, requests):
            config = ('model = "d3-fixture"\nmodel_provider = "fixture"\n'
                'cli_auth_credentials_store = "file"\nproject_doc_max_bytes = 0\n'
                '[features]\nhooks = true\nmemories = false\n'
                '[model_providers.fixture]\nname = "Local D3 fixture"\n'
                f'base_url = "{url}/v1"\nwire_api = "responses"\nrequires_openai_auth = false\n')
            with client.codex(binary, home, self.project, config) as transport:
                transport.send({"id": 2, "method": "hooks/list", "params": {"cwds": [str(self.project)]}})
                entries = transport.response(2)["data"][0]["hooks"]
                self.assertEqual(len(entries), 1)
                entry = entries[0]
                self.assertEqual(entry["trustStatus"], "untrusted")
                transport.send({"id": 3, "method": "thread/start", "params": {
                    "cwd": str(self.project), "approvalPolicy": "never", "sandbox": "read-only"}})
                untrusted_id = transport.response(3)["thread"]["id"]
                client.codex_turn(transport, 4, untrusted_id)
                self.assertFalse(client.contains_notice(requests))
            # Test-only owner approval of our exact generated command/hash. The
            # production fragment never seeds trust, writes it or bypasses it.
            config += '\n[hooks.state.' + json.dumps(entry["key"]) + ']\ntrusted_hash = ' + json.dumps(entry["currentHash"]) + '\n'
            requests.clear()
            with client.codex(binary, home, self.project, config) as transport:
                transport.send({"id": 2, "method": "hooks/list", "params": {"cwds": [str(self.project)]}})
                self.assertEqual(transport.response(2)["data"][0]["hooks"][0]["trustStatus"], "trusted")
                transport.send({"id": 3, "method": "thread/start", "params": {
                    "cwd": str(self.project), "approvalPolicy": "never", "sandbox": "read-only"}})
                thread_id = transport.response(3)["thread"]["id"]
                client.codex_turn(transport, 4, thread_id)
                self.assertTrue(client.contains_notice(requests, source="startup"))
            with client.codex(binary, home, self.project, config) as transport:
                transport.send({"id": 3, "method": "thread/resume", "params": {"threadId": thread_id,
                    "cwd": str(self.project), "approvalPolicy": "never", "sandbox": "read-only"}})
                transport.response(3)
                client.codex_turn(transport, 4, thread_id)
                self.assertTrue(client.contains_notice(requests, source="resume"))
            profile.path.write_bytes(profile.path.read_bytes() + b" ")
            requests.clear()
            with client.codex(binary, home, self.project, config) as transport:
                transport.send({"id": 3, "method": "thread/resume", "params": {"threadId": thread_id,
                    "cwd": str(self.project), "approvalPolicy": "never", "sandbox": "read-only"}})
                transport.response(3)
                client.codex_turn(transport, 4, thread_id)
                self.assertTrue(client.contains_notice(requests, code="HOOK_PROFILE_CHANGED"))
        self.assertEqual(before, self.inventory())

    def test_real_claude_startup_resume_and_failure(self):
        import hook_client_fixture as client
        binary = CLIENTS["claude-code"]
        profile = self.make_profile("claude-code", binary)
        binary = Path(profile.value["client_pin"]["path"])
        home = self.root / "claude-home"
        home.mkdir(mode=0o700)
        settings = home / "settings.json"
        settings.write_bytes(c.encoded(h.fragment(profile)))
        session_id = str(uuid.uuid4())
        before = self.inventory()
        with client.provider() as (url, requests):
            env = {**client.environment(home), "ANTHROPIC_BASE_URL": url}
            common = [str(binary), "--print", "--settings", str(settings), "--setting-sources", "",
                "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--tools", "",
                "--model", "claude-sonnet-4-6", "--output-format", "stream-json", "--verbose",
                "--include-hook-events", "--max-turns", "1"]
            settings.write_bytes(c.encoded({**h.fragment(profile), "disableAllHooks": True}))
            disabled = subprocess.run([*common, "Synthetic disabled-hook fixture: acknowledge without tools."],
                cwd=self.project, env=env, capture_output=True, timeout=120)
            self.assertEqual(disabled.returncode, 0, disabled.stderr[-1000:])
            self.assertFalse(client.contains_notice(requests))
            settings.write_bytes(c.encoded(h.fragment(profile)))
            requests.clear()
            for mode in ("startup", "resume", "failure"):
                if mode == "failure":
                    profile.path.write_bytes(profile.path.read_bytes() + b" ")
                    requests.clear()
                flags = ["--session-id", session_id] if mode == "startup" else ["--resume", session_id]
                result = subprocess.run([*common, *flags, "Synthetic local fixture: acknowledge without tools."],
                    cwd=self.project, env=env, capture_output=True, timeout=120)
                if result.returncode:
                    raise AssertionError((result.stdout[-3000:], result.stderr[-3000:]))
                if mode == "failure":
                    self.assertTrue(client.contains_notice(requests, code="HOOK_PROFILE_CHANGED"))
                else:
                    self.assertTrue(client.contains_notice(requests, source=mode))
        self.assertEqual(before, self.inventory())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cli")
    parser.add_argument("source")
    parser.add_argument("--codex-client", type=Path)
    parser.add_argument("--claude-client", type=Path)
    parser.add_argument("--client-prefix", type=Path)
    args = parser.parse_args(ARGUMENTS)
    CLIENTS = {name: path.resolve(strict=True) for name, path in (
        ("codex-cli", args.codex_client), ("claude-code", args.claude_client)) if path is not None}
    if args.client_prefix:
        if CLIENTS:
            parser.error("choose explicit clients or a temporary npm prefix, not both")
        import hook_client_fixture
        CLIENTS = hook_client_fixture.npm_clients(args.client_prefix)
    names = [name for name in D3.__dict__ if name.startswith("test_") and
        (not name.startswith("test_real_") or
         ("codex" in name and "codex-cli" in CLIENTS) or ("claude" in name and "claude-code" in CLIENTS))]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName("D3." + name, sys.modules[__name__]) for name in names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"schema": "golem.integration-hook-fixture-check.v1", "tests": result.testsRun,
        "status": "PASS" if result.wasSuccessful() else "FAIL", "real_clients_requested": sorted(CLIENTS),
        "provider": "LOOPBACK_SYNTHETIC_ONLY", "existing_product_works_used": False}))
    sys.exit(not result.wasSuccessful())
