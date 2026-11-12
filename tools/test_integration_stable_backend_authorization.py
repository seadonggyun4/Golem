"""Fixed frontend routing into actual D1/D2/D4 admission, using private fixtures.

Transport is an in-process RPC bridge; the actual native process effect is the
existing D4 fixture's capture stub. This is not native/client E2E. Real relay
process replacement and handshake are tested separately in test_integration_stable_relay.
"""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import integration_contract as c
import integration_feature_profiles as profiles
import integration_mutations as mutations
import integration_stable_catalog as builder
import test_integration_mutations as fixtures


SCRIPTS=Path(__file__).resolve().parents[1]/'plugins/golem/scripts'


def load(name):
    spec=importlib.util.spec_from_file_location('backend_fixture_'+name,SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


adapter,contract,relay=load('launcher'),load('stable_contract'),load('stable_relay')


class ActualBackendAuthority(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.D4()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root
        self.catalog=builder.catalog('task',['session_claim','session_begin','projects_list'])
        names=[item['name'] for item in self.catalog['tools']]
        contract._VERIFIED_TYPED_INDEX={'schema':'golem.typed-interface-inventory.v1',
            'profiles':{profile:names[:] for profile in contract.PROFILES},
            'tools':{tool['name']:copy.deepcopy(tool) for tool in self.catalog['tools']}}
        self.addCleanup(setattr,contract,'_VERIFIED_TYPED_INDEX',None)
        self.adapter_state=self.root/'stable-adapter-state'
        launcher=self.write('stable-launcher.json',{'command':sys.executable,
            'args':['-I','-B','-c','raise SystemExit("NOT_A_NATIVE_TEST")']})
        adapter.configure(self.adapter_state,launcher,contract.digest(launcher.read_bytes()),True,'codex')
        approved=adapter.inspect_state(self.adapter_state,'codex')
        catalog_path=self.write('fixed-catalog.json',self.catalog)
        selection=self.write('initial-selection.json',{'schema':'golem.stable-selection.v1',
            'client':'codex','revision':1,'previous_sha256':None,
            'catalog_sha256':contract.digest(catalog_path.read_bytes()),'adapter_state':str(self.adapter_state),
            'approval_sha256':approved['approval_sha256'],'launcher_sha256':approved['launcher_sha256']})
        self.store=self.root/'fixed-store'
        contract.create(self.store,catalog_path,contract.digest(catalog_path.read_bytes()),
            selection,contract.digest(selection.read_bytes()),True,adapter)
        self.frontend=relay.StableRelay(adapter,contract,self.store,'codex')
        self.addCleanup(self.frontend.selector.close)
        self.frontend.launcher,self.frontend.pin,self.frontend.approval_pin=self.frontend.approved(self.adapter_state)
        self.frontend.initialized=True;self.frontend.state='READY';self.frontend.child_generation=1
        self.outputs=[];self.dispatched=[];self.next_id=1
        self.frontend.send_client=self.outputs.append
        self.frontend.send_child=self.deliver
        self.native=self.fixture.api()
        self.backend=profiles.Scoped(self.native,'task')

    def write(self,name,value):
        path=self.root/name;path.write_bytes(contract.encode(value));path.chmod(0o600);return path

    def deliver(self,message):
        self.dispatched.append(copy.deepcopy(message))
        self.assertEqual(message['method'],'tools/call')
        try:
            result=self.backend.call(message['params']['name'][6:],message['params']['arguments'])
        except c.IntegrationError as error:
            result=mutations.blocked(error)
        self.frontend.child_message({'jsonrpc':'2.0','id':message['id'],'result':result})

    def rpc(self,method,params=None):
        number=self.next_id;self.next_id+=1
        self.frontend.client_message({'jsonrpc':'2.0','id':number,'method':method,'params':params or {}})
        self.assertEqual(self.outputs[-1]['id'],number)
        return self.outputs[-1]

    def call(self,name='golem_session_claim',args=None):
        return self.rpc('tools/call',{'name':name,'arguments':args or self.fixture.args})['result']

    def listed(self):
        return self.rpc('tools/list')['result']

    def test_fixed_list_does_not_admit_missing_D4_tool_or_foreign_action(self):
        before=self.fixture.inventory()
        listed=self.listed()
        self.assertIn('golem_session_begin',[tool['name'] for tool in listed['tools']])
        self.assertNotIn('session_begin',self.backend.tools())
        with patch.object(mutations.records,'capture',side_effect=AssertionError('no native effect')) as capture:
            self.assertEqual(self.call('golem_session_begin')['code'],'FEATURE_OWNER_SCOPE')
            result=self.call(args={**self.fixture.args,'action_id':'unapproved'})
            self.assertEqual(result['code'],'MUTATION_SCOPE')
        capture.assert_not_called()
        self.assertEqual(before,self.fixture.inventory())
        self.assertEqual(self.listed(),listed)
        self.assertEqual(list(self.fixture.registry.root.glob('mutation-*')),[])

    def test_exact_D4_fixture_result_remains_single_dispatch_and_historical(self):
        listed=self.listed();before=self.fixture.inventory()
        with patch.object(self.native,'_preflight',self.fixture.preflight), \
             patch.object(mutations.records,'capture',side_effect=self.fixture.capture) as effect:
            first=self.call();second=self.call()
        self.assertEqual(first['state'],'NATIVE_RESULT_RECORDED')
        self.assertEqual(first,second)
        self.assertEqual(effect.call_count,1)
        self.assertEqual(before,self.fixture.inventory())
        self.assertEqual(self.listed(),listed)

    def test_same_frontend_definitions_do_not_revive_revoked_D1_authority(self):
        listed=self.listed();self.fixture.approve('revoke')
        with patch.object(mutations.records,'capture',side_effect=AssertionError('no native effect')) as capture:
            result=self.call()
        self.assertEqual(result['code'],'FEATURE_OWNER_SCOPE')
        capture.assert_not_called()
        self.assertEqual(self.listed(),listed)
        self.assertEqual(list(self.fixture.registry.root.glob('mutation-*')),[])

    def test_current_D2_bytes_drift_blocks_despite_fixed_frontend(self):
        listed=self.listed()
        path=self.fixture.policy_path;path.write_bytes(path.read_bytes()+b' ')
        with patch.object(mutations.records,'capture',side_effect=AssertionError('no native effect')) as capture:
            result=self.call()
        self.assertEqual(result['code'],'TRANSFER_POLICY_CHANGED')
        capture.assert_not_called()
        self.assertEqual(self.listed(),listed)

    def test_new_exact_empty_D4_policy_keeps_catalog_but_removes_call_authority(self):
        listed=self.listed()
        # The fixture substitutes an independently reviewed backend Policy;
        # it does not claim to exercise a process refresh or production update.
        policy=copy.deepcopy(self.fixture.mutation_policy);policy['actions']=[]
        path=self.write('second-empty-D4.json',policy)
        selected=fixtures.contract.Policy(path,c.sha(path.read_bytes()),approve_mutations=True)
        self.backend=profiles.Scoped(mutations.Service(selected),'task')
        with patch.object(mutations.records,'capture',side_effect=AssertionError('no native effect')) as capture:
            self.assertEqual(self.call()['code'],'FEATURE_OWNER_SCOPE')
        capture.assert_not_called()
        self.assertEqual(self.listed(),listed)
        self.assertEqual(list(self.fixture.registry.root.glob('mutation-*')),[])

    def test_action_bytes_change_and_untrusted_argument_cannot_supply_approval(self):
        listed=self.listed()
        self.fixture.action_path.write_bytes(self.fixture.action_path.read_bytes()+b' ')
        with patch.object(mutations.records,'capture',side_effect=AssertionError('no native effect')) as capture:
            self.assertEqual(self.call()['code'],'ACTION_CHANGED')
            self.assertEqual(self.call(args={**self.fixture.args,'approve':True})['code'],'SCHEMA')
        capture.assert_not_called()
        self.assertEqual(self.listed(),listed)

    def test_unknown_result_stays_unknown_across_cached_definitions_and_new_id(self):
        listed=self.listed()
        with patch.object(self.native,'_preflight',self.fixture.preflight), \
             patch.object(mutations.records,'capture',side_effect=OSError('fixture reply lost')) as effect:
            first=self.call();second=self.call()
            third=self.call(args={**self.fixture.args,'request_id':'different-request'})
        self.assertEqual(first['state'],'COMMIT_UNKNOWN')
        self.assertEqual(first,second)
        self.assertEqual(third['code'],'WORK_MUTATION_UNRESOLVED')
        self.assertEqual(effect.call_count,1)
        self.assertFalse(first['automatic_retry_allowed'])
        self.assertEqual(self.listed(),listed)

    def test_native_preflight_stale_or_pending_never_promoted_by_listed_tool(self):
        listed=self.listed()
        for code in ('OBSERVATION_STALE','PENDING_APPROVAL'):
            with patch.object(self.native,'_preflight',side_effect=c.IntegrationError(code)), \
                 patch.object(mutations.records,'capture',side_effect=AssertionError('no native effect')) as effect:
                result=self.call(args={**self.fixture.args,'request_id':code.lower()})
            self.assertEqual(result['code'],code)
            self.assertEqual(result['state'],'PENDING_APPROVAL' if code=='PENDING_APPROVAL' else 'NOT_DISPATCHED')
            self.assertFalse(result['execution_authorized'])
            self.assertFalse(result['native_state_changed'])
            effect.assert_not_called()
        self.assertEqual(self.listed(),listed)


if __name__=='__main__':
    unittest.main()
