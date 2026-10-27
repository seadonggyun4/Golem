import hashlib
from pathlib import Path
import unittest
from dataclasses import replace
from capability_files import SourceFile
from capability_profile import Rule, scan_sources


class Wrapper(unittest.TestCase):
    def sample(self):
        root = Path(__file__).resolve().parents[1]
        files = tuple(SourceFile(p, hashlib.sha256((root/p).read_bytes()).hexdigest(), (root/p).read_bytes())
            for p in ('src/agent_session/coordinator.c', 'src/common/record_internal.h'))
        rule = Rule(files[0].path, files[0].sha256, 'NATIVE_OPERATION', 'golem_agent_session_call', 'op', files[1].sha256)
        return files, rule

    def test_actual_session_operations(self):
        files, rule = self.sample()
        result = scan_sources(files, [rule])
        self.assertEqual({o.selector for o in result.observations},
            {'context','next','reject_output','resume','status'})
        self.assertTrue(result.unresolved)

    def test_definition_drift_or_missing_blocks(self):
        files, rule = self.sample()
        for selected, r in ((files[:1], rule), (files, replace(rule, wrapper_definition_sha256='0'*64))):
            result = scan_sources(selected, [r])
            self.assertEqual(result.observations, ())
            self.assertEqual(result.unresolved[0][2], 'WRAPPER_DEFINITION_MISSING_OR_DRIFT')

    def test_unknown_wrapper_and_extra_arguments_not_guessed(self):
        files, rule = self.sample()
        for raw in (b'OTHER(golem_agent_session_call,(void),(x),d){strcmp(op,"x");}',
                    b'GOLEM_RECORDED_API(golem_agent_session_call,(void),(x),d,extra){strcmp(op,"x");}'):
            f = replace(files[0], data=raw, sha256=hashlib.sha256(raw).hexdigest())
            result = scan_sources((f, files[1]), [replace(rule, sha256=f.sha256)])
            self.assertEqual(result.observations, ())

    def test_changed_wrapper_body_is_rejected_even_after_repin(self):
        files, rule = self.sample()
        raw = files[1].data.replace(b'if (gr_status != GOLEM_OK) return gr_status;', b'/* ignore recording failure */')
        definition = replace(files[1], data=raw, sha256=hashlib.sha256(raw).hexdigest())
        result = scan_sources((files[0], definition), [replace(rule, wrapper_definition_sha256=definition.sha256)])
        self.assertFalse(result.observations)

    def test_forwarding_wrong_parameter_is_not_a_supported_wrapper(self):
        from capability_profile import _recorded_region
        with self.assertRaises(ValueError):
            _recorded_region('GOLEM_RECORDED_API(api,(int x),(y),d){return 0;}', 'api')


if __name__ == '__main__':
    unittest.main()

class AdditionalWrappers(unittest.TestCase):
    def test_callback_declarator_and_unsized_array_only_verify_forwarded_names(self):
        from capability_profile import _recorded_region
        source='GOLEM_RECORDED_API(api,(int x, golem_status (*publish)(void *, const golem_digest *), char *const argv[]),(x,publish,argv),d){return publish(x);}'
        self.assertIn('publish',_recorded_region(source,'api'))
        with self.assertRaises(ValueError):
            _recorded_region(source.replace('(x,publish,argv)','(x,other,argv)'),'api')
        with self.assertRaises(ValueError):
            _recorded_region(source.replace('argv[]','argv[computed()]'),'api')
    def test_actual_required_and_release_declarations(self):
        root=Path(__file__).resolve().parents[1]
        paths=('src/runtime/loop.c','src/common/record_internal.h')
        files=tuple(SourceFile(p,hashlib.sha256((root/p).read_bytes()).hexdigest(),(root/p).read_bytes()) for p in paths)
        from capability_profile import WRAPPER_SEMANTICS
        for name,macro in (('golem_runtime_cancel','GOLEM_RECORDED_REQUIRED_API'),('golem_runtime_free','GOLEM_RECORDED_RELEASE_API')):
            rule=Rule(files[0].path,files[0].sha256,'C_PUBLIC_DECLARATION',name,None,files[1].sha256,macro)
            scan=scan_sources(files,[rule])
            self.assertEqual(len(scan.observations),1)
            self.assertTrue(scan.unresolved)
            bad=scan_sources(files,[replace(rule,wrapper_definition_sha256='0'*64)])
            self.assertFalse(bad.observations)
        self.assertNotEqual(WRAPPER_SEMANTICS['GOLEM_RECORDED_REQUIRED_API'],WRAPPER_SEMANTICS['GOLEM_RECORDED_RELEASE_API'])
    def test_unsupported_macro_or_extra_argument(self):
        from capability_profile import _recorded_region
        from capability_source import ExtractionError
        with self.assertRaises(ExtractionError): _recorded_region('','x','OTHER')
        for macro in ('GOLEM_RECORDED_REQUIRED_API','GOLEM_RECORDED_RELEASE_API'):
            with self.assertRaises(ExtractionError):
                _recorded_region(macro+'(x,(void),(x),extra){return 0;}','x',macro)
