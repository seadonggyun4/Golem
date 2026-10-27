import hashlib
import unittest

from capability_files import SourceFile
from capability_profile import Rule, scan_sources
from capability_obligations import residual_obligations


class ResidualObligations(unittest.TestCase):
    def test_calls_keep_arguments_and_do_not_self_discharge(self):
        raw=b'int route(char *op){if(!strcmp(op,"read")) return helper(op,1);return helper(op,2);}'
        source=SourceFile('src/fixture.c',hashlib.sha256(raw).hexdigest(),raw)
        rule=Rule(source.path,source.sha256,'CLI_ROUTE','route','op')
        scan=scan_sources((source,),(rule,))
        result=residual_obligations((source,),(rule,),scan)
        self.assertEqual(len(result),1)
        self.assertFalse(result[0].discharged)
        self.assertEqual(result[0].selectors,('read',))
        self.assertIn(('helper',('op','1')),result[0].direct_calls)
        self.assertIn(('helper',('op','2')),result[0].direct_calls)
        self.assertIn('helper',result[0].helper_or_external_calls_requiring_review)

    def test_indirection_remains_explicit(self):
        from capability_obligations import _direct_calls
        for body in ('x->call(a);','(*fn)(a);','table[i](a);'):
            self.assertTrue(_direct_calls(body)[1])

    def test_unregistered_python_inventory_never_imports_or_executes_it(self):
        raw=b'raise RuntimeError("do not execute")\ndef helper(): pass\nclass C:\n def method(self):pass\n'
        f=SourceFile('tools/fixture.py',hashlib.sha256(raw).hexdigest(),raw)
        out=residual_obligations((f,),(),scan_sources((f,),()))
        self.assertEqual(out[0].declarations,('helper','C.method'))
        self.assertFalse(out[0].discharged)
