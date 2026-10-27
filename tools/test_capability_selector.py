import hashlib
import unittest
from unittest.mock import patch

from capability_evidence import python_declaration, inspect_references
from capability_files import SourceFile
from test_capability_ledger import metadata_sample


class Selectors(unittest.TestCase):
    def test_direct_function_and_method_lines(self):
        raw = b'def test_one(): pass\nclass Suite:\n    async def test_two(self): pass\n'
        self.assertEqual(python_declaration(raw, 'test_one'), (1, None))
        self.assertEqual(python_declaration(raw, 'Suite.test_two'), (3, None))

    def test_no_execution_or_decorator_evaluation(self):
        raw = b'raise RuntimeError()\n@unknown()\ndef test_one(): pass'
        self.assertEqual(python_declaration(raw, 'test_one'), (3, None))

    def test_duplicate_function_method_or_class(self):
        for raw, selector in [(b'def f(): pass\ndef f(): pass', 'f'),
            (b'class C:\n def f(self): pass\n def f(self): pass', 'C.f'),
            (b'class C:\n def f(self): pass\nclass C: pass', 'C.f')]:
            self.assertIsNone(python_declaration(raw, selector)[0])

    def test_nested_conditional_inherited_dynamic_not_resolved(self):
        raw = b'def outer():\n def f(): pass\nclass Base:\n def m(self): pass\nclass Child(Base): pass\nif True:\n def conditional(): pass\ndynamic = lambda: None'
        for selector in ('f', 'outer.f', 'Child.m', 'conditional', 'dynamic'):
            self.assertIsNone(python_declaration(raw, selector)[0])

    def test_unsupported_selector_forms(self):
        for selector in (None, 'file.py::test_one', 'test_one[param]', 'C.f.extra', '', ' f', 'class'):
            self.assertIsNone(python_declaration(b'def test_one(): pass', selector)[0])

    def test_invalid_source(self):
        for raw in (b'\xff', b'def (', b'\0'):
            self.assertEqual(python_declaration(raw, 'f'), (None, 'PYTHON_SOURCE_UNPARSEABLE'))

    def test_reference_integration_never_promotes_execution(self):
        value = metadata_sample()
        raw = b'def test_not_executed(): pass'
        file = SourceFile('tests/not-present.py', hashlib.sha256(raw).hexdigest(), raw)
        with patch('capability_evidence.read_sources', return_value=(file,)):
            result = inspect_references(value, '/root', [file.path])
        self.assertFalse(result[0].locator_unverified)
        self.assertEqual(result[0].declaration_line, 1)
        self.assertTrue(result[0].execution_unverified)
        self.assertTrue(result[0].sufficiency_unverified)
        self.assertTrue(result[1].locator_unverified)

    def test_doc_and_non_python_stay_unverified(self):
        value = metadata_sample()
        value['capabilities'][0]['test_refs'][0]['path'] = 'tests/example.c'
        files = tuple(SourceFile(p, hashlib.sha256(b'def test_not_executed(): pass').hexdigest(),
                                 b'def test_not_executed(): pass')
                      for p in ('tests/example.c', 'docs/not-present.md'))
        with patch('capability_evidence.read_sources', return_value=files):
            result = inspect_references(value, '/root', [f.path for f in files])
        self.assertTrue(all(r.locator_unverified for r in result))
        self.assertEqual(result[1].locator_diagnostic, 'ANCHOR_UNSPECIFIED')


if __name__ == '__main__':
    unittest.main()
