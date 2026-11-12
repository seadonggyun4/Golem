"""Codex stdio relay; owner-selected child refresh, never an action retry.

The local endpoint is not an MCP tool or a source of authorization. A refresh
can select only an already configured Codex state also selected in config.toml.
No process is killed, no Work request is replayed, and uncertain close/start
permanently blocks this relay until its owning client closes the transport.
"""
import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import select
import selectors
import secrets
import socket
import stat
import struct
import subprocess
import sys
import time
import tomllib
import uuid

FRAME_LIMIT = 1024 * 1024
CONTROL_LIMIT = 16 * 1024
REQUEST_LIMIT = 1024
CATALOG_PAGE_LIMIT = 128
CATALOG_COUNTER_LIMIT = (1 << 63) - 1
CONTROL_TIMEOUT = 2.0
DRAIN_TIMEOUT = 30.0
START_TIMEOUT = 60.0
SCHEMA = 'golem.connection-relay.v1'
DEFINITION_MARKER = re.compile(r'golem-connection-v1:([a-f0-9]{32}):([1-9][0-9]{0,18}):([1-9][0-9]{0,18}):([a-f0-9]{32})\Z')


def parse_definition_marker(value):
    """Public observation, not a credential or authenticated chat identity."""
    match = DEFINITION_MARKER.fullmatch(value) if type(value) is str else None
    require(match is not None, 'DEFINITION_MARKER_INVALID')
    instance, child, catalog, nonce = match.groups()
    require(int(child) <= int(catalog) <= CATALOG_COUNTER_LIMIT, 'DEFINITION_MARKER_INVALID')
    return dict(instance=instance, child_generation=int(child),
                catalog_generation=int(catalog), definition_nonce=nonce)


class RelayError(ValueError):
    pass


def require(value, code):
    if not value:
        raise RelayError(code)


def encoded(value):
    return (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode()


def identifier(value):
    require(type(value) in (str, int) and (type(value) is int or len(value) <= 256), 'RPC_ID')
    return type(value).__name__, value


def peer_uid(conn):
    """Kernel-authenticated UID; never infer a human's approval from it."""
    if hasattr(socket, 'SO_PEERCRED'):
        return struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]
    if sys.platform == 'darwin':
        uid, gid = ctypes.c_uint(), ctypes.c_uint()
        function = ctypes.CDLL(None, use_errno=True).getpeereid
        function.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
        function.restype = ctypes.c_int
        require(function(conn.fileno(), ctypes.byref(uid), ctypes.byref(gid)) == 0, 'PEER_IDENTITY')
        return uid.value
    raise RelayError('PEER_IDENTITY_UNSUPPORTED')


def peer_pid(conn):
    if hasattr(socket, 'SO_PEERCRED'):
        return struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[0]
    if sys.platform == 'darwin':
        # Darwin sys/un.h: SOL_LOCAL=0, LOCAL_PEERPID=0x002.
        return struct.unpack('i', conn.getsockopt(0, 0x002, 4))[0]
    raise RelayError('PEER_IDENTITY_UNSUPPORTED')


def frame_receive(conn):
    deadline = time.monotonic() + CONTROL_TIMEOUT
    def exact(size):
        result = bytearray()
        while len(result) < size:
            conn.settimeout(max(.001, deadline - time.monotonic()))
            require(time.monotonic() < deadline, 'CONTROL_TIMEOUT')
            part = conn.recv(size - len(result))
            require(part, 'CONTROL_EOF')
            result.extend(part)
        return bytes(result)
    size = int.from_bytes(exact(4), 'big')
    require(0 < size <= CONTROL_LIMIT, 'CONTROL_SIZE')
    return exact(size)


def frame_send(conn, value):
    data = encoded(value)
    require(len(data) <= CONTROL_LIMIT, 'CONTROL_SIZE')
    conn.settimeout(CONTROL_TIMEOUT)
    conn.sendall(len(data).to_bytes(4, 'big') + data)


