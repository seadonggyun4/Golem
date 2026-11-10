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
    def test_empty_action_policy_is_valid_and_grants_no_action(self):
        import integration_mutation_contract as mutation
        value=dict(schema='golem.integration-mutations.v1',
                   transfer_policy=dict(path='/unused/policy',sha256='a'*64),
                   actions=[],producer=mutation.producer())
        self.assertEqual(mutation.validate(value)['actions'],[])
        import integration_mutations as mutations
        service=object.__new__(mutations.Service)
        service.registry=None
        service.policy=SimpleNamespace(current=lambda:value)
        with patch.object(mutations.lifecycle,'fence'):
            with self.assertRaisesRegex(c.IntegrationError,'MUTATION_SCOPE'):
                service._admit('intent_qa_accept',dict(action_id='missing',project_id='p',work_id='w'))

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
    def test_enrollment_inspection_packet_cannot_carry_mutation(self):
        import copy
        host=object.__new__(intent.Hosts)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();root.chmod(0o700)
            for name in ('policy.json','bundle.json'):
                (root/name).write_bytes(b'{}');(root/name).chmod(0o600)
            packet=dict(schema='golem.intent-bootstrap-host.v1',operation='enrollment-inspect',
                work=str(root),policy='{}',bundle='{}',control='{}',baseline='{}',enrollment='',
                policy_name='policy.json',bundle_name='bundle.json',sources=[dict(control='{}',text='x')],definitions=['{}'],
                policy_sha256=c.sha(b'{}'),bundle_sha256=c.sha(b'{}'),baseline_operation='0'*64,
                baseline_request='0'*64,publication_operation='0'*64,authority_head='0'*64,
                work_head='0'*64,approval='0'*64,authority_sequence=0,work_sequence=0)
            path=root/'packet.json'
            row=dict(binding_id='q',project_id='p',work_id='w',operation='enrollment-inspect',
                action_id='',action_sha256='0'*64,review_root=dict(path=str(root),identity=intent.r.identity(root)))
            host.policy=SimpleNamespace(transfer=SimpleNamespace(scope=lambda *a:{'binding':{}}),
                registry=SimpleNamespace(authorize=lambda *a:dict(root=str(root),works=[dict(work_id='w',path=str(root))])))
            for changes,allowed in (({},True),({'operation':'enroll'},False),({'approval':'a'*64},False),({'enrollment':'{}'},False)):
                raw=c.encoded(dict(packet,**changes));path.write_bytes(raw);path.chmod(0o600)
                selected=dict(row,packet=dict(path=str(path),sha256=c.sha(raw)))
                with patch.object(host,'current',return_value=dict(repository=str(root),bindings=[selected])):
                    if allowed:self.assertEqual(host.binding('q','p','w')[2],raw)
                    else:
                        with self.assertRaises(c.IntegrationError):host.binding('q','p','w')

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

    def test_enrollment_capture_uses_exact_bootstrap_packet_and_owned_fds(self):
        import sys
        host=object.__new__(intent.Hosts)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();root.chmod(0o700)
            authority_root=root/'authority';authority_root.mkdir(mode=0o700)
            review_root=root/'review';review_root.mkdir(mode=0o700)
            registration='a'*64
            # A disposable protocol peer, not a native Work or authority host.
            # It rejects the wrong route/hash and verifies both inherited FDs.
            bridge=root/'bridge'
            bridge.write_text('#!'+sys.executable+'\nimport hashlib,json,os,stat,sys\n'
                'assert len(sys.argv)==6 and sys.argv[1]=="--bootstrap-fd"\n'
                'assert sys.argv[3]=='+repr(registration)+'\n'
                'expected='+repr([str(authority_root),str(review_root)])+'\n'
                'for fd,path in zip((int(sys.argv[2]),int(sys.argv[4])),expected):\n'
                ' info=os.fstat(fd); wanted=os.stat(path)\n'
                ' assert stat.S_ISDIR(info.st_mode)\n'
                ' assert (info.st_dev,info.st_ino)==(wanted.st_dev,wanted.st_ino)\n'
                'raw=sys.stdin.buffer.read()\n'
                'assert hashlib.sha256(raw).hexdigest()==sys.argv[5]\n'
                'assert json.loads(raw)["operation"]=="enrollment-inspect"\n'
                'sys.stdout.buffer.write(raw)\n')
            bridge.chmod(0o700)
            cfg={'repository':str(root),'registration_sha256':registration,
                 'git':{'path':'/unused/git'},'bridge':intent.r.file_pin(bridge)}
            row={'binding_id':'q','project_id':'p','work_id':'w','operation':'enrollment-inspect',
                 'action_id':'','action_sha256':'0'*64,
                 'review_root':{'path':str(review_root),'identity':intent.r.identity(review_root)}}
            raw=b'{ "operation": "enrollment-inspect", "enrollment": "", "approval": "'+b'0'*64+b'" }\n'
            @contextmanager
            def authority(*args,**kwargs):
                fd=os.open(authority_root,os.O_RDONLY|os.O_DIRECTORY)
                try:yield fd,{'authority':{'pins':[cfg['bridge']]}}
                finally:os.close(fd)
            for stale in (False,True):
                with self.subTest(stale=stale):
                    output=root/str(stale);output.mkdir(mode=0o700)
                    with patch.object(intent.authority,'authorized_root',side_effect=authority),\
                         patch.object(host,'binding',return_value=None if stale else (cfg,row,raw)) as check,\
                         patch.object(intent.records,'run_private',wraps=intent.records.run_private) as dispatch:
                        if stale:
                            with self.assertRaisesRegex(c.IntegrationError,'INTENT_POSTCHECK_CHANGED'):
                                host._capture(cfg,row,raw,output)
                        else:
                            self.assertEqual(host._capture(cfg,row,raw,output)['returncode'],0)
                        dispatch.assert_called_once()
                        argv=dispatch.call_args.args[0]
                        inherited=dispatch.call_args.kwargs['pass_fds']
                        self.assertEqual(argv,[str(bridge),'--bootstrap-fd',str(inherited[0]),
                                               registration,str(inherited[1]),c.sha(raw)])
                        self.assertEqual(len(inherited),2)
                        self.assertNotEqual(inherited[0],inherited[1])
                        check.assert_called_once_with('q','p','w')
                    self.assertEqual((output/'stdout.log').read_bytes(),raw)
                    self.assertEqual((output/'stderr.log').read_bytes(),b'')
                    captured=c.decode((output/'intent-capture.json').read_bytes())
                    self.assertEqual((captured['reason'],captured['returncode']),('EXIT',0))
                    self.assertEqual(c.decode((output/'process/result.json').read_bytes())['reason'],'PROTOCOL_COMPLETE')



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
