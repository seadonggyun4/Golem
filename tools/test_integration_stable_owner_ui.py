"""Isolated view fixtures: no installed app, client, policy, or Work is used."""
import ast
import copy
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

import integration_stable_owner_ui as ui


INSTANCE = 'a'*32
OTHER = 'b'*32
CATALOG = 'c'*64
OLD = 'd'*64
NEW = 'e'*64
HEAD = 'f'*64
TOKEN = '1'*64
MARKER = 'golem-catalog-v2:'+INSTANCE+':'+CATALOG+':'+'2'*32


def report(kind=None, client='codex'):
    current = NEW if kind=='refresh' else OLD
    value = {'schema':ui.REPORT_SCHEMA,'client':client,'state':'OBSERVED',
        'execution_authorized':False,'automatic_retry_allowed':False,'actual_execution':'HOLD',
        'selected':{'selection_sha256':current,'head_sha256':HEAD,'catalog_sha256':CATALOG,
                    'selection':{'client':client,'revision':2 if kind=='refresh' else 1,'adapter_state':'/fixture/state'}},
        'connections':[{'client':client,'instance':INSTANCE,'endpoint_state':'PRESENT'},
                       {'client':client,'instance':OTHER,'endpoint_state':'ABSENT'}],
        'live':{'schema':'golem.stable-connection-relay.v1','client':client,'instance':INSTANCE,
                'state':'READY','busy':False,'failure':None,'pending':0,'server_pending':0,
                'backend_epoch':1,'selection_sha256':OLD,'definition_marker':MARKER},
        'model_observation':{'thread_id':'fixture-chat','turn_id':'fixture-turn','marker':MARKER,
                             'observed_at_ns':123,'tools':['golem_projects_list']},
        'readiness':{'state':'BLOCKED','preparation_allowed':False,'execution_authorized':False,
                     'reason':'LIVE_SELECTION_OR_CATALOG_MISMATCH'},'review':None}
    if kind=='publish':
        value['review']={'kind':'publish','token':TOKEN,'selection_sha256':NEW,'expected_head_sha256':HEAD}
    elif kind=='refresh':
        value['review']={'kind':'refresh','token':TOKEN,'instance':INSTANCE,'marker':MARKER,
                         'old_selection_sha256':OLD,'target_selection_sha256':NEW}
    return value


def correlated_report(kind='refresh', client='codex'):
    value=report(kind,client)
    target={'thread_id':'fixture-chat','server_name':'fixture-server'}
    value['model_observation'].update(source='EXTERNAL_MODEL_DEFINITION_OBSERVATION',
                                     target=target,server_name=target['server_name'])
    value['readiness'].update(schema='golem.stable-definition-correlation.v1',
        state='EXTERNAL_CORRELATION_ONLY',correlated=True,frontend_bound=True,
        same_chat_model_tools='EXTERNALLY_CORRELATED_FIXED_DEFINITIONS',target=copy.deepcopy(target),
        observed_tools=['golem_projects_list'],automatic_retry_allowed=False,actual_execution='HOLD')
    return value


