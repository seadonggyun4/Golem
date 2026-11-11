"""Public MCPB packaging and isolated echo-fixture delegation, never a real client."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import integration_desktop_plugin as package


spec = importlib.util.spec_from_file_location('desktop_adapter', package.PACKAGE / 'scripts/launcher.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class DesktopPackaging(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.installed = self.root / 'Installed extension with spaces'
        self.installed.mkdir()
        self.outside = self.root / 'unrelated project'
        self.outside.mkdir()
        self.state = self.root / 'private state'
        with zipfile.ZipFile(io.BytesIO(package.build())) as archive:
            archive.extractall(self.installed)
        self.config = package.manifest()['server']['mcp_config']

    def run_adapter(self):
        args = [value.replace('${__dirname}', str(self.installed))
                .replace('${user_config.state}', str(self.state)) for value in self.config['args']]
        return subprocess.run([sys.executable, *args], cwd=self.outside,
                              input=b'fixture-only\x00\xff\n', capture_output=True, timeout=10)

    def configure(self, client='claude-desktop'):
        source = self.root / 'fixture-launcher.json'
        raw = json.dumps({'command': sys.executable, 'args': ['-I', '-B', '-c',
            'import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())']}).encode()
        source.write_bytes(raw)
        source.chmod(0o600)
        adapter.configure(self.state, source, hashlib.sha256(raw).hexdigest(), True, client)

    def test_deterministic_exact_allowlist_and_public_manifest(self):
        self.assertEqual(package.build(), package.build())
        with zipfile.ZipFile(io.BytesIO(package.build())) as archive:
            self.assertEqual(archive.namelist(), sorted((*package.FILES, 'manifest.json')))
            for name in package.FILES:
                self.assertEqual(archive.read(name), (package.PACKAGE / name).read_bytes())
                self.assertEqual(archive.getinfo(name).external_attr >> 16, 0o100644)
            manifest = json.loads(archive.read('manifest.json'))
        self.assertEqual((manifest['name'], manifest['version']), ('golem-prepare', '0.2.10'))
        self.assertEqual(manifest['author'], {'name': 'Golem contributors'})
        self.assertEqual(manifest['license'], 'PolyForm-Noncommercial-1.0.0')
        self.assertEqual(manifest['server']['entry_point'], 'scripts/launcher.py')
        self.assertEqual(self.config, {'command': 'python3', 'args': ['-I', '-B',
            '${__dirname}/scripts/launcher.py', 'serve', '--client', 'claude-desktop',
            '--state', '${user_config.state}']})
        self.assertEqual(set(manifest['user_config']), {'state'})
        self.assertTrue(manifest['user_config']['state']['required'])
        self.assertEqual(manifest['user_config']['state']['type'], 'directory')
        self.assertNotIn('default', manifest['user_config']['state'])
        self.assertNotIn('/Volumes/', json.dumps(manifest))
        self.assertNotIn('/Users/', json.dumps(manifest))

    def test_install_and_start_do_not_create_approval_or_launch_unconfigured(self):
        self.assertFalse(self.state.exists())
        result = self.run_adapter()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(json.loads(result.stderr)['state'], 'SETUP_REQUIRED')
        self.assertFalse(self.state.exists())

    def test_reviewed_desktop_state_preserves_stdio_from_unrelated_cwd(self):
        self.configure()
        record = self.state / 'golem-launcher/approval.json'
        before = record.read_bytes()
        self.assertEqual(json.loads(before)['schema'], 'golem.claude-desktop-launcher.v1')
        result = self.run_adapter()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'fixture-only\x00\xff\n')
        self.assertEqual(result.stderr, b'')
        self.assertEqual(record.read_bytes(), before)

    def test_codex_approval_is_not_reused_or_changed(self):
        self.configure('codex')
        record = self.state / 'golem-launcher/approval.json'
        before = record.read_bytes()
        result = self.run_adapter()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(json.loads(result.stderr)['code'], 'APPROVAL_FIELDS')
        self.assertEqual(record.read_bytes(), before)

    def test_cli_never_overwrites_existing_artifact(self):
        target = self.root / 'preserved.mcpb'
        target.write_bytes(b'prior artifact')
        result = subprocess.run([sys.executable, str(Path(package.__file__)),
            '--output', str(target)], capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), b'prior artifact')


if __name__ == '__main__':
    unittest.main()
