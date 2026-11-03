"""QC6 authored transport fixtures; NOT_RUN during validation HOLD."""
import unittest
import tempfile
import json
import os
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch
import integration_contract as c
import integration_intent as intent
import integration_feature_profiles as profiles

class IntentTransportTests(unittest.TestCase):
    def envelope(self,value):
        return {'schema':'golem.integration-native-action.v1','native_json':c.encoded(value).decode(),
                'body':'','context_json':'','count_json':'','approval':None}
    def test_no_host_without_explicit_owner_selection(self):
        with self.assertRaises(c.IntegrationError):intent.Hosts('/unused','0'*64,None)
    def test_exact_reference_only(self):
        self.assertEqual(intent.shape({'tool':'intent_qa_accept'},self.envelope({'binding_id':'selected'})),{'binding_id':'selected'})
        for value in ({'binding_id':'selected','approved':True},{'binding_id':'selected','command':'sh'}):
            with self.assertRaises(c.IntegrationError):intent.shape({'tool':'intent_qa_accept'},self.envelope(value))
    def test_no_legacy_approval_attachment(self):
        envelope=self.envelope({'binding_id':'selected'});envelope['approval']={'approve':True}
        with self.assertRaises(c.IntegrationError):intent.shape({'tool':'intent_completion_finalize'},envelope)
    def test_reference_draft_is_not_native_approval(self):
        args={'tool':'intent_qa_accept','project_id':'p','work_id':'w','session_id':'s','native_binding_id':'',
              'fields_json':'{"binding_id":"selected"}','body':'','context_json':'','count_json':''}
        envelope,value,entry,missing,sources=intent.draft(args,{},'unused')
        self.assertIsNone(envelope['approval']);self.assertEqual(missing,[])
        self.assertEqual(sources['binding_id'],'UNAPPROVED_OWNER_HOST_REFERENCE')
    def test_profile_ceiling_not_grant(self):
        for profile in ('task','quality'):
            self.assertIn('intent_qa_accept',profiles.definition(profile)['tools'])
            self.assertIn('intent_completion_finalize',profiles.definition(profile)['tools'])
        self.assertNotIn('intent_qa_accept',profiles.definition('read')['tools'])
    def test_read_never_dispatches_mutating_binding(self):
        host=object.__new__(intent.Hosts)
        row={'operation':'accept','action_id':'action'}
        class Service:
            def _authorize(self,*args):pass
        with patch.object(host,'binding',return_value=({},row,b'')),patch.object(host,'_capture') as capture:
            with self.assertRaises(c.IntegrationError):host.read(Service(),{},dict(query_id='q',project_id='p',work_id='w'))
            capture.assert_not_called()