class Relay:
    def __init__(self, adapter, state, *, input_fd=0, output_fd=1,
                 drain_timeout=DRAIN_TIMEOUT, start_timeout=START_TIMEOUT):
        self.adapter = adapter
        self.current_state = adapter.canonical(state)
        self.input_fd, self.output_fd = input_fd, output_fd
        self.drain_timeout, self.start_timeout = drain_timeout, start_timeout
        self.instance, self.token = uuid.uuid4().hex, secrets.token_hex(32)
        self.state, self.failure = 'STARTING', None
        self.child = None
        self.pending, self.server_pending, self.seen = set(), set(), set()
        self.initial_request = self.initial_result = None
        self.initialized = False
        self.initial_deadline = None
        self.child_buffer = bytearray()
        self.client_buffer = bytearray()
        self.selector = selectors.DefaultSelector()
        self.endpoint = self.descriptor = self.socket_path = None
        self.pin = self.approval_pin = None
        self.launcher = None
        self.stopping = False
        # Observe only requests the host actually sends. A notification or a
        # replacement handshake never proves that the host rebuilt its tools.
        self.child_generation = self.catalog_generation = 0
        self.catalog_pending = {}
        self.catalog_last_complete = None
        self.catalog_chain = None
        self.catalog_requests = self.catalog_responses = self.catalog_errors = 0
        self.catalog_notifications = 0
        self.catalog_state = 'HOST_CATALOG_NOT_REQUESTED'
        self.catalog_current = None
        self.definition_nonce = None

    def new_catalog_generation(self):
        self.catalog_generation += 1
        self.definition_nonce = uuid.uuid4().hex
        self.catalog_chain = self.catalog_current = None
        self.catalog_requests = self.catalog_responses = self.catalog_errors = 0
        self.catalog_notifications = 0
        self.catalog_state = ('HOST_CATALOG_NOT_REQUESTED' if self.catalog_generation == 1
                              else 'HOST_CATALOG_NOT_RELISTED')

    def definition_marker(self):
        if self.child_generation < 1 or self.definition_nonce is None:
            return None
        return (f'golem-connection-v1:{self.instance}:{self.child_generation}:'
                f'{self.catalog_generation}:{self.definition_nonce}')

    def mark_tool_definitions(self, message):
        """Identify the transport through definitions, without a Work/tool call.

        Only a valid current tools/list reply is annotated. The opaque marker
        exposes no paths, policies, command arguments or endpoint credentials.
        It is also visible when a host preserves descriptions but drops _meta.
        """
        request = self.catalog_pending.get(identifier(message['id']))
        value = message.get('result')
        if (not request or request['generation'] != self.catalog_generation or
                not request['valid'] or not isinstance(value, dict) or
                not isinstance(value.get('tools'), list) or not value['tools'] or
                not all(isinstance(tool, dict) and type(tool.get('name')) is str and
                        isinstance(tool.get('inputSchema'), dict) for tool in value['tools'])):
            return message
        marker = self.definition_marker()
        if marker is None:
            return message
        tools = list(value['tools'])
        first = dict(tools[0])
        description = first.get('description', '')
        if type(description) is not str:
            return message
        first['description'] = description + ('\n\nConnection observation only; no authority: ' + marker)
        tools[0] = first
        annotated = {**message, 'result': {**value, 'tools': tools}}
        # Diagnostics must not turn an otherwise valid near-limit response into
        # a transport failure. Without a delivered marker readiness stays unknown.
        return annotated if len(encoded(annotated)) <= FRAME_LIMIT else message

    @staticmethod
    def catalog_digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                         allow_nan=False).encode()).hexdigest()

    def catalog_request_sent(self, message):
        if message.get('method') != 'tools/list' or 'id' not in message:
            return
        params = message.get('params', {})
        valid = isinstance(params, dict) and (params.get('cursor') is None or
                                               type(params.get('cursor')) is str)
        cursor = params.get('cursor') if valid else None
        cursor_digest = self.catalog_digest(cursor) if cursor is not None else None
        chain = ({'pages': [], 'expected': None, 'seen': set(), 'tools': []} if cursor is None else
                 self.catalog_chain if self.catalog_chain is not None and
                 self.catalog_chain['expected'] == cursor_digest else None)
        self.catalog_pending[identifier(message['id'])] = {
            'generation': self.catalog_generation, 'valid': valid,
            'cursor': cursor_digest, 'chain': chain}
        self.catalog_requests = min(self.catalog_requests + 1, CATALOG_COUNTER_LIMIT)
        self.catalog_current = None
        self.catalog_state = 'HOST_CATALOG_REQUEST_PENDING'

    def catalog_response_sent(self, message):
        request = self.catalog_pending.pop(identifier(message['id']), None)
        if request is None or request['generation'] != self.catalog_generation:
            return  # An old in-flight reply cannot certify a new catalog.
        self.catalog_responses = min(self.catalog_responses + 1, CATALOG_COUNTER_LIMIT)
        self.catalog_current = None
        if 'error' in message:
            self.catalog_errors = min(self.catalog_errors + 1, CATALOG_COUNTER_LIMIT)
            self.catalog_chain = None
            self.catalog_state = 'HOST_CATALOG_ERROR_SENT'
            return
        value = message.get('result')
        if (not request['valid'] or not isinstance(value, dict) or
                not isinstance(value.get('tools'), list) or
                not all(isinstance(tool, dict) and type(tool.get('name')) is str and
                        isinstance(tool.get('inputSchema'), dict) for tool in value['tools']) or
                (value.get('nextCursor') is not None and type(value['nextCursor']) is not str)):
            self.catalog_chain = None
            self.catalog_state = 'HOST_CATALOG_INVALID_RESPONSE'
            return
        cursor = request['cursor']
        if cursor is None:
            chain = request['chain']
        elif (self.catalog_chain is not None and request['chain'] is self.catalog_chain and
              self.catalog_chain['expected'] == cursor):
            chain = self.catalog_chain
        else:
            self.catalog_chain = None
            self.catalog_state = 'HOST_CATALOG_UNVERIFIED_PAGE'
            return
        if len(chain['pages']) >= CATALOG_PAGE_LIMIT:
            self.catalog_chain = None
            self.catalog_state = 'HOST_CATALOG_INVALID_RESPONSE'
            return
        names = chain['tools'] + [tool['name'] for tool in value['tools']]
        if len(names) > 256 or len(set(names)) != len(names):
            self.catalog_chain = None
            self.catalog_state = 'HOST_CATALOG_INVALID_RESPONSE'
            return
        chain['tools'] = names
        chain['pages'].append(self.catalog_digest(value))
        if value.get('nextCursor') is not None:
            following = self.catalog_digest(value['nextCursor'])
            if following == cursor or following in chain['seen']:
                self.catalog_chain = None
                self.catalog_state = 'HOST_CATALOG_INVALID_RESPONSE'
                return
            chain['seen'].add(following)
            chain['expected'] = following
            self.catalog_chain = chain
            self.catalog_state = 'HOST_CATALOG_PARTIAL_RESPONSE'
            return
        self.catalog_current = {'generation': self.catalog_generation,
                                'sha256': self.catalog_digest(chain['pages']),
                                'pages': len(chain['pages']),
                                'tools_sha256': self.catalog_digest(sorted(chain['tools'])),
                                'tool_count': len(chain['tools'])}
        self.catalog_last_complete = dict(self.catalog_current)
        self.catalog_chain = None
        self.catalog_state = 'HOST_CATALOG_RESPONSE_SENT'

    def catalog_status(self):
        current, previous = self.catalog_current or {}, self.catalog_last_complete or {}
        return {'schema': 'golem.host-tool-catalog-observation.v1',
                'child_generation': self.child_generation, 'catalog_generation': self.catalog_generation,
                'state': self.catalog_state, 'requests': self.catalog_requests,
                'responses': self.catalog_responses, 'errors': self.catalog_errors,
                'list_changed_notifications_sent': self.catalog_notifications,
                'last_complete_generation': previous.get('generation'),
                'last_complete_sha256': previous.get('sha256'), 'last_complete_pages': previous.get('pages'),
                'current_complete_sha256': current.get('sha256'), 'current_complete_pages': current.get('pages'),
                'model_delivery_verified': False}

    def approved(self, state):
        with self.adapter.locked(state) as private:
            raw = self.adapter.read_private(private / 'approval.json')
            launcher, pin = self.adapter.load(private, 'codex')
            require(raw == self.adapter.read_private(private / 'approval.json'), 'APPROVAL_CHANGED')
        return launcher, pin, self.adapter.digest(raw)

    def selected(self, state, config_pin):
        path = self.adapter.canonical(Path.home() / '.codex/config.toml')
        raw = self.adapter.read_private(path)
        require(self.adapter.digest(raw) == config_pin, 'CONFIG_CHANGED')
        value = tomllib.loads(raw.decode())
        declaration = value.get('mcp_servers', {}).get('golem-local', {})
        args = declaration.get('args')
        script = str(Path(self.adapter.__file__).resolve())
        variants = [
            ['-I', '-B', script, 'serve', '--client', 'codex', '--state', str(state)],
            ['-I', '-B', script, 'serve', '--state', str(state)],
        ]
        require(args in variants and type(declaration.get('command')) is str
                and Path(declaration['command']).is_absolute()
                and os.path.realpath(declaration['command']) == os.path.realpath(sys.executable)
                and declaration.get('enabled', True) is True, 'CONFIG_STATE_NOT_SELECTED')
        return raw

    def start_endpoint(self):
        # Fixed owner-local location; no client-supplied bind path or TCP.
        directory = self.adapter.canonical(Path.home() / '.local/share/golem/connection-relays')
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
                               pid=os.getpid(), kind='codex-connection-relay'))
            fd = os.open(self.descriptor, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            self.endpoint = endpoint
            self.selector.register(endpoint, selectors.EVENT_READ, 'control')
        except Exception:
            endpoint.close()
            # Only paths this never-published instance created may be removed.
            if self.socket_path.exists():
                self.socket_path.unlink()
            raise

    def spawn(self, launcher, state, pin):
        environment = dict(os.environ)
        environment.update(GOLEM_LAUNCHER_SHA256=pin, GOLEM_LAUNCHER_CLIENT='codex',
                           GOLEM_LAUNCHER_STATE=str(state),
                           GOLEM_LAUNCHER_PLUGIN_VERSION=self.adapter.ADAPTER_VERSION)
        child = subprocess.Popen([launcher['command'], *launcher['args']], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=None, bufsize=0, env=environment,
                                 close_fds=True)
        self.child = child
        self.child_generation += 1
        self.new_catalog_generation()
        os.set_blocking(child.stdout.fileno(), False)
        os.set_blocking(child.stdin.fileno(), False)
        self.child_buffer.clear()
        self.selector.register(child.stdout, selectors.EVENT_READ, 'child')

    def write(self, fd, message, *, deadline=None):
        raw = encoded(message)
        require(len(raw) <= FRAME_LIMIT, 'RPC_SIZE')
        deadline = min(deadline or float('inf'), time.monotonic() + CONTROL_TIMEOUT)
        while raw:
            remaining = deadline - time.monotonic()
            require(remaining > 0 and select.select([], [fd], [], remaining)[1], 'TRANSPORT_WRITE_TIMEOUT')
            try:
                count = os.write(fd, raw)
            except BlockingIOError:
                continue
            require(count > 0, 'TRANSPORT_WRITE_FAILED')
            raw = raw[count:]

    def send_child(self, message):
        require(self.child is not None and self.child.poll() is None, 'CHILD_UNAVAILABLE')
        self.write(self.child.stdin.fileno(), message)

    def send_client(self, message):
        self.write(self.output_fd, message)

    def decode_rpc(self, raw):
        require(0 < len(raw) <= FRAME_LIMIT, 'RPC_SIZE')
        message = self.adapter.decode(raw)
        require(type(message) is dict and message.get('jsonrpc') == '2.0', 'RPC_ENVELOPE')
        if 'method' in message:
            require(type(message['method']) is str and 0 < len(message['method']) <= 256
                    and 'result' not in message and 'error' not in message, 'RPC_METHOD')
            if 'id' in message:
                identifier(message['id'])
        else:
            require('id' in message and (('result' in message) != ('error' in message)), 'RPC_RESPONSE')
            identifier(message['id'])
        return message

    def client_message(self, message):
        if self.state == 'UNKNOWN':
            if 'method' in message and 'id' in message:
                self.send_client({'jsonrpc': '2.0', 'id': message['id'], 'error': {
                    'code': -32000, 'message': 'GOLEM_RELAY_UNKNOWN',
                    'data': {'automatic_retry_allowed': False}}})
            return
        require(self.state in ('STARTING', 'READY'), 'RELAY_NOT_READY')
        if 'method' in message:
            if 'id' in message:
                key = identifier(message['id'])
                require(key not in self.pending and len(self.pending) < REQUEST_LIMIT, 'RPC_REQUEST_LIMIT')
                self.pending.add(key)
            if message['method'] == 'initialize':
                require(self.initial_request is None and 'id' in message, 'INITIALIZE_ONCE')
                self.initial_request = message
                self.initial_deadline = time.monotonic() + self.start_timeout
            elif message['method'] == 'notifications/initialized':
                require(self.initial_result is not None and not self.initialized, 'INITIALIZED_ORDER')
                self.initialized = True
                self.state = 'READY'
            else:
                require(self.initialized, 'INITIALIZATION_REQUIRED')
        else:
            key = identifier(message['id'])
            require(key in self.server_pending, 'UNEXPECTED_CLIENT_RESPONSE')
            self.server_pending.remove(key)
        self.send_child(message)
        self.catalog_request_sent(message)

    def child_message(self, message):
        if self.state == 'UNKNOWN':
            return
        if 'method' in message:
            if 'id' in message:
                key = identifier(message['id'])
                require(key not in self.server_pending and len(self.server_pending) < REQUEST_LIMIT,
                        'SERVER_REQUEST_LIMIT')
                self.server_pending.add(key)
        else:
            key = identifier(message['id'])
            require(key in self.pending, 'UNEXPECTED_CHILD_RESPONSE')
            self.pending.remove(key)
            if self.initial_request and message['id'] == self.initial_request['id'] and not self.initialized:
                if 'error' in message:
                    self.send_client(message)
                    self.unknown('INITIALIZE_FAILED')
                    return
                require(type(message['result']) is dict, 'INITIALIZE_FAILED')
                result = message['result']
                require(type(result.get('protocolVersion')) is str and type(result.get('capabilities')) is dict,
                        'INITIALIZE_RESULT')
                self.initial_result = result
                # The relay, not the child, supplies this notification capability.
                message = self.relay_initialize_result(message)
        catalog_changed = message.get('method') == 'notifications/tools/list_changed'
        if catalog_changed:
            self.new_catalog_generation()
        elif 'method' not in message:
            message = self.mark_tool_definitions(message)
        self.send_client(message)
        if catalog_changed:
            self.catalog_notifications = min(self.catalog_notifications + 1, CATALOG_COUNTER_LIMIT)
        elif 'method' not in message:
            self.catalog_response_sent(message)

    @staticmethod
    def relay_initialize_result(message):
        result = dict(message['result'])
        capabilities = dict(result['capabilities'])
        if 'tools' in capabilities:
            require(type(capabilities['tools']) is dict, 'TOOLS_CAPABILITY')
            capabilities['tools'] = {**capabilities['tools'], 'listChanged': True}
        result['capabilities'] = capabilities
        return {**message, 'result': result}

    def status(self):
        return dict(schema=SCHEMA, instance=self.instance, pid=os.getpid(), state=self.state,
                    busy=bool(self.pending or self.server_pending), pending=len(self.pending),
                    server_pending=len(self.server_pending), launcher_sha256=self.pin,
                    approval_sha256=self.approval_pin, selected_state=str(self.current_state),
                    child_pid=self.child.pid if self.child else None,
                    plugin_version=self.adapter.ADAPTER_VERSION, failure=self.failure,
                    host_catalog=self.catalog_status(),
                    definition_marker=self.definition_marker(),
                    definition_tools_sha256=(self.catalog_current or {}).get('tools_sha256'),
                    definition_tool_count=(self.catalog_current or {}).get('tool_count'),
                    execution_authorized=False, model_tools_delivery_verified=False,
                    work_idle_verified=False, native_leases_observed=False,
                    shutdown_mode='STDIN_EOF_WAIT_ONLY',
                    automatic_retry_allowed=False)

    def unknown(self, code):
        self.state, self.failure = 'UNKNOWN', code
        if self.child and self.child.stdin and not self.child.stdin.closed:
            self.child.stdin.close()

    def unregister_child(self):
        if self.child is not None and self.child.stdout is not None:
            try:
                self.selector.unregister(self.child.stdout)
            except KeyError:
                pass

    def drain(self):
        """EOF is the only stop signal; an Owner export may postpone exit."""
        child = self.child
        require(child is not None, 'CHILD_UNAVAILABLE')
        self.unregister_child()
        if not child.stdin.closed:
            child.stdin.close()
        deadline = time.monotonic() + self.drain_timeout
        eof = False
        while not eof or child.poll() is None:
            if self.state == 'DRAINING':
                self.reject_refresh_requests(deadline)
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'CHILD_DRAIN_UNKNOWN')
            if not eof and select.select([child.stdout], [], [], min(.05, remaining))[0]:
                part = os.read(child.stdout.fileno(), 65536)
                if not part:
                    eof = True
                else:
                    self.child_buffer.extend(part)
                    require(len(self.child_buffer) <= FRAME_LIMIT, 'CHILD_DRAIN_SIZE')
                    while b'\n' in self.child_buffer:
                        raw, _, rest = self.child_buffer.partition(b'\n')
                        self.child_buffer[:] = rest
                        message = self.decode_rpc(raw)
                        # A server request appearing after refresh admission is not safe to replay.
                        require('method' in message and 'id' not in message, 'CHILD_DRAIN_REQUEST')
                        self.send_client(message)
            elif eof:
                time.sleep(min(.01, remaining))
        require(not self.child_buffer and child.returncode == 0, 'CHILD_EXIT_UNKNOWN')
        child.wait(timeout=.1)
        child.stdout.close()

    def replacement_initialize(self):
        self.send_child(self.initial_request)
        deadline = time.monotonic() + self.start_timeout
        result = None
        while result is None:
            self.reject_refresh_requests(deadline)
            remaining = deadline - time.monotonic()
            require(remaining > 0 and self.child.poll() is None, 'CHILD_INITIALIZE_UNKNOWN')
            if not select.select([self.child.stdout], [], [], min(.1, remaining))[0]:
                continue
            part = os.read(self.child.stdout.fileno(), 65536)
            require(part, 'CHILD_INITIALIZE_EOF')
            self.child_buffer.extend(part)
            require(len(self.child_buffer) <= FRAME_LIMIT, 'RPC_SIZE')
            while b'\n' in self.child_buffer:
                raw, _, rest = self.child_buffer.partition(b'\n')
                self.child_buffer[:] = rest
                message = self.decode_rpc(raw)
                require(result is None and 'method' not in message
                        and message['id'] == self.initial_request['id'] and 'result' in message,
                        'CHILD_INITIALIZE_RESPONSE')
                result = message['result']
        require(type(result) is dict
                and result.get('protocolVersion') == self.initial_result['protocolVersion']
                and result.get('capabilities') == self.initial_result['capabilities'], 'CHILD_CAPABILITY_CHANGED')
        require(not self.child_buffer, 'CHILD_INITIALIZE_TRAILING')
        self.send_child({'jsonrpc': '2.0', 'method': 'notifications/initialized'})

    def reject_refresh_requests(self, deadline=None):
        """Never dispatch calls arriving during replacement to the new policy."""
        cutoff = min(deadline or float('inf'), time.monotonic() + .25)
        total = count = 0
        while select.select([self.input_fd], [], [], 0)[0]:
            require(time.monotonic() < cutoff, 'REFRESH_INPUT_LIMIT')
            try:
                part = os.read(self.input_fd, 65536)
            except BlockingIOError:
                break
            if not part:
                self.stopping = True
                raise RelayError('HOST_CLOSED_DURING_REFRESH')
            total += len(part)
            require(total <= FRAME_LIMIT, 'REFRESH_INPUT_LIMIT')
            self.client_buffer.extend(part)
            require(len(self.client_buffer) <= FRAME_LIMIT, 'RPC_SIZE')
            while b'\n' in self.client_buffer:
                raw, _, rest = self.client_buffer.partition(b'\n')
                self.client_buffer[:] = rest
                message = self.decode_rpc(raw)
                count += 1
                require(count <= 128, 'REFRESH_INPUT_LIMIT')
                require('method' in message, 'UNEXPECTED_REFRESH_RESPONSE')
                if 'id' in message:
                    self.write(self.output_fd, {'jsonrpc': '2.0', 'id': message['id'], 'error': {
                        'code': -32000, 'message': 'GOLEM_RELAY_REFRESH_BUSY',
                        'data': {'automatic_retry_allowed': False, 'dispatched': False}}}, deadline=cutoff)

    def refresh(self, args):
        fields = {'expected_launcher_sha256', 'expected_approval_sha256', 'state',
                  'approval_sha256', 'launcher_sha256', 'config_sha256'}
        require(type(args) is dict and set(args) == fields, 'REFRESH_FIELDS')
        require(self.state == 'READY' and self.initialized, 'REFRESH_NOT_READY')
        require(not self.pending and not self.server_pending, 'REFRESH_BUSY')
        require(not self.client_buffer and not self.child_buffer
                and not select.select([self.input_fd, self.child.stdout], [], [], 0)[0],
                'REFRESH_TRANSPORT_BUSY')
        for name in fields - {'state'}:
            require(type(args[name]) is str and re.fullmatch('[0-9a-f]{64}', args[name]), 'REFRESH_DIGEST')
        require(args['expected_launcher_sha256'] == self.pin
                and args['expected_approval_sha256'] == self.approval_pin, 'RELAY_STALE')
        require(self.approved(self.current_state) == (self.launcher, self.pin, self.approval_pin), 'CURRENT_APPROVAL_CHANGED')
        state = self.adapter.canonical(args['state'])
        launcher, pin, approval_pin = self.approved(state)
        require((pin, approval_pin) == (args['launcher_sha256'], args['approval_sha256']), 'TARGET_APPROVAL_CHANGED')
        config = self.selected(state, args['config_sha256'])
        require((state, pin, approval_pin) != (self.current_state, self.pin, self.approval_pin), 'ALREADY_SELECTED')
        self.state = 'DRAINING'
        try:
            self.drain()
            # Recheck both authority selection and exact configuration after drain.
            require(self.approved(state) == (launcher, pin, approval_pin), 'TARGET_APPROVAL_CHANGED')
            require(self.selected(state, args['config_sha256']) == config, 'CONFIG_CHANGED')
            self.state = 'STARTING'
            self.spawn(launcher, state, pin)
            self.replacement_initialize()
            self.reject_refresh_requests()
            require(not self.client_buffer, 'PARTIAL_REQUEST_DURING_REFRESH')
            self.current_state, self.launcher = state, launcher
            self.pin, self.approval_pin = pin, approval_pin
            self.state = 'READY'
            self.send_client({'jsonrpc': '2.0', 'method': 'notifications/tools/list_changed'})
            self.catalog_notifications = min(self.catalog_notifications + 1, CATALOG_COUNTER_LIMIT)
            return {**self.status(), 'refresh_result': 'CHILD_REINITIALIZED',
                    'model_tools_delivery_verified': False}
        except Exception:
            self.unknown('REFRESH_RESULT_UNKNOWN')
            raise

    def control(self, request):
        require(type(request) is dict and set(request) == {'schema', 'instance', 'token', 'request_id', 'operation', 'arguments'},
                'CONTROL_ENVELOPE')
        require(request['schema'] == SCHEMA and request['instance'] == self.instance
                and type(request['token']) is str and hmac.compare_digest(request['token'], self.token), 'CONTROL_AUTH')
        nonce = request['request_id']
        require(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce), 'CONTROL_NONCE')
        require(nonce not in self.seen and len(self.seen) < REQUEST_LIMIT, 'CONTROL_REPLAY_OR_QUOTA')
        self.seen.add(nonce)
        if request['operation'] == 'status':
            require(request['arguments'] == {}, 'CONTROL_ARGUMENTS')
            return self.status()
        require(request['operation'] == 'refresh', 'CONTROL_OPERATION')
        return self.refresh(request['arguments'])

    def accept_control(self):
        conn, _ = self.endpoint.accept()
        with conn:
            try:
                require(peer_uid(conn) == os.getuid(), 'CONTROL_UID')
                request = self.adapter.decode(frame_receive(conn))
                result = self.control(request)
                frame_send(conn, {'ok': True, 'value': result})
            except Exception as error:
                code = str(error) if isinstance(error, (RelayError, self.adapter.SetupError)) else 'CONTROL_FAILED'
                try:
                    frame_send(conn, {'ok': False, 'code': code, 'automatic_retry_allowed': False,
                                      'relay_state': self.state})
                except (OSError, RelayError):
                    pass

    def read_pipe(self, source):
        fd = self.input_fd if source == 'client' else self.child.stdout.fileno()
        try:
            part = os.read(fd, 65536)
        except BlockingIOError:
            return
        if not part:
            if source == 'client':
                self.stopping = True
            else:
                self.unregister_child()
                self.unknown('CHILD_TRANSPORT_CLOSED')
            return
        buffer = self.client_buffer if source == 'client' else self.child_buffer
        buffer.extend(part)
        require(len(buffer) <= FRAME_LIMIT, 'RPC_SIZE')
        while b'\n' in buffer:
            raw, _, rest = buffer.partition(b'\n')
            buffer[:] = rest
            message = self.decode_rpc(raw)
            if source == 'client':
                self.client_message(message)
            else:
                self.child_message(message)

    def close(self):
        if self.child and self.child.poll() is None:
            try:
                self.drain()
            except Exception:
                self.unknown('CHILD_CLOSE_UNKNOWN')
        if self.endpoint:
            self.endpoint.close()
            # Discovery descriptors are retained as closed-connection evidence.
            if self.socket_path and self.socket_path.exists():
                self.socket_path.unlink()
            if self.state != 'UNKNOWN' and self.descriptor and self.descriptor.exists():
                self.descriptor.unlink()
        self.selector.close()

    def run(self):
        try:
            self.launcher, self.pin, self.approval_pin = self.approved(self.current_state)
            self.start_endpoint()
            self.spawn(self.launcher, self.current_state, self.pin)
            self.selector.register(self.input_fd, selectors.EVENT_READ, 'client')
            os.set_blocking(self.input_fd, False)
            os.set_blocking(self.output_fd, False)
            while not self.stopping:
                if self.state == 'STARTING' and self.initial_deadline is not None \
                        and time.monotonic() >= self.initial_deadline:
                    self.unknown('INITIALIZE_TIMEOUT')
                for key, _ in self.selector.select(.1):
                    if key.data == 'control':
                        self.accept_control()
                    else:
                        try:
                            self.read_pipe(key.data)
                        except Exception:
                            self.unknown('TRANSPORT_RESULT_UNKNOWN')
            require(self.state != 'UNKNOWN' and not self.pending and not self.server_pending
                    and not self.client_buffer and not self.child_buffer, 'RELAY_CLOSE_UNKNOWN')
        finally:
            self.close()
        require(self.state != 'UNKNOWN', 'RELAY_CLOSE_UNKNOWN')


