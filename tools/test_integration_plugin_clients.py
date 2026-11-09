"""Disposable multi-client plugin fixtures; never open a real Golem connection."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'plugins/golem'
SCRIPT = PACKAGE / 'scripts/launcher.py'
spec = importlib.util.spec_from_file_location('golem_client_adapter', SCRIPT)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class ClientPackaging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir(mode=0o700)
        self.source = self.root / 'launcher.json'
        self.selected = {'command': sys.executable, 'args': ['-I', '-B', '-c',
            'import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())']}
        self.raw = json.dumps(self.selected).encode()
        self.source.write_bytes(self.raw)
        self.source.chmod(0o600)
        self.pin = hashlib.sha256(self.raw).hexdigest()

    def states(self):
        with patch.object(adapter.Path, 'home', return_value=self.home):
            return {client: adapter.default_state(client) for client in adapter.CLIENTS}

    def configure(self, client):
        state = self.states()[client]
        state.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        return state, adapter.configure(state, self.source, self.pin, True, client)

    def test_manifests_share_identity_and_resolve_local_components(self):
        manifests = [json.loads((PACKAGE / path).read_text()) for path in
                     ('.codex-plugin/plugin.json', '.claude-plugin/plugin.json', 'plugin.json')]
        for manifest in manifests:
            self.assertEqual((manifest['name'], manifest['version']), ('golem', '0.2.8'))
            self.assertEqual(manifest['license'], 'PolyForm-Noncommercial-1.0.0')
        for manifest in manifests[:2]:
            self.assertTrue((PACKAGE / manifest['skills']).is_dir())
        for manifest in (manifests[0], manifests[2]):
            extension = manifest['extensions']['com.openai']
            self.assertTrue((PACKAGE / extension['onboardingSkill']).is_file())
        self.assertEqual(manifests[0]['interface'],
                         manifests[2]['extensions']['com.openai']['interface'])
        self.assertTrue((PACKAGE / manifests[0]['mcpServers']).is_file())

    def test_client_declarations_select_separate_default_approvals(self):
        codex = json.loads((PACKAGE / '.mcp.json').read_text())['mcpServers']['golem-local']
        claude = json.loads((PACKAGE / '.claude-plugin/plugin.json').read_text())['mcpServers']['golem-local']
        portable = json.loads((PACKAGE / 'mcp.json').read_text())['mcpServers']['golem-local']
        self.assertEqual(codex['startup_timeout_sec'], 60)
        self.assertEqual(codex['args'], ['-I', '-B', 'scripts/launcher.py', 'serve'])
        self.assertEqual(claude['args'], ['-I', '-B',
            '${CLAUDE_PLUGIN_ROOT}/scripts/launcher.py', 'serve', '--client', 'claude-code'])
        self.assertEqual(portable['args'], ['-I', '-B', 'scripts/launcher.py',
                                          'serve', '--client', 'portable'])
        for declaration in (codex, claude, portable):
            self.assertEqual(declaration['command'], 'python3')
            self.assertNotIn('env', declaration)
            self.assertNotIn('--state', declaration['args'])
        self.assertFalse((PACKAGE / 'hooks').exists())

    def test_default_state_is_distinct_and_codex_path_is_backward_compatible(self):
        states = self.states()
        self.assertEqual(len(set(states.values())), 4)
        for client, state in states.items():
            self.assertEqual(state, self.home / '.local/share/golem' / f'{client}-plugin')
        with self.assertRaisesRegex(adapter.SetupError, 'CLIENT_REQUIRED'):
            adapter.default_state('../codex')

    def test_unconfigured_clients_do_not_create_state_or_execute(self):
        for client in adapter.CLIENTS:
            with self.subTest(client=client):
                stderr = io.StringIO()
                with patch.object(adapter.Path, 'home', return_value=self.home), \
                     patch.object(sys, 'argv', [str(SCRIPT), 'serve', '--client', client]), \
                     patch.object(adapter.os, 'execv') as execute, \
                     contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
                    adapter.main()
                execute.assert_not_called()
                self.assertFalse(self.states()[client].exists())
                notice = json.loads(stderr.getvalue())
                self.assertEqual(notice['state'], 'SETUP_REQUIRED')
                self.assertFalse(notice['execution_authorized'])

    def test_existing_codex_record_is_neither_imported_nor_cross_client_accepted(self):
        state, _ = self.configure('codex')
        record = state / 'golem-launcher/approval.json'
        before = record.read_bytes()
        self.assertEqual(json.loads(before)['schema'], 'golem.codex-launcher.v1')
        for client in ('claude-code', 'portable', 'claude-desktop'):
            with self.subTest(client=client), patch.object(adapter.os, 'execv') as execute:
                with self.assertRaises(OSError):
                    adapter.serve(self.states()[client], client)
                with self.assertRaisesRegex(adapter.SetupError, 'APPROVAL_FIELDS'):
                    adapter.serve(state, client)
                execute.assert_not_called()
                self.assertFalse(self.states()[client].exists())
        self.assertEqual(record.read_bytes(), before)
        self.assertEqual(adapter.status(state)['launcher_sha256'], self.pin)

    def test_each_client_requires_explicit_exact_launcher_selection(self):
        for client in adapter.CLIENTS:
            state = self.states()[client]
            for pin, approved in ((self.pin, False), ('0' * 64, True)):
                with self.subTest(client=client, approved=approved), \
                     self.assertRaises(adapter.SetupError):
                    adapter.configure(state, self.source, pin, approved, client)
                self.assertFalse(state.exists())
            state, configured = self.configure(client)
            self.assertTrue(configured['changed'])
            before = (state / 'golem-launcher/approval.json').read_bytes()
            with patch.object(adapter.os, 'execv') as execute:
                adapter.serve(state, client)
                execute.assert_called_once_with(self.selected['command'],
                    [self.selected['command'], *self.selected['args']])
            self.assertEqual((state / 'golem-launcher/approval.json').read_bytes(), before)

    def test_real_manifest_commands_resolve_installed_root_and_preserve_stdio(self):
        installed = self.root / 'Plugin path with spaces'
        (installed / 'scripts').mkdir(parents=True)
        shutil.copyfile(SCRIPT, installed / 'scripts/launcher.py')
        outside = self.root / 'unrelated-project'
        outside.mkdir()
        declarations = {
            'codex': json.loads((PACKAGE / '.mcp.json').read_text())['mcpServers']['golem-local'],
            'claude-code': json.loads((PACKAGE / '.claude-plugin/plugin.json').read_text())['mcpServers']['golem-local'],
            'portable': json.loads((PACKAGE / 'mcp.json').read_text())['mcpServers']['golem-local'],
        }
        for client, declaration in declarations.items():
            with self.subTest(client=client):
                state, _ = self.configure(client)
                args = [arg.replace('${CLAUDE_PLUGIN_ROOT}', str(installed))
                        for arg in declaration['args']]
                cwd = installed / declaration['cwd'] if 'cwd' in declaration else outside
                data = f'fixture-only:{client}\n'.encode() + b'\x00\xff'
                result = subprocess.run([sys.executable, *args, '--state', str(state)],
                    cwd=cwd, input=data, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, data)
                self.assertEqual(result.stderr, b'')


if __name__ == '__main__':
    unittest.main()