class Presentation(unittest.TestCase):
    def test_observed_row_requires_explicit_native_correlation_result(self):
        self.assertIsNone(ui.presentation(report('refresh'),'codex')['observed_instance'])
        value=correlated_report();before=copy.deepcopy(value)
        self.assertEqual(ui.presentation(value,'codex')['observed_instance'],INSTANCE)
        self.assertEqual(value,before)
        value['readiness'].update(schema='golem.stable-connection-readiness.v1',
            state='PREPARATION_READY_NOT_AUTHORIZED',preparation_allowed=True,
            stages={'same_chat_model_tools':'EXTERNALLY_CORRELATED_FIXED_DEFINITIONS'})
        self.assertEqual(ui.presentation(value,'codex')['observed_instance'],INSTANCE)

    def test_observed_row_rejects_missing_wrong_or_ambiguous_target(self):
        changes=[('readiness','correlated',False),('readiness','frontend_bound',False),
            ('readiness','target',{'thread_id':'other','server_name':'fixture-server'}),
            ('readiness','observed_tools',['golem_other']),('readiness','actual_execution','RUN'),
            ('readiness','automatic_retry_allowed',True),('readiness','execution_authorized',True),
            ('model_observation','marker','wrong'),('model_observation','source','HOST_CATALOG'),
            ('model_observation','server_name','other'),('live','client','claude-desktop'),
            ('live','instance',OTHER),('live','definition_marker','wrong'),
            ('live','state','CLOSED'),('live','busy',True),('live','pending',1),
            ('live','server_pending',True),('live','failure','UNKNOWN')]
        for part,key,bad in changes:
            with self.subTest(part=part,key=key):
                value=correlated_report();value[part][key]=bad
                self.assertIsNone(ui.presentation(value,'codex')['observed_instance'])
        for change in ('absent','other-client','duplicate','missing','truncated','catalog','blocked'):
            with self.subTest(change=change):
                value=correlated_report()
                if change=='absent':value['connections'][0]['endpoint_state']='ABSENT'
                if change=='other-client':value['connections'][0]['client']='claude-desktop'
                if change=='duplicate':value['connections'].append(copy.deepcopy(value['connections'][0]))
                if change=='missing':value['connections']=value['connections'][1:]
                if change=='truncated':value['connections']+=[{}]*1023
                if change=='catalog':value['selected']['catalog_sha256']='9'*64
                if change=='blocked':value['state']='BLOCKED'
                self.assertIsNone(ui.presentation(value,'codex')['observed_instance'])

    def test_exact_publication_review_and_live_selection_remain_distinct(self):
        value=report('publish');before=copy.deepcopy(value)
        shown=ui.presentation(value,'codex')
        self.assertEqual(shown['review']['kind'],'publish')
        self.assertIn(OLD,shown['selected'])
        self.assertEqual(shown['raw_review']['selection_sha256'],NEW)
        self.assertFalse(shown['preparation_allowed'])
        self.assertEqual(value,before)

    def test_exact_refresh_and_ended_connection_are_not_interchangeable(self):
        shown=ui.presentation(report('refresh'),'codex')
        self.assertEqual(shown['review']['instance'],INSTANCE)
        self.assertEqual(shown['endpoints'][OTHER],'ABSENT')
        self.assertEqual(shown['rows'][1][1][3],'종료됨 · 기록 보존')
        self.assertIn('fixture-chat',shown['model'])
        self.assertIn('123',shown['model'])

    def test_missing_or_cross_client_envelope_never_enables_action(self):
        for key,bad in [('schema','other'),('client','claude-desktop'),('execution_authorized',0),
                        ('automatic_retry_allowed',None),('actual_execution','RUN')]:
            with self.subTest(key=key):
                value=report('publish');value[key]=bad
                shown=ui.presentation(value,'codex')
                self.assertFalse(shown['valid']);self.assertIsNone(shown['review'])
                self.assertFalse(shown['preparation_allowed'])

    def test_publication_requires_exact_current_head_and_new_selection(self):
        for patch in [{'token':'bad'},{'expected_head_sha256':'9'*64},{'selection_sha256':OLD},
                      {'selection_sha256':None}]:
            value=report('publish');value['review'].update(patch)
            self.assertIsNone(ui.presentation(value,'codex')['review'])

    def test_refresh_requires_original_model_marker_and_exact_status(self):
        changes=[('review','marker','golem-catalog-v2:'+OTHER+':'+CATALOG+':'+'2'*32),
                 ('review','old_selection_sha256',NEW),('review','target_selection_sha256',OLD),
                 ('live','definition_marker','wrong'),('live','busy',True),('live','pending',True),
                 ('live','server_pending',1),('live','state','CLOSED'),('live','failure','UNKNOWN'),
                 ('live','client','claude-desktop'),('model_observation','marker','wrong')]
        for part,key,bad in changes:
            with self.subTest(part=part,key=key):
                value=report('refresh');value[part][key]=bad
                self.assertIsNone(ui.presentation(value,'codex')['review'])

    def test_absent_unknown_cross_client_endpoint_blocks_refresh(self):
        for state in ['ABSENT','UNKNOWN',None]:
            value=report('refresh');value['connections'][0]['endpoint_state']=state
            self.assertIsNone(ui.presentation(value,'codex')['review'])
        value=report('refresh');value['connections'][0]['client']='claude-desktop'
        self.assertIsNone(ui.presentation(value,'codex')['review'])

    def test_failed_or_uncertain_result_never_preserves_action_token(self):
        for state in ['BLOCKED','RESULT_UNKNOWN']:
            value=report('refresh');value['state']=state
            self.assertIsNone(ui.presentation(value,'codex')['review'])
        value=report('publish');value['error']='PUBLICATION_UNKNOWN'
        self.assertIsNone(ui.presentation(value,'codex')['review'])

    def test_readiness_is_never_inferred_from_ACK_or_tool_counts(self):
        value=report();value['state']='ACKNOWLEDGED'
        value['readiness'].update(preparation_allowed=True)
        shown=ui.presentation(value,'codex');self.assertFalse(shown['preparation_allowed'])
        value['readiness']['state']='PREPARATION_READY_NOT_AUTHORIZED'
        shown=ui.presentation(value,'codex');self.assertTrue(shown['preparation_allowed'])
        self.assertIn('실행 HOLD',shown['readiness'])
        value['readiness']['execution_authorized']=True
        self.assertFalse(ui.presentation(value,'codex')['preparation_allowed'])

    def test_controls_and_long_metadata_are_literal_not_commands(self):
        value=report();value['model_observation']['thread_id']='$(do-not-run)<x>\x00'
        value['result']={'note':'x'*300000}
        shown=ui.presentation(value,'codex')
        self.assertIn('$(do-not-run)<x>\ufffd',shown['model'])
        self.assertIn('표시 한도',shown['details'])
        self.assertLess(len(shown['details']),262250)

    def test_full_tool_inventory_remains_in_details_not_expanding_summary(self):
        value=report('refresh')
        names=['golem_fixture_'+str(i)+'_long_name'*8 for i in range(78)]
        value['model_observation']['tools']=names
        original=copy.deepcopy(value)
        shown=ui.presentation(value,'codex')
        self.assertIn('78개',shown['model'])
        self.assertIn('원본 상세',shown['model'])
        self.assertLess(len(shown['model']),500)
        for name in names:
            self.assertIn(name,shown['details'])
            self.assertNotIn(name,shown['model'])
        self.assertEqual(value,original)
        self.assertEqual(shown['review']['token'],TOKEN)

    def test_unknown_counters_stay_unknown(self):
        value=report();value['live'].pop('backend_epoch')
        shown=ui.presentation(value,'codex')
        self.assertEqual(shown['rows'][0][1][4],'미확인')

    def test_no_Tk_at_import_or_host_commands(self):
        tree=ast.parse(Path(ui.__file__).read_text())
        imports=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
        self.assertFalse(any('tkinter' in ast.unparse(node) for node in imports))
        calls={ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node,ast.Call)}
        self.assertFalse(calls & {'subprocess.run','subprocess.Popen','os.system','os.kill','exec','eval','webbrowser.open'})


