"""Disposable adapter tests; no user configuration or native Work is accessed."""
import hashlib
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'plugins/golem/scripts/launcher.py'
spec = importlib.util.spec_from_file_location('golem_plugin_adapter', SCRIPT)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class Adapter(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / 'data'
        self.source = self.root / 'launcher.json'
        self.value = {'command': sys.executable,
            'args': ['-I', '-B', '-c', 'import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())']}
        self.raw = json.dumps(self.value).encode()
        self.source.write_bytes(self.raw)
        self.source.chmod(0o600)
        self.pin = hashlib.sha256(self.raw).hexdigest()

    def configure(self):
        return adapter.configure(self.state, self.source, self.pin, True)

    def test_real_exec_preserves_stdio_and_exact_args(self):
        # Non-relay clients preserve arbitrary bytes. Codex's real JSON-RPC
        # transport is covered by the installed-manifest and relay fixtures.
        self.assertTrue(adapter.configure(self.state,self.source,self.pin,True,'portable')['changed'])
        self.assertFalse(adapter.configure(self.state,self.source,self.pin,True,'portable')['changed'])
        data = b'protocol input\n\x00\xff'
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), 'serve',
            '--state', str(self.state),'--client','portable'], env=os.environ, input=data,
            capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, data)
        self.assertEqual(result.stderr, b'')
        self.assertFalse(adapter.status(self.state,'portable')['project_access_verified'])

    def test_approval_digest_and_schema_fail_before_writes(self):
        for pin, approved in ((self.pin, False), ('0' * 64, True)):
            with self.assertRaises(adapter.SetupError):
                adapter.configure(self.state, self.source, pin, approved)
            self.assertFalse(self.state.exists())
        for raw in (b'{"command":"/x","command":"/y","args":[]}',
                    b'{"command":"/x","args":[],"env":{}}',
                    b'{"command":"relative","args":[]}',
                    b'{"command":"/x","args":["${HOME}"]}'):
            self.source.write_bytes(raw)
            with self.assertRaises(adapter.SetupError):
                adapter.configure(self.state, self.source, adapter.digest(raw), True)
            self.assertFalse(self.state.exists())

    def test_existing_approval_is_not_rebound(self):
        self.configure()
        path = self.state / 'golem-launcher/approval.json'
        before = path.read_bytes()
        raw = json.dumps({'command': '/bin/false', 'args': []}).encode()
        self.source.write_bytes(raw)
        with self.assertRaisesRegex(adapter.SetupError, 'EXISTING_APPROVAL_DIFFERS'):
            adapter.configure(self.state, self.source, adapter.digest(raw), True)
        self.assertEqual(path.read_bytes(), before)

    def test_partial_publication_blocks_without_exec_or_cleanup(self):
        self.configure()
        pending = self.state / 'golem-launcher/approval.pending'
        pending.write_bytes(b'partial')
        with patch.object(adapter,'run_relay') as execute:
            with self.assertRaisesRegex(adapter.SetupError, 'PARTIAL_PUBLICATION'):
                adapter.serve(self.state)
            execute.assert_not_called()
        self.assertEqual(pending.read_bytes(), b'partial')

    def test_unsafe_files_and_links_are_rejected(self):
        self.source.chmod(0o644)
        with self.assertRaisesRegex(adapter.SetupError, 'UNSAFE_PRIVATE_FILE'):
            self.configure()
        self.source.chmod(0o600)
        alias = self.root / 'alias.json'
        alias.symlink_to(self.source)
        with self.assertRaisesRegex(adapter.SetupError, 'SYMLINK'):
            adapter.configure(self.state, alias, self.pin, True)
        alias.unlink()
        os.link(self.source, alias)
        with self.assertRaisesRegex(adapter.SetupError, 'UNSAFE_PRIVATE_FILE'):
            self.configure()

    def test_interrupted_publication_retains_evidence(self):
        with patch.object(adapter.os, 'link', side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                self.configure()
        pending = self.state / 'golem-launcher/approval.pending'
        self.assertTrue(pending.exists())
        with self.assertRaisesRegex(adapter.SetupError, 'PARTIAL_PUBLICATION'):
            self.configure()

    def test_live_owner_lock_blocks_launch_without_exec(self):
        self.configure()
        path = self.state / 'golem-launcher/owner.lock'
        with path.open('r+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(adapter,'run_relay') as execute:
                with self.assertRaises(BlockingIOError):
                    adapter.serve(self.state)
                execute.assert_not_called()

    def test_record_tampering_blocks_launch(self):
        self.configure()
        path = self.state / 'golem-launcher/approval.json'
        value = json.loads(path.read_text())
        value['launcher'] = json.dumps({'command': '/bin/false', 'args': []})
        path.write_text(json.dumps(value))
        with patch.object(adapter,'run_relay') as execute:
            with self.assertRaisesRegex(adapter.SetupError, 'APPROVAL_DIGEST'):
                adapter.serve(self.state)
            execute.assert_not_called()

    def test_status_works_when_host_denies_writable_lock_open(self):
        self.configure()
        original = os.open
        def readonly_host(path, flags, *args, **kwargs):
            if Path(path).name == 'owner.lock' and flags & os.O_ACCMODE != os.O_RDONLY:
                raise PermissionError('readonly host')
            return original(path, flags, *args, **kwargs)
        with patch.object(adapter.os, 'open', side_effect=readonly_host):
            self.assertEqual(adapter.status(self.state)['state'], 'CONFIGURED')

    def test_inspect_state_reports_exact_layout_and_bytes_without_execution(self):
        self.configure()
        path = self.state / 'golem-launcher/approval.json'
        before = {str(p.relative_to(self.state)): p.read_bytes()
                  for p in self.state.rglob('*') if p.is_file()}
        approval_pin = adapter.digest(path.read_bytes())
        # A misleading file at the state root must never be accepted.
        decoy = self.state / 'approval.json'
        decoy.write_text('{"not":"the adapter record"}')
        decoy.chmod(0o600)
        with patch.object(adapter, 'run_relay') as relay, \
             patch.object(adapter.os, 'execve') as execute:
            observed = adapter.inspect_state(self.state, 'codex', approval_pin, self.pin)
        relay.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(observed, {
            'schema': 'golem.launcher-inspection.v1', 'state': 'CONFIGURED',
            'client': 'codex', 'adapter_state': str(self.state),
            'approval_path': str(path), 'approval_sha256': approval_pin,
            'launcher_sha256': self.pin, 'adapter_version': adapter.ADAPTER_VERSION,
            'project_access_verified': False, 'execution_authorized': False})
        self.assertNotIn('command', observed)
        self.assertNotIn('args', observed)
        for name, raw in before.items():
            self.assertEqual((self.state / name).read_bytes(), raw)

    def test_inspect_state_rejects_wrong_client_pin_and_incomplete_state(self):
        with self.assertRaises(OSError):
            adapter.inspect_state(self.state)
        self.assertFalse(self.state.exists())
        self.configure()
        for kwargs, code in (
            ({'client': 'claude-desktop'}, 'APPROVAL_FIELDS'),
            ({'expected_approval_sha256': '0' * 64}, 'INSPECT_APPROVAL_CHANGED'),
            ({'expected_launcher_sha256': '0' * 64}, 'INSPECT_LAUNCHER_CHANGED'),
            ({'expected_approval_sha256': 'not-a-pin'}, 'EXPECTED_DIGEST_REQUIRED'),
            ({'expected_launcher_sha256': True}, 'EXPECTED_DIGEST_REQUIRED'),
        ):
            with self.subTest(code=code), self.assertRaisesRegex(adapter.SetupError, code):
                adapter.inspect_state(self.state, **kwargs)
        pending = self.state / 'golem-launcher/approval.pending'
        pending.write_bytes(b'preserve partial result')
        with self.assertRaisesRegex(adapter.SetupError, 'PARTIAL_PUBLICATION'):
            adapter.inspect_state(self.state)
        self.assertEqual(pending.read_bytes(), b'preserve partial result')

    def test_inspect_state_preserves_lock_and_private_file_validation(self):
        self.configure()
        lock = self.state / 'golem-launcher/owner.lock'
        with lock.open('r+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                adapter.inspect_state(self.state)
        alias = self.root / 'state-alias'
        alias.symlink_to(self.state, target_is_directory=True)
        with self.assertRaisesRegex(adapter.SetupError, 'SYMLINK'):
            adapter.inspect_state(alias)
        path = self.state / 'golem-launcher/approval.json'
        value = json.loads(path.read_bytes())
        value['launcher'] = json.dumps({'command': '/bin/false', 'args': []})
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(adapter.SetupError, 'APPROVAL_DIGEST'):
            adapter.inspect_state(self.state)

    def test_inspect_state_cli_is_a_read_only_contract_without_launcher_arguments(self):
        self.value['args'].append('private-argument-sentinel')
        self.raw = json.dumps(self.value).encode()
        self.source.write_bytes(self.raw)
        self.pin = adapter.digest(self.raw)
        self.configure()
        path = self.state / 'golem-launcher/approval.json'
        before = path.read_bytes()
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), 'inspect-state',
            '--client', 'codex', '--state', str(self.state),
            '--expected-approval-sha256', adapter.digest(before),
            '--expected-launcher-sha256', self.pin], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b'')
        self.assertEqual(json.loads(result.stdout)['approval_path'], str(path))
        self.assertNotIn(b'private-argument-sentinel', result.stdout)
        self.assertEqual(path.read_bytes(), before)

    def test_setup_errors_are_private_and_do_not_emit_protocol_stdout(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), 'serve',
            '--state', str(self.root / 'missing')], capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        notice = json.loads(result.stderr)
        self.assertEqual(notice['state'], 'SETUP_REQUIRED')
        self.assertNotIn(str(self.root), result.stderr.decode())

    def test_legacy_catalog_is_empty_and_product_components_resolve(self):
        catalog = json.loads((ROOT / '.agents/plugins/marketplace.json').read_text())
        self.assertEqual(catalog['name'], 'golem')
        self.assertEqual(catalog['plugins'], [])
        package = ROOT / 'plugins/golem'
        manifest = json.loads((package / '.codex-plugin/plugin.json').read_text())
        skill = manifest['extensions']['com.openai']['onboardingSkill']
        self.assertTrue((package / skill).is_file())
        self.assertTrue((package / manifest['skills']).is_dir())
        self.assertEqual(manifest['interface']['developerName'], 'Donggyun Seo')
        self.assertEqual(manifest['interface']['websiteURL'], 'https://github.com/seadonggyun4/Golem')
        self.assertEqual((package / 'assets/icon.png').read_bytes(), (ROOT / 'assets/Golem-mcp.png').read_bytes())
        self.assertEqual((package / 'LICENSE').read_bytes(), (ROOT / 'LICENSE').read_bytes())
        mcp = json.loads((package / '.mcp.json').read_text())
        server = mcp['mcpServers']['golem-local']
        self.assertEqual(server['args'], ['-I', '-B', 'scripts/launcher.py', 'serve'])
        self.assertNotIn('env', server)
        self.assertFalse((package / 'hooks').exists())
