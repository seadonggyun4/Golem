"""Static and adversarial M2 fixture; inspected modules never imported/executed."""
import ast
import copy
import hashlib
from dataclasses import replace
from pathlib import Path
import unittest
from capability_files import SourceFile
from capability_ledger import decode_identified_ledger
from capability_m1 import _functions
from capability_fallback import _shape
from capability_c_graph import fingerprint
from capability_m2 import inspect_m2
from capability_m2_registry import M2
from capability_m2_backlog_registry import M2_BACKLOG

class PreparationProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[1]
        cls.files=tuple(SourceFile(p,hashlib.sha256((cls.root/p).read_bytes()).hexdigest(),(cls.root/p).read_bytes()) for p,_ in M2['pins'])
        cls.ledger=decode_identified_ledger((cls.root/'docs/mcp-m0-observations.json').read_bytes())
    def changed(self,path,old,new,shapes=False):
        files=[];model=copy.deepcopy(M2)
        for f in self.files:
            if f.path==path:
                self.assertIn(old,f.data);raw=f.data.replace(old,new,1);f=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
                model['pins']=tuple((p,f.sha256 if p==path else h) for p,h in model['pins'])
                if shapes:
                    nodes=_functions(ast.parse(raw));model['functions']=tuple((p,n,fingerprint(_shape(nodes[n])) if p==path else h) for p,n,h in model['functions'])
            files.append(f)
        return tuple(files),model
    def inspect(self,files=None,model=None,ledger=None,backlog=None):
        return inspect_m2(self.files if files is None else files,self.ledger if ledger is None else ledger,M2 if model is None else model,M2_BACKLOG if backlog is None else backlog)
    def test_actual_profiles_keep_execution_and_owner_approval_unverified(self):
        v=self.inspect();self.assertFalse(v.blockers);self.assertEqual(len(v.tools),6);self.assertEqual(v.backlog_dependencies,134)
        self.assertFalse(v.approval_created);self.assertFalse(v.native_execution_verified);self.assertEqual(v.client_e2e,'NOT_RUN')
    def test_missing_or_drifted_sources_block(self):
        self.assertTrue(self.inspect(files=()).blockers)
        files,model=self.changed('tools/integration_preparations.py',b'REVIEW_REQUIRED',b'WRONG')
        self.assertTrue(self.inspect(files=files).blockers)
    def test_wrong_schema_reference_and_handler_argument_order_block(self):
        for old,new in ((b'preparations.SCHEMAS["action_prepare"]',b'preparations.SCHEMAS["plan_read"]'),(b'preparations.read(self, scope, name, args)',b'preparations.read(self, scope, args, name)')):
            files,model=self.changed('tools/integration_service.py',old,new,shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_independent_plan_and_approval_guards_survive_fixture_repin(self):
        cases=[('tools/integration_preparations.py',b"c.require(plan['basis']==current,'PREPARATION_STALE')"),
               ('tools/integration_preparations.py',b"c.require(service.preparation_plans.get(args['plan_id'])==args['plan_sha256'],'PREPARATION_INSTANCE_OR_REFERENCE')"),
               ('tools/integration_preparations.py',b"c.require(payload['kind']=='OWNER_ACTION','PREPARATION_OWNER_REVIEW_REQUIRED')"),
               ('tools/integration_mutation_contract.py',b'c.require(c.sha(data) == decision_pin["sha256"], "DECISION_CHANGED")')]
        for path,old in cases:
            files,model=self.changed(path,old,b'pass',shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_d4_dispatch_cannot_opt_into_unapproved_shape_or_default_it_on(self):
        for old,new in ((b'request = action_shape(entry, value)',b'request = action_shape(entry, value, allow_missing_approval=True)'),(b'allow_missing_approval=False',b'allow_missing_approval=True')):
            files,model=self.changed('tools/integration_mutation_contract.py',old,new,shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_validator_cannot_open_work_or_skip_public_core_validation(self):
        for old,new in ((b'golem_agent_request_validate((golem_bytes){input.data, input.size}, NULL)',b'GOLEM_OK'),(b'argc == 4 && !strcmp(argv[2], "validate")',b'argc == 4 && !strcmp(argv[2], "call")')):
            files,model=self.changed('src/cli/agent_session.c',old,new);self.assertTrue(self.inspect(files,model).blockers)
    def test_new_local_prepare_names_cannot_enter_remote_allowlist(self):
        files,model=self.changed('tools/integration_gateway_contract.py',b'REMOTE_READ_NAMES = (',b'REMOTE_READ_NAMES = ("action_prepare", ')
        self.assertTrue(self.inspect(files,model).blockers)
    def test_backlog_coverage_does_not_remove_or_promote_later_actions(self):
        self.assertTrue(self.inspect(backlog=M2_BACKLOG[1:]).blockers)
        ledger=copy.deepcopy(self.ledger);cap=next(c for c in ledger['capabilities'] if c['id']==M2_BACKLOG[0]['capability_id']);cap['target_routes']=['MCP_READ']
        self.assertTrue(self.inspect(ledger=ledger).blockers)