def serve(adapter, state):
    Relay(adapter, state).run()


def _directory():
    directory = Path.home() / '.local/share/golem/connection-relays'
    require(not any(p.is_symlink() for p in (directory, *directory.parents)), 'CONTROL_SYMLINK')
    info = directory.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o700, 'CONTROL_DIRECTORY')
    return directory


def _record(instance):
    require(type(instance) is str and re.fullmatch('[0-9a-f]{32}', instance), 'CONTROL_INSTANCE')
    path = _directory() / (instance + '.json')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1
                and info.st_size <= CONTROL_LIMIT, 'CONTROL_RECORD')
        raw = os.read(fd, CONTROL_LIMIT + 1)
        after = os.fstat(fd)
        require(len(raw) == info.st_size and (info.st_ino, info.st_mtime_ns, info.st_ctime_ns)
                == (after.st_ino, after.st_mtime_ns, after.st_ctime_ns), 'CONTROL_RECORD_CHANGED')
    finally:
        os.close(fd)
    def pairs(values):
        output = {}
        for key, value in values:
            require(key not in output, 'CONTROL_RECORD_DUPLICATE')
            output[key] = value
        return output
    value = json.loads(raw, object_pairs_hook=pairs)
    require(type(value) is dict and set(value) == {'schema', 'instance', 'token', 'pid', 'kind'}
            and value['schema'] == SCHEMA and value['instance'] == instance
            and value['kind'] == 'codex-connection-relay' and type(value['pid']) is int
            and value['pid'] > 0 and type(value['token']) is str
            and re.fullmatch('[0-9a-f]{64}', value['token']), 'CONTROL_RECORD')
    return value


