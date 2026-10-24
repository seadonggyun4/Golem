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
        self.assertTrue(self.configure()['changed'])
        self.assertFalse(self.configure()['changed'])
        data = b'protocol input\n\x00\xff'
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), 'serve',
            '--state', str(self.state)], env=os.environ, input=data,
            capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, data)
        self.assertEqual(result.stderr, b'')
        self.assertFalse(adapter.status(self.state)['project_access_verified'])

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
        with patch.object(adapter.os, 'execv') as execute:
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
            with patch.object(adapter.os, 'execv') as execute:
                with self.assertRaises(BlockingIOError):
                    adapter.serve(self.state)
                execute.assert_not_called()

    def test_record_tampering_blocks_launch(self):
        self.configure()
        path = self.state / 'golem-launcher/approval.json'
        value = json.loads(path.read_text())
        value['launcher'] = json.dumps({'command': '/bin/false', 'args': []})
        path.write_text(json.dumps(value))
        with patch.object(adapter.os, 'execv') as execute:
            with self.assertRaisesRegex(adapter.SetupError, 'APPROVAL_DIGEST'):
                adapter.serve(self.state)
            execute.assert_not_called()

    def test_setup_errors_are_private_and_do_not_emit_protocol_stdout(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(SCRIPT), 'serve',
            '--state', str(self.root / 'missing')], capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        notice = json.loads(result.stderr)
        self.assertEqual(notice['state'], 'SETUP_REQUIRED')
        self.assertNotIn(str(self.root), result.stderr.decode())

    def test_catalog_is_public_and_skill_and_branding_resolve(self):
        catalog = json.loads((ROOT / '.agents/plugins/marketplace.json').read_text())
        package = ROOT / catalog['plugins'][0]['source']['path']
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
