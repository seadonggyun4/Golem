"""Optional, owner-invoked control of an *existing* Desktop app-server.

Only the public ``codex app-server proxy --sock`` transport is used. There is
no new app-server, config mutation, tool execution, thread creation or retry.
The public reload method is host-wide and merely queues refreshes; it has no
Golem-only selector. A stdio-only Desktop therefore remains manual.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import time


DESKTOP_BINARIES = {
    Path('/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'): 'ChatGPT',
    Path('/Applications/Codex.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'): 'Codex',
}
MAX_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 10


class ControlError(Exception):
    pass


def _metadata(argv):
    """Fixed local process metadata commands, never a shell or an IPC client."""
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ControlError('PROCESS_METADATA_UNAVAILABLE') from exc
    if result.returncode or len(result.stdout) > MAX_BYTES:
        raise ControlError('PROCESS_METADATA_UNAVAILABLE')
    return result.stdout.decode('utf-8', 'strict')


def _process(pid):
    row = _metadata(['/bin/ps', '-p', str(pid), '-o', 'uid=,ppid=,lstart=,comm=']).strip().split(None, 7)
    if len(row) != 8 or not row[0].isdigit() or not row[1].isdigit():
        raise ControlError('PROCESS_IDENTITY_UNAVAILABLE')
    return {'uid': int(row[0]), 'ppid': int(row[1]), 'start': ' '.join(row[2:7]), 'exe': row[7]}


def _socket_stat(path):
    if not path.is_absolute() or '..' in path.parts:
        raise ControlError('SOCKET_PATH_INVALID')
    # Resolve only for comparison: never follow a symlink into a control socket.
    if path.resolve(strict=True) != path:
        raise ControlError('SOCKET_SYMLINK')
    value = path.lstat()
    parent = path.parent.stat()
    if (not stat.S_ISSOCK(value.st_mode) or value.st_uid != os.getuid()
            or stat.S_IMODE(value.st_mode) & 0o077 or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) & 0o077):
        raise ControlError('SOCKET_NOT_PRIVATE')
    return {'path': str(path), 'device': value.st_dev, 'inode': value.st_ino,
            'uid': value.st_uid, 'mode': stat.S_IMODE(value.st_mode)}


def _host_identity(cli, socket_path):
    identity = _socket_stat(socket_path)
    if cli not in DESKTOP_BINARIES or cli.resolve(strict=True) != cli:
        raise ControlError('CLI_NOT_DESKTOP_BUNDLE')
    binary = cli.stat()
    if not stat.S_ISREG(binary.st_mode) or binary.st_uid not in (0, os.getuid()) or binary.st_mode & 0o022:
        raise ControlError('CLI_NOT_TRUSTED')
    rows = _metadata(['/usr/sbin/lsof', '-n', '-P', '-a', '-U', '-F', 'pufn', '--', str(socket_path)])
    owners = set()
    pid = uid = None
    for row in rows.splitlines():
        if row.startswith('p') and row[1:].isdigit(): pid, uid = int(row[1:]), None
        elif row.startswith('u') and row[1:].isdigit(): uid = int(row[1:])
        elif row == 'n' + str(socket_path) and pid is not None and uid == os.getuid(): owners.add(pid)
    if len(owners) != 1:
        raise ControlError('SOCKET_HOST_AMBIGUOUS')
    host_pid = next(iter(owners))
    host = _process(host_pid)
    if host['uid'] != os.getuid() or host['exe'] != str(cli):
        raise ControlError('SOCKET_HOST_MISMATCH')
    args = _metadata(['/bin/ps', '-p', str(host_pid), '-o', 'args='])
    if ' app-server' not in args:
        raise ControlError('SOCKET_HOST_NOT_APP_SERVER')
    app = DESKTOP_BINARIES[cli]
    expected_parent = f'/Applications/{app}.app/Contents/MacOS/{app}'
    ancestor = host['ppid']
    for _ in range(8):
        if ancestor <= 1: raise ControlError('DESKTOP_ANCESTRY_UNVERIFIED')
        parent = _process(ancestor)
        if parent['uid'] != os.getuid(): raise ControlError('DESKTOP_ANCESTRY_UNVERIFIED')
        if parent['exe'] == expected_parent: break
        ancestor = parent['ppid']
    else:
        raise ControlError('DESKTOP_ANCESTRY_UNVERIFIED')
    digest = hashlib.sha256()
    with cli.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): digest.update(block)
    if _socket_stat(socket_path) != identity or _process(host_pid) != host:
        raise ControlError('CONTROL_IDENTITY_CHANGED')
    return {**identity, 'host_pid': host_pid, 'host_start': host['start'],
            'host_kind': app, 'cli_path': str(cli), 'cli_sha256': digest.hexdigest()}


class _Proxy:
    """Bounded JSONL through the official proxy. Only this child is cleaned up."""
    def __init__(self, cli, socket_path):
        self.process = subprocess.Popen([str(cli), 'app-server', 'proxy', '--sock', str(socket_path)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, bufsize=0)
        self.deadline = time.monotonic() + TIMEOUT_SECONDS
        self.buffer = b''
        self.total = 0
        self.sequence = 0
        self.reload_dispatched = False

    def send(self, value):
        data = json.dumps(value, separators=(',', ':')).encode() + b'\n'
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def call(self, method, params=None):
        if method not in ('initialize', 'thread/loaded/list', 'mcpServerStatus/list', 'config/mcpServer/reload'):
            raise ControlError('METHOD_NOT_ALLOWED')
        self.sequence += 1
        request = {'id': self.sequence, 'method': method, 'params': params}
        if method == 'config/mcpServer/reload': self.reload_dispatched = True
        self.send(request)
        while True:
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                try: value = json.loads(line)
                except (ValueError, UnicodeError) as exc: raise ControlError('CONTROL_PROTOCOL') from exc
                if not isinstance(value, dict): raise ControlError('CONTROL_PROTOCOL')
                if 'method' in value:
                    if 'id' in value: raise ControlError('CONTROL_SERVER_REQUEST_NOT_SUPPORTED')
                    continue  # Notifications are not evidence of a completed refresh.
                if value.get('id') != self.sequence: raise ControlError('CONTROL_RESPONSE_ID')
                if 'error' in value: raise ControlError('CONTROL_RPC_ERROR')
                if 'result' not in value: raise ControlError('CONTROL_PROTOCOL')
                return value['result']
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise ControlError('CONTROL_TIMEOUT')
            block = os.read(self.process.stdout.fileno(), 65536)
            if not block: raise ControlError('CONTROL_EOF')
            self.total += len(block)
            if self.total > MAX_BYTES: raise ControlError('CONTROL_RESPONSE_LIMIT')
            self.buffer += block

    def initialize(self):
        result = self.call('initialize', {'clientInfo': {'name': 'golem-owner-control', 'version': '1'}})
        if not isinstance(result, dict) or not isinstance(result.get('userAgent'), str):
            raise ControlError('CONTROL_INITIALIZE_INVALID')
        self.send({'method': 'initialized'})

    def close(self):
        try:
            if self.process.stdin: self.process.stdin.close()
        except OSError:
            pass
        try: self.process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            # This is our disposable official proxy, never the existing host.
            self.process.terminate()
            try: self.process.wait(timeout=1)
            except subprocess.TimeoutExpired: pass
        if self.process.stdout: self.process.stdout.close()


class CodexControl:
    def __init__(self, cli_path=None, socket_path=None):
        self.cli_path = Path(cli_path) if cli_path else next(iter(DESKTOP_BINARIES))
        self.socket_path = Path(socket_path) if socket_path else None

    def _base(self):
        return {'state': 'MANUAL', 'verified_desktop': False, 'host_pid': None,
                'host_kind': 'unknown', 'tools': [], 'server_status': 'NOT_OBSERVED',
                'model_tools': 'NOT_OBSERVED', 'active_turn': 'NOT_OBSERVED',
                'reload_supported': False, 'reload_scope': 'HOST_ALL_MCP_CONFIG_AND_LOADED_THREADS',
                'reason': 'SUPPORTED_CONTROL_SOCKET_NOT_SELECTED', 'socket_identity': None,
                'work_calls': 0, 'model_calls': 0}

    def _identity(self):
        if self.socket_path is None: raise ControlError('SUPPORTED_CONTROL_SOCKET_NOT_SELECTED')
        return _host_identity(self.cli_path, self.socket_path)

    def inspect(self, server_name='golem-local', thread_id=None):
        result = self._base()
        proxy = None
        try:
            identity = self._identity()
            result.update(verified_desktop=True, host_pid=identity['host_pid'],
                          host_kind=identity['host_kind'], socket_identity=identity,
                          reload_supported=True, reason='EXPLICIT_THREAD_REQUIRED', state='HOST_VERIFIED')
            if thread_id is None: return result
            if not isinstance(thread_id, str) or not thread_id or len(thread_id) > 128:
                raise ControlError('THREAD_ID_INVALID')
            if not isinstance(server_name, str) or not server_name or len(server_name) > 128:
                raise ControlError('SERVER_NAME_INVALID')
            proxy = _Proxy(self.cli_path, self.socket_path)
            proxy.initialize()
            loaded = proxy.call('thread/loaded/list', {'limit': 100})
            if (not isinstance(loaded, dict) or not isinstance(loaded.get('data'), list)
                    or len(loaded['data']) > 100 or not all(isinstance(key, str) for key in loaded['data'])
                    or thread_id not in loaded['data']):
                raise ControlError('THREAD_NOT_CONFIRMED_LOADED')
            if self._identity() != identity: raise ControlError('CONTROL_IDENTITY_CHANGED')
            reply = proxy.call('mcpServerStatus/list', {'threadId': thread_id, 'serverName': server_name,
                                                       'detail': 'toolsAndAuthOnly', 'limit': 1})
            if not isinstance(reply, dict) or not isinstance(reply.get('data'), list) or len(reply['data']) != 1:
                raise ControlError('SERVER_STATUS_UNAVAILABLE')
            server = reply['data'][0]
            if not isinstance(server, dict) or server.get('name') != server_name or not isinstance(server.get('tools'), dict):
                raise ControlError('SERVER_STATUS_UNAVAILABLE')
            if self._identity() != identity: raise ControlError('CONTROL_IDENTITY_CHANGED')
            result.update(state='OBSERVED', tools=sorted(server['tools']),
                          server_status=server.get('runtimeStatus') or 'NOT_OBSERVED',
                          reason='THREAD_SERVER_METADATA_ONLY', tools_error=server.get('toolsError'))
        except (ControlError, OSError, ValueError) as exc:
            result.update(state='MANUAL', reason=str(exc) if isinstance(exc, ControlError) else 'CONTROL_UNAVAILABLE',
                          reload_supported=False, tools=[], server_status='NOT_OBSERVED',
                          verified_desktop=False, host_pid=None, host_kind='unknown', socket_identity=None)
        finally:
            if proxy is not None: proxy.close()
        return result

    def reload(self, *, allow_host_wide=False, expected_socket_identity=None):
        result = self._base()
        proxy = None
        try:
            if allow_host_wide is not True: raise ControlError('HOST_WIDE_CONFIRMATION_REQUIRED')
            if not isinstance(expected_socket_identity, dict): raise ControlError('EXPECTED_IDENTITY_REQUIRED')
            identity = self._identity()
            if identity != expected_socket_identity: raise ControlError('CONTROL_IDENTITY_CHANGED')
            proxy = _Proxy(self.cli_path, self.socket_path)
            proxy.initialize()
            if self._identity() != identity: raise ControlError('CONTROL_IDENTITY_CHANGED')
            reply = proxy.call('config/mcpServer/reload')
            if not isinstance(reply, dict): raise ControlError('CONTROL_PROTOCOL')
            if self._identity() != identity: raise ControlError('CONTROL_IDENTITY_CHANGED')
            result.update(state='REFRESH_QUEUED', reason='QUEUE_ACK_ONLY', verified_desktop=True,
                          host_pid=identity['host_pid'], host_kind=identity['host_kind'],
                          socket_identity=identity, reload_supported=True)
        except (ControlError, OSError, ValueError) as exc:
            result.update(state='REFRESH_UNKNOWN' if proxy is not None and proxy.reload_dispatched else 'BLOCKED',
                          reason=str(exc) if isinstance(exc, ControlError) else 'CONTROL_UNAVAILABLE')
        finally:
            if proxy is not None: proxy.close()
        return result
