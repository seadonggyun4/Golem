import hashlib
import unittest
from dataclasses import replace
from pathlib import Path

from capability_files import SourceFile
from capability_profile import Rule, scan_sources
from capability_source import ExtractionError


class Profiles(unittest.TestCase):
    def sample(self, text, kind='CLI_ROUTE', entrypoint='dispatch', subject='op', path='src/example.c'):
        data = text.encode() if isinstance(text, str) else text
        source = SourceFile(path, hashlib.sha256(data).hexdigest(), data)
        return source, Rule(path, source.sha256, kind, entrypoint, subject)

    def test_function_scope_excludes_other_functions_and_comments(self):
        s, r = self.sample('int other(){strcmp(op,"wrong");} int dispatch(){/*strcmp(op,"fake");*/ strcmp(op,"right");}')
        result = scan_sources([s], [r])
        self.assertEqual([o.selector for o in result.observations], ['right'])
        self.assertFalse(result.coverage_complete)
        self.assertTrue(result.unresolved)

    def test_prototype_does_not_replace_definition(self):
        s, r = self.sample('int dispatch(void); int dispatch(void){strcmp(op,"right");}')
        self.assertEqual(len(scan_sources([s], [r]).observations), 1)

    def test_public_declaration_not_callback_or_macro(self):
        for text, count in [('int golem_read(void);', 1), ('int (*golem_read)(void);', 0),
                            ('WRAP(golem_read, (void));', 0), ('int x = golem_read(void);', 0),
                            ('typedef int golem_read(void);', 0), ('golem_read(void);', 0), ('int golem_read(void) {}', 0)]:
            s, r = self.sample(text, 'C_PUBLIC_DECLARATION', 'golem_read', None)
            self.assertEqual(len(scan_sources([s], [r]).observations), count)

    def test_unsupported_dispatch_never_empty_success(self):
        for text in ['int dispatch(){switch(op){}}', 'WRAP(dispatch, (void), {strcmp(op,"x");})',
                     'int dispatch(){strcmp(op,NAME);}', 'int dispatch(){strcmp(op,"x");',
                     'int dispatch(){table[op]();}', 'int dispatch(){strncmp(op,"x",1);}']:
            s, r = self.sample(text)
            result = scan_sources([s], [r])
            self.assertEqual(result.observations, ())
            self.assertTrue(result.unresolved)

    def test_preprocessing_never_proves_runtime_support(self):
        s, r = self.sample('#if 0\nint dispatch(){strcmp(op,"disabled");}\n#endif')
        result = scan_sources([s], [r])
        self.assertFalse(result.coverage_complete)
        self.assertTrue(result.unresolved)

    def test_python_does_not_execute_and_dynamic_scope_remains(self):
        s, r = self.sample('TOOLS={"read": fail()}\nTOOLS.update(other)\nraise Exception()',
                           'MCP_TOOL_DECLARATION', 'TOOLS', 'mapping', 'tools/sample.py')
        result = scan_sources([s], [r])
        self.assertEqual(result.observations[0].selector, 'read')
        self.assertEqual(result.unresolved[0][2], 'DECLARATION_ONLY_DYNAMIC_SCOPE_UNVERIFIED')

    def test_hash_pin_drift_requires_review_even_same_names(self):
        s, r = self.sample('int dispatch(){strcmp(op,"x");}')
        changed = s.data + b' /* changed */'
        result = scan_sources([replace(s, data=changed, sha256=hashlib.sha256(changed).hexdigest())], [r])
        self.assertEqual(result.observations, ())
        self.assertEqual(result.unresolved[0][2], 'SOURCE_REVIEW_DRIFT')

    def test_unregistered_missing_empty_are_not_complete(self):
        s, r = self.sample('int dispatch(){strcmp(op,"x");}')
        self.assertEqual(scan_sources([s], []).unresolved[0][2], 'UNREGISTERED_SOURCE')
        self.assertEqual(scan_sources([], [r]).unresolved[0][2], 'SOURCE_NOT_SELECTED')
        self.assertFalse(scan_sources([], []).coverage_complete)

    def test_duplicate_rules_sources_and_forged_hash_rejected(self):
        s, r = self.sample('int dispatch(){strcmp(op,"x");}')
        for sources, rules in [([s, s], [r]), ([s], [r, r]), ([replace(s, sha256='0'*64)], [r])]:
            with self.assertRaises(ExtractionError):
                scan_sources(sources, rules)

    def test_bytes_invalid_utf8_explicit(self):
        s, r = self.sample(b'\xff')
        self.assertEqual(scan_sources([s], [r]).unresolved[0][2], 'SOURCE_NOT_UTF8')

    def test_distinct_entrypoints_preserve_identity(self):
        s, r = self.sample('int dispatch(){strcmp(op,"x");} int other(){strcmp(op,"x");}')
        result = scan_sources([s], [r, replace(r, entrypoint='other')])
        self.assertEqual(len({o.id for o in result.observations}), 2)

    def test_real_macro_wrapped_session_is_unresolved_not_inferred(self):
        raw = (Path(__file__).resolve().parents[1] / 'src/agent_session/coordinator.c').read_bytes()
        s = SourceFile('src/agent_session/coordinator.c', hashlib.sha256(raw).hexdigest(), raw)
        r = Rule(s.path, s.sha256, 'NATIVE_OPERATION', 'golem_agent_session_call', 'op')
        result = scan_sources([s], [r])
        self.assertFalse(result.observations)
        self.assertTrue(result.unresolved)


if __name__ == '__main__':
    unittest.main()
