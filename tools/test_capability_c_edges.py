import hashlib
import unittest
from dataclasses import replace
from capability_files import SourceFile
from capability_c_edges import CEdgeRule,inspect_c_edge

class DirectEdges(unittest.TestCase):
    def data(self,body='if(argc>=2 && !strcmp(argv[1],"leaf")) return leaf(argc,argv);'):
        values={'src/caller.c':('int caller(int argc,char **argv){'+body+'}').encode(),
                'src/leaf.c':b'int leaf(int argc,char **argv){return 0;}',
                'src/leaf.h':b'int leaf(int argc,char **argv);'}
        files=tuple(SourceFile(p,hashlib.sha256(b).hexdigest(),b) for p,b in values.items())
        a,b,c=files
        return files,CEdgeRule(a.path,a.sha256,'caller','argv[1]',b.path,b.sha256,c.path,c.sha256,'leaf')
    def test_direct_call(self):
        files,r=self.data();v=inspect_c_edge(files,r)
        self.assertFalse(v.blockers);self.assertEqual(v.selectors,('leaf',));self.assertFalse(v.transitive_verified)
    def test_inverted_or_computed_selector_is_not_a_positive_route(self):
        for condition in ('strcmp(argv[1],"leaf")', 'strcmp(argv[1],"leaf") != 0',
                          'strcmp(argv[1],"leaf") == 1', 'enabled() && !strcmp(argv[1],"leaf")',
                          'argc>=2 || !strcmp(argv[1],"leaf")',
                          '!strcmp(argv[1],"leaf") && !strcmp(argv[1],"other")'):
            files, rule = self.data('if('+condition+') return leaf(argc,argv);')
            self.assertTrue(inspect_c_edge(files,rule).blockers, condition)

    def test_nested_route_and_local_shadow_are_not_direct_global_edges(self):
        for body in ('if(enabled){if(!strcmp(argv[1],"leaf")) return leaf(argc,argv);}',
                     'int (*leaf)(int,char **)=other; if(!strcmp(argv[1],"leaf")) return leaf(argc,argv);'):
            files, rule = self.data(body)
            self.assertTrue(inspect_c_edge(files,rule).blockers)
    def test_arguments_or_indirection_block(self):
        for body in ('if(!strcmp(argv[1],"leaf")) return leaf(argv,argc);',
                     'return handler(argc,argv);','if(!strcmp(argv[1],"leaf")){return leaf(argc,argv);}'):
            files,r=self.data(body);self.assertTrue(inspect_c_edge(files,r).blockers)
    def test_unconditional_second_call_not_hidden(self):
        files,r=self.data('if(!strcmp(argv[1],"leaf")) return leaf(argc,argv); return leaf(argc,argv);')
        self.assertTrue(inspect_c_edge(files,r).blockers)
    def test_missing_definition(self):
        files,r=self.data();self.assertTrue(inspect_c_edge(files[:1],r).blockers)
    def test_callee_definition_signature_must_match_forwarding(self):
        files,rule=self.data()
        raw=b'int leaf(char **argv,int argc){return 0;}'
        changed=replace(files[1],data=raw,sha256=hashlib.sha256(raw).hexdigest())
        self.assertTrue(inspect_c_edge((files[0],changed,files[2]),replace(rule,callee_sha256=changed.sha256)).blockers)
    def test_source_pin_drift(self):
        files,r=self.data();self.assertTrue(inspect_c_edge(files,replace(r,caller_sha256='0'*64)).blockers)
    def test_macro_decl_not_accepted(self):
        files,r=self.data(); c=files[2];raw=b'#define PROTOTYPE int leaf(int argc,char **argv);\n'
        changed=replace(c,data=raw,sha256=hashlib.sha256(raw).hexdigest())
        self.assertTrue(inspect_c_edge((*files[:2],changed),replace(r,declaration_sha256=changed.sha256)).blockers)
