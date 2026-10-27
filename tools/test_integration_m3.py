"""M3 disposable policy/plan/dispatch doubles, never actual client/Work E2E."""
import base64
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import integration_contract as c
import integration_task_actions as tasks
import integration_mutation_contract as actions
import integration_mutations as mutations
import integration_preparations as prep
import test_integration_m2 as m2
import test_integration_mutations as d4


def cases():
    token={'epoch':1,'attempt_id':'attempt','session_id':'owner-session'}
    ref={'document_id':'selection','revision':1,'digest':'c'*64}
    common={'schema_version':1,'key':'native-key'}
    session={**common,'work_id':'a','expected_sequence':1}
    return {
      'session_start':{**session,'operation':'start','selection_id':'selection'},
      'session_heartbeat':{**session,'operation':'heartbeat','token':token,'ttl_ms':60000},
      'session_reject_output':{**session,'operation':'reject_output','token':token,'input_digest':'e'*64,'source_snapshot':'0'*64,'expected_generation':2,'output':ref,'evidence':['d'*64],'approval_digest':'f'*64},
      'binding_attach':{**session,'operation':'attach','session_id':'owner-session','descriptor_digest':'a'*64,'native_thread_id':'opaque-thread','token':token,'ttl_ms':60000},
      'role_enroll':{**common,'operation':'enroll','selection_id':'selection','expected_generation':2,'contract':{'sample':'native validator owns this'}},
      'role_assess':{**common,'operation':'assess','selection_id':'selection','expected_generation':2,'review':None},
      'completion_finalize':{**common,'operation':'finalize','selection_id':'selection','expected_generation':2,'issues':[]},
      'completion_report':{'sequence':1},'reentry_report':{'sequence':1},
      'reentry_decide':{**common,'operation':'decide','expected_sequence':0,'failure_receipt':'a'*64,'classification':'UNKNOWN','hypothesis':'inspect original','confidence':'LOW','verification':'review original','affected_requirements':['REQ'],'evidence_refs':['a'*64],'policy':{'max_total':2,'max_stage':1,'max_no_progress':1,'max_elapsed_ms':1000}},
      'document_project':{'document_id':'selection','revision':1},
      'work_create':{'relative_directory':'new-work','specification_json':'{"work_id":"new-work"}'},
      'context_publish':{'request_json':'{"recipe":"current-v1"}','token_count_json':''},
      'discovery_snapshot':{'plan_json':'{"schema_version":1,"timeout_seconds":1,"repositories":[]}'},
      'profile_register':{'profile_json':'{"schema_version":1}','key':'native-key'},
      'run_link':{'binding':'b'*64,'journal_base64':base64.b64encode(b'original journal').decode(),'run_id':'run-1','records':1,'bytes':16,'chain_head':'a'*64},
      'work_noop_run':{'capsule_json':'{"schema_version":1}'},
      'adapter_noop_run':{'request_json':'{"type":"run_stage"}'},
      'lineage_store':{'graph_base64':base64.b64encode(b'original graph').decode()},
      'approval_request':{**common,'operation':'request','action':{'work_id':'a','operation':'prepare'},'ttl_ms':1000},
    }


