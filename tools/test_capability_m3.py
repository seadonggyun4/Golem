"""Static and adversarial M3 fixture; inspected modules never imported/executed."""
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
from capability_m3 import inspect_m3
from capability_m3_registry import M3
from capability_m3_backlog_registry import M3_BACKLOG

class TaskProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[1]
        cls.files=tuple(SourceFile(p,hashlib.sha256((cls.root/p).read_bytes()).hexdigest(),(cls.root/p).read_bytes()) for p,_ in M3['pins'])
        cls.ledger=decode_identified_ledger((cls.root/'docs/mcp-m0-observations.json').read_bytes())
    def changed(self,path,old,new,shapes=False):
        files=[];model=copy.deepcopy(M3)
        for f in self.files:
            if f.path==path:
                self.assertIn(old,f.data);raw=f.data.replace(old,new,1);f=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
                model['pins']=tuple((p,f.sha256 if p==path else h) for p,h in model['pins'])
                if shapes:
                    nodes=_functions(ast.parse(raw));model['functions']=tuple((p,n,fingerprint(_shape(nodes[n])) if p==path else h) for p,n,h in model['functions'])
            files.append(f)
        return tuple(files),model
    def inspect(self,files=None,model=None,ledger=None,backlog=None):
        return inspect_m3(self.files if files is None else files,self.ledger if ledger is None else ledger,M3 if model is None else model,M3_BACKLOG if backlog is None else backlog)
    def test_actual_twenty_and_sixty_remain_static_only(self):
        result=self.inspect();self.assertFalse(result.blockers,result.blockers)
        self.assertEqual(len(result.tools),20);self.assertEqual(result.backlog_count,60)
        self.assertFalse(result.native_execution_verified);self.assertFalse(result.policy_satisfaction_verified);self.assertEqual(result.client_e2e,'NOT_RUN')
    def test_sources_missing_or_drifted_fail(self):
        self.assertTrue(self.inspect(files=()).blockers)
        files,model=self.changed('tools/integration_task_actions.py',b'TASK_TOOL',b'WRONG')
        self.assertTrue(self.inspect(files=files).blockers)
    def test_independent_closed_shape_owner_scope_and_discovery_guards_survive_repin(self):
        for expression in (b"c.require(name in NAMES,'TASK_TOOL')",b'c._validate(value,c.obj(fields))',b"c.require(value[field]['session_id']==entry['session_id'],'NATIVE_OWNER_MAPPING')",b"c.require(not target.exists() and not target.is_symlink(),'TASK_DESTINATION_EXISTS')",b"c.require(isinstance(repo,dict) and repo.get('root')==project['root'],'TASK_DISCOVERY_SCOPE')"):
            files,model=self.changed('tools/integration_task_actions.py',expression,b'pass',shapes=True)
            self.assertTrue(self.inspect(files,model).blockers)
    def test_d4_and_m2_argument_swaps_block(self):
        for path,old,new in (('tools/integration_mutation_contract.py',b'tasks.authorize(entry, request, project)',b'tasks.authorize(entry, project, request)'),('tools/integration_prepare_builders.py',b'tasks.draft(args,observed,key)',b'tasks.draft(args,key,observed)')):
            files,model=self.changed(path,old,new,shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_fixed_native_route_change_is_not_automatically_certified(self):
        files,model=self.changed('tools/integration_task_actions.py',b"['session','call',root,path]",b"['session','resume',root,path]")
        self.assertTrue(self.inspect(files,model).blockers)
    def test_added_core_validators_cannot_skip_parser_even_with_pin_refresh(self):
        for path,old in (('src/cli/role.c',b'golem_role_request_validate'),('src/cli/approval.c',b'golem_approval_request_validate'),('src/cli/document.c',b'golem_work_spec_validate'),('src/cli/agent_session.c',b'golem_session_binding_request_validate')):
            files,model=self.changed(path,old,b'fake_parser');self.assertTrue(self.inspect(files,model).blockers)
    def test_new_native_storage_cannot_disappear(self):
        for path,old in (('src/cli/lineage.c',b'golem_lineage_store'),('src/cli/adapter.c',b'golem_adapter_noop_run_stage')):
            files,model=self.changed(path,old,b'fake_apply');self.assertTrue(self.inspect(files,model).blockers)
    def test_missing_route_unimplemented_capability_and_approval_promotion_block(self):
        self.assertTrue(self.inspect(backlog=M3_BACKLOG[1:]).blockers)
        ledger=copy.deepcopy(self.ledger);cap=next(c for c in ledger['capabilities'] if c['id']==M3_BACKLOG[0]['capability_id']);cap['current_routes']=[]
        self.assertTrue(self.inspect(ledger=ledger).blockers)
        backlog=copy.deepcopy(M3_BACKLOG);backlog[0]['client_e2e']='PASS';self.assertTrue(self.inspect(backlog=backlog).blockers)
    def test_new_actions_are_not_remotely_enabled(self):
        files,model=self.changed('tools/integration_gateway_contract.py',b'REMOTE_READ_NAMES = (',b'REMOTE_READ_NAMES = ("work_create", ')
        self.assertTrue(self.inspect(files,model).blockers)
