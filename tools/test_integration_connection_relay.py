"""Disposable stdio/Unix relay fixtures. No Golem, client, Work or GUI is started."""
import hashlib
import copy
import importlib.util
import json
import os
from pathlib import Path
import select
import stat
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
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
    elif msg.get('method')=='tools/list':
        send({'jsonrpc':'2.0','id':msg['id'],'result':{'label':label,'tools':[
            {'name':label,'description':'fixture only','inputSchema':{'type':'object'}}]}})
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

    def test_refresh_notification_without_host_relist_never_reuses_old_catalog(self):
        running = self.running(self.state('old-private-name'))
        running.write('tools/list', 2)
        self.assertEqual(running.read()['result']['label'], 'old-private-name')
        old = self.control(running, 'status', {})['value']['host_catalog']
        self.assertEqual(old['state'], 'HOST_CATALOG_RESPONSE_SENT')
        response = self.control(running, 'refresh', self.refresh_args(running, self.state('new-private-name')))
        self.assertTrue(response['ok'])
        self.assertEqual(self.read_method(running), 'notifications/tools/list_changed')
        current = response['value']['host_catalog']
        self.assertEqual(current['state'], 'HOST_CATALOG_NOT_RELISTED')
        self.assertEqual(current['child_generation'], 2)
        self.assertEqual(current['catalog_generation'], 2)
        self.assertEqual(current['requests'], 0)
        self.assertEqual(current['responses'], 0)
        self.assertEqual(current['list_changed_notifications_sent'], 1)
        self.assertIsNone(current['current_complete_sha256'])
        self.assertEqual(current['last_complete_generation'], 1)
        self.assertEqual(current['last_complete_sha256'], old['current_complete_sha256'])
        self.assertFalse(any(e.get('method')=='tools/list' and e['label']=='new-private-name'
                             for e in self.events_read()))
        running.write('tools/list', 3)
        self.assertEqual(running.read()['result']['label'], 'new-private-name')
        observed = self.control(running, 'status', {})['value']['host_catalog']
        self.assertEqual(observed['state'], 'HOST_CATALOG_RESPONSE_SENT')
        self.assertEqual(observed['last_complete_generation'], 2)
        self.assertNotEqual(observed['current_complete_sha256'], old['current_complete_sha256'])
        self.assertFalse(observed['model_delivery_verified'])
        self.assertNotIn('private-name', json.dumps(observed))
        self.assertFalse(any(e.get('method')=='tools/call' for e in self.events_read()))

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


