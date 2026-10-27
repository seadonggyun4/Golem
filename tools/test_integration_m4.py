"""M4 isolated policies, command/capture doubles and opt-in disposable components."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import integration_contract as c
import integration_registry as r
import integration_quality_actions as quality
import integration_quality_reads as views
import integration_helper_contract as helpers
import integration_mutation_contract as actions
import integration_mutations as mutations
import integration_preparations as prep
import test_integration_m2 as m2
import test_integration_mutations as d4

ROOT=Path(__file__).resolve().parents[1]

def snapshot(cost_known=False):
    report={'schema':'golem.native-cost-report.v1','run_id':'cost-run','sequence':'1','request_id':'observed-call','provider':'codex.exec.v1','model':'unreported','price_revision':'provider-unpriced-v1','currency':'USD','usage_known':True,'cost_known':cost_known,'nano_cost':'0','usage':{'input_tokens':'12','cached_input_tokens':'2','output_tokens':'3','reasoning_tokens':'0','tool_calls':'0'}}
    return {'schema':'golem.native-cost-inbox.v1','run_id':'cost-run','sequence':'1','sealed':True,'reports':[report]}

def cases():
    case=c.decode((ROOT/'samples/research/case.json').read_bytes());case.update(project_id='p',work_id='a')
    return {'evidence_import':{'data_base64':base64.b64encode(b'original\x00evidence').decode()},'proof_publish':{'pack_json':'{}'},
      'research_request':{'schema_version':1,'operation':'case-create','key':'native-key','record':case},
      'research_export':{'case_id':'case','redaction_json':'{}'},
      'cost_inbox_reconcile':{'capsule_json':(ROOT/'samples/work-capsules/basic.json').read_text(),'run_id':'cost-run','inbox_json':c.encoded({'snapshots':[snapshot()]}).decode()},
      'helper_execute':{'helper_id':'selected'},'execution_verify':{'schema_version':1,'operation':'verify','receipt':'a'*64}}

def envelope(value):return {'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),'body':'','context_json':'','count_json':'','approval':None}

class Quality(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','observed','capture','run_call','draft','plan_args','make_active','owner_api'):
        locals()[name]=getattr(m2.Preparations,name)
    def setUp(self):m2.Preparations.setUp(self)
    def test_seven_closed_action_shapes_and_research_binding(self):
        self.assertEqual(set(cases()),set(quality.NAMES))
        for name,value in cases().items():
            entry={'tool':name,'project_id':'p','work_id':'a','session_id':'owner-session','native_binding_id':''}
            self.assertEqual(actions.action_shape(entry,envelope(value)),value)
            for field in ('approve','path','argv','credentials'):
                self.expect('SCHEMA',lambda:actions.action_shape(entry,envelope({**value,field:'injected'})))
        value=cases()['research_request'];value['record']['work_id']='foreign'
        self.expect('QUALITY_RESEARCH_WORK_BINDING',lambda:quality.shape({'tool':'research_request','project_id':'p','work_id':'a'},envelope(value)))
    def test_research_project_and_inbox_cross_run_or_multiple_stage_rejects(self):
        value=cases()['research_request'];value['record']['project_id']='foreign'
        self.expect('QUALITY_RESEARCH_PROJECT_BINDING',lambda:quality.shape({'tool':'research_request','project_id':'p','work_id':'a'},envelope(value)))
        for rows in ([{**snapshot(),'run_id':'other'}],[snapshot(),snapshot()]):
            value=cases()['cost_inbox_reconcile'];value['inbox_json']=c.encoded({'snapshots':rows}).decode()
            with self.assertRaises(c.IntegrationError):quality.shape({'tool':'cost_inbox_reconcile'},envelope(value))
    def test_m2_drafts_use_research_parser_and_immutable_key(self):
        value=cases()['research_request'];fields={k:v for k,v in value.items() if k not in ('schema_version','key')}
        result=self.draft('research_request',fields);native=c.decode(result['plan']['payload']['action']['native_json'].encode())
        self.assertEqual(native['operation'],'case-create');self.assertEqual(len(native['key']),32)
        self.assertEqual(self.captures[-1][3:5],['research','validate']);self.assertFalse(result['plan']['native_state_preconditions_checked'])
    def test_m2_missing_inputs_are_questions_without_dispatch(self):
        with patch.object(quality.records,'capture',side_effect=AssertionError('no invocation')):
            result=self.draft('research_export',{})
        self.assertEqual({v['field'] for v in result['plan']['payload']['questions']},{'case_id','redaction_json'})
    def test_m2_helper_draft_does_not_create_or_substitute_helper_authority(self):
        result=self.draft('helper_execute',{'helper_id':'selected'});self.assertFalse(result['plan']['approval_created'])
        api,_=self.owner_api(result['plan']['payload']['action'],tool='helper_execute')
        self.expect('OWNER_HELPER_EFFECTS_APPROVAL_REQUIRED',lambda:self.run_call('approved_action_prepare',{'action_id':'reviewed'},api.reads))
    def test_each_native_quality_action_uses_existing_d4_intent_and_historical_result(self):
        for name,value in cases().items():
            if name=='helper_execute':continue
            api,_=self.owner_api(envelope(value),tool=name);args={'project_id':'p','work_id':'a','action_id':'reviewed','request_id':'request-'+name};calls=[]
            def capture(argv,output,*a,**kw):
                calls.append(argv);self.assertTrue((output/'dispatch-intent.json').exists());self.assertEqual((output/'request.json').read_bytes(),envelope(value)['native_json'].encode())
                (output/'stdout.log').write_bytes(b'{ "recorded":true }\n');(output/'stdout.log').chmod(0o600)
                return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
            with patch.object(api,'_preflight',lambda *a:{}),patch.object(mutations.records,'capture',capture):
                result=api.call(name,args);again=api.call(name,args)
            self.assertEqual(result['state'],'NATIVE_RESULT_RECORDED',result);self.assertEqual(result,again);self.assertEqual(len(calls),1)
            self.assertFalse(result['acceptance_verified']);self.assertFalse(result['execution_authorized'])
    def test_bounded_export_and_evidence_argv_only_private_spool(self):
        for name,value in cases().items():
            if name=='helper_execute':continue
            output=self.root/name;output.mkdir(mode=0o700)
            argv=quality.command({'tool':name,'work_id':'a','project_id':'p'},None,{'path':str(self.work)},envelope(value),output)
            self.assertNotIn('sh',argv);self.assertNotIn('--approve-contract',argv)
            if name=='evidence_import':self.assertEqual((output/'evidence.bin').read_bytes(),b'original\x00evidence')
            if name=='proof_publish':self.assertTrue((output/'proof').is_dir())
            if name=='research_export':self.assertEqual(argv[argv.index('--output')+1],str(output/'research-export'))
    def test_all_seven_research_operations_preserve_native_records(self):
        for op in quality.RESEARCH:
            value={**cases()['research_request'],'operation':op};entry={'tool':'research_request','project_id':'p','work_id':'a'}
            self.assertEqual(quality.shape(entry,envelope(value))['operation'],op)
        self.expect('SCHEMA',lambda:quality.shape(entry,envelope({**value,'operation':'approve'})))
    def read_call(self,name,args):
        def capture(argv,output,*a,**kw):
            self.captures.append(argv);self.assertEqual(kw['env'],mutations.backend.ENVIRONMENT)
            raw=b'# historical research\n' if name=='research_read' and (args['operation']=='report' or args.get('format')=='markdown') else b'{"integrity_verified":true,"acceptance_verified":false}\n'
            (output/'stdout.log').write_bytes(raw);(output/'stdout.log').chmod(0o600)
            return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(self.api,'_read',self.observed),patch.object(views.records,'capture',capture):return self.api.call(name,{'project_id':'p','work_id':'a',**args})
    def test_four_read_tools_keep_exact_bytes_and_no_acceptance(self):
        inputs=(('proof_read',{'operation':'integrity','pack_json':'{}','manifest_sha256':'a'*64}),('research_read',{'operation':'status'}),('cost_read',{'operation':'reconstruct',**cases()['cost_inbox_reconcile']}),('execution_read',{'operation':'verify','receipt_digest':'a'*64}))
        before=self.inventory()
        for name,args in inputs:
            result=self.read_call(name,args);self.assertFalse(result['current_native_acceptance_verified']);self.assertFalse(result['provider_authenticity_verified'])
            self.assertTrue(base64.b64decode(result['native_stdout']['data']));self.assertEqual(result['state'],'AVAILABLE')
        self.assertEqual(before,self.inventory())
    def test_report_markdown_kept_and_untrusted(self):
        result=self.read_call('research_read',{'operation':'report','sequence':1});self.assertEqual(result['result'],'# historical research\n');self.assertEqual(result['content_role'],'UNTRUSTED_DATA')
    def test_read_operation_shapes_and_no_approve_or_credential_arguments(self):
        for name in views.NAMES:
            with self.assertRaises(c.IntegrationError):self.api.call(name,{'project_id':'p','work_id':'a','operation':'approve','token':'secret'})
    def test_artifact_path_traversal_and_symlink_names_block(self):
        for name in ('../secret','/secret','.git/../secret','a//b','a\\b'):
            output=self.root/('path-'+str(len(list(self.root.glob('path-*')))));output.mkdir(mode=0o700)
            with self.assertRaises(c.IntegrationError):views.files(c.encoded({name:'x'}).decode(),output)
    def test_read_stale_or_failure_does_not_publish(self):
        count=0
        def changing(scope,work,operation,*a):
            nonlocal count
            count+=1;result=self.observed(scope,work,operation);result['result']['document_head']=str(count);return result
        def capture(argv,output,*a,**kw):
            (output/'stdout.log').write_bytes(b'{}');(output/'stdout.log').chmod(0o600);return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(self.api,'_read',changing),patch.object(views.records,'capture',capture):
            self.expect('OBSERVATION_STALE',lambda:self.api.call('research_read',{'project_id':'p','work_id':'a','operation':'status'}))
        dirs=list(self.registry.root.glob('read-m4-*'));self.assertTrue((dirs[0]/'failure.json').exists());self.assertFalse((dirs[0]/'delivery.json').exists())
    def test_read_quota_and_output_budget_reject_instead_of_truncate(self):
        self.policy['max_result_bytes']=4096;self.save_policy();self.api=__import__('integration_service').Service(self.adapter())
        with patch.object(views.backend,'_quota',side_effect=c.IntegrationError('AUDIT_QUOTA')):
            self.expect('AUDIT_QUOTA',lambda:self.read_call('research_read',{'operation':'status'}))
    def test_old_transfer_does_not_gain_new_read_tools(self):
        self.policy['scopes'][0]['tools']=[v for v in self.policy['scopes'][0]['tools'] if v not in views.NAMES];self.save_policy()
        from integration_service import Service
        api=Service(self.adapter());self.assertFalse(set(views.NAMES)&set(api.tools()))
    def test_remote_allowlist_stays_frozen(self):
        import integration_gateway_contract as gateway
        self.assertFalse(set(views.NAMES)&set(gateway.REMOTE_READ_NAMES));self.assertFalse(set(quality.NAMES)&set(gateway.REMOTE_READ_NAMES))

class OwnerHelpers(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','repin','api','preflight'):
        locals()[name]=getattr(d4.D4,name)
    def setUp(self):
        d4.D4.setUp(self);self.entry['tool']='helper_execute';self.action=envelope({'helper_id':'selected'});self.repin();self.owner=actions.Policy(self.mutation_path,self.mutation_digest,approve_mutations=True)
        self.helper_path=self.root/'helper-policy.json';self.input_path=self.root/'source.json';self.input_path.write_bytes(b'{}\n');self.input_path.chmod(0o600)
        self.secret=self.root/'token';self.secret.write_bytes(b'fixture-token-not-credential');self.secret.chmod(0o600)
        self.output_path=self.registry.root/'helper-output-a-approved'
        self.row={'helper_id':'selected','project_id':'p','work_id':'a','action_sha256':self.entry['action']['sha256'],'helper':'provider_costs','python':r.file_pin(Path(sys.executable).resolve()),'argv':['ingest','--query',str(self.input_path),'--output',str(self.output_path)],'cwd':str(self.project),'inputs':[r.file_pin(self.input_path)],'executables':[],'outputs':[str(self.output_path)],'effects':['HOST_EXECUTION','FILESYSTEM_WRITE'],'environment':[],'timeout_seconds':20}
        self.save_helpers()
    def save_helpers(self):
        wire=copy.deepcopy(self.row);wire['argv']=c.encoded(wire['argv']).decode()
        self.helper_value={'schema':'golem.integration-helper-effects.v1','mutation_policy_sha256':self.owner.digest,'assurance':'LOCAL_COOPERATIVE_EXACT_OWNER_EFFECTS_NOT_SANDBOX','helpers':[wire],'producer':helpers.producer()}
        self.helper_path.write_bytes(c.encoded(self.helper_value));self.helper_path.chmod(0o600);self.helper_digest=c.sha(self.helper_path.read_bytes())
    def approved(self):return helpers.Helpers(self.helper_path,self.helper_digest,self.owner,approve_helpers=True)
    def test_separate_owner_approval_is_required_and_hidden_by_default(self):
        self.expect('OWNER_HELPER_EFFECTS_APPROVAL_REQUIRED',lambda:helpers.Helpers(self.helper_path,self.helper_digest,self.owner))
        api=mutations.Service(self.owner);self.assertNotIn('helper_execute',api.tools())
        self.expect('OWNER_HELPER_EFFECTS_APPROVAL_REQUIRED',lambda:api.call('helper_execute',self.args))
        self.assertFalse(list(self.registry.root.glob('mutation-*')))
    def test_binding_action_digest_helper_mode_and_policy_drift_block(self):
        for field,value,code in (('work_id','foreign','HELPER_ACTION_SCOPE'),('action_sha256','f'*64,'HELPER_ACTION_SCOPE'),('argv',['eval','arbitrary'],'HELPER_MODE_SCOPE')):
            old=copy.deepcopy(self.row);self.row[field]=value;self.save_helpers();self.expect(code,lambda:self.approved().select(self.entry,self.action));self.row=old
        self.save_helpers();h=self.approved();self.helper_path.write_bytes(self.helper_path.read_bytes()+b' ');self.expect('HELPER_POLICY_CHANGED',h.current)
    def test_network_credential_and_service_effects_need_explicit_entries(self):
        self.row['argv'][0]='fetch';self.save_helpers();self.expect('HELPER_EFFECTS_NOT_APPROVED',lambda:self.approved().select(self.entry,self.action))
        self.row['effects']+=['NETWORK','CREDENTIALS'];self.row['environment']=[{'name':'API_TOKEN','value_file':r.file_pin(self.secret)}];self.save_helpers();h=self.approved();row=h.select(self.entry,self.action)
        self.assertEqual(h.environment(row)['API_TOKEN'],'fixture-token-not-credential');self.assertNotIn('HOME',h.environment(row))
        self.secret.write_bytes(b'changed');self.expect('HELPER_CREDENTIAL_CHANGED',lambda:h.environment(row))
    def test_service_duration_and_injected_environment_or_project_output_reject(self):
        for change,code in (({'argv':['ingest','--follow']},'HELPER_UNBOUNDED_SERVICE'),({'outputs':[str(self.work/'out')]},'HELPER_OUTPUT_SCOPE'),({'effects':['HOST_EXECUTION','FILESYSTEM_WRITE','CREDENTIALS'],'environment':[{'name':'PYTHONPATH','value_file':r.file_pin(self.secret)}]},'HELPER_ENVIRONMENT_SCOPE')):
            old=copy.deepcopy(self.row);self.row.update(change);self.save_helpers();self.expect(code,lambda:self.approved().select(self.entry,self.action));self.row=old
    def test_changed_input_or_python_pin_prevents_capture(self):
        h=self.approved();self.input_path.write_bytes(b'changed');self.expect('HELPER_INPUT_CHANGED',lambda:h.command(self.entry,self.action))
        self.input_path.write_bytes(b'{}\n');self.row['python']['sha256']='f'*64;self.save_helpers();self.expect('HELPER_EXECUTABLE_CHANGED',lambda:self.approved().command(self.entry,self.action))
    def test_plan_commands_and_inputs_require_declared_executable_pins(self):
        plan={'schema':'golem.agent-command-plan.v1','task':'code','commands':[{'id':'x','argv':['/usr/bin/true'],'timeout':1}]};self.input_path.write_bytes(c.encoded(plan));self.row.update(helper='agent_io',argv=['run','--plan',str(self.input_path)],inputs=[r.file_pin(self.input_path)],effects=['HOST_EXECUTION','FILESYSTEM_WRITE','NATIVE_WRITE','GIT']);self.save_helpers()
        self.expect('HELPER_COMMAND_EXECUTABLE_NOT_PINNED',lambda:self.approved().command(self.entry,self.action))
        self.row['executables']=[r.file_pin(Path('/usr/bin/true').resolve())];self.save_helpers();self.assertIn('agent_io.py',self.approved().command(self.entry,self.action)[2])
    def test_foreign_work_arguments_reject(self):
        self.row['argv']+=['--work-id','foreign'];self.save_helpers();self.expect('HELPER_ARGUMENT_BINDING',lambda:self.approved().command(self.entry,self.action))
    def test_helper_single_dispatch_exact_argv_and_original_result_only(self):
        h=self.approved();api=mutations.Service(self.owner,helpers=h);calls=[]
        def capture(argv,output,*a,**kw):
            calls.append(argv);self.assertEqual(argv,h.command(self.entry,self.action));self.assertTrue((output/'dispatch-intent.json').exists());self.assertEqual(kw['cwd'],self.project)
            (output/'stdout.log').write_bytes(b'opaque helper output\nsecond line\n');(output/'stdout.log').chmod(0o600);return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(api,'_preflight',self.preflight),patch.object(helpers.records,'capture',capture):
            result=api.call('helper_execute',self.args);again=api.call('helper_execute',self.args)
        self.assertEqual(result,again);self.assertEqual(len(calls),1);self.assertEqual(result['state'],'NATIVE_RESULT_RECORDED',result);self.assertFalse(result['acceptance_verified']);self.assertFalse(result['execution_authorized'])
        self.assertEqual(base64.b64decode(result['native_stdout_base64']),b'opaque helper output\nsecond line\n')
    def test_successful_helper_cannot_be_replayed_with_new_request_id(self):
        api=mutations.Service(self.owner,helpers=self.approved())
        def capture(argv,output,*a,**kw):
            (output/'stdout.log').write_bytes(b'historical');(output/'stdout.log').chmod(0o600);return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(api,'_preflight',self.preflight),patch.object(helpers.records,'capture',capture):result=api.call('helper_execute',self.args)
        self.assertEqual(result['state'],'NATIVE_RESULT_RECORDED',result)
        self.expect('HELPER_ACTION_ALREADY_DISPATCHED_REVIEW_ORIGINAL',lambda:api.call('helper_execute',{**self.args,'request_id':'another'}))
    def test_helper_revocation_after_capture_is_uncertain_and_preserves_raw_output(self):
        api=mutations.Service(self.owner,helpers=self.approved())
        def capture(argv,output,*a,**kw):
            (output/'stdout.log').write_bytes(b'observed effects');(output/'stdout.log').chmod(0o600);self.helper_path.write_bytes(self.helper_path.read_bytes()+b' ')
            return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(api,'_preflight',self.preflight),patch.object(helpers.records,'capture',capture):result=api.call('helper_execute',self.args)
        self.assertEqual(result['state'],'COMMIT_UNKNOWN');self.assertEqual(result['code'],'HELPER_POLICY_CHANGED')
        self.assertEqual((self.registry.root/result['local_evidence_id']/'stdout.log').read_bytes(),b'observed effects')
    def test_helper_loss_and_quarantine_keep_original_intent(self):
        api=mutations.Service(self.owner,helpers=self.approved())
        with patch.object(api,'_preflight',self.preflight),patch.object(helpers.records,'capture',side_effect=OSError('lost')):result=api.call('helper_execute',self.args)
        self.assertEqual(result['state'],'COMMIT_UNKNOWN')
        self.expect('HELPER_ACTION_ALREADY_DISPATCHED_REVIEW_ORIGINAL',lambda:api.call('helper_execute',{**self.args,'request_id':'new'}))
    def test_owner_schema_and_plan_commands_do_not_apply_policy_or_change_inputs(self):
        import io
        from types import SimpleNamespace
        original=self.helper_path.read_bytes()
        for arguments in (['helper','schema'],['helper','plan','--input',str(self.helper_path)]):
            output=io.BytesIO()
            with patch.object(sys,'argv',arguments),patch.object(sys,'stdout',SimpleNamespace(buffer=output)):helpers.main()
            value=c.decode(output.getvalue());self.assertIsInstance(value,dict)
        self.assertEqual(self.helper_path.read_bytes(),original);self.assertFalse(self.output_path.exists())
    def test_usage_client_command_needs_explicit_executable_pin(self):
        self.row.update(helper='usage_pipeline',argv=['run-claude','--directory',str(self.output_path),'--','/usr/bin/true'],effects=list(helpers.EFFECTS));self.save_helpers()
        self.expect('HELPER_COMMAND_EXECUTABLE_NOT_PINNED',lambda:self.approved().command(self.entry,self.action))
        self.row['executables']=[r.file_pin(Path('/usr/bin/true').resolve())];self.save_helpers();self.assertEqual(self.approved().command(self.entry,self.action)[-1],'/usr/bin/true')
    def test_duplicate_output_and_missing_argument_cannot_escape_scope(self):
        self.row['argv']+=['--output',str(self.project/'foreign')];self.save_helpers();self.expect('HELPER_OUTPUT_ARGUMENT',lambda:self.approved().command(self.entry,self.action))
        self.row['argv']=['ingest','--output'];self.save_helpers();self.expect('HELPER_ARGUMENT_VALUE_REQUIRED',lambda:self.approved().command(self.entry,self.action))
    def test_output_descendant_symlink_cannot_leave_approved_audit_root(self):
        self.output_path.mkdir(mode=0o700);(self.output_path/'redirect').symlink_to(self.work,target_is_directory=True)
        self.row['argv']=['ingest','--output',str(self.output_path/'redirect/result')];self.save_helpers()
        with self.assertRaises(c.IntegrationError):self.approved().command(self.entry,self.action)
    def test_helper_policy_cannot_bind_another_mutation_policy(self):
        self.helper_value['mutation_policy_sha256']='f'*64;self.helper_path.write_bytes(c.encoded(self.helper_value));digest=c.sha(self.helper_path.read_bytes())
        self.expect('HELPER_MUTATION_POLICY_BINDING',lambda:helpers.Helpers(self.helper_path,digest,self.owner,approve_helpers=True))

class DisposableCoreComponent(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('GOLEM_M4_COMPONENT_CLI'),'explicit disposable component opt-in')
    def test_core_accounting_unknown_money_stays_null_without_work_or_provider(self):
        cli=os.environ['GOLEM_M4_COMPONENT_CLI']
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();inbox=root/'inbox';inbox.mkdir(mode=0o700);capsule=root/'capsule.json';capsule.write_bytes((ROOT/'samples/work-capsules/basic.json').read_bytes())
            target=inbox/'00000000000000000001.json'
            for known in (False,True):
                target.write_bytes(c.encoded(snapshot(known)));target.chmod(0o600)
                result=subprocess.run([cli,'--output-mode','full','cost','inbox',str(capsule),'cost-run',str(inbox),'1'],cwd=root,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr);value=c.decode(result.stdout)
                self.assertFalse(value['live_run_updated']);self.assertFalse(value['acceptance_verified']);self.assertEqual(value['unsettled'],'1')
                self.assertEqual(value['reports'][0]['nano_cost'],'0' if known else None)
            bad=snapshot();bad['sealed']=False;target.write_bytes(c.encoded(bad));result=subprocess.run([cli,'cost','inbox',str(capsule),'cost-run',str(inbox),'1'],cwd=root,capture_output=True);self.assertNotEqual(result.returncode,0)

    @unittest.skipUnless(os.environ.get('GOLEM_M4_COMPONENT_CLI'),'explicit pure core parser component opt-in')
    def test_research_and_redaction_pure_parsers_without_work(self):
        cli=os.environ['GOLEM_M4_COMPONENT_CLI']
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();path=root/'request.json'
            for operation,value in (('validate',cases()['research_request']),('redaction-validate',c.decode((ROOT/'samples/research/redaction-minimal.json').read_bytes()))):
                path.write_bytes(c.encoded(value));result=subprocess.run([cli,'--output-mode','full','research',operation,str(path)],cwd=root,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(c.decode(result.stdout)['structurally_valid'])
                path.write_bytes(c.encoded({**value,'approve':True}));result=subprocess.run([cli,'research',operation,str(path)],cwd=root,capture_output=True);self.assertNotEqual(result.returncode,0)
