"""Optional official-host regression with a local fake model and fake backend.

CI without GOLEM_TEST_CODEX_BINARY explicitly skips this test. Set that variable
to an absolute, locally available Codex executable to opt in. This is not a
Desktop GUI, external-model, native Work or installed-client E2E test. All host
configuration, credentials namespace, relay descriptors and selection records
are disposable. Only normal stdin EOF is used to stop the fixture host.
"""
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import integration_stable_catalog as builder


BINARY = os.environ.get('GOLEM_TEST_CODEX_BINARY')
SOURCE = Path(__file__).resolve().parents[1] / 'plugins/golem/scripts'
PROGRAMS = ('launcher.py', 'connection_relay.py', 'stable_contract.py', 'stable_relay.py')

FAKE_BACKEND = r'''
import json,os,sys
from pathlib import Path
root,version,abi=sys.argv[1:]
def log(**fields):
    with (Path(root)/'backend-events.jsonl').open('a') as out:
        out.write(json.dumps(dict(version=version,pid=os.getpid(),**fields))+'\n')
for line in sys.stdin:
    message=json.loads(line);method=message.get('method')
    log(method=method,id=message.get('id'))
    if method=='initialize':
        result={'protocolVersion':message['params']['protocolVersion'],
                'capabilities':{'tools':{},'experimental':{'golem.fixed-tool-catalog.v1':{'catalog_sha256':abi}}},
                'serverInfo':{'name':'disposable-backend','version':version}}
    elif method=='tools/call' and message['params']['name']=='golem_projects_list':
        result={'content':[{'type':'text','text':'DISPOSABLE_BACKEND_'+version}]}
    elif 'id' not in message:
        continue
    else:
        print(json.dumps({'jsonrpc':'2.0','id':message['id'],'error':{'code':-32601,'message':'fixture only'}}),flush=True)
        continue
    print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}),flush=True)
log(event='EOF_EXIT')
'''

FIXTURE_ENTRY = r'''
import importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
package,store=sys.argv[1:]
def load(name):
    spec=importlib.util.spec_from_file_location(name,Path(package)/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
adapter,contract,relay=load('launcher'),load('stable_contract'),load('stable_relay')
# An explicit source-derived fixture inventory, never a production fallback.
contract._VERIFIED_TYPED_INDEX=json.loads((Path(package)/'typed-interface.json').read_text())
relay.serve(adapter,contract,store,'codex')
'''


