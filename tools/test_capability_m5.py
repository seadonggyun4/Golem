"""M5 adversarial static checks over selected bytes, no inspected code execution."""
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
from capability_m5 import inspect_m5
from capability_m5_registry import M5
from capability_m5_backlog_registry import M5_BACKLOG

class ParallelProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[1]
        cls.files=tuple(SourceFile(p,hashlib.sha256((cls.root/p).read_bytes()).hexdigest(),(cls.root/p).read_bytes()) for p,_ in M5['pins'])
        cls.ledger=decode_identified_ledger((cls.root/'docs/mcp-m0-observations.json').read_bytes())
    def changed(self,path,old,new,shapes=False):
        files=[];model=copy.deepcopy(M5)
        for f in self.files:
            if f.path==path:
                self.assertIn(old,f.data);raw=f.data.replace(old,new,1);f=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
                model['pins']=tuple((p,f.sha256 if p==path else h) for p,h in model['pins'])
                if shapes:
                    nodes=_functions(ast.parse(raw));model['functions']=tuple((p,n,fingerprint(_shape(nodes[n])) if p==path else h) for p,n,h in model['functions'])
            files.append(f)
        return tuple(files),model
    def inspect(self,files=None,model=None,ledger=None,backlog=None):
        return inspect_m5(self.files if files is None else files,self.ledger if ledger is None else ledger,M5 if model is None else model,M5_BACKLOG if backlog is None else backlog)
    def test_actual_47_routes_remain_bounded_and_proposals_unimplemented(self):
        result=self.inspect();self.assertFalse(result.blockers,result.blockers)
        self.assertEqual((len(result.read_tools),len(result.action_tools),len(result.preparation_tools),result.backlog_count),(3,3,2,47))
        self.assertFalse(result.scheduler_implemented);self.assertFalse(result.merge_broker_implemented);self.assertEqual(result.actual_merge,'NOT_RUN')
    def test_missing_source_and_drift_fail(self):
        self.assertTrue(self.inspect(files=()).blockers)
        files,_=self.changed('tools/integration_parallel_actions.py',b'PARALLEL_TOOL',b'CHANGED');self.assertTrue(self.inspect(files=files).blockers)
    def test_owner_termination_and_scope_guards_survive_repin(self):
        for path,old in (
          ('tools/integration_parallel_hosts.py',b"c.require(approve_hosts is True,'OWNER_PARALLEL_HOST_APPROVAL_REQUIRED')"),
          ('tools/integration_parallel_hosts.py',b"c.require(c.sha(raw)==row['config']['sha256'],'PARALLEL_HOST_CONFIG_CHANGED')"),
          ('tools/integration_parallel_hosts.py',b"c.require(selected['termination'] is not None,'OPERATOR_TERMINATION_ATTESTATION_REQUIRED')"),
          ('tools/integration_parallel_hosts.py',b"c.require(len(matches)==1 and matches[0]['action_sha256']==entry['action']['sha256'],'PARALLEL_HOST_ACTION_PIN')"),
          ('tools/integration_parallel_preparations.py',b"c.require(visited==len(tasks),'PARALLEL_CYCLE')"),
          ('tools/integration_parallel_preparations.py',b"c.require(document.get('digest')==reference['digest'],'PARALLEL_SELECTION_DRIFT')")):
            files,model=self.changed(path,old,b'pass',shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_no_hash_or_qa_success_can_promote_readiness_or_merge(self):
        for old,new in ((b"'merge_authorized':False",b"'merge_authorized':True"),(b"'scheduler_state':'NOT_IMPLEMENTED'",b"'scheduler_state':'READY'"),(b"'qa_pass_verified':False",b"'qa_pass_verified':True")):
            files,model=self.changed('tools/integration_parallel_preparations.py',old,new,shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_model_refresh_cannot_add_raw_finish_or_general_command(self):
        for old,new in ((b"'reserve','start'",b"'reserve','finish','start'"),(b"'cohort-record')",b"'cohort-record','grant')")):
            files,model=self.changed('tools/integration_parallel_actions.py',old,new,shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_immutable_intent_cannot_be_bypassed_with_new_request(self):
        files,model=self.changed('tools/integration_mutations.py',b'if name in parallel.HOST_NAMES and previous.get("tool") == name',b'if False and previous.get("tool") == name',shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_schema_handoff_and_native_argv_binding_remain_exact(self):
        files,model=self.changed('tools/integration_service.py',b'parallel_reads.SCHEMAS["candidate_read"]',b'parallel_reads.SCHEMAS["inventory_read"]',shapes=True);self.assertTrue(self.inspect(files,model).blockers)
        files,model=self.changed('tools/integration_mutations.py',b'self.parallel_hosts.command(entry, value, output)',b'self.parallel_hosts.command(value, entry, output)',shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_native_termination_and_active_claim_checks_cannot_disappear(self):
        for old,new in ((b'if (terminating && !h->attested)',b'if (false)'),(b'as_active(log.state)',b'false')):
            files,model=self.changed('src/cli/candidate_host_runtime.c',old,new);self.assertTrue(self.inspect(files,model).blockers)
    def test_readonly_child_handle_and_historical_only_query_cannot_expand(self):
        files,model=self.changed('src/cli/candidate_host_runtime.c',b'golem_document_store_open(b->member.work_root, !readonly,',b'golem_document_store_open(b->member.work_root, true,');self.assertTrue(self.inspect(files,model).blockers)
        files,model=self.changed('tools/integration_mutations.py',b'self._admit(name, args, existing_only=True)',b'self._admit(name, args)',shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_backlog_ids_routes_and_unimplemented_flags_frozen(self):
        self.assertTrue(self.inspect(backlog=M5_BACKLOG[1:]).blockers)
        rows=copy.deepcopy(M5_BACKLOG);rows[0]['scheduler_implemented']=True
        self.assertTrue(self.inspect(backlog=rows).blockers)
        ledger=copy.deepcopy(self.ledger);cap=next(cap for cap in ledger['capabilities'] if cap['id']==M5_BACKLOG[0]['capability_id']);cap['current_routes']=[]
        self.assertTrue(self.inspect(ledger=ledger).blockers)

if __name__=='__main__':unittest.main()