class Worker(unittest.TestCase):
    def test_one_request_in_background_no_duplicate_or_retry(self):
        worker=ui.BackgroundRequest();started=threading.Event();release=threading.Event();calls=[]
        def operation():
            calls.append(threading.get_ident());started.set();release.wait(2);return report()
        try:
            self.assertTrue(worker.start('inspect',operation));self.assertTrue(started.wait(1))
            self.assertFalse(worker.start('refresh',operation))
        finally:release.set()
        worker.thread.join(2);self.assertFalse(worker.thread.is_alive())
        self.assertEqual(worker.take()[0],'inspect');self.assertEqual(len(calls),1)
        self.assertNotEqual(calls[0],threading.get_ident())

    def test_arbitrary_exception_text_is_not_disclosed_or_retried(self):
        worker=ui.BackgroundRequest();calls=[]
        def fail():calls.append(1);raise RuntimeError('/secret/arbitrary content')
        worker.start('refresh',fail);worker.thread.join(2)
        self.assertEqual(worker.take(),('refresh',None,'STABLE_OWNER_OPERATION_FAILED'))
        self.assertEqual(calls,[1]);self.assertIsNone(worker.take())

    def test_close_discards_late_response_without_cancel_or_new_request(self):
        worker=ui.BackgroundRequest();release=threading.Event();finished=[]
        def operation():release.wait(2);finished.append(1);return report()
        worker.start('publish',operation);worker.close()
        self.assertFalse(worker.start('publish',operation));release.set();worker.thread.join(2)
        self.assertIsNone(worker.take());self.assertEqual(finished,[1])


class ActualControllerPresentation(unittest.TestCase):
    def test_pinned_broker_reports_enable_only_the_separate_exact_actions(self):
        import test_integration_stable_owner as fixture
        fx=fixture.StableOwner('test_both_clients_exact_owner_flow_preserves_frontend_and_hold')
        fx.setUp();self.addCleanup(fx.doCleanups)
        for client in ('codex','claude-desktop'):
            with self.subTest(client=client):
                process,path,pin,_=fx.start(client)
                initial=fx.controller.observe(client,path,pin)
                shown=ui.presentation(initial,client)
                self.assertTrue(shown['preparation_allowed']);self.assertIsNone(shown['review'])
                self.assertEqual(shown['observed_instance'],initial['live']['instance'])
                candidate,candidate_pin=fx.proposal(client)
                preview=fx.controller.review_selection(client,candidate,candidate_pin)
                shown=ui.presentation(preview,client)
                self.assertEqual(shown['review']['kind'],'publish')
                selected=fx.controller.publish(client,shown['review']['token'],approve=True)
                self.assertIsNone(ui.presentation(selected,client)['review'])
                self.assertFalse(ui.presentation(selected,client)['preparation_allowed'])
                preview=fx.controller.review_refresh(client,path,pin)
                shown=ui.presentation(preview,client)
                self.assertEqual(shown['review']['kind'],'refresh')
                self.assertEqual(shown['observed_instance'],preview['live']['instance'])
                switched=fx.controller.refresh(client,shown['review']['token'],approve=True)
                self.assertIsNone(ui.presentation(switched,client)['review'])
                self.assertFalse(ui.presentation(switched,client)['preparation_allowed'])
                observed=fx.controller.observe(client,path,pin)
                self.assertTrue(ui.presentation(observed,client)['preparation_allowed'])
                self.assertFalse(observed['execution_authorized'])


class FixtureController:
    clients=('codex','claude-desktop')
    def __init__(self):self.calls=[];self.published=False;self.refreshed=False
    def inspect(self,client):self.calls.append(('inspect',client));return report(client=client)
    def observe(self,client,path,pin):
        self.calls.append(('observe',client,path,pin));value=report(client=client)
        if self.refreshed:
            value['readiness'].update(state='PREPARATION_READY_NOT_AUTHORIZED',preparation_allowed=True)
        return value
    def review_selection(self,client,path,pin):
        self.calls.append(('review-publish',client,path,pin));return report('publish',client)
    def publish(self,client,token,approve=False):
        self.calls.append(('publish',client,token,approve));self.published=True
        value=report('refresh',client);value['state']='SELECTED_NOT_LIVE_APPLIED';value['review']=None
        return value
    def review_refresh(self,client,path,pin):
        self.calls.append(('review-refresh',client,path,pin));return correlated_report('refresh',client)
    def refresh(self,client,token,approve=False):
        self.calls.append(('refresh',client,token,approve));self.refreshed=True
        value=report('refresh',client);value['state']='ACKNOWLEDGED';value['review']=None
        return value


class MemoryTree:
    """Display-only Treeview fixture; no Tk process, connection, or controller."""
    def __init__(self):
        self.rows={};self.selected=();self.focused='';self.visible=None
    def get_children(self):return tuple(self.rows)
    def selection(self):return self.selected
    def selection_set(self,key):
        if key not in self.rows:raise AssertionError('unknown row')
        self.selected=(key,)
    def focus(self,key=None):
        if key is not None:self.focused=key
        return self.focused
    def focus_set(self):self.widget_focused=True
    def see(self,key):self.visible=key
    def delete(self,*keys):
        for key in keys:
            self.rows.pop(key)
            if key in self.selected:self.selected=()
            if key==self.focused:self.focused=''
    def insert(self,parent,where,*,iid,values):self.rows[iid]=values


