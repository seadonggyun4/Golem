"""M5 temporary scopes and fixed capture doubles. No live host/client/Work E2E."""
import base64
import copy
import os
from pathlib import Path
import socket
import subprocess
import unittest
from unittest.mock import patch
import integration_contract as c
import integration_registry as r
import integration_parallel_reads as views
import integration_parallel_actions as actions
import integration_parallel_hosts as hosts
import integration_parallel_preparations as proposals
import integration_quality_reads as quality
import integration_mutation_contract as contract
import integration_mutations as mutations
import integration_preparations as prep
import test_integration_m2 as m2
import test_integration_mutations as d4

ROOT=Path(__file__).resolve().parents[1]

def envelope(value):return {'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),'body':'','context_json':'','count_json':'','approval':None}

def task(task_id='task',work_id='a'):
    return {'task_id':task_id,'work_id':work_id,'selection':{'document_id':'selection','revision':1,'digest':'c'*64},'spec_digest':'d'*64,'source_snapshot':'0'*64,'owner_session_id':'owner-session','runtime_binding':'e'*64,'resources':{'slots':1,'cpu_millis':100,'memory_bytes':4096},'candidate':None}

def dag():return {'schema':'golem.parallel-review-input.v1','baseline_digest':'b'*64,'tasks':[task()],'edges':[]}

def edge(start='task',end='second'):
    return {'edge_id':'edge','predecessor_task':start,'successor_task':end,'type':'QA_ACCEPTED','predecessor_spec_digest':'d'*64,'selected_attempt_ref':None,'required_artifact_refs':[],'evidence_policy_digest':'e'*64,'consumption_mode':'PRODUCT','baseline_digest':'b'*64}

class ViewsAndPlans(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','observed','capture','run_call','draft','plan_args','make_active','owner_api'):
        locals()[name]=getattr(m2.Preparations,name)
    def setUp(self):m2.Preparations.setUp(self)
    def test_all_closed_candidate_and_inventory_argv(self):
        inputs=[('candidate_read',{'operation':op,'request_json':'{}'}) for op in ('validate','host_validate','request_digest','context_candidate')]
        inputs += [('candidate_read',{'operation':'gates','checkpoint':'a'*64}),('candidate_read',{'operation':'status','group_id':'group'}),('candidate_read',{'operation':'diff','group_id':'group','candidate':'one'}),('inventory_read',{'operation':'validate','policy_json':'{}'}),('inventory_read',{'operation':'compare','policy_json':'{}','baseline_json':'{}','current_json':'{}'})]
        for i,(name,value) in enumerate(inputs):
            output=self.root/str(i);output.mkdir(mode=0o700);args={'project_id':'p','work_id':'a',**value}
            argv=views.command(name,args,str(self.work),output)
            self.assertNotIn('--approve-request',argv);self.assertNotIn('merge',argv)
            self.expect('SCHEMA',lambda:views.command(name,{**args,'path':'/secret'},str(self.work),output))
    def test_read_preserves_native_digest_and_exact_bytes(self):
        raw=b'a'*64+b'\n'
        def capture(argv,output,*a,**kw):
            (output/'stdout.log').write_bytes(raw);(output/'stdout.log').chmod(0o600)
            return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        before=self.inventory()
        with patch.object(self.api,'_read',self.observed),patch.object(quality.records,'capture',capture):
            result=self.api.call('candidate_read',{'project_id':'p','work_id':'a','operation':'request_digest','request_json':'{ "operation":"finish" }'})
        self.assertEqual(result['result']['native_digest'],'a'*64);self.assertEqual(base64.b64decode(result['native_stdout']['data']),raw)
        self.assertFalse(result['merge_authorized']);self.assertFalse(result['target_adoption_verified']);self.assertEqual(before,self.inventory())
    def test_inventory_capture_draft_uses_native_policy_validator(self):
        result=self.draft('inventory_capture',{'policy_json':'{}'})
        self.assertEqual(self.captures[-1][3:5],['inventory','validate']);self.assertFalse(result['plan']['approval_created'])
    def test_candidate_draft_never_uses_hash_as_native_state_validation(self):
        result=self.draft('candidate_request',{'host_id':'selected','request_json':'{ "operation":"reserve","group_id":"group","candidate":"one" }'})
        self.assertEqual(result['plan']['payload']['validation']['validation_scope'],'D4_REQUEST_SHAPE_ONLY')
        self.assertIn({'code':'SEPARATE_OWNER_PARALLEL_HOST_REQUIRED'},result['plan']['payload']['blockers']);self.assertEqual(self.captures,[])
    def test_host_and_workspace_shapes_cannot_smuggle_generic_command_or_raw_finish(self):
        for tool,value in [('candidate_request',{'operation':'finish'}),('candidate_request',{'operation':'grant'}),('workspace_request',{'operation':'merge'}),('candidate_request',{'operation':'shutdown'})]:
            self.expect('HOST_OPERATION_SCOPE',lambda:actions.shape({'tool':tool},envelope({'host_id':'selected','request_json':c.encoded(value).decode()})))
        self.expect('SCHEMA',lambda:actions.shape({'tool':'inventory_capture'},envelope({'policy_json':'{}','root':'/secret'})))
    def test_inventory_capture_exact_d4_replay_and_fixed_root(self):
        api,_=self.owner_api(envelope({'policy_json':'{}'}),tool='inventory_capture');calls=[]
        def capture(argv,output,*a,**kw):
            calls.append(argv);self.assertEqual(argv[3:6],['inventory','capture',str(self.project)]);self.assertTrue((output/'dispatch-intent.json').exists())
            (output/'stdout.log').write_bytes(b'{}');(output/'stdout.log').chmod(0o600);return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        args={'project_id':'p','work_id':'a','action_id':'reviewed','request_id':'one'}
        with patch.object(api,'_preflight',lambda *a:{}),patch.object(mutations.records,'capture',capture):
            result=api.call('inventory_capture',args);self.assertEqual(api.call('inventory_capture',args),result)
        self.assertEqual(len(calls),1)
    def proposal(self,name,value,request='proposal-one'):
        with patch.object(self.api,'_read',self.observed):
            return self.api.call(name,{'project_id':'p','work_id':'a','preparation_request_id':request,'proposal_json':c.encoded(value).decode()})
    def test_dag_plan_uses_m2_seal_and_remains_explicitly_unimplemented(self):
        before=self.inventory();result=self.proposal('parallel_prepare',dag());payload=result['plan']['payload']
        self.assertEqual(payload['scheduler_state'],'NOT_IMPLEMENTED');self.assertEqual(payload['readiness'],'NOT_EVALUATED');self.assertFalse(payload['resources_reserved'])
        again=self.proposal('parallel_prepare',dag());self.assertEqual(again['plan_sha256'],result['plan_sha256'])
        self.assertEqual(before,self.inventory())
        with patch.object(self.api,'_read',self.observed):
            loaded=self.api.call('plan_read',{'project_id':'p','work_id':'a',**self.plan_args(result)})
        self.assertEqual(loaded['plan']['payload'],payload)
    def test_dag_cycle_missing_node_spec_drift_and_exploratory_promotion_block(self):
        value=dag();value['tasks'].append(task('second','b'));value['edges']=[edge()]
        self.assertEqual(proposals.structure('parallel_prepare',value),['a','b'])
        bad=copy.deepcopy(value);bad['edges'].append({**edge('second','task'),'edge_id':'reverse'});self.expect('PARALLEL_CYCLE',lambda:proposals.structure('parallel_prepare',bad))
        bad=copy.deepcopy(value);bad['edges'][0]['successor_task']='missing';self.expect('PARALLEL_EDGE_REFERENCE',lambda:proposals.structure('parallel_prepare',bad))
        bad=copy.deepcopy(value);bad['edges'][0]['predecessor_spec_digest']='f'*64;self.expect('PARALLEL_EDGE_DRIFT',lambda:proposals.structure('parallel_prepare',bad))
        bad=copy.deepcopy(value);bad['edges'][0]['type']='ARTIFACT_OBSERVED';self.expect('PARALLEL_EDGE_MODE',lambda:proposals.structure('parallel_prepare',bad))
    def test_dag_duplicate_work_and_reference_drift_block(self):
        value=dag();value['tasks'].append(task('second','a'));self.expect('PARALLEL_DUPLICATE_TASK_OR_WORK',lambda:proposals.structure('parallel_prepare',value))
        result=self.proposal('parallel_prepare',dag());self.record['documents'][0]['digest']='f'*64
        with patch.object(self.api,'_read',self.observed):
            self.expect('PARALLEL_SELECTION_DRIFT',lambda:self.api.call('plan_read',{'project_id':'p','work_id':'a',**self.plan_args(result)}))
    def test_dag_missing_work_no_fallback_and_no_dispatch(self):
        value=dag();value['tasks'][0]['work_id']='foreign'
        with patch.object(quality.records,'capture',side_effect=AssertionError('no command')):
            self.expect('TRANSFER_SCOPE',lambda:self.proposal('parallel_prepare',value))
    def test_merge_input_requires_exact_oid_and_isolation(self):
        value={'schema':'golem.merge-review-input.v1','source_work_id':'a','target_work_id':'b','candidate':{'group_id':'group','candidate':'one'},**{key:'a'*64 for key in ('candidate_result','selection_receipt','qa_receipt','review_receipt','baseline_digest','source_snapshot','input_digest','tree_digest','target_policy_digest')},'target_oid':'a'*40,'target_ref_generation':1}
        self.assertEqual(proposals.structure('merge_prepare',value),['a','b'])
        self.expect('SCHEMA',lambda:proposals.structure('merge_prepare',{**value,'target_oid':'main'}))
        self.expect('MERGE_WORK_ISOLATION',lambda:proposals.structure('merge_prepare',{**value,'target_work_id':'a'}))
    def test_merge_plan_revalidates_both_registered_work_bases(self):
        child=self.project/'.golem/works/b';(child/'events').mkdir(parents=True);(child/'events/00000001.evt').write_bytes(b'synthetic child')
        self.enrollment['project']=r.describe('p',self.project,self.cli,[self.sdk],[('a',self.work),('b',child)])
        self.enrollment['grants'][0]['work_ids']=['a','b'];self.approve()
        self.policy['scopes'][0]['binding']['generation']=2;self.policy['scopes'][0]['work_ids']=['a','b'];self.save_policy()
        self.api=__import__('integration_service').Service(self.adapter());drift=False
        def observed(scope,work_id,operation,*unused):
            result=self.observed(scope,work_id,operation)
            if operation=='record':
                result['result']['work_id']=work_id;result['result']['work_specification']['work_id']=work_id
                if drift and work_id=='b':result['result']['agent_head']='f'*64
            return result
        value={'schema':'golem.merge-review-input.v1','source_work_id':'a','target_work_id':'b','candidate':{'group_id':'group','candidate':'one'},**{key:'a'*64 for key in ('candidate_result','selection_receipt','qa_receipt','review_receipt','baseline_digest','source_snapshot','input_digest','tree_digest','target_policy_digest')},'target_oid':'a'*40,'target_ref_generation':1}
        args={'project_id':'p','work_id':'a','preparation_request_id':'merge','proposal_json':c.encoded(value).decode()}
        with patch.object(self.api,'_read',observed):
            result=self.api.call('merge_prepare',args);payload=result['plan']['payload']
            self.assertEqual(payload['merge_state'],'NOT_IMPLEMENTED');self.assertFalse(payload['qa_pass_verified']);self.assertFalse(payload['target_ref_cas_verified'])
            self.assertEqual(set(result['plan']['basis']['parallel_works']),{'a','b'})
            drift=True
            self.expect('PREPARATION_STALE',lambda:self.api.call('plan_read',{'project_id':'p','work_id':'a',**self.plan_args(result)}))
    def test_old_transfer_and_remote_allowlist_gain_no_tools(self):
        import integration_gateway_contract as gateway
        self.assertFalse(set((*views.NAMES,*actions.NAMES,*proposals.NAMES))&set(gateway.REMOTE_READ_NAMES))
        self.policy['scopes'][0]['tools']=[name for name in self.policy['scopes'][0]['tools'] if name not in (*views.NAMES,*proposals.NAMES)];self.save_policy()
        self.assertFalse(set((*views.NAMES,*proposals.NAMES))&set(self.adapter().value['scopes'][0]['tools']))

class OwnerHost(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','repin','preflight'):
        locals()[name]=getattr(d4.D4,name)
    def setUp(self):
        d4.D4.setUp(self)
        self.child=self.project/'.golem/works/b';(self.child/'events').mkdir(parents=True)
        (self.child/'events/00000001.evt').write_bytes(b'synthetic child genesis')
        self.enrollment['project']=r.describe('p',self.project,self.cli,[self.sdk],[('a',self.work),('b',self.child)])
        self.enrollment['grants'][0]['work_ids']=['a','b'];self.approve()
        self.policy['scopes'][0]['binding']['generation']=2;self.policy['scopes'][0]['work_ids']=['a','b'];self.save_policy()
        self.entry['tool']='candidate_request';self.set_request({'operation':'reserve','group_id':'group','candidate':'one'})
        self.owner=contract.Policy(self.mutation_path,self.mutation_digest,approve_mutations=True)
        for path in (self.project/'.golem/worktrees',self.project/'.golem/admission'):
            path.mkdir(mode=0o700)
        self.config={'schema_version':1,'parent':str(self.work),'admission':str(self.project/'.golem/admission'),'repository_id':'repo','repository_root':str(self.project),'worktree_root':str(self.project/'.golem/worktrees'),'limits':{'slots':1,'cpu_millis':1000,'memory_bytes':10000},'bindings':[{'candidate':'one','session':'owner-session','runtime_binding':'e'*64,'work':str(self.child),'tree':str(self.project/'.golem/worktrees/b/one'),'build':str(self.project/'.golem/build/b'),'temp':str(self.project/'.golem/temp/b'),'environment':'f'*64}],'target':None}
        self.config_path=self.root/'host-config.json';self.config_path.write_bytes(c.encoded(self.config));self.config_path.chmod(0o600)
        socket_dir=self.root/'socket';socket_dir.mkdir(mode=0o700);self.socket_path=socket_dir/'host.sock'
        self.socket=socket.socket(socket.AF_UNIX);self.socket.bind(str(self.socket_path));self.socket_path.chmod(0o600);self.addCleanup(self.socket.close)
        info=self.socket_path.stat()
        self.row={'host_id':'selected','project_id':'p','parent_work_id':'a','config':r.file_pin(self.config_path),'config_digest':'d'*64,'socket':{'path':str(self.socket_path),'identity':{'device':info.st_dev,'inode':info.st_ino}},'work_ids':['a','b'],'roots':[{'path':self.config[key],'identity':r.identity(Path(self.config[key]))} for key in ('repository_root','worktree_root','admission')],'operations':list(hosts.OPS),'actions':[{'action_id':'claim','action_sha256':self.entry['action']['sha256'],'request_digest':'e'*64,'termination':None}],'queries':[]}
        self.host_path=self.root/'host-policy.json';self.persist()
        self.calls=[]
    def set_request(self,value):
        self.action=envelope({'host_id':'selected','request_json':c.encoded(value).decode()});self.repin()
    def persist(self):
        value={'schema':'golem.integration-parallel-hosts.v1','mutation_policy_sha256':self.mutation_digest,'transfer_policy_sha256':self.digest,'hosts':[self.row],'producer':hosts.producer()}
        self.host_path.write_bytes(c.encoded(value));self.host_path.chmod(0o600)
        self.bridge=hosts.Hosts(self.host_path,c.sha(self.host_path.read_bytes()),self.owner,approve_hosts=True)
        self.api=mutations.Service(self.owner,parallel_hosts=self.bridge)
    def capture(self,argv,output,*a,**kw):
        self.calls.append(argv);self.assertEqual(kw['env'],mutations.backend.ENVIRONMENT)
        if argv[3:5]==['candidate','host-validate']:raw=b'd'*64+b'\n'
        else:
            request=c.decode(Path(argv[6]).read_bytes());op=request['operation']
            if op=='host-info':value={'config_digest':'d'*64,'parent_work_id':'a','repository_id':'repo'}
            elif op=='work-record':value={'schema':'golem.work-record.v1','work_id':'a','work_specification':{'work_id':'a'},'execution_authorized':False}
            elif op in ('work-status','work-next'):value={'sequence':1}
            else:value={'historical':True,'merge_authorized':False}
            raw=c.encoded(value)
        (output/'stdout.log').write_bytes(raw);(output/'stdout.log').chmod(0o600)
        return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
    def test_opt_in_default_off_and_separate_from_m4_helper(self):
        self.expect('OWNER_PARALLEL_HOST_APPROVAL_REQUIRED',lambda:hosts.Hosts(self.host_path,c.sha(self.host_path.read_bytes()),self.owner))
        api=mutations.Service(self.owner);self.assertNotIn('candidate_request',api.tools());self.assertNotIn('workspace_read',api.tools())
        self.expect('OWNER_PARALLEL_HOST_REQUIRED',lambda:api.call('candidate_request',self.args))
        self.assertEqual(list(self.registry.root.glob('mutation-*')),[])
    def test_exact_host_action_original_result_and_single_dispatch(self):
        before=self.inventory()
        with patch.object(hosts.records,'capture',self.capture):
            result=self.api.call('candidate_request',self.args);again=self.api.call('candidate_request',self.args)
            self.assertEqual(result,again)
            self.expect('PARALLEL_ACTION_ALREADY_DISPATCHED_REVIEW_ORIGINAL',lambda:self.api.call('candidate_request',{**self.args,'request_id':'other'}))
        self.assertEqual(result['state'],'NATIVE_RESULT_RECORDED',result)
        actions_seen=[argv for argv in self.calls if '--approve-request' in argv];self.assertEqual(len(actions_seen),1)
        self.assertNotIn('--attest-termination',actions_seen[0]);self.assertEqual(before,self.inventory())
    def test_socket_identity_config_and_roots_pin_drift_block_before_intent(self):
        self.row['socket']['identity']['inode']+=1;self.persist()
        self.expect('PARALLEL_HOST_SOCKET_CHANGED',lambda:self.api.call('candidate_request',self.args))
        self.assertEqual(list(self.registry.root.glob('mutation-*')),[])
    def test_config_bytes_or_action_pin_changes_block(self):
        self.config_path.write_bytes(self.config_path.read_bytes()+b' ')
        self.expect('PARALLEL_HOST_CONFIG_CHANGED',lambda:self.bridge.select(self.entry,self.action))
    def test_cross_work_scope_and_foreign_target_block(self):
        self.row['work_ids']=['a'];self.persist()
        self.expect('PARALLEL_HOST_WORK_SCOPE',lambda:self.bridge.select(self.entry,self.action))
        value=c.decode(self.host_path.read_bytes());other=copy.deepcopy(self.row);other.update(host_id='other-host',parent_work_id='b')
        value['hosts'].append(other);self.host_path.write_bytes(c.encoded(value))
        self.expect('DUPLICATE_HOST',lambda:hosts.Hosts(self.host_path,c.sha(self.host_path.read_bytes()),self.owner,approve_hosts=True))
    def test_terminal_operation_requires_separate_exact_attestation(self):
        self.entry['tool']='workspace_request';self.set_request({'operation':'workspace-seal','candidate':'one'})
        self.owner=contract.Policy(self.mutation_path,self.mutation_digest,approve_mutations=True)
        self.row['actions'][0]['action_sha256']=self.entry['action']['sha256'];self.persist()
        self.expect('OPERATOR_TERMINATION_ATTESTATION_REQUIRED',lambda:self.bridge.select(self.entry,self.action))
        attestation={'schema':'golem.integration-operator-termination.v1','host_id':'selected','config_digest':'d'*64,'action_sha256':self.entry['action']['sha256'],'request_digest':'e'*64,'all_workers_stopped':True,'trust':'OPERATOR_ATTESTED_NOT_PROCESS_REAPING_OBSERVATION'}
        path=self.root/'attestation.json';path.write_bytes(c.encoded(attestation));path.chmod(0o600)
        self.row['actions'][0]['termination']=r.file_pin(path);self.persist()
        output=self.root/'command';output.mkdir(mode=0o700);argv=self.bridge.command(self.entry,self.action,output)
        self.assertEqual(argv[-2:],['--attest-termination','e'*64]);self.assertEqual((output/'host-request.json').read_bytes(),c.decode(self.action['native_json'].encode())['request_json'].encode())
    def test_native_server_config_mismatch_and_lost_result_never_retry(self):
        def capture(argv,output,*a,**kw):
            if '--approve-request' in argv:raise OSError('fixture result lost')
            return self.capture(argv,output,*a,**kw)
        with patch.object(hosts.records,'capture',capture):
            result=self.api.call('candidate_request',self.args);again=self.api.call('candidate_request',self.args)
        self.assertEqual(result['state'],'COMMIT_UNKNOWN');self.assertEqual(result,again)
        self.assertFalse(result['automatic_retry_allowed'])
    def test_server_config_digest_mismatch_blocks_without_action_dispatch(self):
        def capture(argv,output,*a,**kw):
            result=self.capture(argv,output,*a,**kw)
            if argv[3:5]==['candidate','call'] and c.decode(Path(argv[6]).read_bytes())['operation']=='host-info':
                (output/'stdout.log').write_bytes(c.encoded({'config_digest':'f'*64,'parent_work_id':'a','repository_id':'repo'}))
            return result
        with patch.object(hosts.records,'capture',capture):result=self.api.call('candidate_request',self.args)
        self.assertEqual(result['state'],'NOT_DISPATCHED');self.assertEqual(result['code'],'PARALLEL_HOST_SERVER_CONFIG_CHANGED')
        self.assertFalse(any('--approve-request' in argv for argv in self.calls))
    def test_every_host_operation_argv_preserves_native_json_and_unknown_accounting(self):
        for name,operations in (('candidate_request',actions.CANDIDATE_OPS),('workspace_request',actions.WORKSPACE_OPS)):
            for op in operations:
                request={'operation':op,'candidate':'one'}
                if op=='settle':request.update(tokens_known=False,cost_known=False,tokens=0,nano_cost=0)
                value=envelope({'host_id':'selected','request_json':c.encoded(request).decode()})
                entry={**self.entry,'tool':name}
                # Selection/authentication is tested separately; this loop checks
                # exact argv/byte transport for the complete finite operation set.
                output=self.root/('argv-'+op);output.mkdir(mode=0o700)
                selected={**self.row['actions'][0],'termination':{'path':'fixture','sha256':'a'*64} if op in hosts.TERMINAL else None}
                with patch.object(self.bridge,'select',return_value=(self.row,selected,None)):
                    argv=self.bridge.command(entry,value,output)
                self.assertEqual((output/'host-request.json').read_bytes(),c.decode(value['native_json'].encode())['request_json'].encode())
                self.assertEqual('--attest-termination' in argv,op in hosts.TERMINAL)
                self.assertNotIn('serve',argv);self.assertNotIn('merge',argv)
                if op=='settle':self.assertFalse(c.decode((output/'host-request.json').read_bytes())['cost_known'])
    def test_workspace_read_retrieves_only_existing_d4_result_without_native_call(self):
        self.entry['tool']='workspace_request';self.set_request({'operation':'workspace-resume','candidate':'one'})
        self.owner=contract.Policy(self.mutation_path,self.mutation_digest,approve_mutations=True)
        self.row['actions'][0]['action_sha256']=self.entry['action']['sha256'];self.persist()
        before=list(self.registry.root.glob('mutation-*'))
        with patch.object(hosts.records,'capture',side_effect=AssertionError('no native query or new intent')):
            self.expect('ORIGINAL_RESULT_NOT_FOUND',lambda:self.api.call('workspace_read',{**self.args,'operation':'result'}))
        self.assertEqual(before,list(self.registry.root.glob('mutation-*')))
        with patch.object(hosts.records,'capture',self.capture):result=self.api.call('workspace_request',self.args)
        with patch.object(hosts.records,'capture',side_effect=AssertionError('historical result only')):
            observed=self.api.call('workspace_read',{**self.args,'operation':'result'})
        self.assertEqual(observed['result'],result);self.assertTrue(observed['historical_result']);self.assertFalse(observed['current_workspace_verified'])
    def test_original_parent_mutations_block_before_dispatch(self):
        entry={**self.entry,'tool':'context_publish'}
        # The production guard is reached before parsing unrelated action bytes.
        with patch.object(self.owner,'current',return_value={**self.mutation_policy,'actions':[entry]}):
            self.expect('PARALLEL_HOST_OWNS_PARENT_WORK',lambda:self.api.call('context_publish',self.args))
    def test_read_bridge_uses_native_held_work_handle_without_approval(self):
        scope=self.owner.transfer.scope('p','a','work_inspect')
        with patch.object(hosts.records,'capture',self.capture),patch.object(mutations.backend,'read',side_effect=AssertionError('no direct locked Work read')):
            result=self.api.reads._read(scope,'a','record')
        self.assertEqual(result['result']['work_id'],'a');self.assertTrue(self.calls)
        self.assertTrue(all('--approve-request' not in argv for argv in self.calls))
    def test_queries_only_exact_read_ops_pinned_owner_requests(self):
        path=self.root/'query.json';path.write_bytes(b'{ "operation":"compare", "group_id":"group" }');path.chmod(0o600)
        self.row['queries']=[{'query_id':'comparison','operation':'compare','request':r.file_pin(path),'request_digest':'f'*64}];self.persist()
        with patch.object(hosts.records,'capture',self.capture):
            result=self.bridge.query('p','a','compare','comparison')
        self.assertFalse(c.decode(result)['merge_authorized'])
        self.expect('PARALLEL_HOST_QUERY_SCOPE',lambda:self.bridge.query('p','a','select','comparison'))

class PureNativeComponents(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('GOLEM_M5_COMPONENT_CLI'),'explicit pure native parser component opt-in')
    def test_inventory_policy_native_cli(self):
        cli=os.environ['GOLEM_M5_COMPONENT_CLI']
        with __import__('tempfile').TemporaryDirectory(prefix='golem-m5-policy-') as directory:
            path=Path(directory).resolve()/'policy.json';path.write_text('{}')
            result=subprocess.run([cli,'--output-mode','full','inventory','validate',str(path)],capture_output=True,env=mutations.backend.ENVIRONMENT)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('GOLEM_ERR_PARSE',result.stderr.decode())
    @unittest.skipUnless(os.environ.get('GOLEM_M5_COMPONENT_CLI'),'explicit pure hash component opt-in')
    def test_native_request_digest_preserves_json_c_boundary(self):
        cli=os.environ['GOLEM_M5_COMPONENT_CLI']
        with __import__('tempfile').TemporaryDirectory(prefix='golem-m5-digest-') as directory:
            path=Path(directory).resolve()/'request.json';path.write_text('{ "operation":"reserve", "candidate":"one" }')
            result=subprocess.run([cli,'--output-mode','full','candidate','request-digest',str(path)],capture_output=True,env=mutations.backend.ENVIRONMENT)
            self.assertEqual(result.returncode,0);c._validate(result.stdout.strip().decode(),c.DIGEST)

if __name__=='__main__':unittest.main()