def endpoint(instance):
    """Validated discovery snapshot; absence is not process/Work completion."""
    value = _record(instance)
    metadata = (_directory() / (instance + '.json')).lstat()
    path = _directory() / (instance + '.sock')
    try:
        info = path.lstat()
        require(stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600, 'CONTROL_SOCKET')
        observation = {'endpoint_state':'PRESENT', 'socket_identity':(info.st_dev, info.st_ino)}
    except FileNotFoundError:
        observation = {'endpoint_state':'ABSENT'}
    require(_record(instance) == value, 'CONTROL_RECORD_CHANGED')
    return {**{key:item for key,item in value.items() if key != 'token'},
            'descriptor_sha256':hashlib.sha256(encoded(value)).hexdigest(),
            'discovery_mtime_ns':metadata.st_mtime_ns, **observation}


def descriptors():
    """Read bounded discovery records, omitting tokens; no connect/probe or deletion."""
    try:
        directory = _directory()
    except FileNotFoundError:
        return []
    entries = list(directory.iterdir())
    require(len(entries) <= 1024, 'CONTROL_DISCOVERY_LIMIT')
    result = []
    for path in sorted(entries):
        if re.fullmatch(r'[0-9a-f]{32}\.json', path.name):
            try:
                result.append(endpoint(path.stem))
            except Exception as error:
                result.append({'instance':path.stem, 'kind':'codex-connection-relay',
                               'endpoint_state':'UNKNOWN',
                               'reason':str(error) if isinstance(error, RelayError) else 'CONTROL_RECORD_UNAVAILABLE'})
    return result


