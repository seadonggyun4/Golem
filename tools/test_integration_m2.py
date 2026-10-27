"""M2 disposable scopes and fixed native validator doubles; no client/Work E2E."""
import base64
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import integration_contract as c
import integration_service as service
import integration_preparations as prep
import integration_prepare_builders as builders
import integration_mutation_contract as actions
import integration_mutations as mutations
import test_integration_d2 as fixture

class Preparations(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter'):
        locals()[name]=getattr(fixture.D2,name)
    def setUp(self):
        fixture.D2.setUp(self);self.api=service.Service(self.adapter());self.captures=[];self.preparation_count=0
        self.status={'sequence':1,'state':{'selection_id':'selection','active':None},'lease_live':False,
                     'resume_preflight':{'reason':'CURRENT','owner_session_id':'','lease_live':False}}
        self.following={'sequence':1,'document_generation':2,'action':'NEXT_ACTION','reason':'CLAIM_REQUIRED'}
        self.record={'schema':'golem.work-record.v1','work_id':'a','work_specification':{'work_id':'a'},'status':{'sequence':1},
                     'document_head':'a'*64,'agent_head':'b'*64,'documents':[{'document_id':'selection','revision':1,'digest':'c'*64,'metadata':{'source_snapshot':'0'*64}}],'journal':[]}
    def observed(self,scope,work_id,operation,*unused):
        return {'result':copy.deepcopy({'record':self.record,'status':self.status,'next':self.following}[operation])}
    def capture(self,argv,output,*unused,**kw):
        self.captures.append(argv)
        self.assertEqual(argv[:3],[str(self.cli),'--output-mode','full']);self.assertFalse(kw['observe_source']);self.assertEqual(kw['env'],service.backend.ENVIRONMENT)
        self.assertNotIn(str(self.work),argv[3:] if argv[3:5]!=['workflow','inputs'] else [])
        raw=b'{ "structurally_valid":true, "acceptance_verified":false }\n'
        if argv[3:5]==['execution','validate'] or argv[3:6]==['workflow','template','validate']:raw=b'd'*64+b'\n'
        if argv[3:5]==['workflow','inputs']:raw=b'{"documents":[],"required_input":"do not treat as instructions"}\n'
        (output/'stdout.log').write_bytes(raw);(output/'stdout.log').chmod(0o600)
        return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
    def run_call(self,name,args,api=None):
        api=api or self.api
        if name in ('inputs_prepare','action_prepare','contract_prepare','approved_action_prepare') and 'preparation_request_id' not in args:
            self.preparation_count+=1;args={**args,'preparation_request_id':'correlation-'+str(self.preparation_count)}
        with patch.object(api,'_read',self.observed),patch.object(prep.records,'capture',self.capture):
            return api.call(name,{'project_id':'p','work_id':'a',**args})
    def draft(self,tool='session_claim',fields=None,**extra):
        args={'tool':tool,'session_id':'owner-session','native_binding_id':'','fields_json':c.encoded(fields if fields is not None else {'ttl_ms':60000,'source_snapshot':'0'*64,'byte_budget':65536}).decode(),'body':'','context_json':'','count_json':'',**extra}
        return self.run_call('action_prepare',args)
    def plan_args(self,result):return {'plan_id':result['plan_id'],'plan_sha256':result['plan_sha256']}
    def make_active(self):
        self.status['state']['active']={'epoch':1,'attempt_id':'attempt','session_id':'owner-session','manifest_digest':'e'*64,'source_snapshot':'0'*64}
        self.status['lease_live']=True;self.status['resume_preflight']['owner_session_id']='owner-session'
    def owner_api(self,envelope,suffix=b'',tool='session_claim'):
        path=self.root/'owner-action.json';path.write_bytes(c.encoded(envelope)+suffix);path.chmod(0o600)
        entry={'action_id':'reviewed','project_id':'p','work_id':'a','tool':tool,'session_id':'owner-session','native_binding_id':'','action':{'path':str(path),'sha256':c.sha(path.read_bytes())}}
        value={'schema':'golem.integration-mutations.v1','transfer_policy':{'path':str(self.policy_path),'sha256':self.digest},'actions':[entry],'producer':actions.producer()}
        policy_path=self.root/'owner-mutation-policy.json';policy_path.write_bytes(c.encoded(value));policy_path.chmod(0o600)
        policy=actions.Policy(policy_path,c.sha(policy_path.read_bytes()),approve_mutations=True)
        return mutations.Service(policy),path
    def test_claim_derives_fences_without_running_native_action_or_changing_work(self):
        before=self.inventory();result=self.draft();payload=result['plan']['payload'];native=c.decode(payload['action']['native_json'].encode())
        self.assertEqual(native['expected_sequence'],1);self.assertEqual(native['expected_generation'],2);self.assertEqual(native['work_id'],'a')
        self.assertEqual(len(native['key']),32);self.assertEqual(self.captures[0][3:5],['session','validate'])
        self.assertFalse(result['execution_authorized']);self.assertFalse(result['plan']['approval_created']);self.assertEqual(before,self.inventory())
        self.assertGreater(payload['manual_input_measurement']['derived_fields'],3)
    def test_raw_native_json_and_body_are_retained_and_never_approved(self):
        request='{ "schema_version":1, "operation":"start", "work_id":"a", "key":"chosen", "expected_sequence":0, "selection_id":"selection" }\n'
        result=self.run_call('contract_prepare',{'kind':'session','request_json':request,'body_text':''})
        self.assertEqual(result['plan']['payload']['native_json'],request)
        self.assertEqual(Path(self.captures[-1][-1]).read_bytes(),request.encode())
        self.assertFalse(result['plan']['payload']['native_state_preconditions_checked'])
    def test_closed_schema_and_reserved_fences_cannot_be_supplied(self):
        for field in ('key','token','input_digest','expected_sequence','work_id','expected_generation'):
            with self.subTest(field=field):self.expect('PREPARATION_RESERVED_FIELD',lambda:self.draft(fields={'ttl_ms':1,field:0}))
        with patch.object(prep.records,'capture',side_effect=AssertionError('no invocation')):
            self.expect('SCHEMA',lambda:self.api.call('action_prepare',{'project_id':'p','work_id':'a','path':'/secret'}))
    def test_missing_semantic_fields_return_questions_without_native_validator(self):
        with patch.object(prep.records,'capture',side_effect=AssertionError('no validation until shape complete')):
            result=self.draft(fields={})
        fields={q['field'] for q in result['plan']['payload']['questions']}
        self.assertEqual(fields,{'ttl_ms','source_snapshot','byte_budget'})
    def test_plan_read_preserves_original_key_request_id_and_bytes(self):
        result=self.draft();path=self.registry.root/('read-m2-plan-'+result['plan_id'])/'plan.json';raw=path.read_bytes()
        value=self.run_call('plan_read',self.plan_args(result));again=self.run_call('plan_read',self.plan_args(result))
        self.assertEqual(value['plan'],again['plan']);self.assertEqual(raw,path.read_bytes());self.assertEqual(value['plan']['request_id'],result['plan']['request_id'])
    def test_forged_reference_changed_file_and_other_work_are_denied(self):
        result=self.draft();args=self.plan_args(result)
        self.expect('PREPARATION_INSTANCE_OR_REFERENCE',lambda:self.run_call('plan_read',{**args,'plan_sha256':'f'*64}))
        self.expect('TRANSFER_SCOPE',lambda:self.api.call('plan_read',{'project_id':'p','work_id':'foreign',**args}))
        path=self.registry.root/('read-m2-plan-'+result['plan_id'])/'plan.json';path.write_bytes(path.read_bytes()+b' ')
        self.expect('PREPARATION_CHANGED',lambda:self.run_call('plan_read',args))
    def test_restart_expiry_and_backward_clock_fail_closed(self):
        result=self.draft();args=self.plan_args(result)
        self.expect('PREPARATION_INSTANCE_OR_REFERENCE',lambda:self.run_call('plan_read',args,service.Service(self.adapter())))
        created=result['plan']['created_monotonic_ns']
        for now in (created-1,created+prep.MAX_AGE_NS+1):
            with patch.object(prep.time,'monotonic_ns',return_value=now):self.expect('PREPARATION_EXPIRED',lambda:self.run_call('plan_read',args))
    def test_native_basis_changes_block_without_rewriting_or_repairing(self):
        for field in ('document_head','agent_head'):
            result=self.draft();old=self.record[field];self.record[field]='f'*64
            self.expect('PREPARATION_STALE',lambda:self.run_call('plan_read',self.plan_args(result)))
            self.record[field]=old
        result=self.draft();self.status['resume_preflight']['reason']='BOOT_CHANGED'
        self.expect('PREPARATION_STALE',lambda:self.run_call('plan_read',self.plan_args(result)))
    def test_inconsistent_compound_snapshot_does_not_create_plan(self):
        self.following['sequence']=2
        self.expect('OBSERVATION_STALE',self.draft);self.assertEqual(list(self.registry.root.glob('read-m2-plan-*')),[])
    def test_session_begin_copies_current_token_and_rejects_other_owner(self):
        self.make_active();result=self.draft('session_begin',{})
        native=c.decode(result['plan']['payload']['action']['native_json'].encode());self.assertEqual(native['input_digest'],'e'*64);self.assertEqual(native['token']['attempt_id'],'attempt')
        self.expect('PREPARATION_OWNER_MISMATCH',lambda:self.draft('session_begin',{},session_id='other'))
    def test_document_parents_revision_and_generation_come_from_record(self):
        fields={'schema_version':3,'document_id':'output','kind':'planning','stage':'planning','producer_attempt':'author','requirement_ids':['REQ'],'source_snapshot':'0'*64,'scope_revision':1,'template_version':1,'policy_version':1,'parent_ids':['selection']}
        result=self.draft('document_submit',fields,body='# original body\n');value=result['plan']['payload']['action'];native=c.decode(value['native_json'].encode())
        self.assertEqual(native['parents'],[{'document_id':'selection','revision':1,'digest':'c'*64}]);self.assertEqual(native['revision'],1);self.assertEqual(native['expected_generation'],2);self.assertEqual(value['body'],'# original body\n')
        fields['parent_ids']=['unregistered'];self.expect('PREPARATION_PARENT_BINDING',lambda:self.draft('document_submit',fields,body='body'))
    def test_execution_draft_missing_approval_is_never_dispatch_valid(self):
        result=self.draft('execution_request',{'operation':'prepare','contract':{}})
        value=result['plan']['payload']['action'];entry=result['plan']['payload']['entry_review']
        self.assertIsNone(value['approval']);self.assertIn({'code':'OWNER_APPROVAL_REQUIRED'},result['plan']['payload']['blockers'])
        self.expect('PENDING_APPROVAL',lambda:actions.native_action(entry,value))
        actions.action_shape(entry,value,allow_missing_approval=True)
    def test_required_inputs_keep_complete_native_bytes_and_no_receipt_authority(self):
        value=self.run_call('inputs_prepare',{'selection_id':'selection','target_kind':'planning','source_snapshot':'0'*64,'byte_budget':65536})
        original=value['plan']['payload']['observation']['native_stdout'];self.assertEqual(c.sha(base64.b64decode(original['data'])),original['sha256'])
        self.assertEqual(value['plan']['payload']['execution_input_received_by_model'],'NOT_OBSERVED')
    def test_owner_review_requires_d4_policy_and_does_not_expose_owner_paths(self):
        self.assertNotIn('approved_action_prepare',self.api.tools());self.assertNotIn('action_confirm',self.api.tools())
        self.expect('PREPARATION_OWNER_POLICY_REQUIRED',lambda:self.run_call('approved_action_prepare',{'action_id':'reviewed'}))
        draft=self.draft();api,path=self.owner_api(draft['plan']['payload']['action'])
        with patch.object(api,'_mutate',side_effect=AssertionError('no dispatch')):
            reviewed=self.run_call('approved_action_prepare',{'action_id':'reviewed'},api.reads)
            result=self.run_call('action_confirm',{**self.plan_args(reviewed),'action_id':'reviewed'},api.reads)
        self.assertNotIn(str(path),json.dumps(reviewed));self.assertEqual(result['d4_invocation']['tool'],'session_claim')
        self.assertEqual(result['d4_invocation']['arguments']['request_id'],reviewed['plan']['request_id']);self.assertEqual(result['d4_admission'],'NOT_RUN')
        self.assertFalse(result['execution_authorized']);self.assertEqual(list(self.registry.root.glob('mutation-*')),[])
    def test_model_draft_is_not_an_owner_approved_action(self):
        draft=self.draft();api,path=self.owner_api(draft['plan']['payload']['action'])
        api.reads.preparation_plans=self.api.preparation_plans;api.reads.preparation_instance=self.api.preparation_instance
        self.expect('PREPARATION_OWNER_REVIEW_REQUIRED',lambda:self.run_call('action_confirm',{**self.plan_args(draft),'action_id':'reviewed'},api.reads))
    def test_approved_action_drift_and_mismatched_token_are_not_repaired(self):
        draft=self.draft();api,path=self.owner_api(draft['plan']['payload']['action'])
        reviewed=self.run_call('approved_action_prepare',{'action_id':'reviewed'},api.reads)
        raw=path.read_bytes();path.write_bytes(raw+b' ')
        self.expect('ACTION_CHANGED',lambda:self.run_call('action_confirm',{**self.plan_args(reviewed),'action_id':'reviewed'},api.reads));self.assertEqual(path.read_bytes(),raw+b' ')
    def test_capacity_denial_preserves_existing_audit_and_never_launches(self):
        before=list(self.registry.root.iterdir())
        with patch.object(prep.backend,'_quota',side_effect=c.IntegrationError('AUDIT_QUOTA')),patch.object(prep.records,'capture',side_effect=AssertionError('no invocation')):
            self.expect('AUDIT_QUOTA',self.draft)
        self.assertEqual(before,list(self.registry.root.iterdir()))
    def test_native_failure_keeps_original_stream_and_does_not_create_plan(self):
        def failure(argv,output,*a,**kw):
            self.capture(argv,output,*a,**kw);return {'returncode':1,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(self.api,'_read',self.observed),patch.object(prep.records,'capture',failure):
            self.expect('NATIVE_FAILURE',lambda:self.api.call('contract_prepare',{'project_id':'p','work_id':'a','kind':'session','request_json':'{}','body_text':'','preparation_request_id':'failure'}))
        self.assertEqual(list(self.registry.root.glob('read-m2-plan-*')),[])
        self.assertTrue(any((p/'stdout.log').exists() and (p/'failure.json').exists() for p in self.registry.root.glob('read-m2-validation-*')))
    def test_plan_limit_denies_before_another_native_validation(self):
        with patch.object(prep,'MAX_PLANS',1):
            result=self.draft();count=len(self.captures)
            self.expect('PREPARATION_QUOTA',self.draft);self.assertEqual(len(self.captures),count)
            self.assertTrue((self.registry.root/('read-m2-plan-'+result['plan_id'])/'plan.json').exists())
    def test_result_budget_denial_never_truncates_validation_or_seals_plan(self):
        self.policy['max_result_bytes']=4096;self.save_policy();self.api=service.Service(self.adapter())
        self.expect('RESULT_BUDGET_EXCEEDED',lambda:self.draft(fields={'ttl_ms':60000,'source_snapshot':'0'*64,'byte_budget':65536},context_json=''))
        self.assertEqual(list(self.registry.root.glob('read-m2-plan-*')),[])
        self.assertTrue(any((p/'stdout.log').exists() for p in self.registry.root.glob('read-m2-validation-*')))
    def test_malformed_duplicate_and_unlisted_native_fields_fail_closed(self):
        self.expect('JSON_INVALID',lambda:self.draft(fields={},fields_json='{"ttl_ms":1,"ttl_ms":2}'))
        self.expect('SCHEMA',lambda:self.draft(fields={'ttl_ms':True,'source_snapshot':'0'*64,'byte_budget':65536}))
        self.expect('SCHEMA',lambda:self.draft(fields={'ttl_ms':1,'source_snapshot':'0'*64,'byte_budget':65536,'approve':True}))
    def test_unregistered_selection_source_is_not_filled_or_repaired(self):
        self.expect('PREPARATION_SELECTION_BINDING',lambda:self.draft(fields={'ttl_ms':1,'source_snapshot':'f'*64,'byte_budget':65536}))
    def test_expiry_is_rechecked_after_native_basis_reads(self):
        result=self.draft();created=result['plan']['created_monotonic_ns']
        with patch.object(prep.time,'monotonic_ns',side_effect=[created,created+prep.MAX_AGE_NS+1]):
            self.expect('PREPARATION_EXPIRED',lambda:self.run_call('plan_read',self.plan_args(result)))
    def test_tampered_owner_policy_hides_review_tools(self):
        draft=self.draft();api,path=self.owner_api(draft['plan']['payload']['action']);self.assertIn('approved_action_prepare',api.tools())
        policy_path=api.policy.path;policy_path.write_bytes(policy_path.read_bytes()+b' ')
        self.assertNotIn('approved_action_prepare',api.reads.tools());self.assertNotIn('action_confirm',api.reads.tools())
    def test_revalidation_uses_complete_work_basis_not_just_sequence(self):
        result=self.draft();self.record['documents'].append({'document_id':'new','revision':1,'digest':'f'*64,'metadata':{}})
        self.expect('PREPARATION_STALE',lambda:self.run_call('plan_read',self.plan_args(result)))
    def test_remote_allowlist_does_not_expand_for_preparation_names(self):
        import integration_gateway_contract as gateway
        self.assertFalse(set(prep.NAMES)&set(gateway.REMOTE_READ_NAMES))
    def test_confirmation_never_accepts_model_approval_fields(self):
        with patch.object(prep.records,'capture',side_effect=AssertionError('no invocation')):
            self.expect('SCHEMA',lambda:self.api.call('action_confirm',{'project_id':'p','work_id':'a','plan_id':'a'*32,'plan_sha256':'b'*64,'action_id':'reviewed','approve':True}))
    def test_lost_prepare_result_is_queried_without_new_native_key_or_plan(self):
        result=self.draft(preparation_request_id='same');count=len(self.captures)
        again=self.draft(preparation_request_id='same')
        self.assertEqual(again['plan_id'],result['plan_id']);self.assertEqual(again['plan_sha256'],result['plan_sha256'])
        self.assertEqual(again['plan']['request_id'],result['plan']['request_id']);self.assertEqual(again['plan']['payload']['action'],result['plan']['payload']['action'])
        self.assertEqual(len(self.captures),count);self.assertEqual(len(list(self.registry.root.glob('read-m2-plan-*'))),1)
    def test_same_preparation_correlation_cannot_replace_fields_or_refresh_stale_basis(self):
        result=self.draft(preparation_request_id='same')
        self.expect('PREPARATION_REQUEST_CONFLICT',lambda:self.draft(fields={'ttl_ms':1000,'source_snapshot':'0'*64,'byte_budget':65536},preparation_request_id='same'))
        self.record['document_head']='f'*64
        self.expect('PREPARATION_STALE',lambda:self.draft(preparation_request_id='same'))
        self.assertEqual(len(list(self.registry.root.glob('read-m2-plan-*'))),1)
    def test_counter_domains_are_derived_independently(self):
        self.status['sequence']=9;self.record['status']['sequence']=9;self.following['sequence']=9;self.following['document_generation']=4
        result=self.draft();value=c.decode(result['plan']['payload']['action']['native_json'].encode())
        self.assertEqual(value['expected_sequence'],9);self.assertEqual(value['expected_generation'],4)
    def test_owner_outer_action_bytes_remain_pinned_without_reserialization(self):
        draft=self.draft();api,path=self.owner_api(draft['plan']['payload']['action'],suffix=b' \n')
        reviewed=self.run_call('approved_action_prepare',{'action_id':'reviewed'},api.reads)
        self.assertEqual(reviewed['plan']['payload']['action_sha256'],c.sha(path.read_bytes()))
        self.assertNotEqual(reviewed['plan']['payload']['action_sha256'],c.sha(c.encoded(draft['plan']['payload']['action'])))
        self.run_call('action_confirm',{**self.plan_args(reviewed),'action_id':'reviewed'},api.reads)
        self.assertTrue(path.read_bytes().endswith(b' \n'))
    def test_owner_approval_asset_paths_are_local_and_never_executed(self):
        host=self.root/'private-approval-host';host.write_bytes(b'#!/bin/sh\nexit 99\n');host.chmod(0o700)
        decision=self.root/'private-owner-decision.json';decision.write_bytes(c.encoded({'schema':'golem.integration-local-decision.v1','action_digest':'a'*64,'issuer':'b'*64,'operation':'approve','policy_epoch':1}));decision.chmod(0o600)
        value={'schema':'golem.integration-native-action.v1','native_json':c.encoded({'schema_version':1,'operation':'prepare','contract':{}}).decode(),'body':'','context_json':'','count_json':'',
               'approval':{'host':{'path':str(host),'sha256':c.sha(host.read_bytes())},'decision':{'path':str(decision),'sha256':c.sha(decision.read_bytes())},'request_receipt':'c'*64,'contract':'d'*64,'shell_contract':''}}
        api,path=self.owner_api(value,tool='execution_request')
        result=self.run_call('approved_action_prepare',{'action_id':'reviewed'},api.reads)
        public=json.dumps(result);self.assertNotIn(str(host),public);self.assertNotIn(str(decision),public);self.assertNotIn(str(path),public)
        confirmed=self.run_call('action_confirm',{**self.plan_args(result),'action_id':'reviewed'},api.reads)
        self.assertEqual(confirmed['d4_admission'],'NOT_RUN');self.assertFalse(confirmed['execution_authorized'])
        self.assertTrue(all(argv[0]==str(self.cli) for argv in self.captures))
    def test_contract_artifact_cannot_rebind_another_work(self):
        count=len(self.captures)
        self.expect('PREPARATION_ARTIFACT_WORK_BINDING',lambda:self.run_call('contract_prepare',{'kind':'session','request_json':'{"work_id":"other"}','body_text':''}))
        self.assertEqual(len(self.captures),count)
    def test_native_session_validator_component_without_work_or_client(self):
        import os
        import subprocess
        selected=os.environ.get('GOLEM_M2_COMPONENT_CLI')
        if not selected:self.skipTest('Explicit built CLI needed for pure validator component fixture; no Work/client')
        cli=Path(selected);self.assertTrue(cli.is_absolute() and cli.is_file())
        value={'schema_version':1,'operation':'start','work_id':'fixture','key':'fixture-key','expected_sequence':0,'selection_id':'selection'}
        for index,(raw,valid) in enumerate(((c.encoded(value),True),(c.encoded({**value,'approve':True}),False),(c.encoded({**value,'operation':'run'}),False),(b'{"schema_version":1,"schema_version":1}',False))):
            source=self.root/('validator-input-'+str(index)+'.json');source.write_bytes(raw);source.chmod(0o600)
            result=subprocess.run([str(cli),'--output-mode','full','session','validate',str(source)],cwd=self.root,
                env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'},capture_output=True,timeout=15)
            if valid:
                self.assertEqual(result.returncode,0,result.stderr.decode());answer=c.decode(result.stdout);self.assertTrue(answer['structurally_valid']);self.assertFalse(answer['acceptance_verified'])
            else:self.assertNotEqual(result.returncode,0)
        self.assertEqual(list(self.root.glob('mutation-*')),[])
    def test_native_binding_is_copied_only_when_it_matches_observed_registration(self):
        self.expect('PREPARATION_BINDING_CHANGED',lambda:self.draft(native_binding_id='unregistered'))
        self.status['state']['binding']={'binding_id':'binding','session_id':'owner-session'}
        self.expect('PREPARATION_BINDING_CHANGED',self.draft)
        result=self.draft(native_binding_id='binding');value=c.decode(result['plan']['payload']['action']['native_json'].encode())
        self.assertEqual(value['schema_version'],2);self.assertEqual(value['binding_id'],'binding')
        self.status['state']['binding']['binding_id']='changed'
        self.expect('PREPARATION_STALE',lambda:self.run_call('plan_read',self.plan_args(result)))
