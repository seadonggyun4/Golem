"""Owner resource fixtures only; no existing files/approvals/client or network."""
import base64
import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import integration_contract as c
import integration_service as service
import integration_read_resources as resources
import integration_read_views as views
import integration_gateway_contract as gateway
import test_integration_d2 as existing

class ResourceReads(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter'):
        locals()[name]=getattr(existing.D2,name)
    def setUp(self):
        existing.D2.setUp(self);self.transfer=self.adapter();self.source=self.root/'resources';self.source.mkdir()
        self.resource_path=self.root/'read-resources.json';self.description=None
        self.publish({'data.bin':b'\x00exact\xff'},['artifact_read'])
    def publish(self,files,tools):
        entries=[]
        for i,(name,data) in enumerate(files.items()):
            p=self.source/('file-'+str(i));p.write_bytes(data);p.chmod(0o600)
            entries.append({'file_id':'f'+str(i),'name':name,'path':str(p),'sha256':c.sha(data),'tools':list(tools)})
        self.description={'schema':'golem.integration-read-resources.v1','transfer_policy_sha256':self.transfer.digest,
            'data_class':'EXPLICIT_OWNER_SELECTED_READ_CONTENT','assurance':'LOCAL_COOPERATIVE',
            'resources':[{'resource_id':'r','project_id':'p','work_id':'a','files':entries}],'producer':resources.producer()}
        self.save_resources()
    def save_resources(self):
        self.resource_path.write_bytes(c.encoded(self.description));self.resource_path.chmod(0o600)
        self.resource_digest=c.sha(self.resource_path.read_bytes())
        self.resources=resources.Resources(self.resource_path,self.resource_digest,self.transfer,approve_resources=True)
        self.api=service.Service(self.transfer,self.resources)
    def call(self,tool='artifact_read',operation='bytes',options=None,resource_id='r'):
        options={'file_id':'f0','offset':0,'max_bytes':65536} if options is None else options
        return self.api.call(tool,{'project_id':'p','work_id':'a','resource_id':resource_id,'operation':operation,'options_json':c.encoded(options).decode()})
    def test_owner_consent_transfer_pin_and_resource_producer_are_required(self):
        self.expect('OWNER_READ_RESOURCE_APPROVAL_REQUIRED',lambda:resources.Resources(self.resource_path,self.resource_digest,self.transfer))
        self.description['transfer_policy_sha256']='0'*64
        self.resource_path.write_bytes(c.encoded(self.description));self.resource_digest=c.sha(self.resource_path.read_bytes())
        self.expect('READ_RESOURCE_TRANSFER_BINDING',lambda:resources.Resources(self.resource_path,self.resource_digest,self.transfer,approve_resources=True))
    def test_model_selects_id_not_path_and_catalog_hides_private_paths(self):
        value=self.api.call('projects_list',{});self.assertNotIn(str(self.source),json.dumps(value))
        self.assertEqual(value['projects'][0]['read_resources'][0]['resource_id'],'r')
        args={'project_id':'p','work_id':'a','resource_id':'r','operation':'bytes','options_json':'{}','path':'/secret'}
        with patch.object(resources,'pinned_bytes',side_effect=AssertionError('no source read')):
            self.expect('SCHEMA',lambda:self.api.call('artifact_read',args))
    def test_exact_byte_window_and_no_work_mutation_or_subprocess(self):
        before=self.inventory()
        with patch.object(service.records,'capture',side_effect=AssertionError('no execution')):
            value=self.call(options={'file_id':'f0','offset':1,'max_bytes':3})
        self.assertEqual(base64.b64decode(value['result']['data_base64']),b'exa');self.assertFalse(value['result']['eof'])
        self.assertEqual(value['result']['sha256'],c.sha(b'\x00exact\xff'));self.assertEqual(before,self.inventory())
        self.assertFalse(value['live_native_acceptance_verified']);self.assertFalse(value['authenticity_verified'])
    def test_tools_work_and_resource_id_intersections(self):
        self.expect('READ_RESOURCE_SCOPE',lambda:self.call(resource_id='other'))
        self.expect('READ_RESOURCE_SCOPE',lambda:self.call('usage_read','totals',{}))
        api=service.Service(self.transfer)
        self.assertNotIn('artifact_read',api.tools())
        self.expect('READ_RESOURCE_POLICY_REQUIRED',lambda:api.call('artifact_read',{'project_id':'p','work_id':'a','resource_id':'r','operation':'bytes','options_json':'{}'}))
        self.description['resources'][0]['work_id']='b';self.save_resources()
        self.expect('READ_RESOURCE_SCOPE',self.call)
    def test_changed_policy_file_and_changed_source_are_denied(self):
        self.resource_path.write_bytes(self.resource_path.read_bytes()+b' ')
        self.expect('READ_RESOURCE_POLICY_CHANGED',self.call)
        self.save_resources();p=Path(self.description['resources'][0]['files'][0]['path']);p.write_bytes(b'changed')
        self.expect('READ_RESOURCE_DIGEST',self.call)
    def test_digest_drift_during_view_never_delivers(self):
        self.publish({'AGENTS.md':b'# local rules\n'},['configuration_read'])
        path=Path(self.description['resources'][0]['files'][0]['path'])
        with patch.object(views,'view',side_effect=lambda *a:(path.write_bytes(b'changed'),{'value':'not-deliver'})[1]):
            self.expect('READ_RESOURCE_DIGEST',lambda:self.call('configuration_read','entrypoint',{}))
        self.assertTrue(any((p/'failure.json').exists() for p in self.registry.root.glob('read-resource-*')))
    def test_symlink_hardlink_directory_and_oversize_are_rejected(self):
        entry=self.description['resources'][0]['files'][0];p=Path(entry['path']);original=p.read_bytes();target=self.source/'target';target.write_bytes(original)
        p.unlink();p.symlink_to(target)
        with self.assertRaises(OSError):self.call()
        p.unlink();os.link(target,p);self.expect('READ_RESOURCE_UNSAFE',self.call)
        p.unlink();p.mkdir();self.expect('READ_RESOURCE_UNSAFE',self.call)
        p.rmdir()
        with p.open('wb') as f:f.truncate(resources.MAX_FILE+1)
        self.expect('READ_RESOURCE_UNSAFE',self.call)
    def test_relative_escaped_and_duplicate_logical_files_rejected(self):
        for name in ('../outside','/absolute','a/../secret','a\\b'):
            self.description['resources'][0]['files'][0]['name']=name
            with self.assertRaises(c.IntegrationError):self.save_resources()
        self.description['resources'][0]['files'][0]['name']='data';self.description['resources'][0]['files'].append(copy.deepcopy(self.description['resources'][0]['files'][0]))
        with self.assertRaises(c.IntegrationError):self.save_resources()
    def test_quota_is_checked_before_copy_and_no_cleanup(self):
        with patch.object(resources.backend,'_quota',side_effect=c.IntegrationError('AUDIT_QUOTA')),patch.object(resources,'pinned_bytes',side_effect=AssertionError('no reads')):
            self.expect('AUDIT_QUOTA',self.call)
        self.assertEqual(list(self.registry.root.glob('read-resource-*')),[])
    def test_corrupt_view_is_blocked_without_echoing_paths(self):
        self.publish({'record.json':b'{}','manifest.json':b'{}'},['artifact_read'])
        with self.assertRaises((ValueError,c.IntegrationError)):self.call('artifact_read','view',{})
        self.assertTrue(any((p/'failure.json').exists() for p in self.registry.root.glob('read-resource-*')))
    def test_configuration_uses_core_marker_parser_without_real_config_reads(self):
        self.publish({'AGENTS.md':b'# owner text\n'},['configuration_read'])
        with patch.object(service.records,'capture',side_effect=AssertionError('no execution')):
            value=self.call('configuration_read','entrypoint',{})
        self.assertIsNone(value['result']['managed_block']);self.assertEqual(value['result']['owner_check'],'NOT_RUN')
    def test_usage_unknown_cost_remains_unknown(self):
        raw=c.encoded({'schema':'golem.work-usage.v1','calls':[]})
        manifest=c.encoded({'schema':'golem.hosted-usage-manifest.v1','files':{'usage.json':c.sha(raw)}})
        self.publish({'usage.json':raw,'manifest.json':manifest},['usage_read'])
        value=self.call('usage_read','totals',{})
        self.assertIsNone(value['result']['cost']);self.assertFalse(value['result']['cost_complete']);self.assertFalse(value['result']['billing_independently_verified'])
    def test_a_pinned_self_declared_billing_receipt_does_not_create_trust(self):
        raw=c.encoded({'schema':'golem.work-usage.v1','calls':[]});manifest=c.encoded({'schema':'golem.hosted-usage-manifest.v1','files':{'usage.json':c.sha(raw)}})
        self.publish({'usage/usage.json':raw,'usage/manifest.json':manifest,'billing.json':b'{}','billing-receipt.json':c.encoded({'trust_level':'PINNED_DELEGATED_BILLING_AUTHORITY'})},['usage_read'])
        with patch.object(views.billing_evidence,'reconcile',side_effect=AssertionError('no trust promotion')):
            value=self.call('usage_read','billing_view',{})
        self.assertFalse(value['result']['delegated_billing_authority_verified']);self.assertFalse(value['result']['work_cost_assigned'])
    def test_stored_revision_pass_never_becomes_current_native_completion(self):
        raw=c.encoded({'schema':'golem.revision-status.v1','binding':{'project_id':'p','work_id':'a'},'native_acceptance_verified':True})
        self.publish({'result.json':raw},['revision_read'])
        value=self.call('revision_read','saved_status',{})
        self.assertTrue(value['result']['capture']['native_acceptance_verified']);self.assertFalse(value['result']['live_native_acceptance_verified']);self.assertEqual(value['result']['overall_completion'],'NOT_INFERRED')
    def test_derived_snapshot_paths_are_logical_not_private_paths(self):
        self.publish({'placeholder':b'data'},['artifact_read'])
        value=self.call('artifact_read','lifecycle',{})
        self.assertEqual(value['result']['evidence'],'resource:r');self.assertNotIn(str(self.registry.root),json.dumps(value))
    def test_new_local_tools_do_not_expand_remote_allowlist(self):
        remote=set(gateway.DELEGATE['properties']['tools']['items']['enum'])
        self.assertFalse(remote & set(resources.NAMES));self.assertNotIn('workflow_read',remote)
    def test_owner_plan_never_reads_selected_files_or_activates_policy(self):
        value=copy.deepcopy(self.description);value.pop('producer')
        with patch.object(resources,'pinned_bytes',side_effect=AssertionError('no selected reads')):
            result=resources.owner_plan(value)
        self.assertFalse(result['resources_read']);self.assertFalse(result['approval_created'])
        self.assertEqual(result['policy_sha256'],c.sha(c.encoded(result['policy'])))
    def test_bundle_commands_use_only_pinned_private_snapshot(self):
        self.publish({'journal.bin':b'pinned','cas/placeholder':b'pinned','descriptor.json':b'{}'},['bundle_read'])
        cases=[({'operation':'lineage_verify','graph_digest':'a'*64},['lineage','verify']),
               ({'operation':'lineage_trace','graph_digest':'a'*64,'sequence':1,'mode':'direct'},['lineage','trace']),
               ({'operation':'cost'},['cost','report']),({'operation':'replay','mode':'terminal'},['replay']),
               ({'operation':'output','digest':'a'*64},['--output-store']),({'operation':'adapter'},['adapter','describe'])]
        calls=[]
        def capture(argv,output,*unused,**kw):
            self.assertEqual(argv[:3],[str(self.cli),'--output-mode','full']);self.assertFalse(kw['observe_source'])
            self.assertEqual(kw['env'],service.backend.ENVIRONMENT);calls.append(argv[3:]);(output/'stdout.log').write_bytes(b'{"pinned":true}\n');(output/'stdout.log').chmod(0o600)
            return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(resources.records,'capture',capture):
            for fields,prefix in cases:
                value=self.api.call('bundle_read',{'project_id':'p','work_id':'a','resource_id':'r',**fields})
                self.assertEqual(calls[-1][:len(prefix)],prefix);self.assertFalse(value['live_native_acceptance_verified'])
                self.assertTrue(any('/snapshot' in arg for arg in calls[-1]))
                self.assertFalse(any(str(self.work) in arg or str(self.source) in arg for arg in calls[-1]))
    def test_event_export_requires_resource_and_preserves_jsonl(self):
        self.publish({'admission.journal':b'pinned'},['events_read']);calls=[]
        def capture(argv,output,*unused,**kw):
            calls.append(argv);(output/'stdout.log').write_bytes(b'{"n":1}\n{"n":2}\n');(output/'stdout.log').chmod(0o600)
            return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        args={'project_id':'p','work_id':'a','resource_id':'r','operation':'export','format':'jsonl','after':''}
        with patch.object(resources.records,'capture',capture):value=self.api.call('events_read',args)
        self.assertEqual(value['result']['value'],[{'n':1},{'n':2}]);self.assertEqual(calls[0][3],'events')
        self.assertTrue(calls[0][4].endswith('/snapshot'));self.assertNotEqual(calls[0][4],str(self.work))
        self.assertEqual(base64.b64decode(value['result']['native_stdout']['data_base64']),b'{"n":1}\n{"n":2}\n')
    def test_contract_schemas_are_pure_read_descriptions(self):
        self.publish({'selected.txt':b'owner-selected'},['configuration_read'])
        for kind in ('gateway_policy','hook_profile','mutation_policy','mutation_action','mutation_decision'):
            with patch.object(service.records,'capture',side_effect=AssertionError('no process')):
                value=self.call('configuration_read','schemas',{'kind':kind})
            self.assertEqual(value['result']['type'],'object');self.assertFalse(value['live_native_acceptance_verified'])
    def test_selected_observation_view_raw_measure_and_scope_are_core_validated(self):
        raw=b'\x00original\xff\n'
        step={'id':'check','status':'EXIT_OK','returncode':0,'reason':'EXIT','logs':{'stdout.log':{'sha256':c.sha(raw),'bytes':len(raw)}}}
        record={'schema':views.io.SCHEMA,'scope':{'project_id':'p','work_id':'a'},'status':'RECORDED','steps':[step]}
        data={'record.json':c.encoded(record),'check/stdout.log':raw}
        data['manifest.json']=c.encoded({'schema':'golem.agent-observation-manifest.v1','files':{name:c.sha(content) for name,content in data.items()}})
        self.publish(data,['artifact_read'])
        value=self.call('artifact_read','view',{});self.assertEqual(value['result']['steps'][0]['status'],'EXIT_OK');self.assertFalse(value['result']['product_acceptance'])
        value=self.call('artifact_read','raw',{'step':'check','stream':'stdout.log','offset':0,'bytes':32});self.assertEqual(base64.b64decode(value['result']['data_base64']),raw)
        value=self.call('artifact_read','measure',{});self.assertEqual(value['result']['raw_bytes'],len(raw));self.assertIsNone(value['result']['agent_success'])
        record['scope']['work_id']='other';data['record.json']=c.encoded(record);data['manifest.json']=c.encoded({'schema':'golem.agent-observation-manifest.v1','files':{name:c.sha(content) for name,content in data.items() if name!='manifest.json'}})
        self.publish(data,['artifact_read'])
        with self.assertRaises(ValueError):self.call('artifact_read','view',{})
    def test_bundle_failure_retains_full_capture_and_never_restarts_cursor(self):
        self.publish({'journal.bin':b'pinned'},['events_read']);calls=[]
        def capture(argv,output,*unused,**kw):
            calls.append(argv);(output/'stdout.log').write_bytes(b'partial evidence');(output/'stdout.log').chmod(0o600)
            return {'returncode':1,'reason':'EXIT','recording':'RECORDED'}
        args={'project_id':'p','work_id':'a','resource_id':'r','operation':'export','format':'jsonl','after':'abc:1'}
        with patch.object(resources.records,'capture',capture):self.expect('NATIVE_FAILURE',lambda:self.api.call('events_read',args))
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][-2:],['--after','abc:1'])
        spool=list(self.registry.root.glob('read-resource-*'))[-1];self.assertEqual((spool/'stdout.log').read_bytes(),b'partial evidence');self.assertTrue((spool/'failure.json').exists())
    def test_bundle_replay_keeps_complete_manifest_and_optional_checkpoint_semantics(self):
        self.publish({'complete.json':b'{}','journal.bin':b'pinned'},['bundle_read']);calls=[]
        def capture(argv,output,*unused,**kw):
            calls.append(argv);snapshot=Path(argv[4]);self.assertTrue((snapshot/'complete.json').is_file())
            (output/'stdout.log').write_bytes(b'{}');(output/'stdout.log').chmod(0o600)
            return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(resources.records,'capture',capture):
            self.api.call('bundle_read',{'project_id':'p','work_id':'a','resource_id':'r','operation':'replay','mode':'terminal','expected_head':'a'*64})
        self.assertTrue(calls[0][4].endswith('/snapshot'));self.assertEqual(calls[0][-3:],['--require-terminal','--expect-chain','a'*64])
    def test_resource_result_budget_and_producer_drift_fail_closed(self):
        self.policy['max_result_bytes']=4096;self.save_policy();self.transfer=self.adapter();self.publish({'data.bin':b'x'*6000},['artifact_read'])
        self.expect('RESULT_BUDGET_EXCEEDED',self.call)
        spool=list(self.registry.root.glob('read-resource-*'))[-1];self.assertEqual((spool/'snapshot/data.bin').read_bytes(),b'x'*6000);self.assertTrue((spool/'failure.json').exists())
        self.description['producer']['integration_read_views.py']='0'*64
        self.resource_path.write_bytes(c.encoded(self.description));self.resource_digest=c.sha(self.resource_path.read_bytes())
        self.expect('READ_RESOURCE_PRODUCER_CHANGED',lambda:resources.Resources(self.resource_path,self.resource_digest,self.transfer,approve_resources=True))
    def test_native_resource_admission_accounts_for_both_capture_streams(self):
        self.publish({'journal.bin':b'pinned'},['bundle_read'])
        capacity=resources.backend.audit_capacity(self.registry.root)
        capacity['remaining']['bytes']=c.MAX_NATIVE+self.transfer.value['max_result_bytes']+c.LIMIT+1024
        with patch.object(resources.backend,'_quota',return_value=capacity),patch.object(resources.records,'capture',side_effect=AssertionError('no launch')):
            self.expect('AUDIT_QUOTA',lambda:self.api.call('bundle_read',{'project_id':'p','work_id':'a','resource_id':'r','operation':'replay','mode':'partial'}))
        self.assertEqual(list(self.registry.root.glob('read-resource-*')),[])
    def test_aggregate_capacity_is_rechecked_before_delivery_without_deleting_capture(self):
        capacity=resources.backend.audit_capacity(self.registry.root)
        with patch.object(resources.backend,'_quota',side_effect=[capacity,c.IntegrationError('AUDIT_QUOTA')]):self.expect('AUDIT_QUOTA',self.call)
        spool=list(self.registry.root.glob('read-resource-*'))[-1];self.assertTrue((spool/'snapshot/data.bin').is_file());self.assertFalse((spool/'delivery.json').exists());self.assertTrue((spool/'failure.json').exists())
    def test_public_bundle_contains_import_closure_without_sdk_or_client_execution(self):
        import io
        import subprocess
        import sys
        import tempfile
        import zipfile
        import integration_mcpb
        with tempfile.TemporaryDirectory() as temporary:
            package=Path(temporary).resolve()
            with zipfile.ZipFile(io.BytesIO(integration_mcpb.build())) as archive:archive.extractall(package)
            script="import sys; sys.path.insert(0,sys.argv[1]); import integration_read_views as views; import integration_read_resources as resources; import integration_service as service; print(len(resources.producer()), len(service.SCHEMAS))"
            result=subprocess.run([sys.executable,'-I','-c',script,str(package/'tools')],cwd=package,capture_output=True,timeout=15,env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})
            self.assertEqual(result.returncode,0,result.stderr.decode());self.assertEqual(result.stdout.strip(),f'{len(resources.MODULES)} {len(service.SCHEMAS)}'.encode())