def request(instance, operation, arguments):
    """One explicit owner request; no fallback, retry, configuration write or discovery probe."""
    require(operation in ('status', 'refresh') and type(arguments) is dict, 'CONTROL_OPERATION')
    record = _record(instance)
    path = _directory() / (instance + '.sock')
    before = path.lstat()
    require(stat.S_ISSOCK(before.st_mode) and before.st_uid == os.getuid()
            and stat.S_IMODE(before.st_mode) == 0o600, 'CONTROL_SOCKET')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(CONTROL_TIMEOUT)
        conn.connect(str(path))
        require(peer_uid(conn) == os.getuid(), 'CONTROL_UID')
        require(peer_pid(conn) == record['pid'], 'CONTROL_PID')
        after = path.lstat()
        require((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino), 'CONTROL_SOCKET_CHANGED')
        frame_send(conn, {'schema': SCHEMA, 'instance': instance, 'token': record['token'],
                         'request_id': uuid.uuid4().hex, 'operation': operation, 'arguments': arguments})
        # Refresh may be waiting for an Owner export to finish before normal exit.
        timeout = DRAIN_TIMEOUT + START_TIMEOUT + CONTROL_TIMEOUT if operation == 'refresh' else CONTROL_TIMEOUT
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
        require(0 < size <= CONTROL_LIMIT, 'CONTROL_SIZE')
        response = json.loads(exact(size))
    require(type(response) is dict and type(response.get('ok')) is bool, 'CONTROL_RESPONSE')
    return response
