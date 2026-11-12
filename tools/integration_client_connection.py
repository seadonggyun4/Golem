"""Owner-local connection observations. Never apply policies or invoke Work tools.

Disk selection, live server, host tools and model delivery are separate facts.
The adapter environment is display provenance, not an authorization credential.
Only the official control proxy may request a host-wide refresh, after explicit
consent; unavailable host control leads to a normal-restart guide, not a new CLI
server, process signal, database change or automatic retry.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import tomllib


def adapter_contract():
    """Use our reviewed adapter payload, never import a selected arbitrary file."""
    try:
        import golem_adapter
        return golem_adapter
    except ModuleNotFoundError as error:
        if error.name != 'golem_adapter':
            raise
        import importlib.util
        path = Path(__file__).resolve().parents[1]/'plugins/golem/scripts/launcher.py'
        require(path.is_file(), 'ADAPTER_INSPECTION_UNAVAILABLE')
        spec = importlib.util.spec_from_file_location('golem_adapter_contract', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

LIMIT = 262144
MAX_CONNECTIONS = 16
ENDPOINT_ABSENT = 'CLOSED_ENDPOINT_ABSENT'
DIGEST = re.compile(r'[a-f0-9]{64}\Z')
HOST_CATALOG_STATES = frozenset((
    'HOST_CATALOG_NOT_REQUESTED', 'HOST_CATALOG_NOT_RELISTED',
    'HOST_CATALOG_REQUEST_PENDING', 'HOST_CATALOG_PARTIAL_RESPONSE',
    'HOST_CATALOG_RESPONSE_SENT', 'HOST_CATALOG_ERROR_SENT',
    'HOST_CATALOG_UNVERIFIED_PAGE', 'HOST_CATALOG_INVALID_RESPONSE',
))


class ConnectionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(value, code):
    if not value:
        raise ConnectionError(code)


def validate_host_catalog(value):
    """Validate bounded relay observations, never host/model delivery authority."""
    code = 'RELAY_HOST_CATALOG_FIELDS'
    fields = {'schema', 'child_generation', 'catalog_generation', 'state', 'requests',
              'responses', 'errors', 'list_changed_notifications_sent',
              'last_complete_generation', 'last_complete_sha256', 'last_complete_pages',
              'current_complete_sha256', 'current_complete_pages', 'model_delivery_verified'}
    require(type(value) is dict and set(value) == fields, code)
    require(value['schema'] == 'golem.host-tool-catalog-observation.v1' and
            type(value['state']) is str and value['state'] in HOST_CATALOG_STATES and
            value['model_delivery_verified'] is False, code)
    for key in ('child_generation', 'catalog_generation'):
        require(type(value[key]) is int and value[key] >= 0, code)
    require((value['child_generation'] == value['catalog_generation'] == 0) or
            1 <= value['child_generation'] <= value['catalog_generation'], code)
    for key in ('requests', 'responses', 'errors', 'list_changed_notifications_sent'):
        require(type(value[key]) is int and 0 <= value[key] <= (1 << 63) - 1, code)
    require(value['errors'] <= value['responses'] <= value['requests'], code)
    for prefix in ('last', 'current'):
        sha, pages = value[prefix+'_complete_sha256'], value[prefix+'_complete_pages']
        require((sha is None and pages is None) or
                (type(sha) is str and DIGEST.fullmatch(sha) and
                 type(pages) is int and 1 <= pages <= 128), code)
    generation = value['last_complete_generation']
    if value['last_complete_sha256'] is None:
        require(generation is None, code)
    else:
        require(type(generation) is int and 1 <= generation <= value['catalog_generation'], code)
    if value['current_complete_sha256'] is not None:
        require(value['state'] == 'HOST_CATALOG_RESPONSE_SENT' and
                generation == value['catalog_generation'] and
                value['current_complete_sha256'] == value['last_complete_sha256'] and
                value['current_complete_pages'] == value['last_complete_pages'] and
                value['responses'] >= value['current_complete_pages'], code)
    if value['state'] == 'HOST_CATALOG_RESPONSE_SENT':
        require(value['current_complete_sha256'] is not None, code)
    if value['state'] in ('HOST_CATALOG_NOT_REQUESTED', 'HOST_CATALOG_NOT_RELISTED'):
        require(value['requests'] == value['responses'] == value['errors'] == 0 and
                value['current_complete_sha256'] is None, code)
    return dict(value)


def read_file(path, *, private=False):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            all(not p.is_symlink() for p in (path, *path.parents)), 'CONNECTION_PATH')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and
                before.st_nlink == 1 and before.st_size <= LIMIT and
                (not private or before.st_mode & 0o077 == 0), 'CONNECTION_FILE')
        raw = os.read(fd, LIMIT + 1)
        after = os.fstat(fd)
        require(len(raw) == before.st_size and
                (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'CONNECTION_FILE_CHANGED')
        return raw
    finally:
        os.close(fd)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def observation_order(row):
    # Freshness is only a discovery priority hint, never identity/authority.
    return (row.get('endpoint_state') != 'PRESENT', -row.get('discovery_mtime_ns', 0), row['instance'])


def display_order(row):
    # Keep observed/reloadable rows visible ahead of preserved history, also
    # when the UI's separate bounded display cannot fit the entire catalog.
    priority = (0 if row.get('refreshable') else
                1 if row.get('relay_current') or row.get('state') == 'CURRENT_ACTIVE_SERVICE' else
                2 if row.get('state') == 'STALE_OR_UNVERIFIED_SERVICE' else
                4 if row.get('state') == ENDPOINT_ABSENT else 3)
    return (priority, -row.get('discovery_mtime_ns', 0), row.get('instance', ''))


def unique(items):
    result = {}
    for key, value in items:
        require(key not in result, 'CONNECTION_DUPLICATE_FIELD')
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique)


def owner_launch_description(launcher):
    """Decode only literal known-owner arguments; never eval/run launcher code."""
    args = launcher.get('args', [])
    values, directories = None, []
    if '-c' in args:
        require(len(args) == 4 and args[:3] == ['-I','-B','-c'], 'OPAQUE_LAUNCHER')
        code = args[args.index('-c') + 1]
        tree = ast.parse(code)
        aliases = {item.asname or item.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                   for item in n.names if item.name == 'integration_owner_desktop'}
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Attribute) and n.func.attr == 'main' and
                 isinstance(n.func.value, ast.Name) and n.func.value.id in aliases]
        require(len(calls) == 1 and len(calls[0].args) == 1 and not calls[0].keywords,
                'OPAQUE_LAUNCHER')
        values = ast.literal_eval(calls[0].args[0])
        for n in ast.walk(tree):
            if (isinstance(n, ast.Assign) and len(n.targets) == 1 and
                isinstance(n.targets[0], ast.Subscript) and
                isinstance(n.targets[0].value, ast.Attribute) and
                isinstance(n.targets[0].value.value, ast.Name) and
                n.targets[0].value.value.id == 'sys' and n.targets[0].value.attr == 'path'):
                declared = ast.literal_eval(n.value)
                require(isinstance(declared, list) and all(type(v) is str for v in declared), 'OPAQUE_LAUNCHER')
                directories.extend(declared)
        require(len(aliases) == 1 and len(tree.body) == 4, 'OPAQUE_LAUNCHER')
        alias = next(iter(aliases))
        # Only the generated linear literal entrypoint is understood. Branches,
        # alias replacement and arbitrary calls are opaque even if never run.
        expected = ast.parse('import sys;sys.path[:0]='+repr(directories)+
            ';import integration_owner_desktop as '+alias+';sys.exit('+alias+'.main('+repr(values)+'))')
        require(ast.dump(tree) == ast.dump(expected), 'OPAQUE_LAUNCHER')
    else:
        indexes = [i for i, v in enumerate(args) if Path(v).name == 'integration_owner_desktop.py']
        require(len(indexes) == 1, 'OPAQUE_LAUNCHER')
        i = indexes[0]
        values, directories = args[i+1:], [str(Path(args[i]).parent)]
    require(isinstance(values, list) and all(type(v) is str for v in values), 'OPAQUE_LAUNCHER')
    def option(key):
        require(values.count(key) == 1, 'OPAQUE_LAUNCHER')
        i = values.index(key)
        require(i + 1 < len(values), 'OPAQUE_LAUNCHER')
        return values[i+1]
    policy, pin = option('--policy'), option('--reviewed-policy-sha256')
    require(bool(DIGEST.fullmatch(pin)), 'CONNECTION_POLICY_DIGEST')
    require(digest(read_file(policy, private=True)) == pin, 'CONNECTION_POLICY_CHANGED')
    candidates = [Path(v)/'integration_owner_desktop.py' for v in directories
                  if Path(v).is_absolute() and (Path(v)/'integration_owner_desktop.py').is_file()]
    require(len(candidates) == 1, 'OPAQUE_RUNTIME')
    return {'policy_sha256':pin, 'runtime_path':str(candidates[0]),
            'runtime_sha256':digest(read_file(candidates[0]))}


def selected_connection(config_path, server_name='golem-local'):
    raw = read_file(config_path, private=True)
    servers = tomllib.loads(raw.decode()).get('mcp_servers', {})
    value = servers.get(server_name)
    require(isinstance(value, dict) and value.get('enabled', True) is True, 'CONNECTION_NOT_CONFIGURED')
    args = value.get('args')
    command = value.get('command')
    require(type(command) is str and Path(command).is_absolute() and
            re.fullmatch(r'python(?:3(?:\.[0-9]+)?)?', Path(command).name) is not None,
            'UNSUPPORTED_ADAPTER_DECLARATION')
    require(isinstance(args, list) and len(args) == 8 and args[:2] == ['-I', '-B'] and
            args[3:7] == ['serve', '--client', 'codex', '--state'] and
            Path(args[2]).name == 'launcher.py', 'UNSUPPORTED_ADAPTER_DECLARATION')
    read_file(args[2])
    state = Path(args[7])
    try:
        inspection = adapter_contract().inspect_state(state, 'codex')
    except (OSError, ValueError) as error:
        raise ConnectionError('CONNECTION_APPROVAL_CHANGED') from error
    approval_path = Path(inspection['approval_path'])
    approval_raw = read_file(approval_path,private=True)
    require(digest(approval_raw) == inspection['approval_sha256'], 'CONNECTION_APPROVAL_CHANGED')
    approval = decode(approval_raw)
    require(set(approval) == {'schema', 'launcher', 'launcher_sha256'} and
            approval['schema'] == 'golem.codex-launcher.v1' and
            type(approval['launcher']) is str and
            digest(approval['launcher'].encode()) == approval['launcher_sha256'], 'CONNECTION_APPROVAL_CHANGED')
    launcher = decode(approval['launcher'])
    require(set(launcher) == {'command', 'args'} and type(launcher['command']) is str and
            isinstance(launcher['args'], list) and all(type(v) is str for v in launcher['args']), 'CONNECTION_LAUNCHER')
    manifest = decode(read_file(Path(args[2]).parent.parent/'.codex-plugin/plugin.json'))
    require(manifest.get('name') == 'golem', 'CONNECTION_PACKAGE')
    selected = {'server_name':server_name, 'adapter_state':str(state),
                'adapter_path':args[2], 'adapter_command':command,
                'approval_sha256':digest(approval_raw),
                'launcher_sha256':approval['launcher_sha256'], 'package_version':manifest.get('version'),
                'config_sha256':digest(raw), 'policy_sha256':None, 'runtime_sha256':None}
    try:
        selected.update(owner_launch_description(launcher))
    except (ConnectionError, OSError, ValueError, TypeError, IndexError, SyntaxError):
        selected['identity_detail'] = 'OPAQUE_OR_CHANGED_LAUNCHER_NOT_EXECUTED'
    require(digest(read_file(config_path, private=True)) == selected['config_sha256'], 'CONNECTION_CONFIG_CHANGED')
    require(read_file(approval_path,private=True) == approval_raw,'CONNECTION_APPROVAL_CHANGED')
    return selected


def live_status(controller, runtime_path):
    """Metadata only; tools() applies the existing admission contract, no call()."""
    environment = os.environ
    pin = environment.get('GOLEM_LAUNCHER_SHA256')
    return {'schema':'golem.owner-connection-status.v1', 'pid':os.getpid(), 'ppid':os.getppid(),
            'client':environment.get('GOLEM_LAUNCHER_CLIENT'),
            'launcher_sha256':pin if pin and DIGEST.fullmatch(pin) else None,
            'adapter_state':environment.get('GOLEM_LAUNCHER_STATE'),
            'package_version':environment.get('GOLEM_LAUNCHER_PLUGIN_VERSION'),
            'policy_sha256':controller.owner.digest,
            'runtime_path':str(Path(runtime_path).resolve()),
            'runtime_sha256':digest(read_file(Path(runtime_path).resolve())),
            'tools':['golem_'+name for name in controller.scoped.tools()],
            'observation':'LOCAL_PROCESS_METADATA_NOT_OWNER_IDENTITY', 'Work_calls':0,
            'model_tool_delivery':'NOT_OBSERVED', 'execution_authorized':False}


def desktop_parent(pid, reader=None):
    """Bounded same-uid process ancestry; no process-wide scan or process signal."""
    if reader is None:
        def reader(number):
            result = subprocess.run(['/bin/ps','-p',str(number),'-o','pid=,ppid=,uid=,comm='],
                                    capture_output=True, text=True, timeout=2, check=True)
            fields = result.stdout.strip().split(None, 3)
            require(len(fields) == 4, 'PROCESS_UNAVAILABLE')
            return {'pid':int(fields[0]),'ppid':int(fields[1]),'uid':int(fields[2]),'exe':fields[3]}
    seen, host = set(), None
    for _ in range(8):
        require(type(pid) is int and pid > 1 and pid not in seen, 'PROCESS_ANCESTRY')
        seen.add(pid)
        row = reader(pid)
        require(row['pid'] == pid and row['uid'] == os.getuid(), 'PROCESS_OWNER')
        path = row['exe']
        for kind in ('ChatGPT', 'Codex'):
            marker = '/'+kind+'.app/Contents/'
            if marker in path and ('codex' in Path(path).name.lower() or 'CodexCLI.app/' in path):
                host = {'host_kind':kind, 'host_pid':pid, 'host_executable':path}
        if host:
            return host
        pid = row['ppid']
    raise ConnectionError('DESKTOP_PARENT_NOT_OBSERVED')


def compare(selected, rows, host):
    current, desktop, unknown = [], [], []
    for row in rows:
        if row.get('state') == ENDPOINT_ABSENT:
            continue
        if row.get('kind') == 'codex-connection-relay':
            if not row.get('relay_current'):
                unknown.append(row)
            continue
        if row.get('host_kind') not in ('ChatGPT','Codex'):
            unknown.append(row)
            continue
        desktop.append(row)
        keys = ('launcher_sha256','policy_sha256','runtime_sha256','adapter_state','package_version')
        tools = row.get('tools')
        valid_tools = (isinstance(tools,list) and 0 < len(tools) <= 256 and
            all(type(t) is str and re.fullmatch(r'golem_[a-z0-9_]{1,120}',t) for t in tools)
            and len(set(tools)) == len(tools))
        matches = valid_tools and all(selected.get(k) is not None and row.get(k) == selected[k] for k in keys)
        row['state'] = 'CURRENT_ACTIVE_SERVICE' if matches else 'STALE_OR_UNVERIFIED_SERVICE'
        if matches:
            current.append(row)
    # A single matching standalone probe can never qualify the Desktop host.
    if desktop and len(current) == len(desktop) and not unknown:
        state, mode = 'CURRENT_ACTIVE_SERVICE_MODEL_UNVERIFIED', 'VERIFIED'
    elif any(row.get('state') in ('LEGACY_OR_UNAVAILABLE', 'RELAY_UNAVAILABLE',
             'RELAY_OBSERVATION_UNAVAILABLE', 'NOT_OBSERVED', 'BOUNDED_OBSERVATION_LIMIT') for row in unknown):
        # Missing observations are not evidence that restarting the host helps.
        state, mode = 'CONNECTION_OBSERVATION_INCOMPLETE', 'OBSERVATION_INCOMPLETE'
    elif host.get('reload_supported') and host.get('verified_desktop'):
        state, mode = 'RELOAD_REQUIRED', 'OFFICIAL_RELOAD_AVAILABLE'
    else:
        state, mode = 'DESKTOP_RELOAD_NOT_CONFIRMED', 'MANUAL_RESTART_REQUIRED'
    return state, mode


class ConnectionMonitor:
    def __init__(self, config_path, review_directory, *, control=None, observer=None, ancestry=None, relay=None):
        self.config_path = Path(config_path)
        self.directory = Path(review_directory)
        self.control, self.observer, self.ancestry = control, observer, ancestry or desktop_parent
        self.relay = relay
        self.attempted = set()
        self.last = None
        self.target_observation = None
        self.refresh_outcome = None

    def clear_target_observation(self):
        self.target_observation = None
        self.last = None

    def set_target_observation(self, thread_id, turn_id, marker, tools, required_tools=None):
        """Explicit external definition observation; never a grant or chat auth.

        The observer copies this from the intended chat's actual inventory. A
        process ID, saved plan, tool call result or guessed marker is insufficient.
        Fresh relay metadata is independently compared on every inspect/refresh.
        """
        self.target_observation = None
        for value in (thread_id, turn_id):
            require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value),
                    'TARGET_CHAT_ID_REQUIRED')
        require(type(tools) is list and 0 < len(tools) <= 256 and
                all(type(t) is str and re.fullmatch(r'golem_[a-z0-9_]{1,120}', t) for t in tools) and len(set(tools)) == len(tools),
                'TARGET_TOOL_DEFINITIONS_REQUIRED')
        required_tools = [] if required_tools is None else required_tools
        require(type(required_tools) is list and len(required_tools) <= 256 and
                all(type(t) is str and re.fullmatch(r'golem_[a-z0-9_]{1,120}', t) for t in required_tools) and
                len(set(required_tools)) == len(required_tools), 'REQUIRED_TOOL_DEFINITIONS_INVALID')
        try:
            identity = self.relay_client().parse_definition_marker(marker)
        except (ValueError, AttributeError) as error:
            raise ConnectionError('TARGET_DEFINITION_MARKER_REQUIRED') from error
        self.target_observation = {'source':'EXTERNAL_MODEL_DEFINITION_OBSERVATION',
            'thread_id':thread_id, 'turn_id':turn_id, 'server_name':'golem-local',
            'marker':identity, 'tools':list(tools), 'required_tools':list(required_tools),
            'observed_at_ns':time.time_ns()}
        self.last = None

    def target_matches(self, row):
        observation = self.target_observation
        if not observation or row.get('kind') != 'codex-connection-relay':
            return False
        try:
            return (self.relay_client().parse_definition_marker(row.get('definition_marker')) ==
                    observation['marker'] and row.get('instance') == observation['marker']['instance'] and
                    row.get('host_kind') in ('ChatGPT','Codex') and row.get('state') == 'READY' and
                    0 <= time.time_ns() - observation['observed_at_ns'] <= 300_000_000_000)
        except (ValueError, AttributeError):
            return False

    def readiness(self, selected, rows):
        from integration_connection_readiness import classify
        model = self.target_observation
        if model is None:
            return {'state':'BLOCKED','reason':'TARGET_CHAT_OBSERVATION_REQUIRED',
                    'preparation_allowed':False,'execution_authorized':False}
        matches = [row for row in rows if self.target_matches(row)]
        live = dict(matches[0], observed_at_ns=time.time_ns(),
                    definition_nonce=model['marker']['definition_nonce']) if len(matches) == 1 else None
        return classify(selected=selected, target={key:model[key] for key in ('thread_id','server_name')},
                        live=live, model=model, refresh=self.refresh_outcome, now_ns=time.time_ns(),
                        required_tools=model['required_tools'])

    def observe(self):
        # Import only when explicitly inspecting; headless MCP startup remains UI-free.
        import integration_owner_desktop as desktop
        def snapshot(instance):
            value = desktop.descriptor(self.directory, instance)
            raw = read_file(self.directory/(instance+'.json'), private=True)
            require(decode(raw) == value, 'CONNECTION_DESCRIPTOR_CHANGED')
            metadata = (self.directory/(instance+'.json')).lstat()
            path = self.directory/(instance+'.sock')
            try:
                info = path.lstat()
                require(stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid() and
                        stat.S_IMODE(info.st_mode) == 0o600, 'CONNECTION_SOCKET')
                endpoint = {'endpoint_state':'PRESENT', 'socket_identity':(info.st_dev, info.st_ino)}
            except FileNotFoundError:
                endpoint = {'endpoint_state':'ABSENT'}
            require(read_file(self.directory/(instance+'.json'), private=True) == raw,
                    'CONNECTION_DESCRIPTOR_CHANGED')
            return {'instance':instance, 'kind':value['kind'],
                    'descriptor_sha256':digest(raw), 'discovery_mtime_ns':metadata.st_mtime_ns, **endpoint}
        catalog, result, closed = [], [], []
        try:
            desktop.private_directory(self.directory)
            paths = sorted(self.directory.glob('*.json'))
            require(len(paths) <= 128, 'OWNER_CONNECTION_LIMIT')
        except Exception as error:
            return [{'state':'NOT_OBSERVED', 'reason':getattr(error,'code','CONNECTION_CATALOG_UNAVAILABLE')}]
        for path in paths:
            if path.name == 'owner-app.json':
                continue
            try:
                row = snapshot(path.stem)
                if row['kind'] != 'review':
                    continue
            except Exception as error:
                row = {'instance':path.stem, 'state':'NOT_OBSERVED',
                       'reason':getattr(error,'code','CONNECTION_DESCRIPTOR_UNAVAILABLE')}
            (closed if row.get('endpoint_state') == 'ABSENT' else catalog).append(row)
        # Missing endpoints never consume the live IPC budget. Unknown records
        # still count and block CURRENT; valid candidates are observed first.
        catalog.sort(key=observation_order)
        for row in catalog[:MAX_CONNECTIONS]:
            instance = row['instance']
            try:
                require(row.get('endpoint_state') == 'PRESENT', row.get('reason','CONNECTION_ENDPOINT_UNAVAILABLE'))
                require(snapshot(instance) == row, 'CONNECTION_DESCRIPTOR_CHANGED')
                remote = desktop.RemoteController(self.directory, instance)
                value = remote.connection_status()
                require(value.get('schema') == 'golem.owner-connection-status.v1', 'CONNECTION_STATUS_SCHEMA')
                require(value.get('pid') == remote.last_peer_pid, 'CONNECTION_PEER_PID')
                require(isinstance(value.get('tools'),list) and 0 < len(value['tools'])<=256 and
                        all(type(t) is str and re.fullmatch(r'golem_[a-z0-9_]{1,120}',t) for t in value['tools']) and
                        len(set(value['tools'])) == len(value['tools']), 'CONNECTION_TOOLS')
                require(not set(value) & {'state','kind','instance','endpoint_state','socket_identity',
                        'descriptor_sha256','relay_current','refreshable','discovery_mtime_ns'}, 'CONNECTION_STATUS_FIELDS')
                require(snapshot(instance) == row, 'CONNECTION_ENDPOINT_CHANGED')
                row.update({key:value.get(key) for key in ('pid','ppid','client','launcher_sha256',
                    'adapter_state','package_version','policy_sha256','runtime_path','runtime_sha256','tools')},
                    **self.ancestry(value['pid']), tools_count=len(value['tools']))
            except Exception as error:
                row.update(state='LEGACY_OR_UNAVAILABLE', reason=getattr(error,'code','CONNECTION_OBSERVATION_UNAVAILABLE'))
            result.append(row)
        if len(catalog) > MAX_CONNECTIONS:
            result.extend(dict(row, state='NOT_OBSERVED', reason='BOUNDED_OBSERVATION_LIMIT')
                          for row in catalog[MAX_CONNECTIONS:])
            result.append({'state':'NOT_OBSERVED','reason':'BOUNDED_OBSERVATION_LIMIT'})
        for row in closed:
            try:
                require(snapshot(row['instance']) == row, 'CONNECTION_ENDPOINT_CHANGED')
                row.update(state=ENDPOINT_ABSENT, reason='SOCKET_PATH_ABSENT_NOT_PROCESS_OR_WORK_COMPLETION')
            except Exception as error:
                row.update(state='NOT_OBSERVED',reason=getattr(error,'code','CONNECTION_ENDPOINT_UNAVAILABLE'))
            result.append(row)
        return result

    def relay_client(self):
        if self.relay is None:
            try:
                import connection_relay
            except ModuleNotFoundError:
                # Source checkout only. Installed runtimes contain the exact
                # canonical relay payload beside this module.
                import importlib.util
                path = Path(__file__).resolve().parents[1]/'plugins/golem/scripts/connection_relay.py'
                require(path.is_file(), 'RELAY_CLIENT_UNAVAILABLE')
                spec = importlib.util.spec_from_file_location('golem_connection_relay', path)
                connection_relay = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(connection_relay)
            self.relay = connection_relay
        return self.relay

    def observe_relays(self, selected):
        result = []
        try:
            relay = self.relay_client()
            descriptors = relay.descriptors()
        except FileNotFoundError:
            return []
        except Exception:
            return [{'kind':'codex-connection-relay','state':'RELAY_OBSERVATION_UNAVAILABLE'}]
        closed = [row for row in descriptors if row.get('endpoint_state') == 'ABSENT']
        candidates = [row for row in descriptors if row.get('endpoint_state') != 'ABSENT']
        candidates.sort(key=observation_order)
        for descriptor in candidates[:MAX_CONNECTIONS]:
            row = {**descriptor, 'refreshable':False}
            try:
                require(descriptor.get('endpoint_state') == 'PRESENT',
                        descriptor.get('reason','RELAY_ENDPOINT_UNAVAILABLE'))
                require(relay.endpoint(descriptor['instance']) == descriptor, 'RELAY_IDENTITY_CHANGED')
                observed = relay.request(descriptor['instance'],'status',{})
                require(observed.get('ok') is True, 'RELAY_STATUS_UNAVAILABLE')
                value = observed['value']
                require(value['pid'] == descriptor['pid'] and value['instance'] == descriptor['instance'],
                        'RELAY_IDENTITY_CHANGED')
                require(value.get('state') in ('STARTING','READY','DRAINING','UNKNOWN') and
                        type(value.get('busy')) is bool, 'RELAY_STATUS_FIELDS')
                require(not set(value) & {'endpoint_state','socket_identity','descriptor_sha256',
                        'relay_current','refreshable','discovery_mtime_ns'}, 'RELAY_STATUS_FIELDS')
                # Legacy relays cannot observe host catalog requests. Missing
                # metadata remains unknown, never a synthetic zero/success.
                catalog = validate_host_catalog(value['host_catalog']) if 'host_catalog' in value else None
                require(catalog is None or value['state'] != 'READY' or catalog['child_generation'] >= 1,
                        'RELAY_HOST_CATALOG_FIELDS')
                if value.get('definition_marker') is not None:
                    marker = relay.parse_definition_marker(value['definition_marker'])
                    require(marker['instance'] == value['instance'] and catalog is not None and
                            all(marker[key] == catalog[key] for key in ('child_generation','catalog_generation')),
                            'RELAY_DEFINITION_MARKER_MISMATCH')
                require(relay.endpoint(descriptor['instance']) == descriptor, 'RELAY_IDENTITY_CHANGED')
                row.update({key:value.get(key) for key in ('pid','instance','state','busy','plugin_version',
                    'selected_state','launcher_sha256','approval_sha256','definition_marker',
                    'definition_tools_sha256','definition_tool_count')}, **self.ancestry(value['pid']))
                row['host_catalog'] = catalog
                same = (value['launcher_sha256'], value['approval_sha256'],value['selected_state']) == (
                    selected['launcher_sha256'],selected['approval_sha256'],selected['adapter_state'])
                row['relay_current'] = (same and value['state'] == 'READY' and
                    row.get('host_kind') in ('ChatGPT','Codex') and value['plugin_version'] == selected['package_version'])
                row['refresh_candidate'] = (not same and value['state'] == 'READY' and not value['busy']
                    and row.get('host_kind') in ('ChatGPT','Codex')
                    and value['plugin_version'] == selected['package_version'])
                row['target_bound'] = self.target_matches(row)
                row['refreshable'] = row['refresh_candidate'] and row['target_bound']
            except Exception as error:
                row.update(state='RELAY_UNAVAILABLE',reason=getattr(error,'code','RELAY_OBSERVATION_UNAVAILABLE'))
            result.append(row)
        if len(candidates) > MAX_CONNECTIONS:
            result.extend(dict(row, state='NOT_OBSERVED', reason='BOUNDED_OBSERVATION_LIMIT', refreshable=False)
                          for row in candidates[MAX_CONNECTIONS:])
            result.append({'kind':'codex-connection-relay','state':'BOUNDED_OBSERVATION_LIMIT'})
        for descriptor in closed:
            row = {**descriptor, 'refreshable':False}
            try:
                require(relay.endpoint(descriptor['instance']) == descriptor, 'RELAY_IDENTITY_CHANGED')
                row.update(state=ENDPOINT_ABSENT, reason='SOCKET_PATH_ABSENT_NOT_PROCESS_OR_WORK_COMPLETION')
            except Exception as error:
                row.update(state='RELAY_UNAVAILABLE',reason=getattr(error,'code','RELAY_ENDPOINT_UNAVAILABLE'))
            result.append(row)
        return result

    def inspect(self):
        from datetime import datetime, timezone
        report = {'model_tool_delivery':'NOT_OBSERVED','Work_calls':0,'automatic_retry_allowed':False,
                  'observed_at':datetime.now(timezone.utc).isoformat()}
        try:
            selected = selected_connection(self.config_path)
        except Exception as error:
            report.update(state='CONNECTION_NOT_CONFIGURED', selected={}, connections=[],
                          summary='현재 Golem 설정을 확인할 수 없습니다. 설정을 변경하거나 연결을 시작하지 않았습니다.',
                          reload={'mode':'NOT_CONFIGURED','reason':getattr(error,'code','CONNECTION_READ_FAILED'),'steps':[]})
            self.last = report
            return report
        rows = self.observer() if self.observer else self.observe()
        # Injected observers are complete deterministic fixture observations.
        if self.observer is None or self.relay is not None:
            rows.extend(self.observe_relays(selected))
        host = self.control.inspect(server_name='golem-local', **(
            {'thread_id':self.target_observation['thread_id']} if self.target_observation else {})) if self.control else {
            'verified_desktop':False,'reload_supported':False,'reason':'SUPPORTED_CONTROL_UNAVAILABLE'}
        require(digest(read_file(self.config_path, private=True)) == selected['config_sha256'], 'CONNECTION_CONFIG_CHANGED')
        state, mode = compare(selected, rows, host)
        if any(row.get('refreshable') for row in rows):
            state, mode = 'GOLEM_REFRESH_REQUIRED', 'GOLEM_RELAY_AVAILABLE'
        elif any(row.get('refresh_candidate') for row in rows):
            state, mode = 'TARGET_NOT_IDENTIFIED', 'TARGET_NOT_IDENTIFIED'
        rows.sort(key=display_order)
        kinds = {r.get('host_kind') for r in rows if r.get('host_kind') in ('ChatGPT','Codex')}
        kind = next(iter(kinds)) if len(kinds)==1 else None
        menu = kind+' → '+kind+' 종료(⌘Q)' if kind else '실제 사용 중인 Codex/ChatGPT 앱의 앱 메뉴 → 종료'
        steps = ['다른 대화와 작업을 저장하고 진행 중인 작업이 끝났는지 확인합니다.',
                 menu+'로 정상 종료한 뒤 같은 앱을 다시 엽니다. 창 닫기는 앱 종료가 아닙니다.',
                 '이 창의 재시작 후 상태 확인을 눌러 새 launcher·정책·runtime·도구를 다시 대조합니다.',
                 '모델에 도구가 전달됐는지는 기존 개발 대화의 실제 도구 목록에서 별도로 확인합니다. Work 호출은 하지 않습니다.']
        if mode == 'OFFICIAL_RELOAD_AVAILABLE':
            steps = ['공식 API는 Golem만 선택할 수 없고 이 호스트의 전체 MCP 설정 갱신을 요청합니다.',
                     '다른 진행 작업을 확인하고 전체 호스트 갱신에 동의한 경우에만 갱신 버튼을 누릅니다.',
                     '접수 응답은 완료가 아닙니다. 이후 상태 확인으로 실제 연결과 도구를 다시 대조합니다.']
        if mode == 'GOLEM_RELAY_AVAILABLE':
            steps = ['목록에서 갱신 가능한 Golem 연결 하나를 선택합니다. 다른 연결은 변경하지 않습니다.',
                     '같은 호스트 PID나 준비안 보유만으로 현재 대화의 연결을 확정할 수 없습니다. 해당 대화 연결 근거를 별도로 확인합니다.',
                     '진행 중인 요청이 없는지 다시 확인한 뒤 기존 child를 정상 EOF로 종료합니다.',
                     '선택된 정확한 launcher·승인 지문을 다시 검사해 새 child를 시작하고 도구 목록 변경을 알립니다.',
                     '변경 알림만으로 호스트가 목록을 다시 읽는다고 가정하지 않습니다. 호스트 목록 관측과 모델 전달은 각각 확인합니다.',
                     '연결 갱신과 모델의 도구 전달은 별개입니다. 실패·응답 유실은 자동 재시도하지 않습니다.']
        if mode == 'TARGET_NOT_IDENTIFIED':
            steps = ['현재 대화의 실제 도구 정의에서 연결 표식과 도구 이름을 확인합니다. Work 호출은 하지 않습니다.',
                     '대화·turn·표식을 대조한 행만 갱신 대상으로 선택할 수 있습니다. PID·준비안·수동 행 선택만으로 갱신하지 않습니다.',
                     '구버전/표식 미전달 호스트는 대상 미확인으로 보존합니다. 지원되는 호스트 경로 없이 임의 연결을 갱신하지 않습니다.']
        if mode == 'OBSERVATION_INCOMPLETE':
            steps = ['일부 연결을 관찰하지 못했습니다. 관찰한 행과 미확인 사유를 확인합니다.',
                     '활성·불확실 후보는 기록의 수정 시각이 최근인 순서로 최대 16개만 관찰합니다. 시각은 신원·최신성 인증이 아닙니다.',
                     '나머지 연결은 미관찰로 보존합니다. 기록을 삭제하거나 한도를 늘리지 않습니다.',
                     '필요하면 연결 상태 확인을 명시적으로 다시 선택합니다. 자동 재시도·정상 재시작은 요청하지 않습니다.']
        report.update(state=state, summary='디스크 선택과 실제 서버 연결을 대조했습니다. 모델 전달·실행 권한은 별도입니다.',
                      selected=selected, connections=rows, host_control=host,
                      reload={'mode':mode,'reason':host.get('reason','실제 활성 연결과 선택 지문 대조'),'steps':steps})
        report['target_bound'] = any(self.target_matches(row) for row in rows)
        report['readiness'] = self.readiness(selected, rows)
        if report['readiness'].get('preparation_allowed') is True:
            report['model_tool_delivery'] = 'EXTERNALLY_OBSERVED_SAME_CHAT_DEFINITIONS'
        report['refresh_token'] = digest(json.dumps({'selected':selected,'mode':mode,
            'host':host.get('socket_identity'), 'connections':rows,
            'target':self.target_observation}, sort_keys=True).encode())
        self.last = report
        return report


    def request_refresh(self, *, expected_token=None, connection_instance=None):
        report = self.inspect()
        mode = report['reload']['mode']
        if mode not in ('OFFICIAL_RELOAD_AVAILABLE','GOLEM_RELAY_AVAILABLE'):
            return report
        require(expected_token is not None and expected_token == report.get('refresh_token'),
                'REFRESH_SELECTION_CHANGED')
        if mode == 'GOLEM_RELAY_AVAILABLE':
            targets = [row for row in report['connections'] if row.get('refreshable') and
                       row.get('instance') == connection_instance]
            require(len(targets) == 1, 'REFRESH_CONNECTION_SELECTION_REQUIRED')
            row, selected = targets[0], report['selected']
            require(self.target_matches(row), 'REFRESH_TARGET_NOT_IDENTIFIED')
            attempt = ('relay',connection_instance,selected['launcher_sha256'],selected['approval_sha256'])
            require(attempt not in self.attempted,'REFRESH_ALREADY_ATTEMPTED_NO_RETRY')
            self.attempted.add(attempt)
            self.refresh_outcome = {'state':'UNKNOWN','attempts':1}
            # Dispatch invalidates the pre-refresh chat observation even if the
            # host/relay acknowledges before replacing its catalog. A plain
            # inspect cannot promote that old turn back to preparation-ready.
            # Selection/no-dispatch errors above retain the prior observation.
            self.clear_target_observation()
            result = self.relay_client().request(connection_instance,'refresh',{
                'expected_launcher_sha256':row['launcher_sha256'],
                'expected_approval_sha256':row['approval_sha256'],
                'state':selected['adapter_state'],'approval_sha256':selected['approval_sha256'],
                'launcher_sha256':selected['launcher_sha256'],'config_sha256':selected['config_sha256']})
            self.refresh_outcome = {'state':'ACKNOWLEDGED' if result.get('ok') is True else 'FAILED','attempts':1}
            report['reload'] = {'mode':'VERIFY_REQUIRED','reason':'Golem child 갱신 결과와 모델 도구 전달을 별도로 확인합니다.',
                'steps':['상태 확인으로 새 연결을 대조합니다. 실패나 응답 유실이면 같은 갱신을 재요청하지 않습니다.']}
            report['refresh_result'] = result
            report['readiness'] = {'state':'BLOCKED','reason':'POST_REFRESH_OBSERVATION_REQUIRED',
                                   'preparation_allowed':False,'execution_authorized':False}
            report['model_tool_delivery'] = 'NOT_OBSERVED'
            report['target_bound'] = False
            self.last = report
            return report
        attempt = ('host',report['host_control']['socket_identity']['inode'])
        require(attempt not in self.attempted, 'REFRESH_ALREADY_ATTEMPTED_NO_RETRY')
        self.attempted.add(attempt)
        # UI requires an explicit host-wide consent checkbox before this method.
        self.refresh_outcome = {'state':'UNKNOWN','attempts':1}
        self.clear_target_observation()
        result = self.control.reload(allow_host_wide=True,
                                     expected_socket_identity=report['host_control']['socket_identity'])
        self.refresh_outcome = {'state':{'REFRESH_QUEUED':'ACKNOWLEDGED',
                                'REFRESH_UNKNOWN':'UNKNOWN'}.get(result.get('state'),'FAILED'),'attempts':1}
        report['reload'] = {'mode':'REFRESH_QUEUED' if result.get('state') == 'REFRESH_QUEUED' else 'VERIFY_REQUIRED',
                            'reason':'공식 요청의 접수와 실제 Desktop 반영은 다릅니다. 자동 재시도하지 않습니다.',
                            'steps':['상태 확인으로 실제 활성 연결을 대조합니다. 같은 갱신 요청을 재실행하지 않습니다.']}
        report['refresh_result'] = result
        report['readiness'] = {'state':'BLOCKED','reason':'POST_REFRESH_OBSERVATION_REQUIRED',
                               'preparation_allowed':False,'execution_authorized':False}
        report['model_tool_delivery'] = 'NOT_OBSERVED'
        report['target_bound'] = False
        self.last = report
        return report

def main(argv=None):
    """Owner-local read-only check. No refresh/config selection/Work dispatch."""
    import argparse
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--review-directory', required=True, type=Path)
    parser.add_argument('--model-observation', type=Path)
    parser.add_argument('--model-observation-sha256')
    args = parser.parse_args(argv)
    try:
        require(bool(args.model_observation) == bool(args.model_observation_sha256),
                'MODEL_OBSERVATION_PIN_REQUIRED')
        monitor = ConnectionMonitor(args.config, args.review_directory)
        if args.model_observation:
            raw = read_file(args.model_observation, private=True)
            require(digest(raw) == args.model_observation_sha256, 'MODEL_OBSERVATION_CHANGED')
            observation = decode(raw)
            require(type(observation) is dict and set(observation) == {'thread_id','turn_id','marker','tools','required_tools','observed_at_ns'},
                    'MODEL_OBSERVATION_FIELDS')
            require(type(observation['observed_at_ns']) is int and
                    0 <= time.time_ns() - observation['observed_at_ns'] <= 300_000_000_000,
                    'MODEL_OBSERVATION_STALE')
            monitor.set_target_observation(**{k:v for k,v in observation.items() if k != 'observed_at_ns'})
            monitor.target_observation['observed_at_ns'] = observation['observed_at_ns']
        report = monitor.inspect()
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if report.get('readiness', {}).get('preparation_allowed') is True else 2
    except (ValueError, OSError) as error:
        print(json.dumps({'state':'BLOCKED','reason':getattr(error,'code','CONNECTION_CHECK_FAILED'),
                          'preparation_allowed':False,'execution_authorized':False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