class InputRequests(unittest.TestCase):
    def setUp(self):
        p=self.panel=ui.StableOwnerPanel.__new__(ui.StableOwnerPanel)
        p.clients=('codex','claude-desktop');p.client=Mock();p.client.get.return_value='codex'
        p.request=SimpleNamespace(busy=False,closed=False);p._submit=Mock();p.controller=Mock()
        p.observation_path=Mock();p.observation_sha=Mock();p.selection_path=Mock();p.selection_sha=Mock()

    def inputs(self,path,pin):
        p=self.panel
        p.observation_path.get.return_value=p.selection_path.get.return_value=path
        p.observation_sha.get.return_value=p.selection_sha.get.return_value=pin

    def test_empty_or_malformed_inputs_cannot_start_a_request(self):
        p=self.panel
        for path,pin in [('',NEW),(' \t\n',NEW),('/fixture/input.json',''),
                         ('/fixture/input.json','a'*63),('/fixture/input.json','a'*65),
                         ('/fixture/input.json','A'*64),('/fixture/input.json','g'*64),
                         ('/fixture/input.json',NEW+'\n')]:
            with self.subTest(path=path,pin=pin):
                self.inputs(path,pin)
                p.observe();p.review_refresh();p.review_selection()
                p._submit.assert_not_called();self.assertEqual(p.controller.mock_calls,[])

    def test_busy_closed_or_unconfigured_client_cannot_start_any_request(self):
        p=self.panel;self.inputs('/fixture/input.json',NEW)
        for condition in ('busy','closed','unconfigured'):
            with self.subTest(condition=condition):
                p.request.busy=condition=='busy';p.request.closed=condition=='closed'
                p.clients=('claude-desktop',) if condition=='unconfigured' else ('codex','claude-desktop')
                p.inspect();p.observe();p.review_refresh();p.review_selection()
                p._submit.assert_not_called();self.assertEqual(p.controller.mock_calls,[])

    def test_valid_shape_is_only_forwarded_on_request_without_normalizing_input(self):
        p=self.panel;path=' /fixture/not-read-by-view.json ';self.inputs(path,NEW)
        for action,kind,method in [(p.observe,'observe',p.controller.observe),
                                  (p.review_refresh,'review-refresh',p.controller.review_refresh),
                                  (p.review_selection,'review-publish',p.controller.review_selection)]:
            action();p._submit.assert_called_once()
            submitted,operation=p._submit.call_args.args;self.assertEqual(submitted,kind)
            method.assert_not_called();operation();method.assert_called_once_with('codex',path,NEW)
            p._submit.reset_mock()


class KeyboardRows(unittest.TestCase):
    def setUp(self):
        self.panel=ui.StableOwnerPanel.__new__(ui.StableOwnerPanel)
        self.panel.tree=MemoryTree();self.panel.selected_instance=None
        self.panel.refresh_consent=Mock();self.panel._enable=Mock()
        self.panel.controller=Mock()
        self.rows=ui.presentation(report(),'codex')['rows']

    def assert_selected(self,key):
        p=self.panel
        self.assertEqual(p.tree.selection(),(key,))
        self.assertEqual(p.tree.focus(),key)
        self.assertEqual(p.tree.visible,key)
        self.assertEqual(p.selected_instance,key)
        self.assertEqual(p.controller.mock_calls,[])

    def test_render_never_selects_then_down_seeds_first_row(self):
        p=self.panel;p._render_rows(self.rows)
        self.assertEqual(p.tree.selection(),());self.assertEqual(p.tree.focus(),'')
        self.assertEqual(p.navigate(1),'break');self.assert_selected(INSTANCE)
        p.refresh_consent.set.assert_called_once_with(False)

    def test_up_without_prior_selection_seeds_last_row(self):
        p=self.panel;p._render_rows(self.rows)
        self.assertEqual(p.navigate(-1),'break');self.assert_selected(OTHER)

    def test_explicit_navigation_clamps_and_clears_consent_only_on_new_row(self):
        p=self.panel;p._render_rows(self.rows);p.navigate(1)
        p.refresh_consent.reset_mock()
        p.navigate(-1);self.assert_selected(INSTANCE)
        p.refresh_consent.set.assert_not_called()
        p.navigate(1);self.assert_selected(OTHER)
        p.refresh_consent.set.assert_called_once_with(False)
        p.refresh_consent.reset_mock();p.navigate(1)
        self.assert_selected(OTHER);p.refresh_consent.set.assert_not_called()

    def test_reordered_report_retains_exact_selected_row_and_focus(self):
        p=self.panel;p._render_rows(self.rows);p.navigate(1)
        p.refresh_consent.reset_mock()
        p._render_rows(list(reversed(self.rows)))
        self.assert_selected(INSTANCE)
        p.refresh_consent.set.assert_not_called()

    def test_disappearing_selected_row_clears_consent_without_replacement(self):
        p=self.panel;p._render_rows(self.rows);p.navigate(1)
        p.refresh_consent.reset_mock();p._render_rows(self.rows[1:])
        self.assertEqual(p.tree.selection(),());self.assertEqual(p.tree.focus(),'')
        self.assertIsNone(p.selected_instance)
        p.refresh_consent.set.assert_called_once_with(False)
        self.assertEqual(p.controller.mock_calls,[])

    def test_empty_table_arrows_do_not_select_or_invoke_backend(self):
        p=self.panel;p._render_rows([]);p._enable.reset_mock()
        for direction in (-1,1):self.assertEqual(p.navigate(direction),'break')
        self.assertEqual(p.tree.selection(),());self.assertEqual(p.tree.focus(),'')
        p._enable.assert_not_called();self.assertEqual(p.controller.mock_calls,[])


class ObservedRows(unittest.TestCase):
    assert_selected = KeyboardRows.assert_selected

    def setUp(self):
        KeyboardRows.setUp(self);p=self.panel
        p.request=SimpleNamespace(busy=False,closed=False)
        p.client=Mock();p.client.get.return_value='codex';p.observation_dirty=False
        p.report=ui.presentation(correlated_report(),'codex')
        p._render_rows(p.report['rows']);p.refresh_consent.reset_mock()

    def test_explicit_selection_targets_correlated_row_and_never_calls_backend(self):
        p=self.panel
        self.assertEqual(p.tree.selection(),())
        p.navigate(-1);self.assert_selected(OTHER);p.refresh_consent.reset_mock()
        p.select_observed();self.assert_selected(INSTANCE)
        self.assertTrue(p.tree.widget_focused)
        p.refresh_consent.set.assert_called_once_with(False)

    def test_dirty_changed_client_busy_closed_or_missing_row_never_selects_fallback(self):
        p=self.panel
        for change in ('dirty','client','busy','closed','missing','uncorrelated'):
            with self.subTest(change=change):
                p.observation_dirty=False;p.client.get.return_value='codex'
                p.request.busy=False;p.request.closed=False
                p.report=ui.presentation(correlated_report(),'codex');p._render_rows(p.report['rows'])
                if change=='dirty':p.observation_dirty=True
                if change=='client':p.client.get.return_value='claude-desktop'
                if change=='busy':p.request.busy=True
                if change=='closed':p.request.closed=True
                if change=='missing':p.tree.delete(INSTANCE)
                if change=='uncorrelated':p.report['observed_instance']=None
                self.assertIsNone(p._available_observed_instance());p.select_observed()
                self.assertEqual(p.tree.selection(),());self.assertEqual(p.controller.mock_calls,[])