class IntentBoundaryTests(unittest.TestCase):
    def test_action_identity_and_operation_are_independent_requirements(self):
        host=object.__new__(intent.Hosts)
        entry={'tool':'intent_qa_accept','project_id':'p','work_id':'w','action_id':'approved','action':{'sha256':'a'*64}}
        envelope={'native_json':'{"binding_id":"b"}','body':'','context_json':'','count_json':'','approval':None}
        row={'operation':'accept','action_id':'approved','action_sha256':'a'*64}
        with patch.object(host,'binding',return_value=({},row,b'fixed')):
            self.assertEqual(host.select(entry,envelope)[2],b'fixed')
        for field,value in [('operation','finalize'),('action_id','other'),('action_sha256','b'*64)]:
            wrong={**row,field:value}
            with patch.object(host,'binding',return_value=({},wrong,b'fixed')):
                with self.assertRaises(c.IntegrationError):host.select(entry,envelope)
    def test_native_blocked_is_not_promoted_by_transport_success(self):
        host=object.__new__(intent.Hosts)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve()
            service=SimpleNamespace(registry=SimpleNamespace(root=root),transfer=SimpleNamespace(value={'max_result_bytes':65536}),_authorize=lambda *a:None)
            native={'execution_status':'PASS','intent_qa_status':'BLOCKED','blockers':[{'code':'NOT_RUN'}]}
            def capture(cfg,row,raw,output):
                (output/'stdout.log').write_bytes(c.encoded(native));os.chmod(output/'stdout.log',0o600)
                return {'returncode':0,'reason':'EXIT','recording':'RECORDED'}
            with patch.object(host,'binding',return_value=({}, {'operation':'assess','action_id':''},b'fixed')),patch.object(host,'_capture',side_effect=capture),patch.object(intent.backend,'_quota'):
                result=host.read(service,{},dict(query_id='q',project_id='p',work_id='w'))
            self.assertEqual(result['native'],native)
            self.assertFalse(result['execution_authorized']);self.assertFalse(result['automatic_retry_allowed'])
            self.assertNotIn('acceptance_verified',result)
    def test_spawn_failure_preserves_logs_without_retry(self):
        host=object.__new__(intent.Hosts)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();os.chmod(root,0o700);info=root.stat()
            cfg={'repository':folder,'registration_sha256':'a'*64,'git':{'path':'/unused/git'},'bridge':{'path':'/unused/bridge','sha256':'b'*64}}
            row={'review_root':{'path':folder,'identity':{'device':info.st_dev,'inode':info.st_ino}}}
            @contextmanager
            def authority(*args,**kwargs):
                fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
                try:yield fd,{'authority':{'pins':[cfg['bridge']]}}
                finally:os.close(fd)
            with patch.object(intent.authority,'authorized_root',side_effect=authority),patch.object(intent.records,'source_observation',return_value={'status':'NOT_OBSERVED'}),patch.object(intent.subprocess,'Popen',side_effect=OSError('fixture spawn failure')) as spawn:
                with self.assertRaises(OSError):host._capture(cfg,row,b'{}',root)
                self.assertEqual(spawn.call_count,1)
            self.assertTrue((root/'stdout.log').exists());self.assertTrue((root/'stderr.log').exists())
            capture=json.loads((root/'intent-capture.json').read_text())
            self.assertIsNone(capture['returncode']);self.assertEqual(capture['reason'],'UNKNOWN')
            observation=json.loads((root/'process/result.json').read_text())
            self.assertEqual(observation['reason'],'LAUNCH_ERROR')

    def test_capture_records_fd_protocol_and_postchecks_without_reexecution(self):
        import sys
        host=object.__new__(intent.Hosts)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();os.chmod(root,0o700);info=root.stat()
            bridge=root/'bridge'
            bridge.write_text('#!'+sys.executable+'\nimport os,sys\n'
                'os.fstat(int(sys.argv[2]));os.fstat(int(sys.argv[4]))\n'
                'sys.stderr.buffer.write(b"x"*131072);sys.stderr.buffer.flush()\n'
                'data=sys.stdin.buffer.read();sys.stdout.buffer.write(data)\n')
            bridge.chmod(0o700)
            cfg={'repository':folder,'registration_sha256':'a'*64,'git':{'path':'/unused/git'},'bridge':{'path':str(bridge),'sha256':c.sha(bridge.read_bytes())}}
            row={'binding_id':'b','project_id':'p','work_id':'w','review_root':{'path':folder,'identity':{'device':info.st_dev,'inode':info.st_ino}}}
            raw=b'x'*262144
            @contextmanager
            def authority(*args,**kwargs):
                fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
                try:yield fd,{'authority':{'pins':[cfg['bridge']]}}
                finally:os.close(fd)
            for stale in (False,True):
                output=root/str(stale);output.mkdir(mode=0o700)
                with patch.object(intent.authority,'authorized_root',side_effect=authority),patch.object(host,'binding',return_value=None if stale else (cfg,row,raw)) as check:
                    if stale:
                        with self.assertRaisesRegex(c.IntegrationError,'INTENT_POSTCHECK_CHANGED'):host._capture(cfg,row,raw,output)
                    else:self.assertEqual(host._capture(cfg,row,raw,output)['returncode'],0)
                    check.assert_called_once_with('b','p','w')
                self.assertEqual((output/'stdout.log').read_bytes(),raw)
                self.assertEqual(len((output/'stderr.log').read_bytes()),131072)
                self.assertEqual(json.loads((output/'process/result.json').read_text())['reason'],'PROTOCOL_COMPLETE')



class IntentAdmissionRegressionTests(unittest.TestCase):
    def test_durable_intent_record_does_not_shadow_transport_module(self):
        import integration_mutations as mutations
        service=object.__new__(mutations.Service)
        entry={'action_id':'a','tool':'intent_qa_accept','project_id':'p','work_id':'w'}
        service.registry=SimpleNamespace()
        service.parallel_hosts=None
        service.intent_hosts=None
        service.policy=SimpleNamespace(current=lambda:{'actions':[entry]},
            authorize=lambda value:({},{}), action=lambda value:({},{}))
        with patch.object(mutations.lifecycle,'fence'):
            with self.assertRaisesRegex(c.IntegrationError,'OWNER_INTENT_HOST_REQUIRED'):
                service._admit('intent_qa_accept',dict(project_id='p',work_id='w',action_id='a'))

if __name__=='__main__':unittest.main()
