import copy
import hashlib
import unittest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from capability_files import SourceFile, SourceReadError
from capability_evidence import inspect_references
from test_capability_ledger import metadata_sample


class ReferenceFiles(unittest.TestCase):
    def test_bytes_hash_not_execution_or_locator_validation(self):
        ledger = metadata_sample()
        before = copy.deepcopy(ledger)
        raw = b'raise RuntimeError("do not run")\n'
        file = SourceFile('tests/not-present.py', hashlib.sha256(raw).hexdigest(), raw)
        with patch('capability_evidence.read_sources', return_value=(file,)) as reader:
            result = inspect_references(ledger, '/explicit/root', [file.path])
        reader.assert_called_once()
        self.assertEqual(result[0].observed_sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(result[0].byte_length, len(raw))
        self.assertTrue(result[0].file_bytes_verified)
        self.assertTrue(result[0].locator_unverified)
        self.assertTrue(result[0].execution_unverified)
        self.assertTrue(result[0].sufficiency_unverified)
        self.assertEqual(result[0].locator, 'test_not_executed')
        self.assertEqual(result[1].diagnostic, 'REFERENCE_NOT_SELECTED')
        self.assertEqual(ledger, before)

    def test_boundary_options_forwarded_without_expansion(self):
        with patch('capability_evidence.read_sources', return_value=()) as reader:
            inspect_references(metadata_sample(), '/root', ['tests/explicit.py'],
                reviewed_new=['tests/explicit.py'], reviewed_fixtures=[], protected_paths=['private.json'])
        reader.assert_called_once_with('/root', ['tests/explicit.py'],
            reviewed_new=['tests/explicit.py'], reviewed_fixtures=[], protected_paths=['private.json'])

    def test_reader_failure_never_partial_success(self):
        paths = ['tests/not-present.py', 'docs/not-present.md']
        for code in ('SOURCE_EXCLUDED', 'SOURCE_CHANGED', 'SOURCE_GIT_REFUSED', 'SOURCE_OPEN_FAILED'):
            with self.subTest(code=code), patch('capability_evidence.read_sources', side_effect=SourceReadError(code)):
                result = inspect_references(metadata_sample(), '/root', paths)
                self.assertTrue(all(r.diagnostic == code for r in result))
                self.assertTrue(all(not r.file_bytes_verified and r.observed_sha256 is None for r in result))

    def test_missing_selection_does_not_auto_discover(self):
        with patch('capability_evidence.read_sources', return_value=()) as reader:
            result = inspect_references(metadata_sample(), '/root', [])
        self.assertEqual(reader.call_args.args[1], [])
        self.assertTrue(all(r.diagnostic == 'REFERENCE_NOT_SELECTED' for r in result))

    def test_shared_file_preserves_each_reference_and_order(self):
        ledger = metadata_sample()
        path = 'tests/not-present.py'
        ledger['capabilities'][0]['test_refs'].append({'path': path, 'selector': 'other'})
        raw = b'not interpreted'
        file = SourceFile(path, hashlib.sha256(raw).hexdigest(), raw)
        with patch('capability_evidence.read_sources', return_value=(file,)):
            result = inspect_references(ledger, '/root', [path])
        self.assertEqual([r.locator for r in result], ['test_not_executed', 'other', None])
        self.assertEqual(result[0].observed_sha256, result[1].observed_sha256)

    def test_bad_ledger_rejected_before_io(self):
        ledger = metadata_sample()
        ledger['capabilities'][0]['doc_refs'][0]['path'] = '../secret'
        with patch('capability_evidence.read_sources') as reader:
            with self.assertRaises(ValueError):
                inspect_references(ledger, '/root', [])
        reader.assert_not_called()

    def test_actual_reader_selected_new_files_and_excluded_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(['/usr/bin/git', 'init', '-q', str(root)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (root / 'tests').mkdir()
            (root / 'docs').mkdir()
            raw = b'raise RuntimeError("must not execute")'
            (root / 'tests/not-present.py').write_bytes(raw)
            (root / 'docs/not-present.md').write_bytes(b'# heading')
            paths = ['tests/not-present.py', 'docs/not-present.md']
            result = inspect_references(metadata_sample(), str(root), paths, reviewed_new=paths)
            self.assertTrue(all(r.file_bytes_verified for r in result))
            self.assertEqual(result[0].observed_sha256, hashlib.sha256(raw).hexdigest())
            self.assertEqual((root / paths[0]).read_bytes(), raw)
            ledger = metadata_sample()
            ledger['capabilities'][0]['doc_refs'][0]['path'] = '.golem/private.json'
            result = inspect_references(ledger, str(root), ['.golem/private.json'])
            self.assertFalse(result[1].file_bytes_verified)
            self.assertIsNotNone(result[1].diagnostic)

    def test_empty_references_no_pass_declaration(self):
        ledger = metadata_sample()
        ledger['capabilities'][0].update(test_refs=[], doc_refs=[])
        with patch('capability_evidence.read_sources', return_value=()):
            self.assertEqual(inspect_references(ledger, '/root', []), ())


if __name__ == '__main__':
    unittest.main()
