"""M1 static/mutation fixtures only; no inspected program imports or execution."""
import ast
import copy
import hashlib
from pathlib import Path
import unittest
from dataclasses import replace
from capability_files import SourceFile
from capability_m1 import inspect_m1,_functions
from capability_m1_registry import M1
from capability_fallback import _shape
from capability_c_graph import fingerprint
from capability_m1_coverage import inspect_coverage
from capability_m1_coverage_registry import BASELINE_IDS,M1_COVERAGE
from capability_ledger import decode_identified_ledger

class M1Profiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[1]
        cls.files=tuple(SourceFile(p,hashlib.sha256((cls.root/p).read_bytes()).hexdigest(),(cls.root/p).read_bytes()) for p,_ in M1['pins'])
    def changed(self,path,old,new,*,review_shape=False):
        model=copy.deepcopy(M1);files=[]
        for f in self.files:
            if f.path==path:
                self.assertIn(old,f.data);raw=f.data.replace(old,new,1);f=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
                model['pins']=tuple((p,f.sha256 if p==path else h) for p,h in model['pins'])
                if review_shape:
                    nodes=_functions(ast.parse(raw))
                    model['functions']=tuple((p,n,fingerprint(_shape(nodes[n])) if p==path else h) for p,n,h in model['functions'])
            files.append(f)
        return tuple(files),model
    def test_actual_closed_read_profiles_have_no_runtime_claims(self):
        value=inspect_m1(self.files,M1)
        self.assertFalse(value.blockers);self.assertEqual(len(value.native_tools),15);self.assertEqual(len(value.resource_tools),6)
        self.assertFalse(value.client_delivery_verified);self.assertFalse(value.native_execution_verified);self.assertFalse(value.policy_satisfied)
    def test_missing_or_drifted_sources_block(self):
        self.assertTrue(inspect_m1((),M1).blockers)
        files,model=self.changed('tools/integration_reads.py',b'NO_COMPLETION_OR_EXECUTION_AUTHORITY_INFERRED',b'WRONG')
        self.assertTrue(inspect_m1(files,M1).blockers)
    def test_schema_key_alias_and_handler_argument_order_block_after_repin(self):
        cases=[('tools/integration_service.py',b'extended_reads.SCHEMAS["workflow_read"]',b'extended_reads.SCHEMAS["role_read"]'),
               ('tools/integration_service.py',b'extended_reads.read(self, scope, name, args)',b'extended_reads.read(self, scope, args, name)'),
               ('tools/integration_reads.py',b"base=['workflow',op,work,selection]",b"base=['run',op,work,selection]")]
        for path,old,new in cases:
            files,model=self.changed(path,old,new);self.assertTrue(inspect_m1(files,model).blockers)
    def test_independent_guards_still_block_after_function_review_is_replaced(self):
        cases=[('tools/integration_reads.py',b"c.require(value.get('operation')==operation,'READ_OPERATION_REQUIRED')",b'pass'),
               ('tools/integration_reads.py',b"c.require(c.encoded(before)==c.encoded(after),'OBSERVATION_STALE')",b'pass'),
               ('tools/integration_read_resources.py',b"c.require(approve_resources is True,'OWNER_READ_RESOURCE_APPROVAL_REQUIRED')",b'pass'),
               ('tools/integration_read_resources.py',b"c.require(c.sha(data)==digest,'READ_RESOURCE_DIGEST')",b'pass')]
        for path,old,new in cases:
            files,model=self.changed(path,old,new,review_shape=True);self.assertTrue(inspect_m1(files,model).blockers)
    def test_readonly_native_flags_are_independent_of_repin(self):
        for path,old,new in [('src/cli/completion.c',b'!check && !inspect',b'true'),('src/cli/reentry.c',b'!readonly',b'true'),('src/cli/reentry.c',b'call && !op',b'false')]:
            files,model=self.changed(path,old,new);self.assertTrue(inspect_m1(files,model).blockers)
    def test_remote_does_not_implicitly_adopt_new_local_tool(self):
        files,model=self.changed('tools/integration_gateway_contract.py',b"REMOTE_READ_NAMES = (",b"REMOTE_READ_NAMES = ('workflow_read', ")
        self.assertTrue(inspect_m1(files,model).blockers)
    def test_original_backlog_requires_every_disposition_and_retained_owner_boundary(self):
        ledger=decode_identified_ledger((self.root/'docs/mcp-m0-observations.json').read_bytes())
        self.assertFalse(inspect_coverage(ledger,self.files,BASELINE_IDS,M1_COVERAGE).blockers)
        self.assertTrue(inspect_coverage(ledger,self.files,BASELINE_IDS,M1_COVERAGE[1:]).blockers)
        bad=copy.deepcopy(M1_COVERAGE);bad[0]['tool']='does_not_exist'
        self.assertTrue(inspect_coverage(ledger,self.files,BASELINE_IDS,bad).blockers)
        cap=next(c for c in ledger['capabilities'] if c['id']=='surface.tools.agent_entrypoint.py.commands.read');cap['target_routes']=['MCP_READ']
        self.assertTrue(inspect_coverage(ledger,self.files,BASELINE_IDS,M1_COVERAGE).blockers)
