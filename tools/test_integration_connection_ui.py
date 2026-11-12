"""Connection UI fixtures never contact a client, Work or installed Owner app."""
import ast
import copy
import os
from pathlib import Path
import threading
import time
import types
import unittest
from unittest.mock import Mock

import integration_connection_ui as ui


def report(mode='MANUAL_RESTART_REQUIRED'):
    return {
        'state': 'STALE_ACTIVE_CONNECTION',
        'summary': '디스크 선택과 실제 연결이 다릅니다.',
        'selected': {'adapter_state': '/fixture/new-state', 'launcher_sha256': 'a'*64,
                     'policy_sha256': 'b'*64, 'package_version': '0.2.9',
                     'runtime_sha256': 'c'*64},
        'connections': [{'instance': 'fixture-instance', 'host_kind': 'ChatGPT',
                         'host_pid': 40, 'pid': 50, 'state': 'POLICY_MISMATCH',
                         'policy_sha256': 'd'*64, 'launcher_sha256': 'e'*64,
                         'tools_count': 28, 'tools': ['golem_projects_list']}],
        'reload': {'mode': mode, 'reason': '공식 Desktop 제어 경로 없음',
                   'steps': ['다른 작업을 저장하세요.', 'ChatGPT 메뉴에서 정상 종료하세요.',
                             '앱을 다시 열고 상태를 확인하세요.']},
        'model_tool_delivery': 'NOT_OBSERVED',
        'observed_at': '2026-11-11T00:00:00+00:00',
        'refresh_token': 'f'*64,
        'target_bound': mode == 'GOLEM_RELAY_AVAILABLE',
    }


def host_catalog(**updates):
    result = {'schema':'golem.host-tool-catalog-observation.v1',
        'child_generation':2,'catalog_generation':3,'state':'HOST_CATALOG_NOT_RELISTED',
        'requests':0,'responses':0,'errors':0,'list_changed_notifications_sent':1,
        'last_complete_generation':1,'last_complete_sha256':'a'*64,'last_complete_pages':1,
        'current_complete_sha256':None,'current_complete_pages':None,'model_delivery_verified':False}
    result.update(updates)
    return result


