"""Opt-in fixed typed MCP catalog with separately selected backend authority.

The frontend and its definition marker survive an exact owner-selected child
transition. Catalog visibility is not permission. Every forwarded tool call
still enters the existing backend/native approval path. No generic dispatch,
automatic selection adoption, replay, rollback, host reload or GUI is provided.
"""
import copy
import contextlib
import hashlib
import hmac
import importlib.util
import itertools
import json
import os
from pathlib import Path
import re
import select
import selectors
import socket
import stat
import subprocess
import time
import uuid


def _module(name):
    path = Path(__file__).resolve().parent / (name + '.py')
    spec = importlib.util.spec_from_file_location('golem_stable_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = globals().get('_VERIFIED_LEGACY') or _module('connection_relay')
require, encoded = legacy.require, legacy.encoded
SCHEMA = 'golem.stable-connection-relay.v1'
KIND = 'golem-stable-connection-relay'
CLIENTS = ('codex', 'claude-desktop')
MARKER = re.compile(r'golem-catalog-v2:([a-f0-9]{32}):([a-f0-9]{64}):([a-f0-9]{32})\Z')


def parse_definition_marker(value):
    match = MARKER.fullmatch(value) if type(value) is str else None
    require(match is not None, 'STABLE_DEFINITION_MARKER_INVALID')
    instance, catalog_sha256, nonce = match.groups()
    return {'instance': instance, 'catalog_sha256': catalog_sha256, 'definition_nonce': nonce}


def _client(client):
    require(type(client) is str and client in CLIENTS, 'STABLE_CLIENT')
    return client


class StableRelay(legacy.Relay):
    def __init__(self, adapter, contract, store, client, **kwargs):
        self.client = _client(client)
        self.contract = contract
        self.store = adapter.canonical(store)
        snapshot = self.contract.inspect(self.store, self.client, adapter)
        self.selection = copy.deepcopy(snapshot['selection'])
        self.selection_sha256 = snapshot['selection_sha256']
        self.head_sha256 = snapshot['head_sha256']
        self.fixed_catalog = copy.deepcopy(snapshot['catalog'])
        self.fixed_catalog_sha256 = snapshot['catalog_sha256']
        self.fixed_names = frozenset(tool['name'] for tool in self.fixed_catalog['tools'])
        super().__init__(adapter, self.selection['adapter_state'], **kwargs)
        self.definition_nonce = uuid.uuid4().hex
        self.catalog_generation = 1
        self.backend_catalog_notifications = 0
        self.refresh_attempted = set()
        self.definition_result = self._definitions()
        # Include worst-case bounded RPC id, not just the catalog payload.
        require(len(encoded({'jsonrpc': '2.0', 'id': 'x' * 256,
                             'result': self.definition_result})) <= legacy.FRAME_LIMIT,
                'STABLE_CATALOG_FRAME_LIMIT')

    def definition_marker(self):
        return f'golem-catalog-v2:{self.instance}:{self.fixed_catalog_sha256}:{self.definition_nonce}'

    def _definitions(self):
        tools = copy.deepcopy(self.fixed_catalog['tools'])
        if tools:
            tools[0]['description'] += ('\n\nFixed catalog observation only; no authority: '
                                         + self.definition_marker())
        return {'tools': tools, '_meta': {'golemStableCatalogMarker': self.definition_marker(),
                                        'catalog_authorizes_execution': False}}

    def approved(self, state):
        with self.adapter.locked(state) as private:
            launcher, pin, raw = self.adapter.load_record(private, self.client)
            require(raw == self.adapter.read_private(private / 'approval.json'), 'APPROVAL_CHANGED')
        return launcher, pin, self.adapter.digest(raw)

    def historical_selection(self):
        snapshot = self.contract.inspect_record(self.store, self.client,
            self.selection['revision'], self.selection_sha256, self.adapter)
        require(snapshot['selection'] == self.selection and
                snapshot['selection_sha256'] == self.selection_sha256 and
                snapshot['catalog_sha256'] == self.fixed_catalog_sha256 and
                snapshot['catalog'] == self.fixed_catalog, 'STABLE_CURRENT_RECORD_CHANGED')
        return snapshot

    def selected_snapshot(self):
        snapshot = self.contract.inspect(self.store, self.client, self.adapter)
        require(snapshot['catalog_sha256'] == self.fixed_catalog_sha256 and
                snapshot['catalog'] == self.fixed_catalog, 'STABLE_CATALOG_CHANGED')
        return snapshot

    def require_current_selection(self):
        snapshot = self.selected_snapshot()
        self.require_snapshot(snapshot)

    def require_snapshot(self, snapshot):
        require(snapshot['catalog_sha256'] == self.fixed_catalog_sha256 and
                snapshot['catalog'] == self.fixed_catalog, 'STABLE_CATALOG_CHANGED')
        require(snapshot['selection_sha256'] == self.selection_sha256 and
                snapshot['selection'] == self.selection and
                snapshot['head_sha256'] == self.head_sha256, 'STABLE_SELECTION_STALE')
        require(self.approved(self.current_state) == (self.launcher, self.pin, self.approval_pin),
                'STABLE_APPROVAL_CHANGED')

    def start_endpoint(self):
        self.require_current_selection()
        directory = self.adapter.canonical(Path.home() / '.local/share/golem/stable-relays' / self.client)
        for parent in reversed((directory, *directory.parents)):
            if not parent.exists():
                parent.mkdir(mode=0o700)
        directory = self.adapter.directory(directory, private=True)
        self.socket_path = directory / (self.instance + '.sock')
        self.descriptor = directory / (self.instance + '.json')
        require(len(str(self.socket_path).encode()) < 104, 'CONTROL_PATH_LENGTH')
        endpoint = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            endpoint.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            endpoint.listen(4)
            endpoint.setblocking(False)
            raw = encoded(dict(schema=SCHEMA, instance=self.instance, token=self.token,
                pid=os.getpid(), kind=KIND, client=self.client))
            fd = os.open(self.descriptor, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            self.endpoint = endpoint
            self.selector.register(endpoint, selectors.EVENT_READ, 'control')
        except Exception:
            endpoint.close()
            if self.socket_path.exists():
                self.socket_path.unlink()
            raise

    def spawn(self, launcher, state, pin):
        # The legacy spawn hard-codes Codex. Preserve all other pipe/lifecycle
        # mechanics while carrying the reviewed client identity explicitly.
        environment = dict(os.environ)
        environment.update(GOLEM_LAUNCHER_SHA256=pin, GOLEM_LAUNCHER_CLIENT=self.client,
            GOLEM_LAUNCHER_STATE=str(state), GOLEM_LAUNCHER_PLUGIN_VERSION=self.adapter.ADAPTER_VERSION)
        environment.update(GOLEM_STABLE_FRONTEND_ABI='golem.fixed-tool-catalog.v1',
            GOLEM_STABLE_FRONTEND_PROFILE=self.fixed_catalog['profile'],
            GOLEM_STABLE_FRONTEND_TOOLS=json.dumps(sorted(name.removeprefix('golem_') for name in self.fixed_names),
                                                  separators=(',', ':')))
        self.child = subprocess.Popen([launcher['command'], *launcher['args']], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=None, bufsize=0, env=environment, close_fds=True)
        self.child_generation += 1
        os.set_blocking(self.child.stdout.fileno(), False)
        os.set_blocking(self.child.stdin.fileno(), False)
        self.child_buffer.clear()
        self.selector.register(self.child.stdout, selectors.EVENT_READ, 'child')

    @staticmethod
    def relay_initialize_result(message):
        # The public frontend implements a fixed tools ABI, not the backend's
        # dynamic resource/prompt catalog. Raw child caps remain recorded by
        # the inherited handshake for exact replacement comparison.
        result = {**message['result'], 'capabilities': {'tools': {'listChanged': False}},
                  'serverInfo': {'name': 'golem-stable', 'version': '1'}}
        return {**message, 'result': result}

    def deny(self, message, code, rpc_code=-32000):
        if 'id' in message:
            key = legacy.identifier(message['id'])
            require(key not in self.pending, 'RPC_REQUEST_LIMIT')
            self.send_client({'jsonrpc': '2.0', 'id': message['id'], 'error': {
                'code': rpc_code, 'message': code,
                'data': {'automatic_retry_allowed': False, 'dispatched': False}}})

    def client_message(self, message):
        if self.state == 'UNKNOWN':
            return super().client_message(message)
        method = message.get('method')
        if method is None:
            return super().client_message(message)  # Existing server request id checks.
        if method == 'initialize':
            params = message.get('params')
            require(type(params) is dict and type(params.get('capabilities')) is dict,
                    'STABLE_INITIALIZE_PARAMS')
            # The fixed tools frontend does not delegate host sampling, roots,
            # elicitation or other client capabilities to a replaceable child.
            # Save this exact forwarded request for replacement initialization.
            message = {**message, 'params': {**params, 'capabilities': {}}}
            return super().client_message(message)
        if method == 'notifications/initialized':
            return super().client_message(message)
        require(self.initialized and self.state == 'READY', 'INITIALIZATION_REQUIRED')
        if method == 'tools/list':
            require('id' in message, 'STABLE_LIST_REQUEST_ID')
            key = legacy.identifier(message['id'])
            require(key not in self.pending, 'RPC_REQUEST_LIMIT')
            params = message.get('params', {})
            if type(params) is not dict or set(params) - {'cursor', '_meta'} or params.get('cursor') is not None:
                return self.deny(message, 'STABLE_CATALOG_CURSOR_UNSUPPORTED', -32602)
            self.catalog_request_sent(message)
            response = {'jsonrpc': '2.0', 'id': message['id'], 'result': self.definition_result}
            self.send_client(response)
            self.catalog_response_sent(response)
            return
        if method not in ('tools/call', 'ping', 'notifications/cancelled'):
            return self.deny(message, 'STABLE_METHOD_UNSUPPORTED', -32601)
        if method == 'notifications/cancelled':
            params = message.get('params', {})
            if ('id' in message or type(params) is not dict or 'requestId' not in params or
                    legacy.identifier(params['requestId']) not in self.pending):
                return self.deny(message, 'STABLE_CANCEL_NOT_PENDING', -32602)
            return super().client_message(message)
        if 'id' not in message:
            return  # Notification-shaped requests cannot perform hidden calls.
        if method == 'tools/call':
            params = message.get('params')
            if (type(params) is not dict or type(params.get('name')) is not str or
                    params['name'] not in self.fixed_names):
                return self.deny(message, 'STABLE_TOOL_NOT_IN_CATALOG', -32602)
        # The SH admission lock is held through the actual pipe write. A
        # publisher cannot slip a new head between our check and dispatch.
        with contextlib.ExitStack() as admission:
            try:
                snapshot = admission.enter_context(self.contract.shared_admission(self.store,
                    self.client, self.selection_sha256, self.head_sha256, self.adapter))
                self.require_snapshot(snapshot)
            except Exception as error:
                code = str(error) if isinstance(error, (legacy.RelayError, self.adapter.SetupError,
                                                        self.contract.ContractError)) else 'STABLE_SELECTION_UNAVAILABLE'
                if code == 'ADMISSION_SELECTION_CHANGED':
                    code = 'STABLE_SELECTION_STALE'
                return self.deny(message, code)
            # Transport failures after admission must reach the inherited
            # UNKNOWN path, never a false 'dispatched:false' response.
            return super().client_message(message)

    def send_client(self, message):
        # Includes notifications encountered by inherited drain(). Backend
        # authority/catalog changes never mutate the frozen frontend ABI.
        if message.get('method') == 'notifications/tools/list_changed':
            require('id' not in message, 'STABLE_BACKEND_CATALOG_NOTIFICATION')
            self.backend_catalog_notifications = min(self.backend_catalog_notifications + 1,
                                                       legacy.CATALOG_COUNTER_LIMIT)
            return
        method = message.get('method')
        if method is not None:
            require((method == 'ping' and 'id' in message) or
                    (method in ('notifications/progress', 'notifications/message') and 'id' not in message),
                    'STABLE_BACKEND_METHOD_UNSUPPORTED')
        return super().send_client(message)

    def child_message(self, message):
        if (self.initial_request and not self.initialized and 'method' not in message and
                message.get('id') == self.initial_request['id'] and 'result' in message):
            result = message['result']
            capabilities = result.get('capabilities') if type(result) is dict else None
            experimental = capabilities.get('experimental') if type(capabilities) is dict else None
            actual = experimental.get('golem.fixed-tool-catalog.v1') if type(experimental) is dict else None
            if actual != {'catalog_sha256': self.fixed_catalog_sha256}:
                self.send_client({'jsonrpc': '2.0', 'id': message['id'], 'error': {
                    'code': -32000, 'message': 'STABLE_BACKEND_ABI_MISMATCH'}})
                self.unknown('STABLE_BACKEND_ABI_MISMATCH')
                return
        if message.get('method') == 'notifications/tools/list_changed':
            return self.send_client(message)
        if 'method' in message and 'id' in message and message['method'] != 'ping':
            # Respond directly to unsupported child requests; never expose a
            # generic server request route to the host/model. No effect retry.
            self.send_child({'jsonrpc': '2.0', 'id': message['id'], 'error': {
                'code': -32601, 'message': 'STABLE_BACKEND_METHOD_UNSUPPORTED'}})
            return
        return super().child_message(message)

    def mark_tool_definitions(self, message):
        return message  # No backend catalog is forwarded or reinterpreted.

    def status(self):
        return {'schema': SCHEMA, 'client': self.client, 'instance': self.instance,
            'frontend_abi': 'golem.fixed-tool-catalog.v1',
            'pid': os.getpid(), 'state': self.state, 'failure': self.failure,
            'busy': bool(self.pending or self.server_pending), 'pending': len(self.pending),
            'server_pending': len(self.server_pending), 'child_pid': self.child.pid if self.child else None,
            'backend_epoch': self.child_generation, 'selection_sha256': self.selection_sha256,
            'selection_revision': self.selection['revision'], 'head_sha256': self.head_sha256,
            'selected_state': str(self.current_state), 'launcher_sha256': self.pin,
            'approval_sha256': self.approval_pin, 'catalog_sha256': self.fixed_catalog_sha256,
            'catalog_tools_sha256': self.fixed_catalog['tools_sha256'],
            'definition_marker': self.definition_marker(), 'definition_tool_count': len(self.fixed_names),
            'definition_tools_sha256': self.catalog_digest(sorted(self.fixed_names)),
            'frontend_catalog': {'schema': 'golem.stable-frontend-catalog-observation.v1',
                'state': self.catalog_state, 'catalog_sha256': self.fixed_catalog_sha256,
                'requests': self.catalog_requests, 'responses': self.catalog_responses,
                'errors': self.catalog_errors,
                'current_complete_sha256': (self.catalog_current or {}).get('sha256'),
                'definition_marker': self.definition_marker(), 'model_delivery_verified': False},
            'backend_catalog_notifications': self.backend_catalog_notifications,
            'execution_authorized': False, 'model_tools_delivery_verified': False,
            'owner_identity_authenticated': False, 'work_idle_verified': False,
            'native_leases_observed': False, 'shutdown_mode': 'STDIN_EOF_WAIT_ONLY',
            'automatic_retry_allowed': False}

    def refresh(self, args):
        require(type(args) is dict and set(args) == {'expected_selection_sha256', 'target_selection_sha256',
                                                   'expected_definition_marker'},
                'STABLE_REFRESH_FIELDS')
        require(all(type(args[key]) is str and re.fullmatch('[0-9a-f]{64}', args[key])
                    for key in ('expected_selection_sha256', 'target_selection_sha256')), 'STABLE_REFRESH_DIGEST')
        require(args['expected_definition_marker'] == self.definition_marker(), 'STABLE_REFRESH_MARKER_CHANGED')
        require(self.state == 'READY' and self.initialized, 'REFRESH_NOT_READY')
        require(not self.pending and not self.server_pending, 'REFRESH_BUSY')
        require(not self.client_buffer and not self.child_buffer and
                not select.select([self.input_fd, self.child.stdout], [], [], 0)[0], 'REFRESH_TRANSPORT_BUSY')
        require(args['expected_selection_sha256'] == self.selection_sha256, 'STABLE_EXPECTED_SELECTION_CHANGED')
        require(args['target_selection_sha256'] != self.selection_sha256, 'ALREADY_SELECTED')
        require(args['target_selection_sha256'] not in self.refresh_attempted, 'STABLE_REFRESH_ALREADY_ATTEMPTED')
        self.historical_selection()
        require(self.approved(self.current_state) == (self.launcher, self.pin, self.approval_pin),
                'CURRENT_APPROVAL_CHANGED')
        target = self.selected_snapshot()
        require(target['selection_sha256'] == args['target_selection_sha256'], 'STABLE_TARGET_NOT_SELECTED')
        selection = target['selection']
        state = self.adapter.canonical(selection['adapter_state'])
        launcher, pin, approval_pin = self.approved(state)
        require((pin, approval_pin) == (selection['launcher_sha256'], selection['approval_sha256']),
                'TARGET_APPROVAL_CHANGED')
        self.refresh_attempted.add(args['target_selection_sha256'])
        self.state = 'DRAINING'
        try:
            self.drain()
            self.historical_selection()
            require(self.selected_snapshot() == target, 'STABLE_TARGET_CHANGED_DURING_DRAIN')
            require(self.approved(state) == (launcher, pin, approval_pin), 'TARGET_APPROVAL_CHANGED')
            self.state = 'STARTING'
            self.spawn(launcher, state, pin)
            self.replacement_initialize()
            self.reject_refresh_requests()
            require(not self.client_buffer, 'PARTIAL_REQUEST_DURING_REFRESH')
            require(self.selected_snapshot() == target, 'STABLE_TARGET_CHANGED_DURING_INITIALIZE')
            require(self.approved(state) == (launcher, pin, approval_pin), 'TARGET_APPROVAL_CHANGED')
            self.current_state, self.launcher, self.pin, self.approval_pin = state, launcher, pin, approval_pin
            self.selection = copy.deepcopy(selection)
            self.selection_sha256, self.head_sha256 = target['selection_sha256'], target['head_sha256']
            self.state = 'READY'
            return {**self.status(), 'refresh_result': 'CHILD_REINITIALIZED_FIXED_CATALOG',
                    'host_reload_required': False, 'new_host_tools_list_required': False}
        except Exception:
            self.unknown('STABLE_REFRESH_RESULT_UNKNOWN')
            raise

    def control(self, request):
        require(type(request) is dict and set(request) == {
            'schema', 'client', 'instance', 'token', 'request_id', 'operation', 'arguments'}, 'CONTROL_ENVELOPE')
        require(request['schema'] == SCHEMA and request['client'] == self.client and
                request['instance'] == self.instance and type(request['token']) is str and
                hmac.compare_digest(request['token'], self.token), 'CONTROL_AUTH')
        nonce = request['request_id']
        require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce), 'CONTROL_NONCE')
        require(nonce not in self.seen and len(self.seen) < legacy.REQUEST_LIMIT, 'CONTROL_REPLAY_OR_QUOTA')
        self.seen.add(nonce)
        if request['operation'] == 'status':
            require(request['arguments'] == {}, 'CONTROL_ARGUMENTS')
            return self.status()
        require(request['operation'] == 'refresh', 'CONTROL_OPERATION')
        return self.refresh(request['arguments'])

    def close(self):
        if self.child and self.child.poll() is None:
            try:
                self.drain()
            except Exception:
                self.unknown('CHILD_CLOSE_UNKNOWN')
        if self.endpoint:
            self.endpoint.close()
            if self.state != 'UNKNOWN' and self.socket_path and self.socket_path.exists():
                self.socket_path.unlink()
            # Immutable discovery evidence is retained for both close outcomes.
        self.selector.close()


