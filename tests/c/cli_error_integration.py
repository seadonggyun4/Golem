"""CLI failure boundary contracts, independent of host clock/socket support."""
import errno
import fcntl
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI, HELPER, ROOT = map(Path, sys.argv[1:4])
del sys.argv[1:4]


class Errors(unittest.TestCase):
    def run_command(self, binary, *args, **kwargs):
        return subprocess.run([str(binary), *map(str, args)], stderr=subprocess.PIPE,
                              stdout=kwargs.pop("stdout", subprocess.PIPE),
                              text=True, timeout=20, **kwargs)

    def envelope(self, result):
        rows = [json.loads(line) for line in result.stderr.splitlines()
                if line.startswith('{')]
        errors = [r for r in rows if r.get('schema') == 'golem.cli-error.v1']
        self.assertEqual(len(errors), 1, result.stderr)
        row = errors[0]
        self.assertEqual(row['exit_code'], result.returncode)
        self.assertFalse(row['retry_effect'])
        self.assertFalse(row['execution_authorized'])
        return row

    def test_native_status_catalog(self):
        header = (ROOT / 'include/golem/error.h').read_text()
        names = re.findall(r'^\s*(GOLEM_ERR_\w+)\s*=\s*(\d+)', header, re.M)
        self.assertGreaterEqual(len(names), 33)
        for name, value in names:
            with self.subTest(code=name):
                row = self.envelope(self.run_command(HELPER, value))
                self.assertEqual(row['code'], name)
                self.assertEqual(row['status_code'], int(value))
                self.assertTrue(row['next_action'])
                self.assertIsNone(row['errno'])
                self.assertEqual(row['command'], 'unknown')

    def test_unknown_status(self):
        row = self.envelope(self.run_command(HELPER, '999'))
        self.assertEqual(row['status_code'], 999)
        self.assertEqual(row['code'], 'CLI_FAILED')

    def test_system_observations_are_not_inferred_causes(self):
        row = self.envelope(self.run_command(HELPER, 'system'))
        self.assertEqual(row['system_errors_role'], 'OBSERVATIONS_NOT_INFERRED_CAUSES')
        self.assertIsNone(row['errno'])
        self.assertEqual(row['system_errors'][0]['operation'], 'write')
        self.assertEqual(row['system_errors'][0]['errno'], errno.ENOSPC)
        self.assertEqual(row['system_errors'][0]['errno_name'], 'ENOSPC')
        self.assertIsNone(row['system_errors'][1]['errno'])
        self.assertEqual(row['system_errors'][1]['kind'], 'validation')

    def test_allocation_fallback(self):
        row = self.envelope(self.run_command(HELPER, 'allocation'))
        self.assertEqual(row['code'], 'CLI_DIAGNOSTIC_UNAVAILABLE')

    def test_reset_and_diagnostic_encoding(self):
        row = self.envelope(self.run_command(HELPER, 'reset'))
        self.assertEqual(row['system_errors'], [])
        self.assertIsNone(row['errno'])
        self.assertIsNone(row['status_code'])
        row = self.envelope(self.run_command(HELPER, 'diagnostic'))
        self.assertIsNone(row['errno'])
        self.assertEqual(row['diagnostic'], 'quote"\nline')
        self.assertEqual(row['offset'], 17)
        self.assertTrue(row['diagnostic_truncated'])
        self.assertEqual(row['phase'], 'parse')

    def test_usage_boundaries(self):
        for command in ('session', 'work', 'doctor', 'approval', 'execution',
                        'role', 'research', 'completion', 'reentry', 'document',
                        'output', 'candidate', 'adapter', 'evidence', 'private-secret'):
            with self.subTest(command=command):
                result = self.run_command(CLI, command)
                row = self.envelope(result)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(row['code'], 'CLI_USAGE')
                self.assertEqual(row['command'], command if command != 'private-secret' else 'unknown')

    def test_missing_request_and_original_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            result = self.run_command(CLI, 'session', 'call', root, root / 'missing')
            row = self.envelope(result)
            self.assertEqual(row['code'], 'GOLEM_ERR_NOT_FOUND')
            self.assertEqual(row['errno'], errno.ENOENT)
            self.assertEqual(row['phase'], 'request_open')
            self.assertIn('golem.session-error.v1', result.stderr)
            self.assertTrue(any(e['component'] == 'evidence.path' and e['operation'] == 'openat'
                                and e['errno'] == errno.ENOENT for e in row['system_errors']))
            self.assertNotIn(str(root), json.dumps(row['system_errors']))

    def test_success_is_silent(self):
        result = self.run_command(HELPER, '0')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, '')

    def test_parse_and_lock_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            request = root / 'request.json'
            request.write_text('{')
            row = self.envelope(self.run_command(CLI, 'session', 'call', root, request))
            self.assertEqual(row['code'], 'GOLEM_ERR_PARSE')
            self.assertIsNone(row['errno'])
            self.assertEqual(row['phase'], 'request_parse')
            with request.open('rb') as locked:
                fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
                row = self.envelope(self.run_command(CLI, 'session', 'call', root, request))
            self.assertEqual(row['code'], 'GOLEM_ERR_JOURNAL_BUSY')
            self.assertEqual(row['phase'], 'request_lock')
            self.assertIn(row['errno'], (errno.EAGAIN, errno.EWOULDBLOCK))

    def test_stdout_failure(self):
        with open('/dev/null', 'rb') as readonly:
            result = self.run_command(CLI, '--version', stdout=readonly)
        row = self.envelope(result)
        self.assertEqual(row['code'], 'GOLEM_ERR_IO')


if __name__ == '__main__':
    unittest.main()