class MemoryViewportWidget:
    def __init__(self, master=None, kind='TButton', top=0, height=24):
        self.master=master;self.kind=kind;self.top=top;self.height=height
        self.children=[];self.tags=(str(id(self)),kind,'all');self.bindings={}
        if master is not None:master.children.append(self)
    def winfo_class(self):return self.kind
    def winfo_children(self):return self.children
    def winfo_rooty(self):return self.top
    def winfo_height(self):return self.height
    def bindtags(self, tags=None):
        if tags is not None:self.tags=tags
        return self.tags
    def bind_class(self, tag, sequence, callback):self.bindings[tag,sequence]=callback


class MemoryViewportCanvas(MemoryViewportWidget):
    def __init__(self, master):
        super().__init__(master,'Canvas',height=400)
        self.extent=(0,0,800,2000);self.offset=0;self.moves=[];self.scrolls=[]
    def bbox(self, target):return self.extent
    def canvasy(self, y):return self.offset+y
    def yview_moveto(self, fraction):self.moves.append(fraction);self.offset=fraction*2000
    def yview_scroll(self, amount, unit):self.scrolls.append((amount,unit))


class ViewportAccess(unittest.TestCase):
    def setUp(self):
        self.panel=ui.StableOwnerPanel.__new__(ui.StableOwnerPanel)
        self.panel.frame=MemoryViewportWidget(kind='TFrame')
        self.panel.canvas=MemoryViewportCanvas(self.panel.frame)
        self.panel.body=MemoryViewportWidget(self.panel.canvas,'TFrame',top=100)
        self.button=MemoryViewportWidget(self.panel.body,top=1400,height=30)
        self.panel.controller=Mock()

    def tearDown(self):self.assertEqual(self.panel.controller.mock_calls,[])

    def event(self, widget=None, **fields):
        return SimpleNamespace(widget=widget or self.button,**fields)

    def test_focus_makes_lower_button_visible_and_retains_already_visible_view(self):
        p=self.panel;p._follow_focus(self.event())
        self.assertEqual(p.canvas.moves,[938/2000])
        p._follow_focus(self.event())
        self.assertEqual(p.canvas.moves,[938/2000])

    def test_reverse_focus_brings_top_input_into_view(self):
        p=self.panel;p.canvas.offset=900
        entry=MemoryViewportWidget(p.body,'TEntry',top=150,height=24)
        p._follow_focus(self.event(entry))
        self.assertEqual(p.canvas.moves,[42/2000])

    def test_tall_nested_widget_focus_shows_its_top_without_repeated_movement(self):
        p=self.panel;text=MemoryViewportWidget(p.body,'Text',top=600,height=700)
        p._follow_focus(self.event(text));p._follow_focus(self.event(text))
        self.assertEqual(p.canvas.moves,[492/2000])

    def test_scoped_page_keys_and_platform_wheel_deltas(self):
        p=self.panel
        for fields,expected in [({'keysym':'Next'},(1,'pages')),({'keysym':'Prior'},(-1,'pages')),
                ({'delta':-240},(2,'units')),({'delta':1},(-1,'units')),
                ({'num':4},(-1,'units')),({'num':5},(1,'units')),({'delta':-24000},(10,'units'))]:
            self.assertEqual(p._scroll_viewport(self.event(**fields)),'break')
            self.assertEqual(p.canvas.scrolls[-1],expected)

    def test_nested_scrollables_and_combobox_keep_their_own_events(self):
        p=self.panel
        for kind in ('Treeview','Text','Listbox','Canvas','TScrollbar','Scrollbar','TCombobox','Spinbox','TSpinbox'):
            nested=MemoryViewportWidget(p.body,kind)
            for target in (nested,MemoryViewportWidget(nested)):
                for fields in ({'keysym':'Next'},{'keysym':'Prior'},{'delta':-120},{'num':5}):
                    self.assertIsNone(p._scroll_viewport(self.event(target,**fields)))
        self.assertEqual(p.canvas.scrolls,[])

    def test_other_tabs_shift_wheel_and_zero_delta_are_not_consumed(self):
        p=self.panel;other=MemoryViewportWidget()
        for event in (self.event(other,delta=120),self.event(state=1,delta=-120),self.event(delta=0)):
            self.assertIsNone(p._scroll_viewport(event))
        p._follow_focus(self.event(other))
        self.assertEqual(p.canvas.moves,[]);self.assertEqual(p.canvas.scrolls,[])

    def test_absent_or_nonoverflowing_geometry_never_moves_view(self):
        p=self.panel
        for extent,height in [(None,400),((0,0,800,300),400),((0,0,800,2000),1)]:
            p.canvas.extent=extent;p.canvas.height=height
            p._follow_focus(self.event())
        self.assertEqual(p.canvas.moves,[])

    def test_bindings_are_panel_local_and_preserve_widget_and_class_bindings(self):
        p=self.panel;other=MemoryViewportWidget();old=other.tags
        old_button=self.button.tags;p._bind_viewport()
        self.assertEqual(self.button.tags,(old_button[0],p.viewport_tag,*old_button[1:]))
        self.assertEqual(other.tags,old);self.assertEqual(other.bindings,{})
        self.assertEqual(set(p.frame.bindings),{(p.viewport_tag,e) for e in p.viewport_events})
        self.assertEqual(p.canvas.scrolls,[]);self.assertEqual(p.canvas.moves,[])