class CatalogObservation(unittest.TestCase):
    """Observe host-originated RPCs without a child, socket or real client."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='golem-catalog-')
        self.addCleanup(self.temp.cleanup)
        self.instance = relay.Relay(adapter, Path(self.temp.name).resolve())
        self.addCleanup(self.instance.selector.close)
        self.instance.child_generation = 1
        self.instance.new_catalog_generation()
        self.instance.state, self.instance.initialized = 'READY', True
        self.child_messages, self.client_messages = [], []
        self.instance.send_child = self.child_messages.append
        self.instance.send_client = self.client_messages.append

    def request(self, request_id, cursor=None, *, params=None):
        args = {} if cursor is None else {'cursor': cursor}
        self.instance.client_message({'jsonrpc':'2.0', 'method':'tools/list', 'id':request_id,
                                      'params':args if params is None else params})

    def reply(self, request_id, *, cursor=None, tools=None, error=False):
        value = {'tools':tools if tools is not None else [
            {'name':'private-tool-name-'+str(request_id),'inputSchema':{'type':'object'},'description':'private description'}]}
        if cursor is not None: value['nextCursor'] = cursor
        self.instance.child_message({'jsonrpc':'2.0','id':request_id, **(
            {'error':{'code':-32000,'message':'fixture'}} if error else {'result':value})})

    def test_marker_is_opaque_definition_metadata_without_new_tool_or_authority(self):
        tools=[{'name':'golem_projects_list','description':'original explanation',
                'inputSchema':{'type':'object','properties':{}},'annotations':{'readOnlyHint':True}},
               {'name':'golem_work_inspect','description':'second untouched',
                'inputSchema':{'type':'object'}}]
        original=copy.deepcopy(tools)
        self.request(1);self.reply(1,tools=tools)
        sent=self.client_messages[-1]['result']['tools']
        marker=self.instance.definition_marker()
        parsed=relay.parse_definition_marker(marker)
        self.assertEqual(parsed['instance'],self.instance.instance)
        self.assertEqual(parsed['child_generation'],1)
        self.assertEqual(parsed['catalog_generation'],1)
        self.assertEqual(len(parsed['definition_nonce']),32)
        self.assertEqual(tools,original)
        self.assertEqual([t['name'] for t in sent],[t['name'] for t in original])
        self.assertEqual(sent[0]['inputSchema'],original[0]['inputSchema'])
        self.assertEqual(sent[0]['annotations'],original[0]['annotations'])
        self.assertEqual(sent[1],original[1])
        self.assertEqual(sent[0]['description'],'original explanation'+
            '\n\nConnection observation only; no authority: '+marker)
        self.assertNotIn(self.instance.token,marker)
        status=self.instance.status()
        self.assertFalse(status['execution_authorized'])
        self.assertFalse(status['model_tools_delivery_verified'])
        forwarded=self.instance.catalog_digest(self.client_messages[-1]['result'])
        self.assertEqual(status['host_catalog']['current_complete_sha256'],
                         self.instance.catalog_digest([forwarded]))

    def test_marker_is_stable_across_pages_but_rotates_on_catalog_change(self):
        self.request(1);self.reply(1,cursor='page-2')
        before=self.instance.definition_marker()
        self.request(2,'page-2');self.reply(2)
        self.assertEqual(self.instance.definition_marker(),before)
        for response in self.client_messages:
            self.assertTrue(response['result']['tools'][0]['description'].endswith(before))
        self.instance.child_message({'jsonrpc':'2.0','method':'notifications/tools/list_changed'})
        after=self.instance.definition_marker()
        self.assertNotEqual(after,before)
        old,new=relay.parse_definition_marker(before),relay.parse_definition_marker(after)
        self.assertEqual(old['instance'],new['instance'])
        self.assertEqual(old['child_generation'],new['child_generation'])
        self.assertEqual(new['catalog_generation'],old['catalog_generation']+1)
        self.assertNotEqual(old['definition_nonce'],new['definition_nonce'])
        self.assertEqual(self.instance.catalog_status()['state'],'HOST_CATALOG_NOT_RELISTED')

    def test_old_pending_reply_never_receives_new_generation_marker(self):
        self.request(1)
        self.instance.child_message({'jsonrpc':'2.0','method':'notifications/tools/list_changed'})
        self.reply(1)
        self.assertNotIn('golem-connection-v1:',self.client_messages[-1]['result']['tools'][0]['description'])
        self.assertIsNone(self.instance.catalog_status()['current_complete_sha256'])

    def test_unrelated_and_malformed_tool_responses_are_not_marked(self):
        self.instance.client_message({'jsonrpc':'2.0','id':1,'method':'ping'})
        ping={'tools':[{'name':'unrelated','inputSchema':{'type':'object'},'description':'unchanged'}]}
        self.instance.child_message({'jsonrpc':'2.0','id':1,'result':ping})
        self.assertEqual(self.client_messages[-1]['result'],ping)
        for request_id,tools in enumerate(([{}],[],[{'name':'malformed','inputSchema':{},'description':None}]),2):
            self.request(request_id);self.reply(request_id,tools=tools)
            self.assertEqual(self.client_messages[-1]['result']['tools'],tools)

    def test_marker_annotation_overflow_preserves_valid_original_frame(self):
        self.request(1)
        tools=[{'name':'golem_projects_list','description':'x'*100,'inputSchema':{'type':'object'}}]
        original={'jsonrpc':'2.0','id':1,'result':{'tools':copy.deepcopy(tools)}}
        with patch.object(relay,'FRAME_LIMIT',len(relay.encoded(original))):
            self.reply(1,tools=tools)
        self.assertEqual(self.client_messages[-1],original)
        self.assertEqual(self.instance.state,'READY')
        self.assertFalse(self.instance.status()['model_tools_delivery_verified'])

    def test_complete_inventory_digest_uses_sorted_all_page_names_and_invalidates_on_relist(self):
        self.request(1);self.reply(1,cursor='two',tools=[{'name':'golem_z','inputSchema':{}}])
        self.assertIsNone(self.instance.status()['definition_tools_sha256'])
        self.assertIsNone(self.instance.status()['definition_tool_count'])
        self.request(2,'two');self.reply(2,tools=[{'name':'golem_a','inputSchema':{}}])
        status=self.instance.status()
        self.assertEqual(status['definition_tools_sha256'],relay.Relay.catalog_digest(['golem_a','golem_z']))
        self.assertEqual(status['definition_tool_count'],2)
        self.request(3)
        status=self.instance.status()
        self.assertIsNone(status['definition_tools_sha256'])
        self.assertIsNone(status['definition_tool_count'])
        self.reply(3,error=True)
        self.assertIsNone(self.instance.status()['definition_tools_sha256'])

    def test_duplicate_or_oversized_inventory_does_not_qualify_catalog(self):
        same={'name':'golem_same','inputSchema':{}}
        self.request(1);self.reply(1,cursor='two',tools=[same])
        self.request(2,'two');self.reply(2,tools=[same])
        self.assertEqual(self.instance.catalog_status()['state'],'HOST_CATALOG_INVALID_RESPONSE')
        self.assertIsNone(self.instance.status()['definition_tools_sha256'])
        self.request(3);self.reply(3,tools=[{'name':'golem_'+str(i),'inputSchema':{}} for i in range(257)])
        self.assertEqual(self.instance.catalog_status()['state'],'HOST_CATALOG_INVALID_RESPONSE')
        self.assertIsNone(self.instance.status()['definition_tool_count'])

    def test_marker_parser_rejects_guessed_extended_and_unbounded_values(self):
        valid='golem-connection-v1:'+'a'*32+':1:2:'+'b'*32
        self.assertEqual(relay.parse_definition_marker(valid)['catalog_generation'],2)
        invalid=(None,'',valid+' trailing',valid+'\n',valid.replace(':1:2:',':3:2:'),
                 valid.replace(':1:2:',':0:2:'),valid.replace(':1:2:',':1:9223372036854775808:'),
                 valid.replace('a'*32,'a'*31),valid.replace('b'*32,'B'*32))
        for value in invalid:
            with self.subTest(marker=value):
                with self.assertRaisesRegex(relay.RelayError,'DEFINITION_MARKER_INVALID'):
                    relay.parse_definition_marker(value)

    def test_exact_response_id_and_full_pagination_are_required(self):
        self.request('first');self.reply('first', cursor='private-cursor')
        state = self.instance.catalog_status()
        self.assertEqual(state['state'], 'HOST_CATALOG_PARTIAL_RESPONSE')
        self.assertIsNone(state['current_complete_sha256'])
        self.request('second', 'private-cursor')
        with self.assertRaisesRegex(relay.RelayError,'UNEXPECTED_CHILD_RESPONSE'):
            self.reply('wrong-id')
        self.assertIsNone(self.instance.catalog_status()['current_complete_sha256'])
        self.reply('second')
        state = self.instance.catalog_status()
        self.assertEqual(state['state'], 'HOST_CATALOG_RESPONSE_SENT')
        self.assertEqual(state['current_complete_pages'], 2)
        self.assertEqual((state['requests'], state['responses']), (2,2))
        self.assertNotIn('private-', json.dumps(state))
        self.assertFalse(state['model_delivery_verified'])

    def test_error_response_preserves_history_but_not_current_success(self):
        self.request(1);self.reply(1)
        original = self.instance.catalog_status()['last_complete_sha256']
        self.request(2);self.reply(2, error=True)
        state = self.instance.catalog_status()
        self.assertEqual(state['state'], 'HOST_CATALOG_ERROR_SENT')
        self.assertEqual((state['requests'],state['responses'],state['errors']),(2,2,1))
        self.assertIsNone(state['current_complete_sha256'])
        self.assertEqual(state['last_complete_sha256'], original)

    def test_notification_invalidates_inflight_and_previous_generation(self):
        self.request(1);self.reply(1)
        self.request(2)
        self.instance.child_message({'jsonrpc':'2.0','method':'notifications/tools/list_changed'})
        self.reply(2)
        state = self.instance.catalog_status()
        self.assertEqual(state['child_generation'], 1)
        self.assertEqual(state['catalog_generation'], 2)
        self.assertEqual(state['state'], 'HOST_CATALOG_NOT_RELISTED')
        self.assertEqual(state['responses'], 0)
        self.assertEqual(state['list_changed_notifications_sent'], 1)
        self.assertEqual(state['last_complete_generation'], 1)
        self.assertIsNone(state['current_complete_sha256'])
        self.assertEqual(self.instance.catalog_pending, {})

    def test_cursor_only_or_interleaved_chain_never_claims_complete_catalog(self):
        self.request(1,'unknown');self.reply(1)
        self.assertEqual(self.instance.catalog_status()['state'],'HOST_CATALOG_UNVERIFIED_PAGE')
        self.request(2);self.reply(2,cursor='same-cursor')
        self.request(3,'same-cursor')  # First chain page is still in flight.
        self.request(4);self.reply(4,cursor='same-cursor')
        self.reply(3)  # Must not splice a page into the later root's chain.
        self.assertEqual(self.instance.catalog_status()['state'],'HOST_CATALOG_UNVERIFIED_PAGE')
        self.assertIsNone(self.instance.catalog_status()['current_complete_sha256'])

    def test_page_loop_and_page_bound_are_not_complete(self):
        self.request(1);self.reply(1,cursor='a')
        self.request(2,'a');self.reply(2,cursor='a')
        self.assertEqual(self.instance.catalog_status()['state'],'HOST_CATALOG_INVALID_RESPONSE')
        with patch.object(relay,'CATALOG_PAGE_LIMIT',2):
            self.request(3);self.reply(3,cursor='a')
            self.request(4,'a');self.reply(4,cursor='b')
            self.request(5,'b');self.reply(5)
        self.assertEqual(self.instance.catalog_status()['state'],'HOST_CATALOG_INVALID_RESPONSE')
        self.assertIsNone(self.instance.catalog_status()['current_complete_sha256'])

    def test_malformed_or_unrelated_response_is_not_catalog_observation(self):
        self.instance.client_message({'jsonrpc':'2.0','id':1,'method':'ping'})
        self.instance.child_message({'jsonrpc':'2.0','id':1,'result':{}})
        self.assertEqual(self.instance.catalog_status()['requests'],0)
        self.request(2,params={'cursor':5});self.reply(2)
        self.assertEqual(self.instance.catalog_status()['state'],'HOST_CATALOG_INVALID_RESPONSE')
        self.request(3);self.reply(3,tools=[{}])
        self.assertEqual(self.instance.catalog_status()['state'],'HOST_CATALOG_INVALID_RESPONSE')
        self.assertIsNone(self.instance.catalog_status()['current_complete_sha256'])

    def test_failed_stdout_write_does_not_attest_delivery(self):
        self.request(1)
        with patch.object(self.instance,'send_client',side_effect=OSError('fixture closed host')):
            with self.assertRaises(OSError):self.reply(1)
        state = self.instance.catalog_status()
        self.assertEqual(state['responses'],0)
        self.assertIsNone(state['current_complete_sha256'])
        self.assertFalse(state['model_delivery_verified'])


class Discovery(unittest.TestCase):
    """Discovery never connects, drops old records, or proves process exit."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='golem-discovery-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.root.chmod(0o700)
        directory=patch.object(relay,'_directory',return_value=self.root)
        directory.start();self.addCleanup(directory.stop)

    def record(self, number):
        instance=f'{number:032x}'
        value={'schema':relay.SCHEMA,'instance':instance,'token':'a'*64,
               'pid':50,'kind':'codex-connection-relay'}
        path=self.root/(instance+'.json')
        path.write_bytes(relay.encoded(value));path.chmod(0o600)
        return instance

    def test_missing_socket_history_is_retained_without_token_or_dispatch(self):
        for i in range(40): self.record(i)
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        with patch.object(relay,'request',side_effect=AssertionError('no IPC')):
            rows=relay.descriptors()
        self.assertEqual(len(rows),40)
        self.assertTrue(all(r['endpoint_state']=='ABSENT' for r in rows))
        self.assertTrue(all('token' not in r for r in rows))
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})

    def test_invalid_record_symlink_socket_and_wrong_uid_stay_unknown(self):
        invalid=self.record(1);(self.root/(invalid+'.json')).write_bytes(b'{}')
        linked=self.record(2);(self.root/(linked+'.sock')).symlink_to(self.root/(linked+'.json'))
        foreign=self.record(3)
        original=Path.lstat
        def info(path,*args,**kwargs):
            if path.name==foreign+'.sock':
                return SimpleNamespace(st_mode=stat.S_IFSOCK|0o600,st_uid=os.getuid()+1,st_dev=1,st_ino=1)
            return original(path,*args,**kwargs)
        with patch.object(Path,'lstat',side_effect=info,autospec=True): rows=relay.descriptors()
        self.assertEqual([r['endpoint_state'] for r in rows],['UNKNOWN']*3)
        self.assertTrue(all('token' not in r for r in rows))

    def test_discovery_bound_1024_entries_is_not_increased(self):
        for i in range(1025): (self.root/str(i)).touch()
        with self.assertRaisesRegex(relay.RelayError,'CONTROL_DISCOVERY_LIMIT'):
            relay.descriptors()

    def test_record_change_during_endpoint_observation_is_rejected(self):
        instance=self.record(1)
        original=relay._record
        first=original(instance)
        with patch.object(relay,'_record',side_effect=[first,dict(first,pid=51)]):
            with self.assertRaisesRegex(relay.RelayError,'CONTROL_RECORD_CHANGED'):
                relay.endpoint(instance)


if __name__ == '__main__':
    unittest.main()
