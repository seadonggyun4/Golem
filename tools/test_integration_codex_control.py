"""Disposable control-protocol fixtures; never attach to a real Desktop host."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

import integration_codex_control as control


IDENTITY = {'path': '/fixture/control.sock', 'device': 1, 'inode': 2,
            'uid': os.getuid(), 'mode': 0o600, 'host_pid': 123,
            'host_start': 'fixture-start', 'host_kind': 'ChatGPT',
            'cli_path': '/fixture/codex', 'cli_sha256': 'a' * 64}


class FakeProxy:
    created = []
    fail = None
    before_reload = False
    loaded = ['chosen-thread']
    reply = {'data': [{'name': 'golem-local', 'tools': {'golem_projects_list': {}},
                       'runtimeStatus': 'connected', 'toolsError': None}]}

    def __init__(self, *args):
        self.calls = []
        self.closed = False
        self.reload_dispatched = False
        self.created.append(self)

    def initialize(self):
        self.calls.append(('initialize', None))
        if self.before_reload: raise control.ControlError('CONTROL_EOF')

    def call(self, method, params=None):
        self.calls.append((method, params))
        if method == 'config/mcpServer/reload':
            self.reload_dispatched = True
            if self.fail: raise control.ControlError(self.fail)
            return {}
        if method == 'thread/loaded/list': return {'data': self.loaded}
        if method == 'mcpServerStatus/list': return self.reply
        raise AssertionError(method)

    def close(self): self.closed = True


class DesktopControl(unittest.TestCase):
    def setUp(self):
        FakeProxy.created = []
        FakeProxy.fail = None
        FakeProxy.before_reload = False
        FakeProxy.loaded = ['chosen-thread']
        FakeProxy.reply = {'data': [{'name': 'golem-local', 'tools': {'golem_projects_list': {}},
                                     'runtimeStatus': 'connected', 'toolsError': None}]}
        self.api = control.CodexControl('/fixture/codex', '/fixture/control.sock')
        self.addCleanup(patch.stopall)
        self.identity = patch.object(self.api, '_identity', return_value=dict(IDENTITY)).start()
        patch.object(control, '_Proxy', FakeProxy).start()

    def test_no_socket_is_manual_without_starting_any_child(self):
        api = control.CodexControl()
        result = api.inspect()
        self.assertEqual(result['state'], 'MANUAL')
        self.assertFalse(result['verified_desktop'])
        self.assertFalse(result['reload_supported'])
        self.assertEqual(result['tools'], [])
        self.assertEqual(FakeProxy.created, [])

    def test_no_thread_never_triggers_transient_server_discovery(self):
        value = self.api.inspect()
        self.assertTrue(value['verified_desktop'])
        self.assertEqual(value['model_tools'], 'NOT_OBSERVED')
        self.assertEqual(value['active_turn'], 'NOT_OBSERVED')
        self.assertEqual(FakeProxy.created, [])

    def test_explicit_loaded_thread_limits_status_to_one_server(self):
        value = self.api.inspect(thread_id='chosen-thread')
        self.assertEqual(value['state'], 'OBSERVED')
        self.assertEqual(value['tools'], ['golem_projects_list'])
        self.assertEqual(value['server_status'], 'connected')
        self.assertEqual(value['model_tools'], 'NOT_OBSERVED')
        self.assertEqual(value['work_calls'], 0)
        proxy, = FakeProxy.created
        self.assertEqual([m for m, _ in proxy.calls], ['initialize', 'thread/loaded/list', 'mcpServerStatus/list'])
        self.assertEqual(proxy.calls[-1][1], {'threadId': 'chosen-thread', 'serverName': 'golem-local',
                                              'detail': 'toolsAndAuthOnly', 'limit': 1})
        self.assertTrue(proxy.closed)

    def test_unloaded_thread_does_not_create_resume_or_discover(self):
        FakeProxy.loaded = []
        value = self.api.inspect(thread_id='chosen-thread')
        self.assertEqual(value['reason'], 'THREAD_NOT_CONFIRMED_LOADED')
        self.assertEqual(len(FakeProxy.created[0].calls), 2)

    def test_other_server_response_is_not_golem_success(self):
        FakeProxy.reply['data'][0]['name'] = 'unrelated'
        value = self.api.inspect(thread_id='chosen-thread')
        self.assertEqual(value['reason'], 'SERVER_STATUS_UNAVAILABLE')
        self.assertFalse(value['verified_desktop'])
        self.assertIsNone(value['socket_identity'])

    def test_malformed_loaded_list_does_not_continue_or_attest(self):
        FakeProxy.loaded = 7
        value = self.api.inspect(thread_id='chosen-thread')
        self.assertEqual(value['reason'], 'THREAD_NOT_CONFIRMED_LOADED')
        self.assertFalse(value['verified_desktop'])
        self.assertEqual(len(FakeProxy.created[0].calls), 2)

    def test_missing_runtime_state_is_not_ready(self):
        del FakeProxy.reply['data'][0]['runtimeStatus']
        self.assertEqual(self.api.inspect(thread_id='chosen-thread')['server_status'], 'NOT_OBSERVED')

    def test_reload_requires_explicit_host_wide_choice_and_exact_identity(self):
        self.assertEqual(self.api.reload()['reason'], 'HOST_WIDE_CONFIRMATION_REQUIRED')
        self.assertEqual(self.api.reload(allow_host_wide=True)['reason'], 'EXPECTED_IDENTITY_REQUIRED')
        changed = dict(IDENTITY, inode=3)
        self.assertEqual(self.api.reload(allow_host_wide=True, expected_socket_identity=changed)['reason'],
                         'CONTROL_IDENTITY_CHANGED')
        self.assertEqual(FakeProxy.created, [])

    def test_identity_change_after_handshake_never_sends_reload(self):
        self.identity.side_effect = [dict(IDENTITY), dict(IDENTITY, host_pid=999)]
        value = self.api.reload(allow_host_wide=True, expected_socket_identity=IDENTITY)
        self.assertEqual(value['state'], 'BLOCKED')
        self.assertEqual(FakeProxy.created[0].calls, [('initialize', None)])

    def test_reload_is_single_host_wide_null_request_ack_only(self):
        value = self.api.reload(allow_host_wide=True, expected_socket_identity=IDENTITY)
        self.assertEqual(value['state'], 'REFRESH_QUEUED')
        self.assertEqual(value['reason'], 'QUEUE_ACK_ONLY')
        self.assertEqual(value['server_status'], 'NOT_OBSERVED')
        self.assertEqual(FakeProxy.created[0].calls, [('initialize', None), ('config/mcpServer/reload', None)])

    def test_identity_drift_after_reload_ack_is_not_current_success(self):
        self.identity.side_effect = [dict(IDENTITY), dict(IDENTITY), dict(IDENTITY, host_pid=999)]
        value = self.api.reload(allow_host_wide=True, expected_socket_identity=IDENTITY)
        self.assertEqual(value['state'], 'REFRESH_UNKNOWN')
        self.assertFalse(value['verified_desktop'])
        self.assertEqual(FakeProxy.created[0].calls.count(('config/mcpServer/reload', None)), 1)

    def test_post_dispatch_failure_is_uncertain_and_never_retried(self):
        for failure in ('CONTROL_EOF', 'CONTROL_TIMEOUT', 'CONTROL_RPC_ERROR'):
            with self.subTest(failure=failure):
                FakeProxy.fail = failure
                value = self.api.reload(allow_host_wide=True, expected_socket_identity=IDENTITY)
                self.assertEqual(value['state'], 'REFRESH_UNKNOWN')
                self.assertEqual(FakeProxy.created[-1].calls.count(('config/mcpServer/reload', None)), 1)
                self.assertTrue(FakeProxy.created[-1].closed)

    def test_pre_dispatch_failure_is_blocked(self):
        FakeProxy.before_reload = True
        value = self.api.reload(allow_host_wide=True, expected_socket_identity=IDENTITY)
        self.assertEqual(value['state'], 'BLOCKED')
        self.assertEqual(len(FakeProxy.created[0].calls), 1)


class SocketIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.root.chmod(0o700)
        self.path = self.root / 'control.sock'
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(self.socket.close)
        self.socket.bind(str(self.path))
        self.path.chmod(0o600)

    def test_private_socket_stat_accepts_only_exact_non_symlink(self):
        self.assertEqual(control._socket_stat(self.path)['inode'], self.path.stat().st_ino)
        link = self.root / 'alias.sock'
        link.symlink_to(self.path)
        with self.assertRaisesRegex(control.ControlError, 'SOCKET_SYMLINK'): control._socket_stat(link)

    def test_public_parent_or_socket_fails_closed(self):
        self.path.chmod(0o666)
        with self.assertRaisesRegex(control.ControlError, 'SOCKET_NOT_PRIVATE'): control._socket_stat(self.path)
        self.path.chmod(0o600)
        self.root.chmod(0o755)
        with self.assertRaisesRegex(control.ControlError, 'SOCKET_NOT_PRIVATE'): control._socket_stat(self.path)

    def test_named_socket_owned_by_cli_without_desktop_ancestry_is_rejected(self):
        cli = next(iter(control.DESKTOP_BINARIES))
        process = {'uid': os.getuid(), 'ppid': 1, 'start': 'start', 'exe': str(cli)}
        records = f'p123\nu{os.getuid()}\nf7\nn{self.path}\n'
        with patch.object(control.Path, 'resolve', lambda value, strict=False: value), \
             patch.object(control.Path, 'stat', return_value=os.stat_result((0o100755, 0, 0, 1, os.getuid(), 0, 1, 0, 0, 0))), \
             patch.object(control, '_socket_stat', return_value={'path': str(self.path)}), \
             patch.object(control, '_metadata', side_effect=[records, str(cli) + ' app-server']), \
             patch.object(control, '_process', return_value=process):
            with self.assertRaisesRegex(control.ControlError, 'DESKTOP_ANCESTRY_UNVERIFIED'):
                control._host_identity(cli, self.path)


class ProxyProtocol(unittest.TestCase):
    def fixture(self, body):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        executable = Path(temp.name) / 'fixture-proxy'
        executable.write_text('#!' + sys.executable + '\n' + body)
        executable.chmod(0o700)
        proxy = control._Proxy(executable, '/unused-fixture.sock')
        self.addCleanup(proxy.close)
        return proxy

    def test_public_proxy_argv_and_jsonl_handshake(self):
        proxy = self.fixture('import sys,json\nassert sys.argv[1:]==["app-server","proxy","--sock","/unused-fixture.sock"]\n'
                             'for line in sys.stdin:\n r=json.loads(line)\n'
                             ' if "id" in r: print(json.dumps({"id":r["id"],"result":{"userAgent":"fixture"}}),flush=True)\n')
        proxy.initialize()
        self.assertEqual(proxy.call('thread/loaded/list', {'limit': 1}), {'userAgent': 'fixture'})
        with self.assertRaisesRegex(control.ControlError, 'METHOD_NOT_ALLOWED'): proxy.call('turn/start', {})

    def test_eof_after_reload_marks_dispatched_without_retry(self):
        proxy = self.fixture('import sys,json\nfor line in sys.stdin:\n r=json.loads(line)\n'
                             ' if r.get("method")=="config/mcpServer/reload": sys.exit(0)\n'
                             ' if "id" in r: print(json.dumps({"id":r["id"],"result":{"userAgent":"fixture"}}),flush=True)\n')
        proxy.initialize()
        with self.assertRaisesRegex(control.ControlError, 'CONTROL_EOF'): proxy.call('config/mcpServer/reload')
        self.assertTrue(proxy.reload_dispatched)

    def test_server_approval_request_is_never_answered(self):
        proxy = self.fixture('import sys,json\nsys.stdin.readline()\nprint(json.dumps({"id":90,"method":"item/commandExecution/requestApproval"}),flush=True)\nsys.stdin.read()\n')
        with self.assertRaisesRegex(control.ControlError, 'CONTROL_SERVER_REQUEST_NOT_SUPPORTED'): proxy.initialize()


if __name__ == '__main__': unittest.main()