def serve(adapter, contract, store, client):
    StableRelay(adapter, contract, store, client).run()


def _directory(client):
    directory = Path.home() / '.local/share/golem/stable-relays' / _client(client)
    require(not any(path.is_symlink() for path in (directory, *directory.parents)), 'CONTROL_SYMLINK')
    info = directory.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
            stat.S_IMODE(info.st_mode) == 0o700, 'CONTROL_DIRECTORY')
    return directory


def _record(client, instance):
    require(type(instance) is str and re.fullmatch('[0-9a-f]{32}', instance), 'CONTROL_INSTANCE')
    path = _directory(client) / (instance + '.json')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and
                stat.S_IMODE(before.st_mode) == 0o600 and before.st_nlink == 1 and
                before.st_size <= legacy.CONTROL_LIMIT, 'CONTROL_RECORD')
        raw = os.read(fd, legacy.CONTROL_LIMIT + 1)
        after = os.fstat(fd)
        require(len(raw) == before.st_size and
                (before.st_ino, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_ino, after.st_mtime_ns, after.st_ctime_ns), 'CONTROL_RECORD_CHANGED')
    finally:
        os.close(fd)
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'CONTROL_RECORD_DUPLICATE')
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique)
    require(type(value) is dict and set(value) == {'schema', 'client', 'instance', 'token', 'pid', 'kind'} and
            value['schema'] == SCHEMA and value['client'] == client and value['instance'] == instance and
            value['kind'] == KIND and type(value['pid']) is int and value['pid'] > 0 and
            type(value['token']) is str and re.fullmatch('[0-9a-f]{64}', value['token']), 'CONTROL_RECORD')
    return value