class Presentation(unittest.TestCase):
    def test_selected_and_live_policy_separate_without_authority_inference(self):
        source = report()
        before = copy.deepcopy(source)
        shown = ui.presentation(source)
        self.assertIn('b'*64, shown['selected'])
        self.assertIn('d'*64, shown['details'])
        self.assertIn('미확인', shown['model_delivery'])
        self.assertEqual(shown['rows'][0][1][4], '28')
        self.assertEqual(source, before)

    def test_missing_and_malformed_metadata_does_not_become_zero_or_success(self):
        shown = ui.presentation({'connections': [None, {'tools_count': True},
                                                   {'tools_count': -1}, {'tools_count': 0}]})
        self.assertEqual([x[1][4] for x in shown['rows']], ['미확인', '미확인', '미확인', '0'])
        self.assertIn('미확인', shown['renewal_label'])
        self.assertIn('미확인', shown['selected'])
        with self.assertRaisesRegex(ValueError, 'CONNECTION_REPORT_REQUIRED'):
            ui.presentation(None)

    def test_reload_ack_and_independent_probe_cannot_become_verified(self):
        value = report('REFRESH_QUEUED')
        value['state'] = 'ACK_RECEIVED'
        value['connections'][0]['tools_count'] = 31
        value['connections'][0]['host_kind'] = 'INDEPENDENT_STDIO'
        shown = ui.presentation(value)
        self.assertIn('반영은 아직 미확인', shown['renewal_label'])
        self.assertNotIn('대조 완료', shown['renewal_label'])
        self.assertIn('미확인', shown['model_delivery'])

    def test_verified_connection_still_does_not_imply_model_or_Work_validation(self):
        shown = ui.presentation(report('VERIFIED'))
        self.assertIn('모델 전달 검증은 별도', shown['renewal_label'])
        self.assertIn('미확인', shown['model_delivery'])

    def test_ready_server_and_host_catalog_requery_are_distinct(self):
        value=report('VERIFIED')
        value['connections'][0].update(state='READY',host_catalog=host_catalog())
        shown=ui.presentation(value)
        self.assertEqual(shown['rows'][0][1][3],'READY')
        self.assertEqual(shown['rows'][0][1][6],'변경 후 목록 재조회 없음')
        self.assertIn('현 목록 세대 요청 / 전송 응답 / 오류: 0 / 0 / 0',shown['details'])
        self.assertIn('현 세대 전체 페이지 SHA-256 / 페이지 수: 미확인 / 미확인',shown['details'])
        self.assertIn('과거일 수 있음',shown['details'])
        self.assertIn('호스트 PID나 준비안 보유만으로 현재 대화의 transport를 확정하지 않습니다',shown['details'])
        self.assertIn('미확인',shown['model_delivery'])

    def test_complete_response_never_becomes_model_or_current_chat_success(self):
        value=report('VERIFIED')
        value['connections'][0]['host_catalog']=host_catalog(state='HOST_CATALOG_RESPONSE_SENT',
            requests=1,responses=1,last_complete_generation=3,last_complete_sha256='b'*64,
            current_complete_sha256='b'*64,current_complete_pages=1)
        shown=ui.presentation(value)
        self.assertEqual(shown['rows'][0][1][6],'목록 응답 전송 · 모델 미확인')
        self.assertIn('호스트 cache 반영·모델 도구 전달·실행 권한을 증명하지 않습니다',shown['details'])
        self.assertIn('미확인',shown['model_delivery'])

    def test_missing_catalog_is_unobserved_without_invented_zero_counts(self):
        shown=ui.presentation(report())
        self.assertEqual(shown['rows'][0][1][6],'미관찰')
        self.assertIn('NOT_OBSERVED',shown['details'])
        self.assertNotIn('현 목록 세대 요청 / 전송 응답 / 오류:',shown['details'])

    def test_malformed_catalog_cannot_display_counters_or_false_success(self):
        for observation in ({},{'state':'HOST_CATALOG_RESPONSE_SENT'},
                            host_catalog(model_delivery_verified=True),host_catalog(requests=True)):
            with self.subTest(observation=observation):
                value=report()
                value['connections'][0]['host_catalog']=observation
                shown=ui.presentation(value)
                self.assertEqual(shown['rows'][0][1][6],'관측 형식 미확인')
                self.assertIn('INVALID_METADATA',shown['details'])
                self.assertNotIn('현 목록 세대 요청 / 전송 응답 / 오류:',shown['details'])
                self.assertIn('미확인',shown['model_delivery'])

    def test_partial_observation_is_not_a_restart_or_success_recommendation(self):
        value=report('OBSERVATION_INCOMPLETE')
        value['connections'][0]['reason']='BOUNDED_OBSERVATION_LIMIT'
        shown=ui.presentation(value)
        self.assertIn('일부 연결 미관찰',shown['renewal_label'])
        self.assertNotIn('재시작 필요 ·',shown['renewal_label'])
        self.assertIn('BOUNDED_OBSERVATION_LIMIT',shown['details'])

    def test_refresh_token_is_exact_or_unavailable_never_synthesized(self):
        value = report('OFFICIAL_RELOAD_AVAILABLE')
        self.assertEqual(ui.presentation(value)['refresh_token'], 'f'*64)
        for invalid in (None, '', 'g'*64, 'f'*63, ['f'*64]):
            value['refresh_token'] = invalid
            self.assertIsNone(ui.presentation(value)['refresh_token'])

    def test_only_explicit_exact_relay_identity_is_selectable(self):
        value=report('GOLEM_RELAY_AVAILABLE')
        value['connections']=[{'instance':'a'*32,'refreshable':True},
                              {'instance':'b'*32,'refreshable':False},
                              {'instance':'c'*32,'refreshable':1},
                              {'instance':'not-a-relay','refreshable':True}]
        self.assertEqual(ui.presentation(value)['relay_targets'], {'0':'a'*32})
        value['target_bound'] = False
        self.assertEqual(ui.presentation(value)['relay_targets'], {})

    def test_readiness_is_separate_from_approval_and_requires_exact_flags(self):
        value = report('VERIFIED')
        value['readiness'] = {'state': 'READY_FOR_PREPARATION', 'preparation_allowed': True,
                              'reason': 'EXTERNAL_OBSERVATION_MATCHED'}
        shown = ui.presentation(value)
        self.assertFalse(shown['readiness']['preparation_allowed'])
        self.assertIn('준비 보류', shown['readiness']['label'])
        value['target_bound'] = True
        shown = ui.presentation(value)
        self.assertTrue(shown['readiness']['preparation_allowed'])
        self.assertIn('외부 관측', shown['readiness']['label'])
        self.assertNotIn('승인 완료', shown['readiness']['label'])
        value['readiness']['preparation_allowed'] = 1
        self.assertFalse(ui.presentation(value)['readiness']['preparation_allowed'])

    def test_missing_target_has_explicit_no_refresh_guidance(self):
        value = report('TARGET_NOT_IDENTIFIED')
        value['connections'][0].update(instance='a'*32, refreshable=True)
        shown = ui.presentation(value)
        self.assertIn('연결 미식별', shown['renewal_label'])
        self.assertEqual(shown['relay_targets'], {})
        self.assertFalse(shown['readiness']['preparation_allowed'])

    def test_metadata_is_literal_bounded_and_never_interpreted_as_command(self):
        value = report()
        value['connections'][0]['instance'] = '<script>$(do-not-run)\x00</script>'
        value['reload']['reason'] = 'x'*9000
        value['connections'] *= 200
        shown = ui.presentation(value)
        self.assertEqual(len(shown['rows']), 128)
        self.assertIn('<script>$(do-not-run)\ufffd</script>', shown['details'])
        self.assertEqual(len(shown['reason']), ui.MAX_TEXT)

    def test_no_top_level_Tk_or_host_execution(self):
        tree = ast.parse(Path(ui.__file__).read_text())
        imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertFalse(any('tkinter' in ast.unparse(node) for node in imports))
        calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        self.assertFalse(calls & {'subprocess.run', 'subprocess.Popen', 'os.system',
                                  'os.kill', 'exec', 'eval', 'webbrowser.open'})


