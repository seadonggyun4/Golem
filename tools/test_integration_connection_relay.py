"""Disposable stdio/Unix relay fixtures. No Golem, client, Work or GUI is started."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/golem/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location('fixture_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = load('launcher')
relay = load('connection_relay')

FAKE = r'''
import json,os,sys,time,threading
from pathlib import Path
label,events,delay,failure=sys.argv[1:]
delay=float(delay)
def log(kind,**values):
    with open(events,'a') as out:out.write(json.dumps(dict(kind=kind,label=label,pid=os.getpid(),**values))+'\n')
def send(value):print(json.dumps(value),flush=True)
log('start')
for line in sys.stdin:
    msg=json.loads(line);log('message',method=msg.get('method'),id=msg.get('id'))
    if msg.get('method')=='initialize':
        if failure=='initialize':
            send({'jsonrpc':'2.0','id':msg['id'],'error':{'code':-1,'message':'fixture init failed'}})
        else:
            send({'jsonrpc':'2.0','id':msg['id'],'result':{'protocolVersion':'2025-06-18',
                'capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':label}}})
    elif msg.get('method')=='hold':
        time.sleep(.15)
        send({'jsonrpc':'2.0','id':msg['id'],'result':{'held':True}})
    elif 'method' in msg and 'id' in msg:
        send({'jsonrpc':'2.0','id':msg['id'],'result':{'label':label}})
log('eof')
time.sleep(delay)
log('exit')
'''


class Running:
    def __init__(self, adapter_state, timeout=.8):
        self.reader, self.writer = os.pipe()
        self.output_reader, self.output_writer = os.pipe()
        self.instance = relay.Relay(adapter, adapter_state, input_fd=self.reader,
                                    output_fd=self.output_writer, drain_timeout=timeout,
                                    start_timeout=.8)
        self.error = None
        self.buffer = bytearray()
        self.closed = False
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def run(self):
        try:
            self.instance.run()
        except Exception as error:
            self.error = error

    def wait(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while not predicate():
            if time.monotonic() >= deadline:
                raise AssertionError(('fixture deadline', self.error, self.instance.status()))
            time.sleep(.005)

    def write(self, method, request_id=None):
        msg = {'jsonrpc': '2.0', 'method': method}
        if request_id is not None:
            msg['id'] = request_id
        if method == 'initialize':
            msg['params'] = {'protocolVersion': '2025-06-18', 'capabilities': {},
                             'clientInfo': {'name': 'fixture', 'version': '1'}}
        os.write(self.writer, relay.encoded(msg))

    def read(self, timeout=3):
        deadline = time.monotonic() + timeout
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.output_reader], [], [], remaining)[0]:
                raise AssertionError(('no response', self.error, self.instance.status()))
            self.buffer.extend(os.read(self.output_reader, 65536))
        raw, _, rest = self.buffer.partition(b'\n')
        self.buffer[:] = rest
        return json.loads(raw)

    def initialize(self):
        self.wait(lambda: self.instance.child is not None)
        self.write('initialize', 1)
        response = self.read()
        self.write('notifications/initialized')
        self.wait(lambda: self.instance.state == 'READY')
        return response

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.writer is not None:
            os.close(self.writer)
        self.thread.join(4)
        if self.thread.is_alive():
            raise AssertionError('relay fixture did not stop; no force-kill allowed')
        child = self.instance.child
        if child is not None:
            # Every fixture child has a bounded EOF path, including drain timeout.
            child.wait(timeout=3)
            for stream in (child.stdin, child.stdout):
                if stream and not stream.closed:
                    stream.close()
        for fd in (self.reader, self.output_reader, self.output_writer):
            os.close(fd)


class ConnectionRelay(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gr-', dir='/private/tmp' if sys.platform == 'darwin' else '/tmp')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.home.chmod(0o700)
        self.patch_home = patch.object(Path, 'home', return_value=self.home)
        self.patch_home.start()
        self.addCleanup(self.patch_home.stop)
        self.script = self.home / 'fake.py'
        self.script.write_text(FAKE)
        self.events = self.home / 'events.jsonl'
        self.counter = 0
        self.gui_modules_before = {name for name in sys.modules if name == 'tkinter' or name.startswith('tkinter.')}
        (self.home / '.codex').mkdir(mode=0o700)

    def state(self, label, delay=0, failure='none'):
        self.counter += 1
        state = self.home / ('state' + str(self.counter))
        state.mkdir(mode=0o700)
        source = self.home / ('launcher' + str(self.counter) + '.json')
        raw = json.dumps({'command': sys.executable, 'args': ['-I', '-B', str(self.script),
            label, str(self.events), str(delay), failure]}).encode()
        source.write_bytes(raw)
        source.chmod(0o600)
        adapter.configure(state, source, hashlib.sha256(raw).hexdigest(), True)
        return state

    def running(self, state, timeout=.8):
        running = Running(state, timeout)
        self.addCleanup(running.close)
        running.initialize()
        return running

    def config(self, state, command=None):
        args = ['-I', '-B', str(SCRIPTS / 'launcher.py'), 'serve', '--client', 'codex', '--state', str(state)]
        raw = ('[mcp_servers.golem-local]\ncommand=' + json.dumps(command or sys.executable)
               + '\nargs=' + json.dumps(args) + '\n').encode()
        path = self.home / '.codex/config.toml'
        path.write_bytes(raw)
        path.chmod(0o600)
        return hashlib.sha256(raw).hexdigest()

    def refresh_args(self, running, state):
        _, pin, approval = running.instance.approved(state)
        return {'expected_launcher_sha256': running.instance.pin,
                'expected_approval_sha256': running.instance.approval_pin,
                'state': str(state), 'approval_sha256': approval, 'launcher_sha256': pin,
                'config_sha256': self.config(state)}

    def events_read(self):
        return [json.loads(line) for line in self.events.read_text().splitlines()] if self.events.exists() else []

    def control(self, running, operation, arguments):
        return relay.request(running.instance.instance, operation, arguments)

    def test_headless_initialize_status_and_notification_capability(self):
        running = Running(self.state('first'))
        self.addCleanup(running.close)
        response = running.initialize()
        self.assertTrue(response['result']['capabilities']['tools']['listChanged'])
        status = self.control(running, 'status', {})['value']
        self.assertEqual(status['state'], 'READY')
        self.assertFalse(status['execution_authorized'])
        self.assertFalse(status['model_tools_delivery_verified'])
        self.assertFalse(status['work_idle_verified'])
        self.assertFalse(status['native_leases_observed'])
        rows = relay.descriptors()
        self.assertEqual([r['instance'] for r in rows], [running.instance.instance])
        self.assertNotIn('token', rows[0])
        self.assertEqual(self.gui_modules_before,
                         {name for name in sys.modules if name == 'tkinter' or name.startswith('tkinter.')})

    def test_refresh_preserves_transport_drains_then_initializes_once_and_notifies(self):
        running = self.running(self.state('first', delay=.08))
        next_state = self.state('second')
        args = self.refresh_args(running, next_state)
        response = self.control(running, 'refresh', args)
        self.assertTrue(response['ok'], response)
        self.assertEqual(response['value']['refresh_result'], 'CHILD_REINITIALIZED')
        self.assertEqual(self.read_method(running), 'notifications/tools/list_changed')
        running.write('tools/list', 2)
        self.assertEqual(running.read()['result']['label'], 'second')
        events = self.events_read()
        self.assertLess(next(i for i, e in enumerate(events) if e['label']=='first' and e['kind']=='exit'),
                        next(i for i, e in enumerate(events) if e['label']=='second' and e['kind']=='start'))
        self.assertEqual(sum(e.get('method')=='initialize' and e['label']=='second' for e in events), 1)
        self.assertEqual(sum(e.get('method')=='tools/list' and e['label']=='second' for e in events), 1)

    def read_method(self, running):
        return running.read()['method']

    def test_busy_request_blocks_refresh_before_any_child_close(self):
        running = self.running(self.state('first'))
        args = self.refresh_args(running, self.state('second'))
        running.write('hold', 2)
        running.wait(lambda: bool(running.instance.pending))
        response = self.control(running, 'refresh', args)
        self.assertFalse(response['ok'])
        self.assertEqual(response['code'], 'REFRESH_BUSY')
        self.assertTrue(running.read()['result']['held'])
        self.assertFalse(any(e['kind']=='eof' for e in self.events_read()))
        self.assertFalse(any(e['label']=='second' for e in self.events_read()))

    def test_stale_config_or_approval_blocks_without_dispatch(self):
        running = self.running(self.state('first'))
        target = self.state('second')
        args = self.refresh_args(running, target)
        for key in ('expected_launcher_sha256', 'expected_approval_sha256', 'approval_sha256', 'config_sha256'):
            with self.subTest(key=key):
                invalid = {**args, key: '0' * 64}
                response = self.control(running, 'refresh', invalid)
                self.assertFalse(response['ok'])
                self.assertEqual(running.instance.state, 'READY')
        self.assertFalse(any(e['kind']=='eof' for e in self.events_read()))

    def test_unselected_state_and_shell_command_cannot_start(self):
        running = self.running(self.state('first'))
        target = self.state('second')
        args = self.refresh_args(running, target)
        args['config_sha256'] = self.config(running.instance.current_state)
        self.assertEqual(self.control(running,'refresh',args)['code'], 'CONFIG_STATE_NOT_SELECTED')
        args['config_sha256'] = self.config(target, '/bin/sh')
        self.assertEqual(self.control(running,'refresh',args)['code'], 'CONFIG_STATE_NOT_SELECTED')
        self.assertFalse(any(e['kind']=='eof' for e in self.events_read()))

    def test_init_failure_is_unknown_no_retry_or_work_forwarding(self):
        running = self.running(self.state('first'))
        args = self.refresh_args(running, self.state('bad', failure='initialize'))
        response = self.control(running, 'refresh', args)
        self.assertFalse(response['ok'])
        self.assertEqual(running.instance.state, 'UNKNOWN')
        self.assertFalse(self.control(running, 'refresh', args)['ok'])
        running.write('tools/call', 3)
        result = running.read()
        self.assertEqual(result['error']['message'], 'GOLEM_RELAY_UNKNOWN')
        self.assertEqual(sum(e['kind']=='start' and e['label']=='bad' for e in self.events_read()), 1)
        self.assertFalse(any(e.get('method')=='tools/call' for e in self.events_read()))

    def test_drain_timeout_never_spawns_replacement_or_kills_child(self):
        running = self.running(self.state('first', delay=.3), timeout=.04)
        original_pid = running.instance.child.pid
        response = self.control(running, 'refresh', self.refresh_args(running, self.state('second')))
        self.assertFalse(response['ok'])
        self.assertEqual(running.instance.state, 'UNKNOWN')
        self.assertEqual(running.instance.child.pid, original_pid)
        self.assertIsNone(running.instance.child.poll())
        self.assertFalse(any(e['label']=='second' for e in self.events_read()))
        self.assertFalse(self.control(running, 'refresh', {})['ok'])

    def test_requests_during_refresh_are_rejected_not_queued_to_new_child(self):
        running = self.running(self.state('first', delay=.2))
        args = self.refresh_args(running, self.state('second'))
        output = []
        worker = threading.Thread(target=lambda: output.append(self.control(running, 'refresh', args)))
        worker.start()
        running.wait(lambda: running.instance.state == 'DRAINING')
        running.write('tools/call', 4)
        result = running.read()
        self.assertEqual(result['error']['message'], 'GOLEM_RELAY_REFRESH_BUSY')
        self.assertFalse(result['error']['data']['dispatched'])
        worker.join(3)
        self.assertTrue(output[0]['ok'], output)
        self.assertEqual(self.read_method(running), 'notifications/tools/list_changed')
        self.assertFalse(any(e.get('method')=='tools/call' for e in self.events_read()))

    def test_approval_changed_during_drain_stops_before_new_child(self):
        running = self.running(self.state('first', delay=.2))
        target = self.state('second')
        args = self.refresh_args(running, target)
        output = []
        worker = threading.Thread(target=lambda: output.append(self.control(running, 'refresh', args)))
        worker.start()
        running.wait(lambda: running.instance.state == 'DRAINING')
        approval = target / 'golem-launcher/approval.json'
        approval.write_bytes(approval.read_bytes() + b' ')
        worker.join(3)
        self.assertFalse(output[0]['ok'])
        self.assertEqual(running.instance.state, 'UNKNOWN')
        self.assertFalse(any(e['label']=='second' for e in self.events_read()))

    def test_host_eof_during_refresh_stops_without_new_child_or_force_kill(self):
        running = self.running(self.state('first', delay=.2))
        args = self.refresh_args(running, self.state('second'))
        output = []
        worker = threading.Thread(target=lambda: output.append(self.control(running, 'refresh', args)))
        worker.start()
        running.wait(lambda: running.instance.state == 'DRAINING')
        os.close(running.writer)
        running.writer = None
        worker.join(3)
        self.assertFalse(output[0]['ok'])
        self.assertEqual(running.instance.state, 'UNKNOWN')
        self.assertFalse(any(e['label']=='second' for e in self.events_read()))

    def test_partial_request_during_refresh_is_never_dispatched(self):
        running = self.running(self.state('first', delay=.2))
        args = self.refresh_args(running, self.state('second'))
        output = []
        worker = threading.Thread(target=lambda: output.append(self.control(running, 'refresh', args)))
        worker.start()
        running.wait(lambda: running.instance.state == 'DRAINING')
        os.write(running.writer, b'{"jsonrpc":"2.0","id":8,"method":')
        worker.join(3)
        self.assertFalse(output[0]['ok'])
        self.assertEqual(running.instance.state, 'UNKNOWN')
        self.assertFalse(any(e.get('id')==8 for e in self.events_read()))

    def test_initial_initialize_failure_is_forwarded_without_restart(self):
        running = Running(self.state('bad', failure='initialize'))
        self.addCleanup(running.close)
        running.wait(lambda: running.instance.child is not None)
        running.write('initialize', 1)
        self.assertEqual(running.read()['error']['message'], 'fixture init failed')
        running.wait(lambda: running.instance.state == 'UNKNOWN')
        self.assertEqual(sum(e['kind']=='start' for e in self.events_read()), 1)

    def test_replay_and_other_instance_token_are_rejected(self):
        first = self.running(self.state('first'))
        second = self.running(self.state('second'))
        message = {'schema': relay.SCHEMA, 'instance': first.instance.instance,
                   'token': first.instance.token, 'request_id': 'a'*32, 'operation': 'status', 'arguments': {}}
        self.assertEqual(first.instance.control(message)['state'], 'READY')
        with self.assertRaisesRegex(relay.RelayError, 'CONTROL_REPLAY_OR_QUOTA'):
            first.instance.control(message)
        with self.assertRaisesRegex(relay.RelayError, 'CONTROL_AUTH'):
            second.instance.control(message)
        first.close()
        second.write('tools/list', 5)
        self.assertEqual(second.read()['result']['label'], 'second')

    def test_descriptor_pid_mismatch_is_rejected(self):
        running = self.running(self.state('first'))
        path = running.instance.descriptor
        data = json.loads(path.read_bytes())
        data['pid'] += 1
        path.write_bytes(relay.encoded(data))
        with self.assertRaisesRegex(relay.RelayError, 'CONTROL_PID'):
            self.control(running, 'status', {})

    def test_target_configuration_is_read_only(self):
        running = self.running(self.state('first'))
        target = self.state('second')
        args = self.refresh_args(running, target)
        paths = [self.home/'.codex/config.toml', target/'golem-launcher/approval.json',
                 running.instance.current_state/'golem-launcher/approval.json']
        before = {str(p):p.read_bytes() for p in paths}
        self.assertTrue(self.control(running, 'refresh', args)['ok'])
        self.assertEqual(self.read_method(running), 'notifications/tools/list_changed')
        self.assertEqual(before, {str(p):p.read_bytes() for p in paths})

    def test_continuous_client_notifications_cannot_starve_drain_deadline(self):
        instance = relay.Relay(adapter, self.home)
        self.addCleanup(instance.selector.close)
        notification = relay.encoded({'jsonrpc':'2.0', 'method':'notifications/progress'})
        with patch.object(relay.select, 'select', return_value=([0], [], [])), \
             patch.object(relay.os, 'read', return_value=notification) as read:
            with self.assertRaisesRegex(relay.RelayError, 'REFRESH_INPUT_LIMIT'):
                instance.reject_refresh_requests()
        self.assertLessEqual(read.call_count, 129)

    def test_stalled_host_reader_cannot_block_past_write_deadline(self):
        running = self.running(self.state('first'))
        self.assertFalse(os.get_blocking(running.output_writer))
        start = time.monotonic()
        with self.assertRaisesRegex(relay.RelayError, 'TRANSPORT_WRITE_TIMEOUT'):
            running.instance.write(running.output_writer,
                {'jsonrpc':'2.0', 'method':'notifications/progress', 'params':{'data':'x'*500000}},
                deadline=start+.03)
        self.assertLess(time.monotonic()-start, 1.0)


if __name__ == '__main__':
    unittest.main()