def endpoint(client, instance):
    value = _record(client, instance)
    metadata = (_directory(client) / (instance + '.json')).lstat()
    path = _directory(client) / (instance + '.sock')
    try:
        info = path.lstat()
        require(stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o600, 'CONTROL_SOCKET')
        observation = {'endpoint_state': 'PRESENT', 'socket_identity': (info.st_dev, info.st_ino)}
    except FileNotFoundError:
        observation = {'endpoint_state': 'ABSENT'}
    require(_record(client, instance) == value, 'CONTROL_RECORD_CHANGED')
    return {**{key: item for key, item in value.items() if key != 'token'},
            'descriptor_sha256': hashlib.sha256(encoded(value)).hexdigest(),
            'discovery_mtime_ns': metadata.st_mtime_ns, **observation}


def descriptors(client):
    try:
        directory = _directory(client)
    except FileNotFoundError:
        return []
    entries = list(itertools.islice(directory.iterdir(), 1025))
    require(len(entries) <= 1024, 'CONTROL_DISCOVERY_LIMIT')
    result = []
    for path in sorted(entries):
        if re.fullmatch(r'[0-9a-f]{32}\.json', path.name):
            try:
                result.append(endpoint(client, path.stem))
            except Exception:
                result.append({'instance': path.stem, 'client': client, 'kind': KIND,
                               'endpoint_state': 'UNKNOWN', 'reason': 'CONTROL_RECORD_UNAVAILABLE'})
    return result


