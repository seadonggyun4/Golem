"""Disposable real-host bootstrap tests. No production/client paths or QA runner."""
import json
import os
from pathlib import Path
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

import integration_contract as c
import intent_authority as authority
import intent_bootstrap as bootstrap
import test_intent_authority as fixtures

SOURCE = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('GOLEM_INTENT_HOST'), 'native host required')
class Bootstrap(unittest.TestCase):
    git = fixtures.IdentityTests.git

    def setUp(self):
        fixtures.IdentityTests.setUp(self)
        self.bridge = Path(os.environ['GOLEM_INTENT_HOST']).resolve(strict=True)
        # CTest's host and CLI targets need not share an output directory.
        self.assertTrue(os.environ.get('GOLEM_NATIVE_CLI'),
                        "GOLEM_NATIVE_CLI must explicitly select this build's native CLI")
        self.native_cli = Path(os.environ['GOLEM_NATIVE_CLI']).resolve(strict=True)
        self.assertTrue(self.native_cli.is_file() and os.access(self.native_cli, os.X_OK))
        p = authority.registration_plan(self.repo, self.authority, [self.bridge], git=self.git_binary)
        self.registration = authority.register(self.repo, self.authority, [self.bridge], p['plan_sha256'],
            git=self.git_binary, bridge=self.bridge, approve_local_owner=True)['registration_sha256']
        self.seed = json.loads((SOURCE/'tests/fixtures/intent/qa-resolved-local.json').read_text())
        self.bo, self.br = c.sha(b'bootstrap-baseline'), c.sha(b'bootstrap-source')
        state = self.inspect()
        args = (self.repo, self.registration, self.bo, self.br, state['committed'], state['head'],
                self.seed['baseline'].encode(), ((self.seed['source'].encode(), self.seed['text'].encode()),))
        p = authority.object_store_plan(*args, git=self.git_binary, bridge=self.bridge)
        authority.store_objects(*args, p['plan_sha256'], git=self.git_binary, bridge=self.bridge,
                                approve_local_owner=True)
        self.review = self.base/'review'; self.review.mkdir(mode=0o700)
        self.audit = self.base/'audit'; self.audit.mkdir(mode=0o700)
        self.packet = self.base/'packet.json'
        self.kw = dict(git=self.git_binary, bridge=self.bridge, packet=self.packet,
                       review_root=self.review, action_id='question-01', audit_root=self.audit)
        self.prepare()

    def inspect(self):
        return authority.native_inspect(self.repo, self.registration, git=self.git_binary, bridge=self.bridge)

    def write(self, path, value):
        path.write_bytes(c.encoded(value) if not isinstance(value, str) else value.encode())
        path.chmod(0o600)

    def prepare(self, expired=False):
        state = self.inspect(); baseline = json.loads(self.seed['bundle'])['baseline_digest']
        control = dict(schema='golem.intent.review-control.v1', project_id='demo', work_id='work',
            baseline_digest=baseline, operation='question', expected_epoch=0,
            body=dict(question_digest=c.sha(b'question'), evidence_digest=c.sha(b'question evidence')))
        raw = c.encoded(control).decode(); op=c.sha(b'question publication'); now=int(time.time())
        bundle=dict(schema='golem.intent.review-host-bundle.v1', project_id='demo', work_id='work',
            baseline_digest=baseline, policy_digest=self.seed['policy_pin'], registration_digest=self.registration,
            control_digest=c.sha(raw.encode()), owner='owner', owner_session='owner-session',
            not_before=now-10, expires_at=now-1 if expired else now+300, evidence=[],
            publication_operation=op, expected_sequence=state['committed'], expected_head=state['head'])
        bundle_raw=c.encoded(bundle).decode()
        self.write(self.review/'policy.json', self.seed['policy']); self.write(self.review/'bundle.json',bundle_raw)
        packet=dict(schema='golem.intent-bootstrap-host.v1',operation='review',work='',policy=self.seed['policy'],
            bundle=bundle_raw,control=raw,policy_sha256=self.seed['policy_pin'],bundle_sha256=c.sha(bundle_raw.encode()),
            policy_name='policy.json',bundle_name='bundle.json',baseline=self.seed['baseline'],
            sources=[dict(control=self.seed['source'],text=self.seed['text'])],definitions=[self.seed['definition']],
            baseline_operation=self.bo,baseline_request=self.br,publication_operation=op,
            authority_sequence=state['committed'],authority_head=state['head'],work_sequence=0,work_head='0'*64,
            enrollment='',approval='0'*64)
        self.write(self.packet,packet)

    def plan(self):
        return bootstrap.plan(self.repo,self.registration,**self.kw)['plan_sha256']

    def test_real_review_and_no_replay(self):
        before=self.inspect(); pin=self.plan()
        result=bootstrap.apply(self.repo,self.registration,pin,**self.kw,approve_local_owner=True)
        self.assertEqual(result['status'],'NATIVE_RETURNED')
        self.assertFalse(result['execution_authorized'])
        self.assertEqual(self.inspect()['committed'],before['committed']+1)
        with self.assertRaises(FileExistsError):
            bootstrap.apply(self.repo,self.registration,pin,**self.kw,approve_local_owner=True)

    def test_owner_and_packet_pin(self):
        pin=self.plan(); before=self.inspect()
        with self.assertRaisesRegex(c.IntegrationError,'OWNER_APPROVAL_REQUIRED'):
            bootstrap.apply(self.repo,self.registration,pin,**self.kw)
        self.packet.write_bytes(self.packet.read_bytes()+b'\n')
        with self.assertRaisesRegex(c.IntegrationError,'PLAN_STALE'):
            bootstrap.apply(self.repo,self.registration,pin,**self.kw,approve_local_owner=True)
        self.assertEqual(self.inspect(),before)

    def test_concurrent_same_action_dispatches_once(self):
        pin=self.plan(); before=self.inspect(); gate=threading.Barrier(2)
        def run():
            gate.wait()
            try:
                return bootstrap.apply(self.repo,self.registration,pin,**self.kw,approve_local_owner=True)['status']
            except FileExistsError:
                return 'ALREADY_ATTEMPTED'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:run(),range(2)))
        self.assertEqual(sorted(results),['ALREADY_ATTEMPTED','NATIVE_RETURNED'])
        self.assertEqual(self.inspect()['committed'],before['committed']+1)

    def test_stale_cas_is_not_replayed_with_another_action(self):
        bootstrap.apply(self.repo,self.registration,self.plan(),**self.kw,approve_local_owner=True)
        before=self.inspect(); self.kw['action_id']='different-action-same-stale-packet'
        with self.assertRaisesRegex(c.IntegrationError,'BOOTSTRAP_NATIVE_FAILURE'):
            bootstrap.apply(self.repo,self.registration,self.plan(),**self.kw,approve_local_owner=True)
        self.assertEqual(self.inspect(),before)

    def test_no_mcp_mutation_or_extra_fields_and_external_work(self):
        original=self.packet.read_bytes()
        for update in ({'operation':'accept'}, {'approved':True},
                       {'operation':'enrollment-inspect','work':str(self.authority)}):
            packet=json.loads(original);packet.update(update);self.write(self.packet,packet)
            with self.assertRaises(c.IntegrationError): self.plan()
        self.packet.write_bytes(original)
        self.write(self.review/'policy.json','{}')
        with self.assertRaisesRegex(c.IntegrationError,'BOOTSTRAP_REVIEW_PIN'): self.plan()

    def test_expired_bundle_retains_unknown_without_retry(self):
        self.prepare(expired=True); before=self.inspect(); pin=self.plan()
        with self.assertRaisesRegex(c.IntegrationError,'BOOTSTRAP_NATIVE_FAILURE'):
            bootstrap.apply(self.repo,self.registration,pin,**self.kw,approve_local_owner=True)
        self.assertEqual(self.inspect(),before)
        result=json.loads((self.audit/'question-01/result.json').read_text())
        self.assertEqual(result['status'],'COMMIT_UNKNOWN')
        with self.assertRaises(FileExistsError):
            bootstrap.apply(self.repo,self.registration,pin,**self.kw,approve_local_owner=True)

    def test_real_activation_and_enrollment_with_native_digest(self):
        """Synthetic attestations only; never authenticates a human reviewer."""
        baseline=json.loads(self.seed['bundle'])['baseline_digest']
        spec=json.loads((SOURCE/'samples/documents/work.json').read_text())
        spec.update(schema_version=3,work_id='work',support_profile='LOCAL_NO_MERGE',
            runtime_profile=json.loads((SOURCE/'samples/runtime-profile.json').read_text()),
            intent_binding=dict(registration_ref=self.registration,baseline_ref=baseline,
                                policy_ref=self.seed['policy_pin']))
        specfile=self.base/'work.json';self.write(specfile,spec);work=self.repo/'work'
        subprocess.run([str(self.native_cli),'work','start',str(work),str(specfile)],
                       capture_output=True,check=True,timeout=20)
        evidence=[];serial=0
        def invoke(mode,control,**fields):
            nonlocal serial
            serial+=1;state=self.inspect();op=c.sha(('bootstrap-'+str(serial)).encode());now=int(time.time())
            packet=json.loads(self.packet.read_text());raw=c.encoded(control).decode()
            bundle=dict(schema='golem.intent.review-host-bundle.v1',project_id='demo',work_id='work',
                baseline_digest=baseline,policy_digest=self.seed['policy_pin'],registration_digest=self.registration,
                control_digest=c.sha(raw.encode()),owner='owner',owner_session='owner-session',
                not_before=now-1,expires_at=now+300,evidence=evidence,publication_operation=op,
                expected_sequence=state['committed'],expected_head=state['head'])
            packet.update(operation=mode,work='' if mode=='review' else str(work),control=raw,
                bundle=c.encoded(bundle).decode(),bundle_sha256=c.sha(c.encoded(bundle)),publication_operation=op,
                authority_sequence=state['committed'],authority_head=state['head'],**fields)
            self.write(self.review/'bundle.json',packet['bundle']);self.write(self.packet,packet)
            self.kw['action_id']='step-'+str(serial)
            return bootstrap.apply(self.repo,self.registration,self.plan(),**self.kw,approve_local_owner=True)['native']
        selected=dict(project_id='demo',work_id='work',baseline_digest=baseline)
        snapshot=invoke('enrollment-inspect',selected)
        def statement(purpose,body,owner=False):
            who='owner' if owner else 'reviewer'
            value=dict(schema='golem.intent.review-host-evidence.v1',purpose=purpose,
                **selected,policy_digest=self.seed['policy_pin'],policy_epoch=1,issuer=who,
                issuer_session=who+'-session',producer='' if owner else 'producer',
                producer_session='' if owner else 'producer-session',body=body)
            raw=c.encoded(value).decode();digest=c.sha(raw.encode());evidence.append(dict(sha256=digest,bytes=raw));return digest
        body=dict(stage='REQUIREMENTS',input_manifest=c.sha(b'isolated fixture only'),
            definitions_digest=snapshot['definitions_digest'],verdict='PASS',original_source_reviewed=True)
        review=statement('STAGE',body)
        control=dict(schema='golem.intent.review-control.v1',**selected,operation='review',expected_epoch=0,
            body={k:v for k,v in body.items() if k!='original_source_reviewed'})
        control['body'].update(producer='producer',reviewer='reviewer',evidence_digest=review)
        invoke('review',control)
        statement('SOURCE_ADOPTION',dict(disposition='ADOPT_EXACT_BASELINE',all_source_decisions_reviewed=True),True)
        activation=statement('ACTIVATION',dict(review_digest=review,policy_digest=self.seed['policy_pin']),True)
        control.update(operation='activate',expected_epoch=1,body=dict(decision_digest=activation,
            review_digest=review,policy_digest=self.seed['policy_pin']))
        invoke('review',control)
        state=self.inspect()
        enrollment=dict(schema='golem.intent.work-enrollment.v1',**selected,created_by_assertion='DISPOSABLE_FIXTURE',
            body=dict(baseline_ref=baseline,work_spec_digest=snapshot['work_spec_digest'],
                requirement_mapping=[dict(requirement_ref=json.loads(self.seed['baseline'])['body']['requirement_refs'][0],
                                          acceptance_id='REQ-1')],support_profile='LOCAL_NO_MERGE',
                policy_ref=self.seed['policy_pin'],activation_decision_ref=activation,predecessor_ref=None))
        digest=invoke('enrollment-digest',selected,enrollment=c.encoded(enrollment).decode(),
            work_sequence=snapshot['work_sequence'],work_head=snapshot['work_head'])
        # Preserve the exact publication operation, CAS and bundle used for digest planning.
        packet=json.loads(self.packet.read_text());packet['operation']='enroll';packet['approval']=digest['approval_digest']
        self.write(self.packet,packet);self.kw['action_id']='exact-enroll'
        result=bootstrap.apply(self.repo,self.registration,self.plan(),**self.kw,approve_local_owner=True)
        self.assertEqual(result['native']['operation'],'enroll')
        self.assertEqual(self.inspect()['committed'],state['committed']+1)
        self.assertFalse(result['execution_authorized'])


if __name__=='__main__': unittest.main()
