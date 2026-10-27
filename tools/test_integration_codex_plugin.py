import json
from pathlib import Path
import tempfile
import unittest

import integration_codex_plugin as plugin


class Packaging(unittest.TestCase):
    def test_exact_launcher_allowlist_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            launcher = root / 'launcher.json'
            value = {'command': '/reviewed/python', 'args': ['-I', '-B', '/reviewed/launch.py']}
            launcher.write_text(json.dumps(value))
            (root / 'secret-policy.json').write_text('not-for-package')
            output = root / 'package'
            plugin.build(output, launcher)
            paths = {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}
            self.assertEqual(len(paths), 10)
            self.assertIn("plugins/golem/skills/golem-work/SKILL.md", paths)
            self.assertIn("plugins/golem/skills/golem-setup/SKILL.md", paths)
            server = json.loads((output / 'plugins/golem/.mcp.json').read_text())
            self.assertEqual(server['mcpServers']['golem-local'], {'type': 'stdio', **value})
            self.assertFalse(any(b'not-for-package' in p.read_bytes()
                                 for p in output.rglob('*') if p.is_file()))
            with self.assertRaises(FileExistsError):
                plugin.build(output, launcher)

    def test_invalid_inputs_do_not_create_output(self):
        cases = ['{"command":"/a","command":"/b","args":[]}',
                 '{"command":"relative","args":[]}',
                 '{"command":"/a","args":[],"env":{"SECRET":"x"}}',
                 '{"command":"/a","args":["${HOME}"]}']
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for raw in cases:
                launcher = root / 'launcher.json'
                launcher.write_text(raw)
                with self.assertRaises(ValueError):
                    plugin.build(root / 'output', launcher)
                self.assertFalse((root / 'output').exists())