class Worker(unittest.TestCase):
    def finish(self, worker):
        worker.thread.join(timeout=2)
        self.assertFalse(worker.thread.is_alive())
        return worker.take()

    def test_one_explicit_request_runs_off_event_thread_and_busy_blocks_duplicates(self):
        worker = ui.BackgroundRequest()
        started, release = threading.Event(), threading.Event()
        called = []
        def operation():
            called.append(threading.get_ident())
            started.set()
            release.wait(timeout=2)
            return report()
        try:
            self.assertTrue(worker.start('inspect', operation))
            self.assertTrue(started.wait(timeout=1))
            self.assertFalse(worker.start('refresh', operation))
        finally:
            release.set()
        kind, result, error = self.finish(worker)
        self.assertEqual(kind, 'inspect')
        self.assertIsNone(error)
        self.assertEqual(result['state'], 'STALE_ACTIVE_CONNECTION')
        self.assertEqual(len(called), 1)
        self.assertNotEqual(called[0], threading.get_ident())
        self.assertFalse(worker.busy)

    def test_failure_never_retries_or_leaks_arbitrary_exception_message(self):
        worker = ui.BackgroundRequest()
        calls = []
        def fail():
            calls.append(True)
            raise RuntimeError('sensitive unrelated host content')
        worker.start('refresh', fail)
        _, result, error = self.finish(worker)
        self.assertIsNone(result)
        self.assertEqual(error, 'CONNECTION_OBSERVATION_FAILED')
        self.assertEqual(len(calls), 1)
        self.assertIsNone(worker.take())

    def test_closing_view_discards_late_result_and_never_starts_replacement(self):
        worker = ui.BackgroundRequest()
        release = threading.Event()
        calls = []
        def operation():
            calls.append(True)
            release.wait(timeout=2)
            return report()
        worker.start('inspect', operation)
        worker.close()
        self.assertFalse(worker.start('refresh', operation))
        release.set()
        self.assertIsNone(self.finish(worker))
        self.assertEqual(calls, [True])