def envelope(name,value):
    return {'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),'body':'','context_json':'','count_json':c.encoded({'contract_digest':'a'*64}).decode() if name=='role_enroll' else '', 'approval':None}


class TaskActions(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','observed','capture','run_call','draft','plan_args','make_active','owner_api'):
        locals()[name]=getattr(m2.Preparations,name)
    def setUp(self):m2.Preparations.setUp(self)
    def test_all_twenty_are_closed_exact_shapes(self):
        self.assertEqual(set(cases()),set(tasks.NAMES));self.assertEqual(len(tasks.NAMES),20)
        for name,value in cases().items():
            entry={'tool':name,'work_id':'a','session_id':'owner-session','native_binding_id':''}
            self.assertEqual(actions.action_shape(entry,envelope(name,value)),value)
            for changed in ({**value,'argv':['sh']},{**value,'approve':True}):
                self.expect('SCHEMA',lambda:actions.action_shape(entry,envelope(name,changed)))
    def test_approval_request_cannot_approve_deny_or_cross_work(self):
        entry={'tool':'approval_request','work_id':'a','session_id':'owner-session','native_binding_id':''}
        for op in ('approve','deny','revoke','recover','expire'):
            value={**cases()['approval_request'],'operation':op};self.expect('SCHEMA',lambda:actions.action_shape(entry,envelope('approval_request',value)))
        value=cases()['approval_request'];value['action']['work_id']='foreign'
        self.expect('TASK_APPROVAL_SCOPE',lambda:actions.action_shape(entry,envelope('approval_request',value)))
    def test_token_owner_and_binary_bounds(self):
        entry={'tool':'session_heartbeat','work_id':'a','session_id':'other','native_binding_id':''}
        self.expect('NATIVE_OWNER_MAPPING',lambda:actions.action_shape(entry,envelope('session_heartbeat',cases()['session_heartbeat'])))
        for text in ('!','',base64.b64encode(b'x'*(c.LIMIT+1)).decode()):
            with self.assertRaises(c.IntegrationError):tasks.binary(text)
    def test_twenty_fixed_argv_routes_preserve_input_and_local_spool(self):
        prefixes={'session_start':['session','call'],'session_heartbeat':['session','call'],'session_reject_output':['session','call'],'binding_attach':['agent','binding','attach'],'role_enroll':['role','call'],'role_assess':['role','call'],'completion_finalize':['completion','call'],'completion_report':['completion','report'],'reentry_decide':['reentry','call'],'reentry_report':['reentry','report'],'document_project':['document','project'],'work_create':['work','start'],'context_publish':['context','publish'],'discovery_snapshot':['discovery','snapshot'],'profile_register':['profile','register'],'run_link':['profile','link'],'work_noop_run':['run','--noop'],'adapter_noop_run':['adapter','noop','run-file'],'lineage_store':['lineage','store'],'approval_request':['approval','call']}
        project={'root':str(self.project),'works':[{'work_id':'a'}]}
        for name,value in cases().items():
            with self.subTest(tool=name):
                output=self.root/('argv-'+name);output.mkdir(mode=0o700);action=envelope(name,value);records=tasks.records
                records.save(output/'request.json',action['native_json'].encode())
                entry={'tool':name,'work_id':'a','session_id':'owner-session','native_binding_id':''}
                argv=tasks.command(entry,project,{'path':str(self.work)},action,output)
                self.assertEqual(argv[:len(prefixes[name])],prefixes[name]);self.assertNotIn('sh',argv)
                if name=='work_noop_run':self.assertEqual(argv[-1],str(output/'simulation'))
                if name=='work_create':self.assertEqual(argv[2],str(self.project/'new-work'));self.assertFalse((self.project/'new-work').exists())
                if name=='role_enroll':self.assertEqual(argv[-1],'a'*64)
                if name=='run_link':self.assertEqual((output/'journal.bin').read_bytes(),b'original journal')
    def test_creation_does_not_register_and_refuses_existing_symlink_or_registered_identity(self):
        entry={'tool':'work_create'};request=cases()['work_create'];project={'root':str(self.project),'works':[{'work_id':'a'}]}
        tasks.authorize(entry,request,project,require_new=True)
        target=self.project/'new-work';target.symlink_to(self.work,target_is_directory=True)
        self.expect('TASK_DESTINATION_EXISTS',lambda:tasks.authorize(entry,request,project,require_new=True))
        # Historical result retrieval is not blocked merely because creation already succeeded.
        tasks.authorize(entry,request,project)
        request['specification_json']='{"work_id":"a"}'
        self.expect('TASK_WORK_ALREADY_REGISTERED',lambda:tasks.authorize(entry,request,project))
    def test_discovery_cannot_read_other_roots_parent_paths_or_symlinks(self):
        entry={'tool':'discovery_snapshot'};project={'root':str(self.project)}
        for root,paths in (('/private',['secret']),(str(self.project),['../secret']),(str(self.project),['.git/config'])):
            request={'plan_json':c.encoded({'repositories':[{'root':root,'paths':paths}]}).decode()}
            self.expect('TASK_DISCOVERY_SCOPE',lambda:tasks.authorize(entry,request,project))
    def test_m2_start_heartbeat_rejection_and_binding_fences(self):
        self.make_active()
        for name,fields in (('session_start',{'selection_id':'selection'}),('session_heartbeat',{'ttl_ms':1000}),('session_reject_output',{'output':cases()['session_reject_output']['output'],'evidence':['d'*64],'approval_digest':'f'*64}),('binding_attach',{'descriptor_digest':'a'*64,'native_thread_id':'opaque','ttl_ms':1000})):
            result=self.draft(name,fields);value=c.decode(result['plan']['payload']['action']['native_json'].encode())
            self.assertEqual(value['expected_sequence'],1);self.assertEqual(value['key'].__len__(),32)
            self.assertEqual(self.captures[-1][3:5],['session','validate'] if name.startswith('session_') else ['agent','binding'])
            self.assertFalse(result['plan']['native_state_changed'])
    def test_m2_missing_role_approval_and_other_semantics_are_questions(self):
        result=self.draft('role_enroll',{'selection_id':'selection','contract':{}})
        self.assertIn('count_json.contract_digest',{q['field'] for q in result['plan']['payload']['questions']})
        result=self.draft('completion_finalize',{'selection_id':'selection','issues':[]})
        self.assertEqual(self.captures[-1][3:5],['completion','validate']);self.assertEqual(result['plan']['payload']['blockers'],[])
    def test_reentry_sequence_is_not_session_sequence(self):
        value=cases()['reentry_decide'];fields={k:v for k,v in value.items() if k not in ('key','expected_sequence','schema_version','operation')};fields['reentry_sequence']=0
        result=self.draft('reentry_decide',fields);native=c.decode(result['plan']['payload']['action']['native_json'].encode())
        self.assertEqual(native['expected_sequence'],0);self.assertEqual(result['plan']['basis']['sequence'],1)
    def test_role_completion_version_two_is_explicit_and_retained(self):
        result=self.draft('completion_finalize',{'selection_id':'selection','issues':[],'completion_schema_version':2})
        native=c.decode(result['plan']['payload']['action']['native_json'].encode())
        self.assertEqual(native['schema_version'],2)
        self.assertNotIn('completion_schema_version',native)
    def test_fixture_cycle_prepares_reviews_dispatches_and_then_reads_historical_results(self):
        self.make_active();trace=[]
        for tool,fields in (('session_start',{'selection_id':'selection'}),('session_heartbeat',{'ttl_ms':1000}),('role_assess',{'selection_id':'selection','review':None}),('completion_finalize',{'selection_id':'selection','issues':[],'completion_schema_version':2}),('completion_report',{'sequence':1})):
            draft=self.draft(tool,fields);action=draft['plan']['payload']['action'];api,path=self.owner_api(action,tool=tool)
            reviewed=self.run_call('approved_action_prepare',{'action_id':'reviewed'},api.reads)
            with patch.object(api.reads,'_read',self.observed):
                confirmation=api.call('action_confirm',{'project_id':'p','work_id':'a',**self.plan_args(reviewed),'action_id':'reviewed'})
            calls=[]
            def capture(argv,output,*a,**kw):
                calls.append(argv);self.assertTrue((output/'dispatch-intent.json').exists())
                raw=b'# historical completion\n' if tool=='completion_report' else b'{"recorded":true}\n'
                (output/'stdout.log').write_bytes(raw);(output/'stdout.log').chmod(0o600)
                return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
            with patch.object(api.reads,'call',lambda name,args:self.observed(None,'a',args['view'])),patch.object(mutations.records,'capture',capture):
                result=api.call(tool,confirmation['d4_invocation']['arguments']);again=api.call(tool,confirmation['d4_invocation']['arguments'])
            self.assertEqual(result['state'],'NATIVE_RESULT_RECORDED',result);self.assertEqual(again,result);self.assertEqual(len(calls),1)
            self.assertFalse(result['acceptance_verified']);trace.append(tool)
            if tool.startswith('session_'):
                self.status['sequence']+=1;self.following['sequence']+=1;self.record['status']['sequence']+=1
        self.assertEqual(trace,['session_start','session_heartbeat','role_assess','completion_finalize','completion_report'])
    def test_m2_native_reference_and_generation_drift_rejects(self):
        request=cases()['completion_finalize'];entry={'tool':'completion_finalize'}
        tasks.validate_observed(entry,request,{'record':self.record,'status':self.status,'next':self.following})
        self.following['document_generation']=3
        self.expect('PREPARATION_STALE',lambda:tasks.validate_observed(entry,request,{'record':self.record,'status':self.status,'next':self.following}))
    def test_owner_bytes_confirmed_without_dispatch(self):
        action=envelope('completion_finalize',cases()['completion_finalize']);api,path=self.owner_api(action,tool='completion_finalize')
        result=self.run_call('approved_action_prepare',{'action_id':'reviewed'},api.reads)
        with patch.object(mutations.records,'capture',side_effect=AssertionError('confirmation cannot dispatch')):
            # _read is the explicit native observation double, no validator at confirmation.
            with patch.object(api.reads,'_read',self.observed):
                answer=api.call('action_confirm',{'project_id':'p','work_id':'a',**self.plan_args(result),'action_id':'reviewed'})
        self.assertEqual(answer['d4_invocation']['tool'],'completion_finalize');self.assertEqual(answer['d4_admission'],'NOT_RUN')
        self.assertEqual(path.read_bytes(),c.encoded(action))


class Dispatch(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','repin','api','preflight','capture'):
        locals()[name]=getattr(d4.D4,name)
    def setUp(self):d4.D4.setUp(self)
    def select(self,name):
        self.entry['tool']=name;self.native=cases()[name];self.action=envelope(name,self.native);self.repin();return self.api()
    def invoke(self,api,capture=None):
        with patch.object(api,'_preflight',self.preflight),patch.object(mutations.records,'capture',capture or self.capture):return api.call(self.entry['tool'],self.args)
    def test_new_action_requires_exact_owner_scope_and_cannot_inject_native_json(self):
        api=self.select('session_heartbeat');self.assertIn('session_heartbeat',api.tools());self.assertNotIn('completion_finalize',api.tools())
        self.expect('SCHEMA',lambda:api.call('session_heartbeat',{**self.args,'native_json':'{}'}))
        self.expect('MUTATION_SCOPE',lambda:api.call('completion_finalize',self.args))
    def test_each_action_uses_durable_intent_and_one_dispatch_only(self):
        # Independent disposable registry for each action; all native effects are doubles.
        for name in tasks.NAMES:
            with self.subTest(tool=name):
                api=self.select(name)
                args={**self.args,'request_id':'request-'+name}
                def capture(argv,output,*a,**kw):
                    self.assertTrue((output/'dispatch-intent.json').exists());raw=b'# historical report\n' if name.endswith('_report') else b'{ "committed":true }\n'
                    (output/'stdout.log').write_bytes(raw);(output/'stdout.log').chmod(0o600)
                    return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
                with patch.object(api,'_preflight',self.preflight),patch.object(mutations.records,'capture',capture) as cap:
                    result=api.call(name,args);again=api.call(name,args)
                self.assertEqual(result['state'],'NATIVE_RESULT_RECORDED',result);self.assertEqual(result,again)
                self.assertFalse(result['acceptance_verified']);self.assertFalse(result['execution_authorized'])
                self.assertTrue(base64.b64decode(result['native_stdout_base64']))
    def test_timeout_blocks_fresh_id_and_does_not_retry(self):
        api=self.select('session_heartbeat')
        def failed(*a,**kw):raise OSError('result lost')
        result=self.invoke(api,failed);self.assertEqual(result['state'],'COMMIT_UNKNOWN')
        with patch.object(mutations.records,'capture',side_effect=AssertionError('no retry')):
            self.assertEqual(api.call('session_heartbeat',self.args),result)
            self.expect('WORK_MUTATION_UNRESOLVED',lambda:api.call('session_heartbeat',{**self.args,'request_id':'new'}))
    def test_current_sequence_preflight_remains_required(self):
        api=self.select('session_heartbeat')
        def read(name,args):return {'result':{'sequence':2}}
        with patch.object(api.reads,'call',read):self.expect('OBSERVATION_STALE',lambda:api._preflight(self.entry,self.native))
    def test_result_recording_failure_and_changed_action_do_not_redispatch(self):
        api=self.select('completion_finalize')
        with patch.object(api,'_publish',side_effect=OSError('disk')):result=self.invoke(api)
        self.assertEqual(result['state'],'COMMIT_UNKNOWN')
        self.action_path.write_bytes(self.action_path.read_bytes()+b' ')
        self.expect('ACTION_CHANGED',lambda:api.call('completion_finalize',self.args))


class NativeValidators(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('GOLEM_M3_COMPONENT_CLI'),'explicit pure validator component opt-in')
    def test_only_pure_new_validators_on_temporary_json(self):
        cli=os.environ['GOLEM_M3_COMPONENT_CLI']
        binding=cases()['binding_attach'];role=cases()['role_assess']
        spec=c.decode((Path(__file__).resolve().parents[1]/'samples/documents/work.json').read_bytes())
        approval=cases()['approval_request'];approval['action']={'schema_version':1,'domain':'golem.approval-action.v1','work_id':'a','operation':'prepare','binding_id':'','token':None,**{field:'a'*64 for field in ('request_digest','policy_digest','contract_digest','input_digest','source_digest','executables_digest','profile_digest','role_digest')}}
        completion={**cases()['completion_finalize'],'schema_version':2}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp).resolve()/'request.json'
            for route,value in ((['agent','binding','validate'],binding),(['role','request-validate'],role),(['approval','validate'],approval),(['work','validate'],spec),(['completion','validate'],completion)):
                path.write_bytes(c.encoded(value));run=subprocess.run([cli,'--output-mode','full',*route,str(path)],cwd=path.parent,capture_output=True)
                self.assertEqual(run.returncode,0,run.stderr);self.assertTrue(c.decode(run.stdout)['structurally_valid'])
                path.write_bytes(c.encoded({**value,'approve':True}));run=subprocess.run([cli,'--output-mode','full',*route,str(path)],cwd=path.parent,capture_output=True);self.assertNotEqual(run.returncode,0)
