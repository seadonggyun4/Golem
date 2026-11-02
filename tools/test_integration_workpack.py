"""Work Pack MCP boundary regression; fixtures never select a production Work."""
import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import integration_contract as c
import integration_workpack_reads as wp
import integration_quality_reads as reads
import integration_service as service
import integration_feature_profiles as profiles
import integration_read_resources as resources
import test_integration_m2 as fixture
import test_integration_m1_resources as rf

class Reads(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','observed'):
        locals()[name]=getattr(fixture.Preparations,name)
    def setUp(self):fixture.Preparations.setUp(self)
    def call(self,args):return self.api.call('workpack_read',{'project_id':'p','work_id':'a',**args})
    def test_native_bytes_are_exact_and_no_authority_promoted(self):
        pack=' { "schema":"untrusted-native-input" }\n';before=self.inventory();calls=[]
        def capture(argv,output,*args,**kwargs):
            calls.append(argv);self.assertEqual(Path(argv[-1]).read_text(),pack)
            resources.records.save(output/'stdout.log',b'{"authorized":false,"native":"value"}\n')
            return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(self.api,'_read',self.observed),patch.object(reads.records,'capture',capture):
            result=self.call({'operation':'inspect','pack_json':pack})
        self.assertEqual(calls[0][3:5],['pack','inspect']);self.assertFalse(result['execution_authorized'])
        self.assertEqual(result['result']['native'],'value');self.assertFalse(result['current_native_acceptance_verified'])
        self.assertEqual(before,self.inventory())
    def test_native_failure_retains_audit_without_retry(self):
        calls=[]
        def fail(*args,**kw):calls.append(1);return {'returncode':1,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(self.api,'_read',self.observed),patch.object(reads.records,'capture',fail):
            self.expect('NATIVE_FAILURE',lambda:self.call({'operation':'validate','pack_json':'{}'}))
        self.assertEqual(len(calls),1);self.assertTrue(list(self.registry.root.glob('read-m4-*/failure.json')))
    def test_work_drift_refuses_delivery(self):
        count=[]
        def observed(*args):count.append(1);return {'result':{'generation':len(count)}}
        def capture(argv,output,*a,**kw):
            resources.records.save(output/'stdout.log',b'{}');return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(self.api,'_read',observed),patch.object(reads.records,'capture',capture):
            self.expect('OBSERVATION_STALE',lambda:self.call({'operation':'explain'}))
    def test_closed_scope_and_no_host_paths(self):
        for args in ({'operation':'bind'},{'operation':'inspect','pack_json':'{}','path':'/private'}, {'operation':'assess','proposals':['{}']*9}):
            with self.assertRaises(c.IntegrationError):self.call(args)
        self.policy['scopes'][0]['tools'].remove('workpack_read');self.save_policy();self.api=service.Service(self.adapter())
        self.expect('TRANSFER_SCOPE',lambda:self.call({'operation':'explain'}))
    def test_argv_uses_finite_commands_and_byte_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base={'project_id':'p','work_id':'a'}
            argv=wp.command('workpack_read',{**base,'operation':'reference_observe','capture_json':'{}','source_sha256':'a'*64,'config_sha256':'b'*64,'pack_sha256':'c'*64},'/work',root)
            self.assertEqual(argv[0:2],['pack','reference-observe']);self.assertEqual(argv[-1],'c'*64)
            with self.assertRaises(c.IntegrationError):wp.command('workpack_read',{**base,'operation':'validate','pack_json':'é'*40000},'/work',root)
    def test_profile_does_not_implicitly_select_owner_scope(self):
        for profile in profiles.NAMES:
            self.assertIn('workpack_read',profiles.definition(profile)['tools'])
            self.assertEqual(profiles.diagnose(profile,[])['available_tools'],[])

class Resource(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','publish','save_resources'):
        locals()[name]=getattr(rf.ResourceReads,name)
    def setUp(self):rf.ResourceReads.setUp(self)
    def test_resource_selection_required_and_snapshot_only(self):
        self.assertNotIn('workpack_resource_read',self.api.tools())
        self.publish({'index.json':b'{}'},['workpack_resource_read']);calls=[]
        def capture(argv,output,*a,**kw):
            calls.append(argv);self.assertTrue(Path(argv[-1]).is_relative_to(output/'snapshot'))
            resources.records.save(output/'stdout.log',b'{"available":false}')
            return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
        args={'project_id':'p','work_id':'a','resource_id':'r','operation':'list','index_name':'index.json'}
        with patch.object(resources.records,'capture',capture):
            result=self.api.call('workpack_resource_read',args)
        self.assertEqual(calls[0][3:5],['pack','list']);self.assertFalse(result['authenticity_verified'])
        for name in ('../secret','/secret','..','a/b'):
            with self.assertRaises(c.IntegrationError):self.api.call('workpack_resource_read',{**args,'index_name':name})
        self.expect('READ_RESOURCE_SCOPE',lambda:self.api.call('workpack_resource_read',{**args,'resource_id':'foreign'}))
    def test_receipt_verify_has_independent_expected_digest(self):
        args={'project_id':'p','work_id':'a','resource_id':'r','operation':'receipt_verify','manifest_sha256':'c'*64}
        self.assertEqual(wp.resource_command(args,Path('/snapshot')),['receipt','verify','/snapshot','--expect-manifest','c'*64])
        with self.assertRaises(c.IntegrationError):wp.resource_command({**args,'directory':'/secret'},Path('/snapshot'))


import integration_workpack_actions as wa
import integration_mutation_contract as mc
import integration_mutations as mutations
import integration_registry as registry
import test_integration_mutations as d4

class Actions(unittest.TestCase):
    for name in ('approve','query','expect','inventory','save_policy','adapter','repin','api','preflight','capture'):
        locals()[name]=getattr(d4.D4,name)
    def setUp(self):
        d4.D4.setUp(self);self.parent=self.root/'exports';self.parent.mkdir(mode=0o700)
    def select(self,tool,**changes):
        value={'request_json':' { "native": "exact bytes" }\n'}
        if tool!='workpack_bind':value.update(output_parent=str(self.parent),output_identity=registry.identity(self.parent),format='json')
        if tool!='workpack_receipt_manifest':value['approval_digest']='c'*64
        value.update(changes);self.entry['tool']=tool;self.action['native_json']=c.encoded(value).decode();self.repin();return value
    def test_all_three_exact_actions_reuse_intent_and_saved_results(self):
        for tool in wa.NAMES:
            value=self.select(tool);api=self.api();calls=[]
            def capture(argv,output,*a,**kw):
                calls.append(argv);self.assertTrue((output/'dispatch-intent.json').exists())
                self.assertEqual((output/'workpack-native.json').read_text(),value['request_json'])
                records=mutations.records;records.save(output/'stdout.log',b'{"authorized":false}')
                return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
            args={**self.args,'request_id':tool}
            with patch.object(api,'_preflight',self.preflight),patch.object(mutations.records,'capture',capture):
                first=api.call(tool,args);again=api.call(tool,args)
            self.assertEqual(first['state'],'NATIVE_RESULT_RECORDED',first);self.assertEqual(first,again);self.assertEqual(len(calls),1)
            self.assertFalse(first['execution_authorized']);self.assertFalse(first['acceptance_verified'])
            if tool=='workpack_bind':self.assertEqual(calls[0][-2:],['--approve-binding','c'*64])
            if tool=='workpack_receipt_export':self.assertEqual(calls[0][-2:],['--approve-export','c'*64])
    def test_failed_native_dispatch_remains_unknown_without_retry(self):
        self.select('workpack_receipt_export');api=self.api();calls=[]
        def fail(*a,**kw):calls.append(1);return {'returncode':1,'reason':'EXIT','recording':'RECORDED'}
        with patch.object(api,'_preflight',self.preflight),patch.object(mutations.records,'capture',fail):
            first=api.call(self.entry['tool'],self.args);again=api.call(self.entry['tool'],self.args)
        self.assertEqual(first['state'],'COMMIT_UNKNOWN');self.assertEqual(first,again);self.assertEqual(len(calls),1)
    def test_output_scope_identity_and_private_mode_are_required(self):
        for parent in (self.registry.root,self.root,self.work):
            self.select('workpack_receipt_manifest',output_parent=str(parent),output_identity=registry.identity(parent))
            with self.assertRaises(c.IntegrationError):self.api().policy.action(self.entry)
        self.select('workpack_receipt_export',output_identity={'device':0,'inode':0})
        self.expect('WORKPACK_OUTPUT_CHANGED',lambda:self.api().policy.action(self.entry))
        self.select('workpack_receipt_manifest');self.parent.chmod(0o755)
        self.expect('WORKPACK_OUTPUT_PRIVATE',lambda:self.api().policy.action(self.entry))
    def test_execution_receipt_cannot_replace_binding_or_export_digest(self):
        self.select('workpack_bind');self.action['approval']={}
        with self.assertRaises(c.IntegrationError):mc.action_shape(self.entry,self.action)
        self.action['approval']=None;value=c.decode(self.action['native_json'].encode());del value['approval_digest'];self.action['native_json']=c.encoded(value).decode()
        with self.assertRaises(c.IntegrationError):mc.action_shape(self.entry,self.action)
    def test_m2_draft_does_not_approve_or_inspect_output_parent(self):
        args={'tool':'workpack_receipt_export','project_id':'p','work_id':'a','session_id':'owner','native_binding_id':'','fields_json':'{}','body':'','context_json':'','count_json':''}
        with patch.object(registry,'real_path',side_effect=AssertionError('no host inspection')):
            envelope,request,entry,missing,sources=wa.draft(args,{},'unused')
        self.assertIn('approval_digest',missing);self.assertIn('output_parent',missing);self.assertIsNone(envelope['approval'])

if __name__=='__main__':unittest.main()
