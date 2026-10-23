import asyncio
import copy
from importlib.metadata import PackageNotFoundError, version
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import integration_mcpb as bundle
import integration_transfer as transfer
import integration_mcp as branding
import integration_mcpb_entry as entry
import integration_contract as contract
import integration_registry as registry
import execution_record as records


class Bundle(unittest.TestCase):
    def test_extracted_bundle_real_stdio_with_no_project_grants(self):
        try:
            if version('mcp') != '2.3.0' or version('mcp-types') != '2.3.0':
                self.skipTest('Pinned MCP SDK required')
        except PackageNotFoundError:
            self.skipTest('Pinned MCP SDK required')
        from mcp.client import Client
        from mcp.client.stdio import StdioServerParameters
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            package = root / 'package'
            with zipfile.ZipFile(io.BytesIO(bundle.build())) as archive:
                archive.extractall(package)
            authority = registry.Registry.create(root / 'empty-registry', approve_local_owner=True)
            policy = {'schema': 'golem.integration-transfer.v1', 'registry': str(authority.root),
                'registry_identity': authority.root_identity, 'destination': 'MODEL_SERVICE',
                'destination_id': 'icon-test', 'data_class': 'APPROVED_WORK_CONTENT',
                'max_result_bytes': 4096, 'producer': transfer.producer(),
                'scopes': [{'binding': {'schema': 'golem.integration-client-binding.v1',
                    'project_id': 'unregistered', 'generation': 1, 'principal_id': 'owner',
                    'client_id': 'icon-test', 'assurance': 'LOCAL_COOPERATIVE'},
                    'work_ids': ['unregistered'], 'tools': ['projects_list'], 'recipients': []}]}
            transfer.validate(policy)
            raw = contract.encoded(policy)
            path = root / 'policy.json'
            records.save(path, raw)

            async def exercise():
                for mode in ('auto', 'legacy'):
                    params = StdioServerParameters(command=sys.executable,
                        args=[str(package / 'tools/integration_mcpb_entry.py')], cwd=str(package),
                        env={'GOLEM_TRANSFER_POLICY': str(path),
                             'GOLEM_REVIEWED_POLICY_SHA256': contract.sha(raw),
                             'GOLEM_APPROVE_DATA_TRANSFER': 'true'})
                    async with Client(params, mode=mode, read_timeout_seconds=30) as client:
                        self.assertEqual((await client.list_tools()).tools, [])
                        self.assertEqual(client.server_info.icons[0].src, branding.server_icons()[0].src)
                    stale = copy.deepcopy(policy)
                    stale['producer']['integration_service.py'] = '0' * 64
                    stale_raw = contract.encoded(stale)
                    stale_path = root / ('stale-' + mode + '.json')
                    records.save(stale_path, stale_raw)
                    for code, changes in (
                        ('OWNER_TRANSFER_APPROVAL_REQUIRED', {'GOLEM_APPROVE_DATA_TRANSFER': 'false',
                            'GOLEM_TRANSFER_POLICY': '/private/never-read-policy.json'}),
                        ('PRODUCER_CHANGED', {'GOLEM_TRANSFER_POLICY': str(stale_path),
                            'GOLEM_REVIEWED_POLICY_SHA256': contract.sha(stale_raw)}),
                        ('TRANSFER_POLICY_CHANGED', {'GOLEM_REVIEWED_POLICY_SHA256': 'f' * 64})):
                        blocked_params = StdioServerParameters(command=sys.executable,
                            args=params.args, cwd=str(package), env={**params.env, **changes})
                        async with Client(blocked_params, mode=mode, read_timeout_seconds=30) as client:
                            self.assertEqual([t.name for t in (await client.list_tools()).tools],
                                             ['golem_setup_status'])
                            result = await client.call_tool('golem_setup_status', {})
                            notice = json.loads(result.content[0].text)
                            self.assertEqual(notice['code'], code)
                            self.assertFalse(notice['project_access_enabled'])
                            self.assertFalse(notice['execution_authorized'])
                            self.assertNotIn(str(root), result.content[0].text)
                            self.assertNotIn('/private/never-read-policy.json', result.content[0].text)
                            denied = await client.call_tool('golem_work_inspect', {})
                            self.assertTrue(denied.is_error)
                            invalid = await client.call_tool('golem_setup_status', {'approve': True})
                            self.assertTrue(invalid.is_error)
                            self.assertEqual([t.name for t in (await client.list_tools()).tools],
                                             ['golem_setup_status'])
            asyncio.run(asyncio.wait_for(exercise(), timeout=60))
            self.assertEqual(list(authority.root.iterdir()), [])

    def test_explicit_consent_uses_unchanged_transfer_and_service(self):
        with patch.dict(os.environ, {'GOLEM_TRANSFER_POLICY': '/owner/policy.json',
                'GOLEM_REVIEWED_POLICY_SHA256': 'a' * 64,
                'GOLEM_APPROVE_DATA_TRANSFER': 'true'}), patch.object(entry, 'Transfer') as approved:
            service, notice = entry.configured_service()
            self.assertIsNone(notice)
            self.assertIs(service.transfer, approved.return_value)
            approved.assert_called_once_with(Path('/owner/policy.json'), 'a' * 64, approve_data_transfer=True)

    def test_malformed_policy_digest_never_constructs_project_service(self):
        for digest in ('', 'A' * 64, 'a' * 63, 'a' * 65):
            with patch.dict(os.environ, {'GOLEM_TRANSFER_POLICY': '/owner/policy.json',
                    'GOLEM_REVIEWED_POLICY_SHA256': digest,
                    'GOLEM_APPROVE_DATA_TRANSFER': 'true'}), \
                    patch.object(entry, 'Transfer') as approved:
                service, notice = entry.configured_service()
                self.assertIsNone(service)
                self.assertEqual(notice['code'], 'MCPB_REVIEWED_POLICY_REQUIRED')
                approved.assert_not_called()

    def test_reproducible_public_allowlist_and_original_producer_bytes(self):
        data = bundle.build()
        self.assertEqual(data, bundle.build())
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(set(archive.namelist()), {
                "manifest.json", "pyproject.toml", "assets/Golem-mcp.png", "LICENSE",
                "tools/integration_mcpb_entry.py", *('tools/' + n for n in transfer.PRODUCER_NAMES)})
            self.assertEqual(archive.read("assets/Golem-mcp.png"), branding.icon_bytes())
            for name in transfer.PRODUCER_NAMES:
                self.assertEqual(archive.read("tools/" + name),
                    (Path(bundle.__file__).parent / name).read_bytes())
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["icon"], "assets/Golem-mcp.png")
            self.assertFalse(manifest["user_config"]["approve_data_transfer"]["default"])
            self.assertNotIn("win32", manifest["compatibility"]["platforms"])

    def test_no_implicit_consent_or_policy(self):
        for consent in ("", "false", "1", "yes"):
            env = {k: v for k, v in os.environ.items() if not k.startswith("GOLEM_")}
            env.update(GOLEM_TRANSFER_POLICY="/not-enrolled/policy.json",
                       GOLEM_REVIEWED_POLICY_SHA256="a" * 64,
                       GOLEM_APPROVE_DATA_TRANSFER=consent)
            with patch.dict(os.environ, env, clear=True), patch.object(entry, 'Transfer') as approved:
                service, notice = entry.configured_service()
                self.assertIsNone(service)
                self.assertEqual(notice['code'], 'OWNER_TRANSFER_APPROVAL_REQUIRED')
                approved.assert_not_called()

    def test_setup_errors_never_disclose_exception_details_or_infer_approval(self):
        for error in (OSError('/private/secret'), contract.IntegrationError('unknown-private-data')):
            with patch.dict(os.environ, {'GOLEM_TRANSFER_POLICY': '/private/secret',
                    'GOLEM_REVIEWED_POLICY_SHA256': 'a' * 64, 'GOLEM_APPROVE_DATA_TRANSFER': 'true'}), \
                    patch.object(entry, 'Transfer', side_effect=error):
                service, notice = entry.configured_service()
                self.assertIsNone(service)
                self.assertEqual(notice['code'], 'SETUP_VALIDATION_FAILED')
                self.assertNotIn('private', json.dumps(notice))
                self.assertFalse(notice['approval_modified'])


if __name__ == "__main__":
    unittest.main()