def load(name, path):
    spec = importlib.util.spec_from_file_location('host_fixture_' + name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def response_events(index):
    """Four deterministic fake Responses replies; no real model is contacted."""
    if index in (1, 3):
        item = {'id':f'fc_{index}', 'type':'function_call', 'status':'completed',
                'call_id':f'call_{index}', 'namespace':'mcp__golem_local',
                'name':'golem_projects_list', 'arguments':'{}'}
        events = [
            {'type':'response.output_item.added', 'output_index':0,
             'item':{**item, 'status':'in_progress', 'arguments':''}},
            {'type':'response.function_call_arguments.delta', 'item_id':item['id'], 'output_index':0, 'delta':'{}'},
            {'type':'response.function_call_arguments.done', 'item_id':item['id'], 'output_index':0, 'arguments':'{}'},
            {'type':'response.output_item.done', 'output_index':0, 'item':item}]
    else:
        part = {'type':'output_text', 'text':'Disposable fixture complete.', 'annotations':[]}
        item = {'id':f'msg_{index}', 'type':'message', 'role':'assistant', 'status':'completed', 'content':[part]}
        events = [
            {'type':'response.output_item.added', 'output_index':0,
             'item':{**item, 'status':'in_progress', 'content':[]}},
            {'type':'response.content_part.added', 'item_id':item['id'], 'output_index':0,
             'content_index':0, 'part':{**part, 'text':''}},
            {'type':'response.output_text.delta', 'item_id':item['id'], 'output_index':0,
             'content_index':0, 'delta':part['text']},
            {'type':'response.output_text.done', 'item_id':item['id'], 'output_index':0,
             'content_index':0, 'text':part['text']},
            {'type':'response.content_part.done', 'item_id':item['id'], 'output_index':0,
             'content_index':0, 'part':part},
            {'type':'response.output_item.done', 'output_index':0, 'item':item}]
    response = {'id':f'resp_{index}', 'object':'response', 'created_at':int(time.time()),
                'model':'fixture', 'status':'completed', 'output':[item],
                'usage':{'input_tokens':0, 'output_tokens':0, 'total_tokens':0,
                         'input_tokens_details':{'cached_tokens':0}, 'output_tokens_details':{'reasoning_tokens':0}}}
    return [{'type':'response.created', 'response':{**response, 'status':'in_progress', 'output':[]}},
            *events, {'type':'response.completed', 'response':response}]


@unittest.skipUnless(BINARY and os.name == 'posix',
    'NOT_RUN: set GOLEM_TEST_CODEX_BINARY to explicitly enable the isolated official-host fixture')
class OfficialHost(unittest.TestCase):
    def setUp(self):
        candidate = Path(BINARY)
        self.assertTrue(candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK),
                        'GOLEM_TEST_CODEX_BINARY must name an existing executable by absolute path')
        self.binary = candidate.resolve()
        # Short private home also bounds the Unix control endpoint pathname.
        temporary_parent = '/private/tmp' if sys.platform == 'darwin' else '/tmp'
        self.root = Path(tempfile.mkdtemp(prefix='sh-', dir=temporary_parent)).resolve()
        self.root.chmod(0o700)
        self.process = self.server = self.log = None
        self.deadline = time.monotonic() + 120
        self.events, self.requests, self.http_errors = [], [], []
        self.queue = queue.Queue()
        self.sequence = 0
        self.addCleanup(self.cleanup)

    def cleanup(self):
        stopped = True
        if self.process is not None:
            if not self.process.stdin.closed:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                stopped = False
            if stopped:
                self.process.stdout.close()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.log is not None:
            self.log.close()
        if not stopped:
            self.fail(f'Fixture host did not exit on EOF; no signal sent; evidence preserved at {self.root}')
        shutil.rmtree(self.root)

    def write(self, name, value):
        path = self.root / name
        path.write_bytes(builder.encoded(value))
        path.chmod(0o600)
        return path

    def prepare(self):
        package = self.root / 'package'
        package.mkdir(mode=0o700)
        for name in PROGRAMS:
            shutil.copyfile(SOURCE / name, package / name)
            (package / name).chmod(0o600)
        (package / 'typed-interface.json').write_bytes(builder.encoded(builder.typed_inventory()))
        (package / 'typed-interface.json').chmod(0o600)
        self.adapter = load('launcher', package / 'launcher.py')
        self.contract = load('stable_contract', package / 'stable_contract.py')
        self.contract._VERIFIED_TYPED_INDEX = builder.typed_inventory()
        self.relay = load('stable_relay', package / 'stable_relay.py')
        self.catalog = self.write('catalog.json', builder.catalog('read', ['projects_list']))
        self.store = self.root / 'store'
        (self.root / 'fake-backend.py').write_text(FAKE_BACKEND)
        (self.root / 'fixture-entry.py').write_text(FIXTURE_ENTRY)
        initial = self.selection('old')
        self.old = self.contract.create(self.store, self.catalog, sha(self.catalog),
            initial, sha(initial), True, self.adapter)
        self.new = self.selection('new', self.old)
        self.args = ['-I', '-B', str(self.root / 'fixture-entry.py'), str(package), str(self.store)]

    def selection(self, label, previous=None):
        state = self.root / (label + '-state')
        state.mkdir(mode=0o700)
        launcher = self.write(label + '-launcher.json', {'command':sys.executable,
            'args':['-I', '-B', str(self.root / 'fake-backend.py'), str(self.root), label, sha(self.catalog)]})
        self.adapter.configure(state, launcher, sha(launcher), True, 'codex')
        approval = self.adapter.inspect_state(state, 'codex')
        return self.write(label + '-selection.json', {
            'schema':'golem.stable-selection.v1', 'client':'codex', 'revision':2 if previous else 1,
            'previous_sha256':previous['selection_sha256'] if previous else None,
            'catalog_sha256':sha(self.catalog), 'adapter_state':str(state),
            'approval_sha256':approval['approval_sha256'], 'launcher_sha256':approval['launcher_sha256']})

    def start(self):
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                try:
                    self.connection.settimeout(5)
                    size = int(self.headers.get('Content-Length', '0'))
                    assert 0 < size < 4 * 1024 * 1024
                    raw = self.rfile.read(size)
                    if self.headers.get('Content-Encoding') == 'gzip':
                        raw = gzip.decompress(raw)
                    assert len(raw) < 4 * 1024 * 1024
                    fixture.requests.append(json.loads(raw))
                    index = len(fixture.requests)
                    assert index <= 4, 'No additional model requests are permitted'
                    output = ''.join('event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n'
                                     for e in response_events(index)).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Content-Length', str(len(output)))
                    self.end_headers()
                    self.wfile.write(output)
                    self.wfile.flush()
                except Exception as error:
                    fixture.http_errors.append(repr(error))
                    self.send_error(500)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        codex_directory = self.root / 'codex-home'
        codex_directory.mkdir(mode=0o700)
        self.config = codex_directory / 'config.toml'
        self.config.write_text(
            'model_provider = "fixture"\nmodel = "fixture"\nmcp_optional_startup_grace_ms = 0\n'
            '[model_providers.fixture]\nname = "fixture"\nbase_url = "http://127.0.0.1:' +
            str(self.server.server_port) + '/v1"\nwire_api = "responses"\nrequires_openai_auth = false\n'
            '[mcp_servers.golem-local]\ncommand = ' + json.dumps(sys.executable) + '\nargs = ' +
            json.dumps(self.args) + '\nstartup_timeout_sec = 15\n')
        self.config.chmod(0o600)
        self.config_sha = sha(self.config)
        self.log = (self.root / 'host-stderr.log').open('w')
        # Child-only, isolated directories; do not inherit API keys, auth state,
        # client settings, shell env, proxy config or production MCP entries.
        environment = {'PATH':'/usr/bin:/bin', 'HOME':str(self.root),
                       'CODEX_HOME':str(codex_directory), 'TMPDIR':str(self.root)}
        self.process = subprocess.Popen([str(self.binary), 'app-server', '--listen', 'stdio://'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True, bufsize=1,
            cwd=self.root, env=environment)
        def read():
            for line in self.process.stdout:
                try:
                    self.queue.put(json.loads(line))
                except Exception:
                    self.queue.put({'invalid_stdout':line[:1024]})
        threading.Thread(target=read, daemon=True).start()

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + '\n')
        self.process.stdin.flush()

    def next_event(self, timeout):
        remaining = min(self.deadline, timeout) - time.monotonic()
        self.assertGreater(remaining, 0, 'Fixture deadline exceeded; no automatic retry')
        event = self.queue.get(timeout=remaining)
        self.events.append(event)
        self.assertLess(len(self.events), 2048)
        return event

    def call(self, method, params):
        self.sequence += 1
        self.send({'id':self.sequence, 'method':method, 'params':params})
        deadline = time.monotonic() + 25
        while True:
            event = self.next_event(deadline)
            if event.get('id') == self.sequence:
                self.assertNotIn('error', event, event)
                return event['result']

    def turn(self, thread):
        reply = self.call('turn/start', {'threadId':thread, 'input':[{'type':'text',
            'text':'Disposable protocol fixture. Call the fake projects_list tool once, then finish.'}]})
        turn_id = reply['turn']['id']
        deadline = time.monotonic() + 30
        while True:
            event = self.next_event(deadline)
            if event.get('method') == 'turn/completed':
                self.assertEqual(event['params']['turn']['id'], turn_id)
                return turn_id

    def observation(self, index):
        namespaces = [tool for tool in self.requests[index].get('tools', [])
                      if tool.get('type') == 'namespace' and tool.get('name') == 'mcp__golem_local']
        self.assertEqual(len(namespaces), 1)
        definitions = namespaces[0]['tools']
        markers = [marker for tool in definitions for marker in re.findall(
            r'golem-catalog-v2:[a-f0-9]{32}:[a-f0-9]{64}:[a-f0-9]{32}', tool.get('description', ''))]
        self.assertEqual(len(set(markers)), 1)
        return markers[0], definitions

    def control(self, marker, operation, args):
        instance = self.relay.parse_definition_marker(marker)['instance']
        with patch.object(Path, 'home', return_value=self.root):
            result = self.relay.request('codex', instance, operation, args)
        self.assertTrue(result['ok'], result)
        return result['value']

    def test_same_thread_and_catalog_accept_new_backend_without_host_reload(self):
        self.prepare()
        self.start()
        self.call('initialize', {'clientInfo':{'name':'stable_fixture', 'version':'1'},
                                 'capabilities':{'experimentalApi':True}})
        self.send({'method':'initialized', 'params':{}})
        created = self.call('thread/start', {'ephemeral':True, 'cwd':str(self.root),
            'modelProvider':'fixture', 'model':'fixture', 'approvalPolicy':'never', 'sandbox':'read-only',
            'baseInstructions':'Only the disposable fake MCP projects_list tool may be called. No other tools.'})
        thread = created['thread']['id']
        self.turn(thread)
        self.assertEqual(len(self.requests), 2)
        marker, definitions = self.observation(0)
        before = self.control(marker, 'status', {})
        self.assertIn('DISPOSABLE_BACKEND_old', json.dumps(self.requests[1].get('input', [])))
        target = self.contract.publish(self.store, self.new, sha(self.new),
            self.old['head_sha256'], True, self.adapter)
        self.control(marker, 'refresh', {'expected_selection_sha256':self.old['selection_sha256'],
            'target_selection_sha256':target['selection_sha256'], 'expected_definition_marker':marker})
        self.turn(thread)
        self.assertEqual(len(self.requests), 4)
        self.assertEqual(self.observation(2), (marker, definitions))
        self.assertIn('DISPOSABLE_BACKEND_new', json.dumps(self.requests[3].get('input', [])))
        after = self.control(marker, 'status', {})
        self.assertEqual((before['pid'], before['instance']), (after['pid'], after['instance']))
        self.assertNotEqual(before['child_pid'], after['child_pid'])
        self.assertEqual(after['backend_epoch'], before['backend_epoch'] + 1)
        self.assertEqual(before['frontend_catalog']['requests'], after['frontend_catalog']['requests'])
        self.assertEqual(sha(self.config), self.config_sha)
        self.assertFalse(self.http_errors)
        rows = [json.loads(line) for line in (self.root / 'backend-events.jsonl').read_text().splitlines()]
        self.assertEqual([row['version'] for row in rows if row.get('method') == 'tools/call'], ['old', 'new'])
        self.assertFalse(any(row.get('method') == 'tools/list' for row in rows))
        self.process.stdin.close()
        self.assertEqual(self.process.wait(timeout=10), 0)


if __name__ == '__main__':
    unittest.main()