class ObservationInput(unittest.TestCase):
    marker = 'golem-connection-v1:' + 'a'*32 + ':1:2:' + 'b'*32

    def test_literal_inventory_and_required_tools_remain_separate(self):
        values = ui.observation_inputs(' chat ', ' turn ', self.marker,
            'golem_projects_list,\ngolem_work_inspect', 'golem_document_submit')
        self.assertEqual(values, ('chat', 'turn', self.marker,
            ['golem_projects_list', 'golem_work_inspect'], ['golem_document_submit']))
        self.assertEqual(ui.observation_inputs('c', 't', self.marker, 'golem_projects_list')[-1], [])
        # Do not infer or silently normalize names, deduplicate, or fabricate a
        # required tool. The controller performs semantic validation.
        self.assertEqual(ui.observation_inputs('c', 't', self.marker, 'x,x')[-2], ['x', 'x'])

    def test_empty_and_oversized_inputs_are_blocked_before_controller(self):
        valid = ['c', 't', self.marker, 'golem_projects_list', '']
        for index, bad in ((0, ''), (1, ' '*3), (2, None), (3, ''),
                           (0, 'c'*257), (2, 'm'*513), (3, 'x'*65537),
                           (3, ','.join(['x']*257)), (4, 'y'*65537)):
            with self.subTest(index=index, bad_type=type(bad).__name__):
                values = valid[:]
                values[index] = bad
                with self.assertRaises(ui.ConnectionError):
                    ui.observation_inputs(*values)

    def panel_stub(self):
        panel = ui.ConnectionPanel.__new__(ui.ConnectionPanel)
        panel.request = types.SimpleNamespace(busy=False)
        panel.controller = Mock()
        panel.controller.inspect.return_value = report('TARGET_NOT_IDENTIFIED')
        panel.thread_id = Mock(get=Mock(return_value='chat'))
        panel.turn_id = Mock(get=Mock(return_value='turn'))
        panel.marker = Mock(get=Mock(return_value=self.marker))
        panel.observed_tools = Mock(get=Mock(return_value='golem_projects_list'))
        panel.required_tools = Mock(get=Mock(return_value='golem_document_submit'))
        panel._submit = Mock()
        return panel

    def test_explicit_observation_runs_only_set_and_inspect_when_dispatched(self):
        panel = self.panel_stub()
        panel.observe_target()
        panel.controller.set_target_observation.assert_not_called()
        panel.controller.inspect.assert_not_called()
        kind, operation = panel._submit.call_args.args
        self.assertEqual(kind, 'target-observation')
        operation()
        panel.controller.set_target_observation.assert_called_once_with(
            'chat', 'turn', self.marker, ['golem_projects_list'], ['golem_document_submit'])
        panel.controller.inspect.assert_called_once_with()
        panel.controller.request_refresh.assert_not_called()

    def test_busy_or_invalid_observation_never_refreshes_or_uses_old_input(self):
        panel = self.panel_stub()
        panel.request.busy = True
        panel.observe_target()
        panel._submit.assert_not_called()
        panel.request.busy = False
        panel.marker.get.return_value = ''
        panel.observe_target()
        operation = panel._submit.call_args.args[1]
        with self.assertRaises(ui.ConnectionError):
            operation()
        panel.controller.set_target_observation.assert_not_called()
        panel.controller.inspect.assert_not_called()
        panel.controller.request_refresh.assert_not_called()

    def test_edit_invalidates_report_and_only_clears_memory_when_idle(self):
        panel = self.panel_stub()
        panel.target_revision = 0
        panel.target_dirty = False
        panel.report = report('GOLEM_RELAY_AVAILABLE')
        panel.reload_consent = Mock()
        panel.readiness = Mock()
        panel.model_status = Mock()
        panel._enable = Mock()
        panel._target_changed()
        self.assertIsNone(panel.report)
        self.assertTrue(panel.target_dirty)
        self.assertEqual(panel.target_revision, 1)
        panel.reload_consent.set.assert_called_with(False)
        panel.controller.clear_target_observation.assert_called_once_with()
        panel.controller.inspect.assert_not_called()
        panel.controller.request_refresh.assert_not_called()
        panel.request.busy = True
        panel._target_changed()
        self.assertEqual(panel.controller.clear_target_observation.call_count, 1)


