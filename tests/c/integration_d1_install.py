"""Actual installed config/launcher/MCP, disposable native Works only."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import unittest

ARGUMENTS = sys.argv[1:]
import integration_d2_mcp as fixtures
import workflow_integration as native
import integration_config as config
import integration_contract as c
import integration_install as install
import integration_launch as launch
import integration_registry as registry
import integration_reload_probe as runtime_adapter
import execution_record as records

CLIENTS = {}


class Install(fixtures.D2):
    def draft(self, identifier="installed"):
        path, digest = self.make_policy()
        state = self.root / "install-state"
        registry.Registry.create(state, approve_local_owner=True)
        self.manager = install.Installer(state)
        self.homes = {}
        targets = []
        for client in config.CLIENTS:
            home = self.root / client
            home.mkdir(mode=0o700)
            self.homes[client] = home
            target = (self.project if client == "claude-code-project" else home) / config.FILENAMES[client]
            target.write_bytes(b'# preserve comment\nmodel = "fixture"\n' if client == "codex-config" else b'{"unmanaged" : {"keep" : true}}\n')
            target.chmod(0o600)
            targets.append({"client": client, "config": str(target), "server_name": "golem",
                "runtime": runtime_adapter.runtime(), "transfer_policy": {"path": str(path), "sha256": digest}})
        return {"installation_id": identifier, "clients_stopped": "STOPPED_OWNER_ATTESTED", "targets": targets}

    def apply(self, plan):
        return self.manager.apply(plan, c.sha(c.encoded(plan)), approve_installation=True)

    def test_installed_three_profiles_real_mcp_and_readonly_removal(self):
        request = self.draft()
        original = {t["config"]: Path(t["config"]).read_bytes() for t in request["targets"]}
        before = self.inventory()
        result = self.apply(self.manager.plan("install", request))
        self.assertEqual(result["client_activation"], "NOT_OBSERVED")
        entries = []
        for target in request["targets"]:
            _, value, key = config.parsed(target["client"], Path(target["config"]).read_bytes())
            entries.append(value[key]["golem"])

        async def query():
            from mcp import Client
            from mcp.client.stdio import StdioServerParameters
            for index, entry in enumerate(entries):
                params = StdioServerParameters(command=entry["command"], args=entry["args"], cwd=str(self.root),
                    env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin", "PYTHONPATH": "/not-trusted"})
                async with Client(params, mode="legacy" if index == 1 else "auto", read_timeout_seconds=120) as client:
                    names = {t.name for t in (await client.list_tools()).tools}
                    self.assertIn("golem_work_inspect", names)
                    for view in ("status", "next"):
                        response = await client.call_tool("golem_work_inspect", {
                            "project_id": "project", "work_id": "example-work", "view": view})
                        self.assertFalse(response.is_error)
                        self.assertFalse(json.loads(response.content[0].text)["native_state_changed"])
        asyncio.run(asyncio.wait_for(query(), timeout=240))
        self.assertEqual(before, self.inventory())
        self.apply(self.manager.plan("remove", {"installation_id": "installed", "clients_stopped": "STOPPED_OWNER_ATTESTED"}))
        self.assertEqual(original, {p: Path(p).read_bytes() for p in original})
        self.assertEqual(before, self.inventory())
        path = self.manager.directory("installed") / "launch-0.json"
        with self.assertRaises(c.IntegrationError):
            launch.check(path, c.sha(path.read_bytes()))

    def test_bootstrap_scaffold_is_not_native_work_or_approval(self):
        state = registry.Registry.create(self.root / "bootstrap-state", approve_local_owner=True)
        self.manager = install.Installer(state.root)
        root = self.root / "empty-project"
        root.mkdir(mode=0o700)
        user = root / "unrelated.txt"
        user.write_bytes(b"unchanged")
        before = self.inventory()
        plan = self.manager.plan("bootstrap", {"bootstrap_id": "empty", "project_id": "empty", "root": str(root)})
        value = self.apply(plan)
        self.assertFalse(value["work_created"])
        self.assertFalse(value["grants_created"])
        self.assertEqual(before, self.inventory())
        self.assertEqual(user.read_bytes(), b"unchanged")
        with self.assertRaises(c.IntegrationError):
            self.manager.plan("bootstrap", plan["request"])

    def test_real_clients_parse_installed_scoped_configuration(self):
        request = self.draft()
        self.apply(self.manager.plan("install", request))
        before = self.inventory()
        for client, binary in CLIENTS.items():
            home = self.homes["codex-config" if client == "codex-cli" else "claude-code-project"]
            if client == "codex-cli":
                argv = [str(binary), "mcp", "list", "--json"]
            else:
                argv = [str(binary), "mcp", "get", "golem"]
            output = self.root / (client + "-config-observation")
            output.mkdir(mode=0o700)
            process = records.capture(argv, output, 60, cwd=self.project, observe_source=False, limit=262144,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "HOME": str(home),
                     "CODEX_HOME": str(home), "CLAUDE_CONFIG_DIR": str(home), "DISABLE_AUTOUPDATER": "1"})
            self.assertEqual(process["returncode"], 0, (output / "stderr.log").read_text())
            self.assertIn("golem", (output / "stdout.log").read_text())
        self.assertEqual(before, self.inventory())
        self.apply(self.manager.plan("remove", {"installation_id": "installed", "clients_stopped": "STOPPED_OWNER_ATTESTED"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cli")
    parser.add_argument("source")
    parser.add_argument("--client-prefix", type=Path)
    args = parser.parse_args(ARGUMENTS)
    if args.client_prefix:
        import hook_client_fixture
        CLIENTS = hook_client_fixture.npm_clients(args.client_prefix)
    names = [n for n in Install.__dict__ if n.startswith("test_") and
             (n != "test_real_clients_parse_installed_scoped_configuration" or CLIENTS)]
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName("Install." + n, sys.modules[__name__]) for n in names)
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
