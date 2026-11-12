"""Disposable stdio/socket fixtures; no real client, Golem Work or policy."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import socket
import sys
import threading
import time
import unittest
import uuid
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/golem/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location('stable_test_' + name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter, contract, relay = load('launcher'), load('stable_contract'), load('stable_relay')

FAKE = r'''
import json,os,sys,time
label,events,mode,delay,abi=sys.argv[1:]
def log(kind,**fields):
    with open(events,'a') as out:out.write(json.dumps(dict(kind=kind,label=label,client=os.environ.get('GOLEM_LAUNCHER_CLIENT'),**fields))+'\n')
def send(value):print(json.dumps(value),flush=True)
log('start',abi=os.environ.get('GOLEM_STABLE_FRONTEND_ABI'),profile=os.environ.get('GOLEM_STABLE_FRONTEND_PROFILE'),tools=os.environ.get('GOLEM_STABLE_FRONTEND_TOOLS'))
for line in sys.stdin:
    msg=json.loads(line);log('message',method=msg.get('method'),id=msg.get('id'),params=msg.get('params'))
    if msg.get('method')=='initialize':
        if mode=='init-error':send({'jsonrpc':'2.0','id':msg['id'],'error':{'code':-1,'message':'fixture initialize failure'}})
        else:
            caps={'tools':{'different':True} if mode=='caps-change' else {}}
            if mode!='abi-missing':caps['experimental']={'golem.fixed-tool-catalog.v1':{'catalog_sha256':'f'*64 if mode=='abi-mismatch' else abi}}
            send({'jsonrpc':'2.0','id':msg['id'],'result':{'protocolVersion':'2025-06-18','capabilities':caps,'serverInfo':{'name':'fake','version':label}}})
    elif msg.get('method')=='notifications/initialized' and mode=='notify':
        send({'jsonrpc':'2.0','method':'notifications/tools/list_changed'})
    elif msg.get('method')=='notifications/initialized' and mode=='sampling':
        send({'jsonrpc':'2.0','id':'child-1','method':'sampling/createMessage','params':{'messages':[]}})
    elif msg.get('method')=='tools/call':
        name=msg['params']['name']
        if mode=='notifycall':send({'jsonrpc':'2.0','method':'notifications/tools/list_changed'})
        if name=='golem_hold':time.sleep(.12)
        result=({'isError':True,'content':[{'type':'text','text':'OWNER_ACTION_NOT_ALLOWED'}]} if name=='golem_blocked' else {'content':[{'type':'text','text':label}]})
        send({'jsonrpc':'2.0','id':msg['id'],'result':result})
    elif msg.get('method')=='ping':send({'jsonrpc':'2.0','id':msg['id'],'result':{}})
log('eof')
if mode=='eofbad':send({'jsonrpc':'2.0','method':'notifications/arbitrary'})
time.sleep(float(delay));log('exit')
'''


class Running:
    def __init__(self, store, client, timeout=.8):
        self.reader, self.writer = os.pipe()
        self.output_reader, self.output_writer = os.pipe()
        self.instance = relay.StableRelay(adapter, contract, store, client, input_fd=self.reader,
            output_fd=self.output_writer, drain_timeout=timeout, start_timeout=.8)
        self.error, self.buffer, self.closed = None, bytearray(), False
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

    def write(self, method, request_id=None, params=None):
        msg = {'jsonrpc': '2.0', 'method': method}
        if request_id is not None:
            msg['id'] = request_id
        if params is not None:
            msg['params'] = params
        os.write(self.writer, relay.encoded(msg))

    def read(self, timeout=3):
        deadline = time.monotonic() + timeout
        while b'\n' not in self.buffer:
            remaining = deadline-time.monotonic()
            if remaining <= 0 or not select.select([self.output_reader], [], [], remaining)[0]:
                raise AssertionError(('no response', self.error, self.instance.status()))
            block = os.read(self.output_reader, 65536)
            if not block:
                raise AssertionError(('fixture EOF', self.error))
            self.buffer.extend(block)
        raw, _, rest = self.buffer.partition(b'\n')
        self.buffer[:] = rest
        return json.loads(raw)

    def initialize(self, capabilities=None):
        self.wait(lambda: self.instance.child is not None or self.error is not None)
        if self.error:
            raise self.error
        self.write('initialize', 1, {'protocolVersion': '2025-06-18', 'capabilities': capabilities or {},
                                    'clientInfo': {'name': 'fixture', 'version': '1'}})
        response = self.read()
        self.write('notifications/initialized')
        self.wait(lambda: self.instance.state == 'READY')
        return response

    def close(self):
        if self.closed:
            return
        self.closed = True
        os.close(self.writer)
        self.thread.join(4)
        if self.thread.is_alive():
            raise AssertionError('fixture did not stop; no forced kill allowed')
        child = self.instance.child
        if child is not None:
            child.wait(timeout=3)
            for stream in (child.stdin, child.stdout):
                if stream and not stream.closed:
                    stream.close()
        for fd in (self.reader, self.output_reader, self.output_writer):
            os.close(fd)


class StableRelay(unittest.TestCase):
    def setUp(self):
        # macOS has a short Unix socket pathname limit. This disposable home
        # must leave room for both exact client namespaces without weakening it.
        parent = Path('/private/tmp' if sys.platform == 'darwin' else '/tmp')
        for attempt in range(100):
            self.home = parent / ('g' + uuid.uuid4().hex[:2])
            try:
                self.home.mkdir(mode=0o700)
                break
            except FileExistsError:
                continue
        else:
            self.fail('no short exclusive fixture home available')
        self.addCleanup(shutil.rmtree, self.home)
        self.patch_home = patch.object(Path, 'home', return_value=self.home)
        self.patch_home.start()
        self.addCleanup(self.patch_home.stop)
        self.script = self.home/'fake.py'
        self.script.write_text(FAKE)
        self.events = self.home/'events.jsonl'
        self.count = 0
        catalog = self.catalog_value()
        names = [tool['name'] for tool in catalog['tools']]
        contract._VERIFIED_TYPED_INDEX = {'schema':'golem.typed-interface-inventory.v1',
            'profiles':{profile:names for profile in ('read','prepare','task','quality','parallel')},
            'tools':{tool['name']:copy.deepcopy(tool) for tool in catalog['tools']}}
        self.catalog = self.write('catalog.json', catalog)
        self.store = self.home/'store'

    def write(self, name, value):
        path = self.home/name
        raw = contract.canonical(value)
        path.write_bytes(raw)
        path.chmod(0o600)
        return path

    def catalog_value(self):
        tools = [{'name': name, 'description': 'Synthetic typed tool; visibility grants no authority.',
            'inputSchema': {'type': 'object', 'properties': {'request_id': {'type': 'string'}}},
            'annotations': {'readOnlyHint': False, 'destructiveHint': True,
                            'idempotentHint': False, 'openWorldHint': False}}
            for name in ('golem_blocked', 'golem_echo', 'golem_hold')]
        return {'schema': 'golem.fixed-tool-catalog.v1', 'profile': 'task',
                'tools': tools, 'tools_sha256': contract.digest(contract.canonical(tools))}

    def selection(self, label, client='codex', mode='normal', delay=0, prior=None):
        self.count += 1
        state = self.home/('state-'+str(self.count))
        state.mkdir(mode=0o700)
        launcher = self.write('launcher-'+str(self.count)+'.json', {'command': sys.executable,
            'args': ['-I', '-B', str(self.script), label, str(self.events), mode, str(delay),
                     contract.digest(self.catalog.read_bytes())]})
        adapter.configure(state, launcher, contract.digest(launcher.read_bytes()), True, client)
        approval = adapter.inspect_state(state, client)
        return self.write('selection-'+str(self.count)+'.json', {
            'schema': 'golem.stable-selection.v1', 'client': client,
            'revision': prior['selection']['revision']+1 if prior else 1,
            'previous_sha256': prior['selection_sha256'] if prior else None,
            'catalog_sha256': contract.digest(self.catalog.read_bytes()),
            'adapter_state': str(state), 'approval_sha256': approval['approval_sha256'],
            'launcher_sha256': approval['launcher_sha256']})

    def create(self, label='old', client='codex', mode='normal', delay=0):
        selection = self.selection(label, client, mode, delay)
        return contract.create(self.store, self.catalog, contract.digest(self.catalog.read_bytes()),
            selection, contract.digest(selection.read_bytes()), True, adapter)

    def publish(self, label='new', client='codex', mode='normal', delay=0):
        before = contract.inspect(self.store, client, adapter)
        selection = self.selection(label, client, mode, delay, before)
        return contract.publish(self.store, selection, contract.digest(selection.read_bytes()),
                                 before['head_sha256'], True, adapter)

    def running(self, client='codex', timeout=.8, capabilities=None):
        running = Running(self.store, client, timeout)
        self.addCleanup(running.close)
        running.initialize(capabilities)
        return running

    def control(self, running, operation, arguments):
        return relay.request(running.instance.client, running.instance.instance, operation, arguments)

    def refresh(self, running, target):
        return self.control(running, 'refresh', {'expected_selection_sha256': running.instance.selection_sha256,
            'target_selection_sha256': target['selection_sha256'],
            'expected_definition_marker': running.instance.definition_marker()})

    def events_read(self):
        return [json.loads(line) for line in self.events.read_text().splitlines()] if self.events.exists() else []

    def test_fixed_catalog_is_local_and_definitions_do_not_authorize_backend_call(self):
        self.create()
        running = self.running()
        running.write('tools/list', 2)
        result = running.read()['result']
        self.assertEqual([t['name'] for t in result['tools']], ['golem_blocked','golem_echo','golem_hold'])
        self.assertFalse(result['_meta']['catalog_authorizes_execution'])
        running.write('tools/call', 3, {'name':'golem_blocked','arguments':{'request_id':'r1'}})
        response = running.read()
        self.assertTrue(response['result']['isError'])
        self.assertEqual(response['result']['content'][0]['text'], 'OWNER_ACTION_NOT_ALLOWED')
        self.assertEqual(sum(e.get('method')=='tools/list' for e in self.events_read()),0)
        self.assertEqual(sum(e.get('method')=='tools/call' for e in self.events_read()),1)
        started=next(e for e in self.events_read() if e['kind']=='start')
        self.assertEqual(started['abi'],'golem.fixed-tool-catalog.v1')
        self.assertEqual(started['profile'],'task')
        self.assertEqual(json.loads(started['tools']),['blocked','echo','hold'])

    def test_policy_transition_preserves_definitions_marker_and_front_transport_without_relist(self):
        self.create()
        running = self.running()
        running.write('tools/list', 2)
        original = running.read()['result']
        instance = running.instance.instance
        child_pid = running.instance.child.pid
        target = self.publish()
        response = self.refresh(running, target)
        self.assertTrue(response['ok'],response)
        self.assertEqual(response['value']['backend_epoch'],2)
        self.assertFalse(response['value']['host_reload_required'])
        self.assertFalse(response['value']['new_host_tools_list_required'])
        self.assertEqual(instance,running.instance.instance)
        self.assertNotEqual(child_pid,running.instance.child.pid)
        self.assertEqual(original['_meta']['golemStableCatalogMarker'],running.instance.definition_marker())
        self.assertEqual(response['value']['frontend_catalog']['requests'],1)
        # The next existing typed call works without another host list or reload.
        running.write('tools/call', 3, {'name':'golem_echo','arguments':{}})
        self.assertEqual(running.read()['result']['content'][0]['text'],'new')
        running.write('tools/list',4)
        self.assertEqual(running.read()['result'],original)
        events=self.events_read()
        self.assertLess(next(i for i,e in enumerate(events) if e['label']=='old' and e['kind']=='exit'),
                        next(i for i,e in enumerate(events) if e['label']=='new' and e['kind']=='start'))
        self.assertEqual(sum(e.get('method')=='initialize' and e['label']=='new' for e in events),1)
        self.assertEqual(sum(e.get('method')=='tools/list' for e in events),0)

    def test_two_connections_only_exact_target_switches_other_calls_block_stale(self):
        self.create()
        first,second=self.running(),self.running()
        second_pid=second.instance.child.pid
        target=self.publish()
        self.assertTrue(self.refresh(first,target)['ok'])
        self.assertEqual(second.instance.child.pid,second_pid)
        self.assertNotEqual(second.instance.selection_sha256,target['selection_sha256'])
        second.write('tools/call',2,{'name':'golem_echo','arguments':{}})
        blocked=second.read()
        self.assertEqual(blocked['error']['message'],'STABLE_SELECTION_STALE')
        self.assertFalse(blocked['error']['data']['dispatched'])
        second.write('tools/list',3)
        self.assertEqual(len(second.read()['result']['tools']),3)
        self.assertEqual(sum(e.get('method')=='tools/call' for e in self.events_read()),0)

    def test_claude_client_namespace_and_child_environment_are_separate(self):
        self.create(client='claude-desktop')
        running=self.running('claude-desktop')
        result=self.control(running,'status',{})['value']
        self.assertEqual(result['client'],'claude-desktop')
        self.assertEqual([r['instance'] for r in relay.descriptors('claude-desktop')],[running.instance.instance])
        self.assertEqual(relay.descriptors('codex'),[])
        self.assertEqual({e['client'] for e in self.events_read()},{'claude-desktop'})
        with self.assertRaises(FileNotFoundError):relay.request('codex',running.instance.instance,'status',{})

    def test_backend_catalog_notifications_are_evidence_only_not_host_abi_changes(self):
        self.create(mode='notifycall')
        running=self.running()
        running.write('tools/call',2,{'name':'golem_echo','arguments':{}})
        self.assertEqual(running.read()['result']['content'][0]['text'],'old')
        running.wait(lambda:running.instance.backend_catalog_notifications==1)
        running.write('tools/list',3)
        original=running.read()['result']
        target=self.publish(mode='notifycall')
        response=self.refresh(running,target)
        self.assertTrue(response['ok'],response)
        running.write('tools/call',4,{'name':'golem_echo','arguments':{}})
        self.assertEqual(running.read()['result']['content'][0]['text'],'new')
        running.wait(lambda:running.instance.backend_catalog_notifications==2)
        self.assertEqual(running.instance.definition_result,original)
        self.assertEqual(running.instance.catalog_generation,1)

    def test_unknown_tool_and_arbitrary_rpc_never_dispatch(self):
        self.create();running=self.running()
        for index,(method,params,code) in enumerate([
            ('tools/call',{'name':'shell_exec','arguments':{}},'STABLE_TOOL_NOT_IN_CATALOG'),
            ('tools/call',{'name':['golem_echo']},'STABLE_TOOL_NOT_IN_CATALOG'),
            ('arbitrary/exec',{},'STABLE_METHOD_UNSUPPORTED'),
            ('resources/read',{},'STABLE_METHOD_UNSUPPORTED')],2):
            running.write(method,index,params)
            self.assertEqual(running.read()['error']['message'],code)
        self.assertEqual(sum(e.get('method') not in ('initialize','notifications/initialized')
                             for e in self.events_read() if e['kind']=='message'),0)

    def test_catalog_cursor_not_silently_ignored(self):
        self.create();running=self.running()
        running.write('tools/list',2,{'cursor':'unknown'})
        self.assertEqual(running.read()['error']['message'],'STABLE_CATALOG_CURSOR_UNSUPPORTED')

    def test_child_sampling_request_and_client_capabilities_are_not_forwarded(self):
        self.create(mode='sampling');running=self.running(capabilities={'sampling':{},'roots':{'listChanged':True}})
        running.wait(lambda:any(e.get('id')=='child-1' and e.get('method') is None
                                for e in self.events_read()))
        initialized=next(e for e in self.events_read() if e.get('method')=='initialize')
        self.assertEqual(initialized['params']['capabilities'],{})
        running.write('tools/call',2,{'name':'golem_echo','arguments':{}})
        response=running.read()
        self.assertEqual(response['id'],2)  # No sampling request reached the host.
        self.assertEqual(response['result']['content'][0]['text'],'old')
        self.assertFalse(running.instance.server_pending)

    def test_unsupported_notification_during_drain_blocks_target_start(self):
        self.create(mode='eofbad');running=self.running();target=self.publish()
        response=self.refresh(running,target)
        self.assertFalse(response['ok'])
        self.assertEqual(response['code'],'STABLE_BACKEND_METHOD_UNSUPPORTED')
        self.assertEqual(running.instance.state,'UNKNOWN')
        self.assertFalse(any(e['kind']=='start' and e['label']=='new' for e in self.events_read()))

    def test_busy_and_partial_frames_block_before_old_child_eof(self):
        self.create();running=self.running();target=self.publish()
        running.instance.pending.add(('int',99))
        response=self.refresh(running,target)
        self.assertFalse(response['ok']);self.assertEqual(response['code'],'REFRESH_BUSY')
        running.instance.pending.clear()
        running.instance.client_buffer.extend(b'{')
        response=self.refresh(running,target)
        self.assertFalse(response['ok']);self.assertEqual(response['code'],'REFRESH_TRANSPORT_BUSY')
        running.instance.client_buffer.clear()
        self.assertFalse(any(e['kind']=='eof' for e in self.events_read()))

    def test_wrong_target_or_expected_selection_never_stops_child(self):
        self.create();running=self.running();target=self.publish()
        for expected,target_sha in [('a'*64,target['selection_sha256']),
                                    (running.instance.selection_sha256,'b'*64)]:
            response=self.control(running,'refresh',{'expected_selection_sha256':expected,
                'target_selection_sha256':target_sha,
                'expected_definition_marker':running.instance.definition_marker()})
            self.assertFalse(response['ok'])
        self.assertFalse(any(e['kind']=='eof' for e in self.events_read()))

    def test_wrong_marker_never_stops_child_or_uses_target(self):
        self.create();running=self.running();target=self.publish()
        marker=running.instance.definition_marker()
        response=self.control(running,'refresh',{'expected_selection_sha256':running.instance.selection_sha256,
            'target_selection_sha256':target['selection_sha256'],
            'expected_definition_marker':marker[:-1]+('a' if marker[-1]!='a' else 'b')})
        self.assertFalse(response['ok'])
        self.assertEqual(response['code'],'STABLE_REFRESH_MARKER_CHANGED')
        self.assertEqual(running.instance.child_generation,1)
        self.assertFalse(any(e['kind']=='eof' for e in self.events_read()))

    def test_catalog_change_blocks_before_drain(self):
        self.create();running=self.running();target=self.publish()
        original=contract.inspect
        def changed(*args,**kwargs):
            value=original(*args,**kwargs)
            value['catalog_sha256']='f'*64
            return value
        with patch.object(contract,'inspect',side_effect=changed):response=self.refresh(running,target)
        self.assertFalse(response['ok']);self.assertEqual(response['code'],'STABLE_CATALOG_CHANGED')
        self.assertFalse(any(e['kind']=='eof' for e in self.events_read()))

    def test_drain_failure_is_unknown_and_never_starts_target_or_retries(self):
        self.create(delay=.2);running=self.running(timeout=.03);target=self.publish()
        response=self.refresh(running,target)
        self.assertFalse(response['ok']);self.assertEqual(running.instance.state,'UNKNOWN')
        self.assertFalse(any(e['kind']=='start' and e['label']=='new' for e in self.events_read()))
        again=self.refresh(running,target)
        self.assertFalse(again['ok']);self.assertEqual(again['code'],'REFRESH_NOT_READY')
        running.write('tools/call',2,{'name':'golem_echo','arguments':{}})
        self.assertEqual(running.read()['error']['message'],'GOLEM_RELAY_UNKNOWN')

    def test_initialize_capability_change_is_unknown_no_rollback(self):
        self.create();running=self.running();target=self.publish(mode='caps-change')
        response=self.refresh(running,target)
        self.assertFalse(response['ok']);self.assertEqual(running.instance.state,'UNKNOWN')
        self.assertEqual(sum(e['kind']=='start' and e['label']=='old' for e in self.events_read()),1)

    def test_missing_initial_backend_abi_is_unknown_without_public_initialize_success(self):
        self.create(mode='abi-missing')
        running=Running(self.store,'codex');self.addCleanup(running.close)
        running.wait(lambda:running.instance.child is not None)
        running.write('initialize',1,{'protocolVersion':'2025-06-18','capabilities':{}})
        response=running.read()
        self.assertEqual(response['error']['message'],'STABLE_BACKEND_ABI_MISMATCH')
        running.wait(lambda:running.instance.state=='UNKNOWN')
        self.assertIsNone(running.instance.initial_result)

    def test_changed_replacement_backend_abi_is_unknown(self):
        self.create();running=self.running();target=self.publish(mode='abi-mismatch')
        response=self.refresh(running,target)
        self.assertFalse(response['ok'])
        self.assertEqual(response['code'],'CHILD_CAPABILITY_CHANGED')
        self.assertEqual(running.instance.state,'UNKNOWN')

    def test_initialize_failure_is_unknown_and_preserves_target_attempt(self):
        self.create();running=self.running();target=self.publish(mode='init-error')
        response=self.refresh(running,target)
        self.assertFalse(response['ok'])
        self.assertEqual(running.instance.state,'UNKNOWN')
        self.assertIn(target['selection_sha256'],running.instance.refresh_attempted)
        self.assertEqual(sum(e['kind']=='start' for e in self.events_read()),2)
        self.assertFalse(self.refresh(running,target)['ok'])
        self.assertEqual(sum(e['kind']=='start' for e in self.events_read()),2)

    def test_head_change_during_replacement_handshake_is_unknown_not_ready(self):
        self.create();running=self.running();target=self.publish()
        original=running.instance.replacement_initialize
        def changed():
            original()
            self.publish(label='unselected-third')
        with patch.object(running.instance,'replacement_initialize',side_effect=changed):
            response=self.refresh(running,target)
        self.assertFalse(response['ok'])
        self.assertEqual(response['code'],'STABLE_TARGET_CHANGED_DURING_INITIALIZE')
        self.assertEqual(running.instance.state,'UNKNOWN')
        self.assertFalse(any(e['kind']=='start' and e['label']=='unselected-third'
                             for e in self.events_read()))

    def test_inflight_forwarded_call_blocks_refresh_and_is_not_replayed(self):
        self.create();running=self.running()
        running.write('tools/call',2,{'name':'golem_hold','arguments':{}})
        running.wait(lambda:bool(running.instance.pending))
        target=self.publish()
        response=self.refresh(running,target)
        self.assertFalse(response['ok'])
        self.assertEqual(response['code'],'REFRESH_BUSY')
        self.assertEqual(running.read()['result']['content'][0]['text'],'old')
        self.assertEqual(sum(e.get('method')=='tools/call' for e in self.events_read()),1)
        self.assertFalse(any(e['kind']=='eof' for e in self.events_read()))

    def test_publication_cannot_interleave_head_check_and_pipe_dispatch(self):
        self.create();running=self.running()
        checked=threading.Event();attempted=threading.Event();finished=threading.Event()
        outcomes=[];timeline=[]
        original_check=running.instance.require_snapshot
        original_send=running.instance.send_child
        def checked_snapshot(snapshot):
            original_check(snapshot);checked.set()
            self.assertTrue(attempted.wait(1))
            self.assertTrue(finished.wait(1))
            self.assertEqual(str(outcomes[0]),'STORE_BUSY')
        def send_child(message):
            if message.get('method')=='tools/call':timeline.append('dispatch')
            return original_send(message)
        def publish():
            try:
                if not checked.wait(1):raise AssertionError('no admission checkpoint')
                attempted.set();outcomes.append(self.publish());timeline.append('published')
            except Exception as error:outcomes.append(error)
            finally:finished.set()
        publisher=threading.Thread(target=publish);publisher.start()
        try:
            with patch.object(running.instance,'require_snapshot',side_effect=checked_snapshot), \
                    patch.object(running.instance,'send_child',side_effect=send_child):
                running.write('tools/call',2,{'name':'golem_echo','arguments':{}})
                self.assertEqual(running.read()['result']['content'][0]['text'],'old')
            self.assertTrue(finished.wait(2))
            self.assertEqual(timeline,['dispatch'])
            self.assertIsInstance(outcomes[0],contract.ContractError)
            self.assertEqual(contract.inspect(self.store,'codex',adapter)['selection_sha256'],
                             running.instance.selection_sha256)
            # A separate explicit publication after admission has ended may
            # succeed; it must block the next call on this old connection.
            self.publish()
            running.write('tools/call',3,{'name':'golem_echo','arguments':{}})
            self.assertEqual(running.read()['error']['message'],'STABLE_SELECTION_STALE')
            self.assertEqual(sum(e.get('method')=='tools/call' for e in self.events_read()),1)
        finally:publisher.join(3)

    def test_request_nonce_replay_and_client_mismatch_block(self):
        self.create();running=self.running()
        request={'schema':relay.SCHEMA,'client':'codex','instance':running.instance.instance,
                 'token':running.instance.token,'request_id':'a'*32,'operation':'status','arguments':{}}
        running.instance.control(request)
        with self.assertRaisesRegex(relay.legacy.RelayError,'CONTROL_REPLAY_OR_QUOTA'):
            running.instance.control(request)
        request.update(client='claude-desktop',request_id='b'*32)
        with self.assertRaisesRegex(relay.legacy.RelayError,'CONTROL_AUTH'):running.instance.control(request)

    def test_lost_refresh_reply_is_not_repeated_or_rolled_back(self):
        self.create();running=self.running();target=self.publish()
        original_selection=running.instance.selection_sha256
        record=relay._record('codex',running.instance.instance)
        path=relay._directory('codex')/(running.instance.instance+'.sock')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
            conn.connect(str(path))
            relay.legacy.frame_send(conn,{'schema':relay.SCHEMA,'client':'codex',
                'instance':running.instance.instance,'token':record['token'],'request_id':'c'*32,
                'operation':'refresh','arguments':{'expected_selection_sha256':original_selection,
                'target_selection_sha256':target['selection_sha256'],
                'expected_definition_marker':running.instance.definition_marker()}})
            # Deliberately do not receive the response. Only status may follow.
        running.wait(lambda:running.instance.selection_sha256==target['selection_sha256'])
        status=self.control(running,'status',{})
        self.assertEqual(status['value']['backend_epoch'],2)
        self.assertEqual(sum(e['kind']=='start' and e['label']=='new' for e in self.events_read()),1)
        # A caller trying a fresh control nonce with the old expectation is denied.
        blocked=self.control(running,'refresh',{'expected_selection_sha256':original_selection,
            'target_selection_sha256':target['selection_sha256'],
            'expected_definition_marker':running.instance.definition_marker()})
        self.assertFalse(blocked['ok'])
        self.assertEqual(sum(e['kind']=='start' and e['label']=='new' for e in self.events_read()),1)

    def test_normal_close_preserves_descriptor_and_only_removes_own_socket(self):
        self.create();running=self.running()
        instance=running.instance.instance
        running.close()
        self.assertEqual(relay.endpoint('codex',instance)['endpoint_state'],'ABSENT')
        self.assertTrue((relay._directory('codex')/(instance+'.json')).is_file())

    def test_v2_marker_never_reinterprets_legacy_marker(self):
        value='golem-catalog-v2:'+'a'*32+':'+'b'*64+':'+'c'*32
        self.assertEqual(relay.parse_definition_marker(value),{'instance':'a'*32,
            'catalog_sha256':'b'*64,'definition_nonce':'c'*32})
        for invalid in ('golem-connection-v1:'+'a'*32+':1:1:'+'c'*32,{},value+'x'):
            with self.assertRaisesRegex(relay.legacy.RelayError,'STABLE_DEFINITION_MARKER_INVALID'):
                relay.parse_definition_marker(invalid)


if __name__=='__main__':unittest.main()
