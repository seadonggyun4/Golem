"""Static and adversarial M4 fixture; inspected modules never imported/executed."""
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
from capability_m4 import inspect_m4
from capability_m4_registry import M4
from capability_m4_backlog_registry import M4_BACKLOG

class QualityProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[1]
        cls.files=tuple(SourceFile(p,hashlib.sha256((cls.root/p).read_bytes()).hexdigest(),(cls.root/p).read_bytes()) for p,_ in M4['pins'])
        cls.ledger=decode_identified_ledger((cls.root/'docs/mcp-m0-observations.json').read_bytes())
    def changed(self,path,old,new,shapes=False):
        files=[];model=copy.deepcopy(M4)
        for f in self.files:
            if f.path==path:
                self.assertIn(old,f.data);raw=f.data.replace(old,new,1);f=replace(f,data=raw,sha256=hashlib.sha256(raw).hexdigest())
                model['pins']=tuple((p,f.sha256 if p==path else h) for p,h in model['pins'])
                if shapes:
                    nodes=_functions(ast.parse(raw));model['functions']=tuple((p,n,fingerprint(_shape(nodes[n])) if p==path else h) for p,n,h in model['functions'])
            files.append(f)
        return tuple(files),model
    def inspect(self,files=None,model=None,ledger=None,backlog=None):
        return inspect_m4(self.files if files is None else files,self.ledger if ledger is None else ledger,M4 if model is None else model,M4_BACKLOG if backlog is None else backlog)
    def test_actual_tools_and_83_rows_remain_static_only(self):
        result=self.inspect();self.assertFalse(result.blockers,result.blockers)
        self.assertEqual(len(result.read_tools),4);self.assertEqual(len(result.action_tools),7);self.assertEqual(result.backlog_count,83)
        self.assertFalse(result.native_execution_verified);self.assertFalse(result.provider_authenticity_verified);self.assertEqual(result.external_service_calls,'NOT_RUN')
    def test_source_missing_or_unreviewed_byte_drift_blocks(self):
        self.assertTrue(self.inspect(files=()).blockers)
        files,model=self.changed('tools/integration_quality_actions.py',b'QUALITY_TOOL',b'WRONG');self.assertTrue(self.inspect(files=files).blockers)
    def test_independent_effect_pin_owner_and_scope_guards_survive_repin(self):
        cases=[('tools/integration_helper_contract.py',b"c.require(approve_helpers is True,'OWNER_HELPER_EFFECTS_APPROVAL_REQUIRED')"),('tools/integration_helper_contract.py',b"c.require(required<=set(row['effects']),'HELPER_EFFECTS_NOT_APPROVED')"),('tools/integration_helper_contract.py',b"c.require(c.sha(raw)==pin['sha256'],'HELPER_CREDENTIAL_CHANGED')"),('tools/integration_quality_actions.py',b"c.require(value['record'].get('work_id',entry['work_id'])==entry['work_id'],'QUALITY_RESEARCH_WORK_BINDING')"),('tools/integration_quality_reads.py',b"c.require(c.encoded(before)==c.encoded(after),'OBSERVATION_STALE')")]
        for path,old in cases:
            files,model=self.changed(path,old,b'pass',shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_schema_alias_and_read_handoff_swaps_block(self):
        for old,new in ((b'quality_reads.SCHEMAS["proof_read"]',b'quality_reads.SCHEMAS["cost_read"]'),(b'quality_reads.read(self, scope, name, args)',b'quality_reads.read(self, scope, args, name)')):
            files,model=self.changed('tools/integration_service.py',old,new,shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_helper_dispatch_arguments_and_post_capture_scope_cannot_change(self):
        files,model=self.changed('tools/integration_mutations.py',b'self.helpers.capture(entry, value, output)',b'self.helpers.capture(value, entry, output)',shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_new_request_id_cannot_bypass_helper_one_dispatch_guard(self):
        files,model=self.changed('tools/integration_mutations.py',b'previous.get("action") == entry',b'False',shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_accounting_scope_cannot_be_promoted_to_multi_stage_live_run(self):
        files,model=self.changed('tools/integration_quality_actions.py',b"len(inbox['snapshots'])==1",b"len(inbox['snapshots'])<=6",shapes=True);self.assertTrue(self.inspect(files,model).blockers)
    def test_native_verify_cannot_open_a_writable_store_after_pin_refresh(self):
        files,model=self.changed('src/cli/execution.c',b'golem_document_store_open(argv[3], false, NULL, &store, NULL)',b'golem_document_store_open(argv[3], true, NULL, &store, NULL)');self.assertTrue(self.inspect(files,model).blockers)
    def test_original_receipted_qa_host_cannot_disappear(self):
        files,model=self.changed('tools/integration_approval_host.c',b'golem_execution_call_receipted',b'fake_dispatch');self.assertTrue(self.inspect(files,model).blockers)
    def test_backlog_and_authority_flags_stay_frozen(self):
        self.assertTrue(self.inspect(backlog=M4_BACKLOG[1:]).blockers)
        ledger=copy.deepcopy(self.ledger);next(c for c in ledger['capabilities'] if c['id']==M4_BACKLOG[0]['capability_id'])['current_routes']=[];self.assertTrue(self.inspect(ledger=ledger).blockers)
        backlog=copy.deepcopy(M4_BACKLOG);backlog[0]['provider_authenticity_verified']=True;self.assertTrue(self.inspect(backlog=backlog).blockers)
    def test_no_new_tools_on_remote_allowlist(self):
        files,model=self.changed('tools/integration_gateway_contract.py',b'REMOTE_READ_NAMES = (',b'REMOTE_READ_NAMES = ("helper_execute", ');self.assertTrue(self.inspect(files,model).blockers)
    def test_stored_result_cannot_gain_dispatch_or_missing_intent_fallback_after_repin(self):
        for old,new in ((b"self._admit('execution_request', args, existing_only=True)",b"self._admit('execution_request', args, existing_only=False)"),
                        (b"result = self._result(output)",b"result = self._mutate('execution_request', args)"),
                        (b'c.require(not existing_only, "ORIGINAL_RESULT_NOT_FOUND")',b'pass')):
            files,model=self.changed('tools/integration_mutations.py',old,new,shapes=True)
            self.assertTrue(self.inspect(files,model).blockers)