class NativePanel(unittest.TestCase):
    def setUp(self):
        if os.environ.get('GOLEM_TEST_TK')!='1':
            self.skipTest('native display fixture requires GOLEM_TEST_TK=1')
        import tkinter as tk
        self.root=tk.Tk();self.addCleanup(self.root.destroy)
        self.controller=FixtureController();self.panel=ui.StableOwnerPanel(self.root,self.controller)

    def settle(self):
        until=time.monotonic()+3
        while self.panel.request.busy and time.monotonic()<until:
            self.root.update();time.sleep(.01)
        self.root.update();self.assertFalse(self.panel.request.busy)

    def observation_input(self):
        self.panel.observation_path.set('/fixture/model.json');self.panel.observation_sha.set('a'*64)

    def selection_input(self):
        self.panel.selection_path.set('/fixture/selection.json');self.panel.selection_sha.set(NEW)

    def test_native_client_buttons_support_tab_space_return_and_direction_keys(self):
        p=self.panel;self.root.update()
        codex=p.client_buttons['codex'];claude=p.client_buttons['claude-desktop']
        codex.focus_force();self.root.update();codex.event_generate('<Tab>');self.root.update()
        self.assertIs(self.root.focus_get(),claude);self.assertEqual(p.client.get(),'codex')
        claude.event_generate('<space>');self.root.update()
        self.assertEqual(p.client.get(),'claude-desktop');self.assertIn('Claude Desktop',p.client_label.get())
        for widget,key,target in [(claude,'Left','codex'),(codex,'End','claude-desktop'),
                                  (claude,'Home','codex'),(codex,'Right','claude-desktop')]:
            widget.event_generate('<'+key+'>');self.root.update()
            self.assertEqual(p.client.get(),target);self.assertIs(self.root.focus_get(),p.client_buttons[target])
        codex.focus_force();self.root.update();codex.event_generate('<Return>');self.root.update()
        self.assertEqual(p.client.get(),'codex');self.assertIn('Codex',p.client_label.get())
        self.assertEqual(self.controller.calls,[])

    def test_native_invalid_inputs_disable_controls_and_never_invoke_backend(self):
        p=self.panel;self.root.update()
        controls=(p.observe_button,p.review_refresh_button,p.recheck_button,p.review_selection_button)
        for path,pin in [('',NEW),(' \t',NEW),('/fixture/input.json',''),
                         ('/fixture/input.json','A'*64),('/fixture/input.json','a'*63)]:
            with self.subTest(path=path,pin=pin):
                p.observation_path.set(path);p.observation_sha.set(pin)
                p.selection_path.set(path);p.selection_sha.set(pin);self.root.update()
                for button in controls:
                    self.assertEqual(str(button.cget('state')),'disabled')
                    button.focus_force();self.root.update()
                    button.event_generate('<space>');button.event_generate('<KeyRelease-space>');button.invoke()
                p.observe();p.review_refresh();p.review_selection();self.root.update()
                self.assertFalse(p.request.busy);self.assertEqual(self.controller.calls,[])
        self.observation_input();self.root.update()
        for button in controls[:3]:self.assertEqual(str(button.cget('state')),'normal')
        self.assertEqual(str(p.review_selection_button.cget('state')),'disabled')
        p.observe_button.invoke();self.settle()
        self.assertEqual(self.controller.calls,[('observe','codex','/fixture/model.json','a'*64)])
        self.selection_input();self.root.update()
        self.assertEqual(str(p.review_selection_button.cget('state')),'normal')
        self.assertEqual(len(self.controller.calls),1)

    def test_native_client_buttons_and_requests_stay_disabled_while_busy_or_closed(self):
        p=self.panel;self.observation_input();self.selection_input();release=threading.Event()
        self.addCleanup(release.set)
        def delayed(client):
            self.controller.calls.append(('inspect',client));release.wait(3);return report(client=client)
        self.controller.inspect=delayed;p.inspect_button.invoke();self.root.update()
        self.assertTrue(p.request.busy)
        for closed in (False,True):
            if closed:
                release.set();self.settle();p.request.close();p._enable()
            for button in p.client_buttons.values():
                self.assertEqual(str(button.cget('state')),'disabled')
                button.focus_force();self.root.update()
                for key in ('space','Return','Left','Right','Home','End'):button.event_generate('<'+key+'>')
                button.invoke()
            for button in (p.observe_button,p.review_refresh_button,p.recheck_button,p.review_selection_button):
                self.assertEqual(str(button.cget('state')),'disabled');button.invoke()
            p.select_client('claude-desktop');p.inspect();p.observe();p.review_refresh();p.review_selection()
            self.root.update();self.assertEqual(p.client.get(),'codex')
            self.assertEqual(self.controller.calls,[('inspect','codex')])

    def test_native_only_configured_client_buttons_exist_and_reselection_keeps_review(self):
        self.panel.frame.destroy();self.controller.clients=('claude-desktop',)
        p=self.panel=ui.StableOwnerPanel(self.root,self.controller);self.selection_input()
        self.assertEqual(tuple(p.client_buttons),('claude-desktop',));self.assertEqual(p.client.get(),'claude-desktop')
        p.review_selection_button.invoke();self.settle();p.publish_consent.set(True);p._enable()
        previous=p.report;revision=p.input_revision;expected_calls=list(self.controller.calls)
        button=p.client_buttons['claude-desktop'];button.focus_force();self.root.update()
        for key in ('Left','Right','Home','End','space','Return'):button.event_generate('<'+key+'>')
        p.select_client('codex');self.root.update()
        self.assertEqual(p.client.get(),'claude-desktop');self.assertIs(p.report,previous)
        self.assertEqual(p.input_revision,revision);self.assertTrue(p.publish_consent.get())
        self.assertEqual(self.controller.calls,expected_calls)

    def test_open_inputs_and_row_selection_never_call_backend(self):
        p=self.panel;self.root.update();self.assertEqual(self.controller.calls,[])
        p.observation_path.set('/fixture/observed.json');p.observation_sha.set('a'*64)
        p.selection_path.set('/fixture/selection.json');p.selection_sha.set(NEW)
        self.root.update();self.assertEqual(self.controller.calls,[])
        p.inspect_button.invoke();self.settle()
        p.tree.selection_set(OTHER);self.root.update()
        self.assertEqual(self.controller.calls,[('inspect','codex')])
        self.assertEqual(str(p.refresh_button.cget('state')),'disabled')
        self.assertEqual(str(p.publish_button.cget('state')),'disabled')

    def test_native_arrow_events_seed_first_and_last_without_backend_calls(self):
        p=self.panel;p.inspect_button.invoke();self.settle()
        expected_calls=list(self.controller.calls)
        self.assertEqual(p.tree.selection(),());self.assertEqual(p.tree.focus(),'')
        p.tree.focus_force();p.tree.event_generate('<Down>');self.root.update()
        self.assertEqual(p.tree.selection(),(INSTANCE,));self.assertEqual(p.tree.focus(),INSTANCE)
        p.tree.selection_remove(*p.tree.selection());p.tree.focus('');self.root.update()
        p.tree.event_generate('<Up>');self.root.update()
        self.assertEqual(p.tree.selection(),(OTHER,));self.assertEqual(p.tree.focus(),OTHER)
        self.assertEqual(self.controller.calls,expected_calls)
        self.assertEqual(str(p.refresh_button.cget('state')),'disabled')

    def test_native_report_reorder_preserves_selection_focus_and_requires_consent(self):
        p=self.panel;self.observation_input();p.review_refresh_button.invoke();self.settle()
        p.tree.focus_force();p.tree.event_generate('<Down>');self.root.update()
        self.assertEqual(p.tree.selection(),(INSTANCE,))
        shown=ui.presentation(report('refresh'),'codex');shown['rows'].reverse()
        p._render(shown);self.root.update()
        self.assertEqual(p.tree.selection(),(INSTANCE,));self.assertEqual(p.tree.focus(),INSTANCE)
        self.assertFalse(p.refresh_consent.get())
        self.assertEqual(str(p.refresh_button.cget('state')),'disabled')
        self.assertEqual(self.controller.calls,[('review-refresh','codex','/fixture/model.json','a'*64)])

    def test_native_observed_button_selects_exact_hidden_row_only_on_explicit_click(self):
        p=self.panel;self.root.geometry('700x400');self.root.focus_force();self.root.update()
        self.assertEqual(str(p.select_observed_button.cget('state')),'disabled')
        self.observation_input()
        p.review_refresh_button.invoke();self.settle()
        value=correlated_report()
        value['connections']=[{'client':'codex','instance':f'{i:032x}','endpoint_state':'ABSENT'}
                              for i in range(30)]+value['connections']
        p._render(ui.presentation(value,'codex'));self.root.update()
        expected_calls=list(self.controller.calls)
        self.assertEqual(p.tree.selection(),());self.assertEqual(p.tree.bbox(INSTANCE),'')
        self.assertEqual(str(p.select_observed_button.cget('state')),'normal')
        p.select_observed_button.invoke();self.root.update()
        self.assertEqual(p.tree.selection(),(INSTANCE,));self.assertEqual(p.tree.focus(),INSTANCE)
        self.assertTrue(p.tree.bbox(INSTANCE));self.assertIs(self.root.focus_get(),p.tree)
        self.assertFalse(p.refresh_consent.get())
        self.assertEqual(str(p.refresh_button.cget('state')),'disabled')
        self.assertEqual(self.controller.calls,expected_calls)

    def test_native_observed_button_invalidates_without_choosing_another_row(self):
        p=self.panel;self.observation_input();p.review_refresh_button.invoke();self.settle()
        expected_calls=list(self.controller.calls)
        p.observation_sha.set('9'*64);self.root.update()
        self.assertEqual(str(p.select_observed_button.cget('state')),'disabled')
        p.select_observed();self.assertEqual(p.tree.selection(),())
        p.observation_dirty=False
        for change in ('ended','missing','uncorrelated'):
            value=correlated_report()
            if change=='ended':value['connections'][0]['endpoint_state']='ABSENT'
            if change=='missing':value['connections']=value['connections'][1:]
            if change=='uncorrelated':value['readiness']['correlated']=False
            p._render(ui.presentation(value,'codex'));self.root.update()
            self.assertEqual(str(p.select_observed_button.cget('state')),'disabled')
            p.select_observed();self.assertEqual(p.tree.selection(),())
        p._render(ui.presentation(correlated_report(),'codex'));p.tree.delete(INSTANCE);p._enable()
        self.assertEqual(str(p.select_observed_button.cget('state')),'disabled')
        p.select_observed();self.assertEqual(p.tree.selection(),())
        p.client.set('claude-desktop');self.root.update()
        self.assertEqual(str(p.select_observed_button.cget('state')),'disabled')
        p.select_observed();self.assertEqual(p.tree.selection(),())
        self.assertEqual(self.controller.calls,expected_calls)

    def test_native_observed_button_is_display_only_and_disabled_during_request_or_close(self):
        p=self.panel;self.observation_input();p.review_refresh_button.invoke();self.settle()
        expected_calls=list(self.controller.calls)
        p.request.busy=True;p._enable()
        self.assertEqual(str(p.select_observed_button.cget('state')),'disabled')
        p.select_observed();self.assertEqual(p.tree.selection(),())
        p.request.busy=False;p.request.close();p._enable()
        self.assertEqual(str(p.select_observed_button.cget('state')),'disabled')
        p.select_observed();self.assertEqual(p.tree.selection(),())
        self.assertEqual(self.controller.calls,expected_calls)

    def test_publish_requires_matching_review_checkbox_and_one_attempt(self):
        p=self.panel;p.selection_path.set('/fixture/selection.json');p.selection_sha.set(NEW)
        p.review_selection_button.invoke();self.settle()
        p.publish_button.invoke();self.assertEqual(len(self.controller.calls),1)
        p.publish_consent.set(True);p._enable();p.publish_button.invoke();self.settle()
        self.assertEqual(self.controller.calls[-1],('publish','codex',TOKEN,True))
        self.assertIn('SELECTED_NOT_LIVE_APPLIED',p.status.get())
        p.review_selection_button.invoke();self.settle();p.publish_consent.set(True);p._enable()
        p.publish_button.invoke();self.settle()
        self.assertEqual(sum(c[0]=='publish' for c in self.controller.calls),1)

    def test_exact_selected_row_consent_refresh_ACK_then_explicit_readiness(self):
        p=self.panel;p.observation_path.set('/fixture/model.json');p.observation_sha.set('a'*64)
        p.review_refresh_button.invoke();self.settle()
        p.tree.selection_set(OTHER);self.root.update();p.refresh_consent.set(True);p._enable()
        self.assertEqual(str(p.refresh_button.cget('state')),'disabled')
        p.tree.selection_set(INSTANCE);self.root.update()
        self.assertFalse(p.refresh_consent.get())
        p.refresh_consent.set(True);p._enable();p.refresh_button.invoke();self.settle()
        self.assertEqual(self.controller.calls[-1],('refresh','codex',TOKEN,True))
        self.assertIn('대조 미충족',p.readiness.get())
        p.recheck_button.invoke();self.settle()
        self.assertIn('대조 충족',p.readiness.get());self.assertIn('실행 HOLD',p.readiness.get())
        p.review_refresh_button.invoke();self.settle();p.tree.selection_set(INSTANCE);self.root.update()
        p.refresh_consent.set(True);p._enable();p.refresh_button.invoke();self.settle()
        self.assertEqual(sum(c[0]=='refresh' for c in self.controller.calls),1)

    def test_input_edit_invalidates_review_and_plain_inspect_does_not_adopt_model(self):
        p=self.panel;self.observation_input();p.review_refresh_button.invoke();self.settle()
        p.tree.selection_set(INSTANCE);self.root.update();p.refresh_consent.set(True);p._enable()
        p.observation_sha.set('b'*64);self.root.update()
        self.assertFalse(p.refresh_consent.get());self.assertIsNone(p.report['review'])
        p.inspect_button.invoke();self.settle()
        self.assertIn('관측 입력 미대조',p.readiness.get())
        self.assertEqual(str(p.refresh_button.cget('state')),'disabled')

    def test_client_change_clears_selection_and_blocks_old_review(self):
        p=self.panel;self.selection_input();p.review_selection_button.invoke();self.settle()
        p.publish_consent.set(True);p._enable();expected_calls=list(self.controller.calls)
        p.client_buttons['codex'].focus_force();self.root.update()
        p.client_buttons['codex'].event_generate('<Tab>');self.root.update()
        self.assertIs(self.root.focus_get(),p.client_buttons['claude-desktop'])
        p.client_buttons['claude-desktop'].event_generate('<space>');self.root.update()
        self.assertIsNone(p.report);self.assertFalse(p.publish_consent.get())
        self.assertTrue(p.observation_dirty);self.assertIsNone(p.selected_instance)
        self.assertFalse(p.refresh_consent.get());self.assertIn('대조 미충족',p.readiness.get())
        self.assertEqual(p.tree.get_children(),())
        self.assertEqual(self.controller.calls,expected_calls)
        p.publish_button.invoke();self.assertFalse(any(c[0]=='publish' for c in self.controller.calls))
        p.inspect_button.invoke();self.settle()
        self.assertEqual(self.controller.calls[-1],('inspect','claude-desktop'))

    def test_close_does_not_cancel_in_flight_or_start_refresh(self):
        p=self.panel;release=threading.Event();completed=[]
        def delayed(client):release.wait(2);completed.append(client);return report(client=client)
        self.controller.inspect=delayed;p.inspect_button.invoke();self.root.update()
        p.frame.destroy();self.root.update();release.set();p.request.thread.join(2)
        self.assertEqual(completed,['codex']);self.assertTrue(p.request.closed)
        self.assertEqual(self.controller.calls,[])

    def test_long_metadata_has_scrollable_details_and_viewport(self):
        p=self.panel;p.inspect_button.invoke();self.settle()
        self.root.geometry('700x500');self.root.update()
        self.assertTrue(p.canvas.cget('yscrollcommand'))
        self.assertTrue(p.details.cget('yscrollcommand'));self.assertTrue(p.details.cget('xscrollcommand'))
        self.assertEqual(p.details.cget('wrap'),'none')

    def test_native_tab_focus_tracks_inputs_and_lower_controls(self):
        p=self.panel;self.observation_input();self.root.geometry('700x400');self.root.update()
        p.input_widgets[1].focus_force();self.root.update()
        p.input_widgets[1].event_generate('<Tab>');self.root.update()
        self.assertIs(self.root.focus_get(),p.input_widgets[2])
        p.review_refresh_button.focus_force();self.root.update()
        top=p.review_refresh_button.winfo_rooty()-p.canvas.winfo_rooty()
        self.assertGreaterEqual(top,0)
        self.assertLessEqual(top+p.review_refresh_button.winfo_height(),p.canvas.winfo_height())
        self.assertEqual(self.controller.calls,[])
        self.assertEqual(str(p.refresh_button.cget('state')),'disabled')

    def test_native_page_and_wheel_scroll_outer_panel_without_stealing_tree(self):
        p=self.panel;self.observation_input();self.root.geometry('700x400');self.root.update()
        p.observe_button.focus_force();self.root.update();p.canvas.yview_moveto(0)
        p.observe_button.event_generate('<Next>');self.root.update()
        self.assertGreater(p.canvas.yview()[0],0)
        p.canvas.yview_moveto(0);p.observe_button.event_generate('<MouseWheel>',delta=-120)
        self.root.update();self.assertGreater(p.canvas.yview()[0],0)
        p.tree.focus_force();self.root.update();position=p.canvas.yview()
        p.tree.event_generate('<MouseWheel>',delta=-120);p.tree.event_generate('<Next>')
        self.root.update();self.assertEqual(p.canvas.yview(),position)
        self.assertEqual(self.controller.calls,[])


if __name__=='__main__':unittest.main()
