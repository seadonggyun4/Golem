import hashlib
import unittest
from unittest.mock import patch
from dataclasses import replace
from capability_files import SourceFile
from capability_handler import HandlerRule,inspect_handler

class Handler(unittest.TestCase):
    def fixture(self, body):
        raw=('NAMES=("one","two")\nclass Service:\n    def call(self,name):\n'+''.join('        '+l+'\n' for l in body.splitlines())).encode()
        f=SourceFile('tools/service.py',hashlib.sha256(raw).hexdigest(),raw)
        return (f,),HandlerRule(f.path,f.sha256,'NAMES',False,f.path,f.sha256,'Service.call','name')

    def test_literal_comparisons_without_execution(self):
        files,r=self.fixture('if name == "one": pass\nif name in ("two",): pass')
        with patch('builtins.open',side_effect=AssertionError('no IO')):
            self.assertTrue(inspect_handler(files,r).linked)

    def test_else_is_not_inferred(self):
        files,r=self.fixture('if name == "one": pass\nelse: pass')
        v=inspect_handler(files,r)
        self.assertEqual(v.missing,('two',)); self.assertIn('ELSE_FALLBACK',[b[0] for b in v.blockers])

    def test_computed_and_helpers_block(self):
        files,r=self.fixture('if name in registry: pass\nhelper(name)')
        codes={b[0] for b in inspect_handler(files,r).blockers}
        self.assertTrue({'COMPUTED_COMPARISON','UNREGISTERED_HELPER'}<=codes)

    def test_drift(self):
        files,r=self.fixture('pass')
        self.assertFalse(inspect_handler(files,replace(r,handler_sha256='0'*64)).linked)

    def test_nested_and_alias_do_not_certify(self):
        files,r=self.fixture('alias=name\ndef inner():\n    return name == "two"\nif name == "one": pass')
        v=inspect_handler(files,r)
        self.assertEqual(v.missing,('two',));self.assertFalse(v.linked)

    def test_extra_literal(self):
        files,r=self.fixture('if name in ("one","two","extra"): pass')
        self.assertEqual(inspect_handler(files,r).extra,('extra',))

    def test_actual_handlers_preserve_fallback_and_helper_gaps(self):
        from pathlib import Path
        from capability_handler_registry import HANDLERS
        root=Path(__file__).resolve().parents[1]
        paths={p for r in HANDLERS for p in (r.declaration_path,r.handler_path)}
        files=tuple(SourceFile(p,hashlib.sha256((root/p).read_bytes()).hexdigest(),(root/p).read_bytes()) for p in paths)
        d2,d4=(inspect_handler(files,r) for r in HANDLERS)
        self.assertEqual(d2.missing,('history_read',))
        self.assertEqual(set(d2.compared),set(d2.declared)-{'history_read'})
        self.assertIn('workflow_read',d2.compared)
        self.assertFalse(d2.linked)
        self.assertFalse(d4.linked)
        self.assertIn('UNREGISTERED_HELPER',{v[0] for v in d4.blockers})