def request(client, instance, operation, arguments):
    """One explicit owner-local request; no retry, selection publication or call."""
    require(operation in ('status', 'refresh') and type(arguments) is dict, 'CONTROL_OPERATION')
    record = _record(client, instance)
    path = _directory(client) / (instance + '.sock')
    before = path.lstat()
    require(stat.S_ISSOCK(before.st_mode) and before.st_uid == os.getuid() and
            stat.S_IMODE(before.st_mode) == 0o600, 'CONTROL_SOCKET')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(legacy.CONTROL_TIMEOUT)
        conn.connect(str(path))
        require(legacy.peer_uid(conn) == os.getuid() and legacy.peer_pid(conn) == record['pid'], 'CONTROL_PEER')
        after = path.lstat()
        require((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino), 'CONTROL_SOCKET_CHANGED')
        legacy.frame_send(conn, {'schema': SCHEMA, 'client': client, 'instance': instance,
            'token': record['token'], 'request_id': uuid.uuid4().hex, 'operation': operation, 'arguments': arguments})
        timeout = (legacy.DRAIN_TIMEOUT + legacy.START_TIMEOUT + legacy.CONTROL_TIMEOUT
                   if operation == 'refresh' else legacy.CONTROL_TIMEOUT)
        deadline = time.monotonic() + timeout
        def exact(size):
            output = bytearray()
            while len(output) < size:
                require(time.monotonic() < deadline, 'CONTROL_RESULT_UNKNOWN')
                conn.settimeout(max(.001, deadline - time.monotonic()))
                chunk = conn.recv(size - len(output))
                require(chunk, 'CONTROL_RESULT_UNKNOWN')
                output.extend(chunk)
            return bytes(output)
        size = int.from_bytes(exact(4), 'big')
        require(0 < size <= legacy.CONTROL_LIMIT, 'CONTROL_SIZE')
        response = json.loads(exact(size))
    require(type(response) is dict and type(response.get('ok')) is bool, 'CONTROL_RESPONSE')
    return response
