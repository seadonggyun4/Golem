"""Pure fixed-frontend/readiness evidence fixtures; no host or Work calls."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import integration_stable_readiness as readiness


def canonical_pin(value):
    return hashlib.sha256((json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False)+'\n').encode()).hexdigest()


def names_pin(names):
    return hashlib.sha256(json.dumps(sorted(names),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def snapshot(selection, catalog):
    pin=canonical_pin(selection)
    return {'selection':selection,'selection_sha256':pin,'catalog':catalog,
        'catalog_sha256':canonical_pin(catalog), 'current_head_selection_sha256':pin,'is_current':True,
        'head_sha256':canonical_pin({'schema':'golem.stable-head.v1','client':selection['client'],
            'revision':selection['revision'],'selection_sha256':pin,'catalog_sha256':canonical_pin(catalog)}),
        'execution_authorized':False,'publication_state':'SELECTED_NOT_LIVE_APPLIED'}


class StableReadiness(unittest.TestCase):
    def setUp(self):
        self.now=1_000_000_000_000_000
        self.tools=['golem_action_prepare','golem_projects_list']
        definitions=[{'name':name,'description':'Typed fixed definition only.',
            'inputSchema':{'type':'object','properties':{},'additionalProperties':False},
            'annotations':{'readOnlyHint':False,'destructiveHint':False,
                'idempotentHint':False,'openWorldHint':False}} for name in self.tools]
        catalog={'schema':readiness.FRONTEND_ABI,'profile':'prepare','tools':definitions,
                 'tools_sha256':canonical_pin(definitions)}
        selection={'schema':'golem.stable-selection.v1','client':'codex','revision':1,
            'previous_sha256':None,'catalog_sha256':canonical_pin(catalog),'adapter_state':'/private/fixture/state-1',
            'approval_sha256':'a'*64,'launcher_sha256':'b'*64}
        self.selected=snapshot(selection,catalog)
        self.marker='golem-catalog-v2:'+('1'*32)+':'+self.selected['catalog_sha256']+':'+('2'*32)
        self.live={'schema':'golem.stable-connection-relay.v1','client':'codex','instance':'1'*32,
            'frontend_abi':readiness.FRONTEND_ABI,'state':'READY','busy':False,'failure':None,
            'pending':0,'server_pending':0,'backend_epoch':1,'selection_revision':1,
            'selection_sha256':self.selected['selection_sha256'],'head_sha256':self.selected['head_sha256'],
            'selected_state':selection['adapter_state'],'approval_sha256':selection['approval_sha256'],
            'launcher_sha256':selection['launcher_sha256'],'catalog_sha256':self.selected['catalog_sha256'],
            'catalog_tools_sha256':catalog['tools_sha256'],'definition_marker':self.marker,
            'definition_tool_count':2,'definition_tools_sha256':names_pin(self.tools),
            'observed_at_ns':self.now-10_000_000,'frontend_catalog':{
                'schema':'golem.stable-frontend-catalog-observation.v1','state':'HOST_CATALOG_RESPONSE_SENT',
                'catalog_sha256':self.selected['catalog_sha256'],'requests':1,'responses':1,'errors':0,
                'current_complete_sha256':'c'*64,'definition_marker':self.marker,'model_delivery_verified':False}}
        self.model={'source':readiness.MODEL_SOURCE,'target':{'thread_id':'chat-1','server_name':'golem-local'},
            'thread_id':'chat-1','server_name':'golem-local','turn_id':'turn-1',
            'observed_at_ns':self.now-20_000_000,'marker':self.marker,'tools':self.tools[:]}

    def classify(self, **changes):
        args={'selected':self.selected,'live':self.live,'model':self.model,
              'required_tools':['golem_action_prepare'],'now_ns':self.now}
        args.update(changes)
        return readiness.classify(**args)

    def blocked(self, **changes):
        result=self.classify(**changes)
        self.assertFalse(result['preparation_allowed'])
        self.assertEqual(result['state'],'BLOCKED')
        self.assertFalse(result['execution_authorized'])
        return result

    def assert_no_authority(self, result):
        for key in ('execution_authorized','native_work_verified','owner_identity_authenticated','automatic_retry_allowed'):
            self.assertIs(result[key],False)
        self.assertEqual(result['actual_execution'],'HOLD')

    def test_current_fixed_definitions_and_backend_are_readiness_only(self):
        result=self.classify()
        self.assertTrue(result['preparation_allowed'])
        self.assertEqual(result['state'],'PREPARATION_READY_NOT_AUTHORIZED')
        self.assertFalse(result['host_relist_required'])
        self.assertEqual(result['target'],self.model['target'])
        self.assert_no_authority(result)

    def test_claude_client_uses_same_contract_without_codex_inference(self):
        selection=dict(self.selected['selection'],client='claude-desktop')
        self.selected=snapshot(selection,self.selected['catalog'])
        self.live.update(client='claude-desktop',selection_sha256=self.selected['selection_sha256'],
                         head_sha256=self.selected['head_sha256'])
        self.assertTrue(self.classify()['preparation_allowed'])
        self.live['client']='codex'
        self.assertEqual(self.blocked()['reason'],'LIVE_SELECTION_OR_CATALOG_MISMATCH')

    def test_preserved_frontend_evidence_accepts_fresh_new_backend_without_host_relist(self):
        previous=self.selected
        next_selection=dict(previous['selection'],revision=2,previous_sha256=previous['selection_sha256'],
            adapter_state='/private/fixture/state-2',approval_sha256='d'*64,launcher_sha256='e'*64)
        self.selected=snapshot(next_selection,previous['catalog'])
        self.assertEqual(self.blocked()['reason'],'LIVE_SELECTION_OR_CATALOG_MISMATCH')
        refresh={'state':'ACKNOWLEDGED','attempts':1,'completed_at_ns':self.now-15_000_000,
                 'previous_backend_epoch':1,'target_selection_sha256':self.selected['selection_sha256']}
        self.live.update(backend_epoch=2,selection_revision=2,selection_sha256=self.selected['selection_sha256'],
            head_sha256=self.selected['head_sha256'],selected_state=next_selection['adapter_state'],
            approval_sha256=next_selection['approval_sha256'],launcher_sha256=next_selection['launcher_sha256'])
        before=copy.deepcopy(self.model)
        result=self.classify(refresh=refresh)
        self.assertTrue(result['preparation_allowed'])
        self.assertEqual(self.model,before)
        self.assertEqual(self.live['frontend_catalog']['requests'],1)
        self.assertEqual(self.live['definition_marker'],self.marker)
        self.assertFalse(result['host_relist_required'])
        self.assert_no_authority(result)
        self.live['backend_epoch']=1
        self.assertEqual(self.blocked(refresh=refresh)['reason'],'POST_ACK_BACKEND_PROOF_NOT_OBSERVED')

    def test_ACK_without_fresh_status_cannot_reuse_old_backend_proof(self):
        refresh={'state':'ACKNOWLEDGED','attempts':1,'completed_at_ns':self.now-5_000_000,
                 'previous_backend_epoch':1,'target_selection_sha256':self.selected['selection_sha256']}
        self.assertEqual(self.blocked(refresh=refresh)['reason'],'POST_ACK_BACKEND_PROOF_NOT_OBSERVED')
        self.live['backend_epoch']=2
        self.assertEqual(self.blocked(refresh=refresh)['reason'],'POST_ACK_BACKEND_PROOF_NOT_OBSERVED')
        self.live['observed_at_ns']=self.now
        self.assertTrue(self.classify(refresh=refresh)['preparation_allowed'])

    def test_unknown_failed_and_repeated_refresh_never_become_ready(self):
        for refresh in ({'state':'UNKNOWN','attempts':1},{'state':'FAILED','attempts':1},
                        {'state':'ACKNOWLEDGED','attempts':2},{'state':'ACKNOWLEDGED','attempts':True},
                        {'state':'NOT_ATTEMPTED','attempts':1},'unknown'):
            with self.subTest(refresh=refresh):self.blocked(refresh=refresh)
        self.assertTrue(self.classify(refresh={'state':'NOT_ATTEMPTED','attempts':0})['preparation_allowed'])

    def test_missing_or_invalid_ACK_target_time_epoch_blocks(self):
        base={'state':'ACKNOWLEDGED','attempts':1,'completed_at_ns':self.now-15_000_000,
              'previous_backend_epoch':1,'target_selection_sha256':self.selected['selection_sha256']}
        self.live['backend_epoch']=2
        for change in ({'completed_at_ns':self.now+1},{'completed_at_ns':None},
                       {'previous_backend_epoch':False},{'target_selection_sha256':'f'*64}):
            with self.subTest(change=change):self.blocked(refresh=dict(base,**change))
        historical=dict(base,completed_at_ns=self.now-readiness.MAX_AGE_NS-1)
        self.assertTrue(self.classify(refresh=historical)['preparation_allowed'])

    def test_live_pin_head_client_catalog_abi_and_state_mismatch_block(self):
        for key in ('client','selected_state','selection_sha256','head_sha256','approval_sha256',
                    'launcher_sha256','catalog_sha256','catalog_tools_sha256','frontend_abi','schema'):
            with self.subTest(key=key):self.blocked(live=dict(self.live,**{key:'wrong'}))
        for change in ({'state':'UNKNOWN'},{'state':'STARTING'},{'busy':True},{'pending':1},
                       {'server_pending':1},{'pending':False},{'failure':'LOST_REPLY'},
                       {'backend_epoch':0},{'backend_epoch':True},{'selection_revision':True}):
            with self.subTest(change=change):self.blocked(live=dict(self.live,**change))

    def test_missing_forged_stale_and_wrong_instance_marker_blocks(self):
        variants=[None,'golem-connection-v1:'+('1'*32)+':1:1:'+('2'*32),
                  self.marker[:-1]+'3',self.marker.replace('1'*32,'3'*32),
                  self.marker.replace(self.selected['catalog_sha256'],'f'*64)]
        for marker in variants:
            with self.subTest(marker=marker):self.blocked(model=dict(self.model,marker=marker))
        self.blocked(live=dict(self.live,definition_marker=self.marker.replace('1'*32,'3'*32)))
        altered=copy.deepcopy(self.live);altered['frontend_catalog']['definition_marker']=self.marker[:-1]+'3'
        self.blocked(live=altered)

    def test_complete_fixed_catalog_forwarding_is_required_without_claiming_delivery(self):
        for change in ({'state':'NOT_OBSERVED'},{'requests':0},{'responses':0},{'errors':1},
                       {'responses':2},{'current_complete_sha256':None},{'model_delivery_verified':True},
                       {'catalog_sha256':'f'*64}):
            live=copy.deepcopy(self.live);live['frontend_catalog'].update(change)
            with self.subTest(change=change):self.blocked(live=live)
        self.blocked(live=dict(self.live,frontend_catalog=None))
        self.blocked(model=None)

    def test_full_observed_inventory_not_subset_or_same_count_substitute(self):
        for names in ([],['golem_action_prepare'],self.tools+['golem_unknown'],
                      ['golem_action_prepare','golem_unknown'],['golem_action_prepare']*2,[{}]):
            with self.subTest(names=names):self.blocked(model=dict(self.model,tools=names))
        self.blocked(live=dict(self.live,definition_tool_count=1))
        self.blocked(live=dict(self.live,definition_tools_sha256='f'*64))
        self.assertTrue(self.classify(model=dict(self.model,tools=list(reversed(self.tools))))['preparation_allowed'])

    def test_required_tools_explicitly_selected_and_present(self):
        self.assertEqual(self.blocked(required_tools=[])['reason'],'PREPARATION_TOOLS_NOT_SELECTED')
        self.assertEqual(self.blocked(required_tools=['golem_document_submit'])['reason'],
                         'REQUIRED_MODEL_TOOL_DEFINITIONS_MISSING')
        for tools in (['shell'],['golem_action_prepare']*2,[{}]):
            with self.assertRaisesRegex(ValueError,'REQUIRED_TOOL_NAMES'):self.classify(required_tools=tools)

    def test_exact_external_target_turn_source_required_not_authenticated(self):
        for change in ({'thread_id':'different'},{'server_name':'other'},{'turn_id':''},
                       {'turn_id':'bad\nturn'},{'target':None},{'source':'AGENT_ASSERTION'}):
            with self.subTest(change=change):self.blocked(model=dict(self.model,**change))
        self.assert_no_authority(self.classify())

    def test_both_model_and_live_5minute_freshness_with_no_clock_IO(self):
        for key in ('live','model'):
            value=copy.deepcopy(getattr(self,key))
            for when in (self.now-readiness.MAX_AGE_NS-1,self.now+1,None,True):
                value['observed_at_ns']=when
                with self.subTest(key=key,when=when):self.blocked(**{key:value})
        model=dict(self.model,observed_at_ns=self.now)
        self.assertEqual(self.blocked(model=model)['reason'],'LIVE_OBSERVATION_PRECEDES_MODEL')
        with self.assertRaisesRegex(ValueError,'OBSERVATION_CLOCK'):self.classify(now_ns=True)

    def test_tampered_or_historical_selected_snapshot_does_not_qualify(self):
        for field in ('selection_sha256','catalog_sha256','head_sha256','current_head_selection_sha256'):
            with self.subTest(field=field):self.blocked(selected=dict(self.selected,**{field:'f'*64}))
        self.blocked(selected=dict(self.selected,is_current=False))
        value=copy.deepcopy(self.selected);value['selection']['approval_sha256']='f'*64
        self.blocked(selected=value)
        value=copy.deepcopy(self.selected);value['catalog']['tools'][0]['description']='modified ABI'
        self.blocked(selected=value)

    def test_inputs_unchanged_and_no_io(self):
        before=copy.deepcopy((self.selected,self.live,self.model))
        with patch('builtins.open',side_effect=AssertionError('no file access')):
            self.assertTrue(self.classify()['preparation_allowed'])
        self.assertEqual((self.selected,self.live,self.model),before)


if __name__=='__main__':
    unittest.main()
