"""Isolated view fixtures: no installed app, client, policy, or Work is used."""
import ast
import copy
import os
from pathlib import Path
import threading
import time
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


class Presentation(unittest.TestCase):
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
        self.calls.append(('review-refresh',client,path,pin));return report('refresh',client)
    def refresh(self,client,token,approve=False):
        self.calls.append(('refresh',client,token,approve));self.refreshed=True
        value=report('refresh',client);value['state']='ACKNOWLEDGED';value['review']=None
        return value


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
        p=self.panel;p.review_refresh_button.invoke();self.settle()
        p.tree.selection_set(INSTANCE);self.root.update();p.refresh_consent.set(True);p._enable()
        p.observation_sha.set('b'*64);self.root.update()
        self.assertFalse(p.refresh_consent.get());self.assertIsNone(p.report['review'])
        p.inspect_button.invoke();self.settle()
        self.assertIn('관측 입력 미대조',p.readiness.get())
        self.assertEqual(str(p.refresh_button.cget('state')),'disabled')

    def test_client_change_clears_selection_and_blocks_old_review(self):
        p=self.panel;p.review_selection_button.invoke();self.settle()
        p.publish_consent.set(True);p.client.set('claude-desktop');self.root.update()
        self.assertIsNone(p.report);self.assertFalse(p.publish_consent.get())
        self.assertEqual(p.tree.get_children(),())
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


if __name__=='__main__':unittest.main()
