"""Connection UI fixtures never contact a client, Work or installed Owner app."""
import ast
import copy
import os
from pathlib import Path
import threading
import time
import unittest

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
    }


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