class NativePanel(unittest.TestCase):
    def setUp(self):
        if os.environ.get('GOLEM_TEST_TK') != '1':
            self.skipTest('native display fixture requires GOLEM_TEST_TK=1')
        import tkinter as tk
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)

    def settle(self, panel):
        until = time.monotonic()+3
        while panel.request.busy and time.monotonic() < until:
            self.root.update()
            time.sleep(.01)
        self.root.update()
        self.assertFalse(panel.request.busy)

    def test_target_inputs_require_explicit_comparison_and_edit_discards_readiness(self):
        class Controller:
            def __init__(self): self.calls=[];self.bound=False
            def clear_target_observation(self): self.bound=False
            def set_target_observation(self, *arguments):
                self.calls.append(('observe', arguments));self.bound=True
            def inspect(self):
                self.calls.append(('inspect',))
                value=report('VERIFIED' if self.bound else 'TARGET_NOT_IDENTIFIED')
                value['target_bound']=self.bound
                value['readiness']={'state':'READY_FOR_PREPARATION' if self.bound else 'TARGET_NOT_IDENTIFIED',
                    'preparation_allowed':self.bound,'reason':'EXTERNAL_OBSERVATION_MATCHED'}
                return value
            def request_refresh(self, **kwargs): raise AssertionError('comparison does not refresh')
        controller=Controller()
        panel=ui.ConnectionPanel(self.root,controller)
        panel.thread_id.set('chat');panel.turn_id.set('turn')
        panel.marker.set(ObservationInput.marker)
        panel.observed_tools.insert('1.0','golem_projects_list\ngolem_document_submit')
        panel.required_tools.insert('1.0','golem_document_submit')
        self.root.update()
        self.assertEqual(controller.calls, [])
        self.assertEqual(str(panel.refresh_button.cget('state')), 'disabled')
        panel.observation_button.invoke();self.settle(panel)
        self.assertEqual(controller.calls, [('observe', ('chat','turn',ObservationInput.marker,
            ['golem_projects_list','golem_document_submit'],['golem_document_submit'])), ('inspect',)])
        self.assertIn('외부', panel.readiness.get())
        self.assertIn('진행 가능',panel.readiness.get())
        panel.turn_id.set('next-turn');self.root.update()
        self.assertIsNone(panel.report)
        self.assertFalse(controller.bound)
        self.assertIn('준비 보류',panel.readiness.get())
        # Even a faulty/old controller response cannot restore edited evidence
        # through the ordinary status button.
        controller.bound=True
        panel.inspect_button.invoke();self.settle(panel)
        self.assertFalse(panel.report['target_bound'])
        self.assertFalse(panel.report['readiness']['preparation_allowed'])
        self.assertIn('준비 보류',panel.readiness.get())

    def test_unidentified_target_blocks_refresh_even_with_forged_row_flag(self):
        class Controller:
            def inspect(self):
                value=report('TARGET_NOT_IDENTIFIED')
                value['connections'][0].update(instance='a'*32,refreshable=True)
                return value
            def request_refresh(self, **kwargs): raise AssertionError('unbound target must not refresh')
        panel=ui.ConnectionPanel(self.root,Controller())
        panel.inspect_button.invoke();self.settle(panel)
        panel.tree.selection_set('0');self.root.update()
        panel.reload_consent.set(True);panel._enable()
        self.assertEqual(str(panel.refresh_button.cget('state')), 'disabled')
        self.assertEqual(str(panel.observation_button.cget('state')), 'normal')
        self.assertIn('연결 미식별',panel.guidance.get())

    def test_partial_observation_only_allows_explicit_inspection(self):
        class Controller:
            def __init__(self): self.calls=[]
            def inspect(self): self.calls.append('inspect');return report('OBSERVATION_INCOMPLETE')
            def request_refresh(self, **kwargs): raise AssertionError('no refresh for missing observations')
        controller=Controller()
        panel=ui.ConnectionPanel(self.root,controller)
        panel.inspect_button.invoke();self.settle(panel)
        self.assertIn('일부 연결 미관찰',panel.guidance.get())
        for button in (panel.refresh_button,panel.ack_button,panel.recheck_button,panel.reload_consent_button):
            self.assertEqual(str(button.cget('state')),'disabled')
            button.invoke()
        self.assertEqual(controller.calls,['inspect'])
        panel.inspect_button.invoke();self.settle(panel)
        self.assertEqual(controller.calls,['inspect','inspect'])

    def test_manual_guide_has_no_automatic_inspection_or_restart(self):
        class Controller:
            def __init__(self): self.calls = []
            def inspect(self): self.calls.append('inspect'); return report()
            def request_refresh(self): self.calls.append('refresh'); return report()
        controller = Controller()
        panel = ui.ConnectionPanel(self.root, controller)
        self.root.update()
        self.assertEqual(controller.calls, [])
        panel.refresh_button.invoke()
        self.assertEqual(controller.calls, [])
        panel.inspect_button.invoke(); self.settle(panel)
        self.assertEqual(panel.refresh_button.cget('text'), '정상 재시작 안내')
        self.assertIn('b'*64, panel.selected.get())
        self.assertIn('d'*64, panel.details.get('1.0', 'end'))
        panel.refresh_button.invoke(); self.settle(panel)
        self.assertEqual(controller.calls, ['inspect', 'inspect'])
        panel.recheck_button.invoke()
        self.assertEqual(controller.calls, ['inspect', 'inspect'])
        panel.ack.set(True); panel.acknowledge()
        self.assertIn('ChatGPT 메뉴', panel.guidance.get())
        panel.recheck_button.invoke(); self.settle(panel)
        self.assertEqual(controller.calls, ['inspect', 'inspect', 'inspect'])
        self.assertIn('미확인', panel.model_status.get())

    def test_official_refresh_requires_explicit_consent_and_one_attempt(self):
        class Controller:
            def __init__(self): self.calls = []
            def inspect(self): self.calls.append('inspect'); return report('OFFICIAL_RELOAD_AVAILABLE')
            def request_refresh(self, *, expected_token, connection_instance):
                self.calls.append('refresh')
                self.token = expected_token
                self.instance = connection_instance
                return report('REFRESH_QUEUED')
        controller = Controller()
        panel = ui.ConnectionPanel(self.root, controller)
        panel.inspect_button.invoke(); self.settle(panel)
        self.assertEqual(panel.refresh_button.cget('text'), '호스트 MCP 갱신 요청')
        self.assertIn('전체 MCP', panel.reload_consent_button.cget('text'))
        panel.refresh_button.invoke()
        self.assertEqual(controller.calls, ['inspect'])
        panel.reload_consent.set(True); panel._enable()
        panel.refresh_button.invoke(); self.settle(panel)
        self.assertEqual(controller.calls, ['inspect', 'refresh'])
        self.assertEqual(controller.token, 'f'*64)
        self.assertIsNone(controller.instance)
        self.assertIn('반영은 아직 미확인', panel.guidance.get())
        panel.recheck_button.invoke(); self.settle(panel)
        # Even a repeated AVAILABLE observation cannot redispatch that attempt.
        panel.reload_consent.set(True); panel._enable()
        panel.refresh_button.invoke()
        self.assertEqual(controller.calls, ['inspect', 'refresh', 'inspect'])

    def test_relay_consent_is_connection_scoped_and_no_auto_refresh(self):
        class Controller:
            def __init__(self): self.calls = []
            def inspect(self):
                self.calls.append('inspect')
                value=report('GOLEM_RELAY_AVAILABLE')
                value['connections'][0].update(instance='a'*32,refreshable=True)
                return value
            def request_refresh(self, *, expected_token, connection_instance):
                self.calls.append('refresh')
                self.token = expected_token
                self.instance = connection_instance
                return report('VERIFY_REQUIRED')
        controller = Controller()
        panel = ui.ConnectionPanel(self.root, controller)
        panel.inspect_button.invoke(); self.settle(panel)
        self.assertEqual(panel.refresh_button.cget('text'), 'Golem 연결 갱신')
        self.assertIn('Golem 연결', panel.reload_consent_button.cget('text'))
        self.assertNotIn('전체 MCP', panel.reload_consent_button.cget('text'))
        panel.reload_consent.set(True);panel._enable()
        panel.refresh_button.invoke()
        self.assertEqual(controller.calls, ['inspect'])
        panel.tree.selection_set('0');self.root.update()
        panel.refresh_button.invoke()
        self.assertEqual(controller.calls, ['inspect'])
        self.assertFalse(panel.reload_consent.get())
        panel.reload_consent.set(True);panel._enable()
        panel.refresh_button.invoke()
        self.settle(panel)
        self.assertEqual(controller.calls, ['inspect', 'refresh'])
        self.assertEqual(controller.token, 'f'*64)
        self.assertEqual(controller.instance, 'a'*32)
        self.assertIn('완료로 판정하지 않음', panel.guidance.get())
        self.assertIn('미확인', panel.model_status.get())

    def test_manual_guide_capability_change_never_dispatches_without_consent(self):
        class Controller:
            def __init__(self): self.calls = []
            def inspect(self):
                self.calls.append('inspect')
                return report('MANUAL_RESTART_REQUIRED' if len(self.calls)==1 else 'OFFICIAL_RELOAD_AVAILABLE')
            def request_refresh(self, **kwargs): raise AssertionError('manual action must not dispatch')
        controller = Controller()
        panel = ui.ConnectionPanel(self.root, controller)
        panel.inspect_button.invoke(); self.settle(panel)
        panel.refresh_button.invoke(); self.settle(panel)
        self.assertEqual(controller.calls, ['inspect', 'inspect'])
        self.assertFalse(panel.reload_attempted)
        self.assertEqual(str(panel.refresh_button.cget('state')), 'disabled')

    def test_other_relay_requires_new_observation_and_never_retries_first_target(self):
        class Controller:
            def __init__(self): self.calls=[];self.token='a'*64
            def inspect(self):
                value=report('GOLEM_RELAY_AVAILABLE')
                value['refresh_token']=self.token
                value['connections']=[{'instance':i*32,'refreshable':True} for i in ('a','b')]
                return value
            def request_refresh(self, *, expected_token, connection_instance):
                self.calls.append((expected_token,connection_instance))
                self.token='b'*64
                return report('VERIFY_REQUIRED')
        controller=Controller()
        panel=ui.ConnectionPanel(self.root,controller)
        panel.inspect_button.invoke();self.settle(panel)
        def choose(index):
            panel.tree.selection_set(index);self.root.update()
            panel.reload_consent.set(True);panel._enable()
        choose('0');panel.refresh_button.invoke();self.settle(panel)
        self.assertEqual(controller.calls,[('a'*64,'a'*32)])
        panel.inspect_button.invoke();self.settle(panel)
        choose('0');panel.refresh_button.invoke()
        self.assertEqual(controller.calls,[('a'*64,'a'*32)])
        choose('1');panel.refresh_button.invoke();self.settle(panel)
        self.assertEqual(controller.calls,[('a'*64,'a'*32),('b'*64,'b'*32)])


if __name__ == '__main__':
    unittest.main()
