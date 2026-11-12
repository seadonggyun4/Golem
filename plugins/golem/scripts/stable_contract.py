"""Opt-in owner-local fixed definitions and exact runtime selection storage.

This module publishes only selection records. It never starts a launcher,
changes its approval, grants a Work operation or claims a live transition.
The lock is a cooperative local-owner contract, not human authentication.
"""
from contextlib import contextmanager
import fcntl
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import re
import stat

CATALOG_LIMIT = 512 * 1024
SELECTION_LIMIT = 16 * 1024
MAX_TOOLS = 128
MAX_REVISIONS = 256
PROFILES = frozenset(('read', 'prepare', 'task', 'quality', 'parallel'))
CLIENTS = frozenset(('codex', 'claude-desktop'))
DIGEST = re.compile(r'[0-9a-f]{64}')
SELECTION_FIELDS = frozenset(('schema', 'client', 'revision', 'previous_sha256',
    'catalog_sha256', 'adapter_state', 'approval_sha256', 'launcher_sha256'))
HEAD_FIELDS = frozenset(('schema', 'client', 'revision', 'selection_sha256', 'catalog_sha256'))
# Installed entrypoints inject the exact typed inventory from their reviewed
# closed bundle. No handwritten-catalog or arbitrary-tool fallback is provided.
_VERIFIED_TYPED_INDEX = globals().get('_VERIFIED_TYPED_INDEX')


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def encode(value):
    """Canonical bytes used by explicit owner-side candidate builders."""
    return canonical(value)


def _pairs(items):
    value = {}
    for key, item in items:
        require(key not in value, 'DUPLICATE_FIELD')
        value[key] = item
    return value


def decode(raw):
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ContractError('NONFINITE_JSON')))
        require(canonical(value) == raw, 'NONCANONICAL_JSON')
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as error:
        raise ContractError('INVALID_JSON') from error


def _pin(value):
    return type(value) is str and DIGEST.fullmatch(value) is not None


def read(path, limit, adapter):
    """Same exact private-file contract as the adapter, with catalog's bound."""
    path = adapter.canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and stat.S_IMODE(before.st_mode) & 0o077 == 0 and before.st_nlink == 1
                and before.st_size <= limit, 'UNSAFE_PRIVATE_FILE')
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        require(len(raw) == before.st_size and len(raw) <= limit and
                all(getattr(before, key) == getattr(after, key) for key in fields), 'FILE_CHANGED')
        return raw
    finally:
        os.close(fd)


def validate_catalog(raw):
    require(len(raw) <= CATALOG_LIMIT, 'CATALOG_SIZE')
    value = decode(raw)
    require(type(value) is dict and set(value) == {'schema', 'profile', 'tools', 'tools_sha256'}
            and value['schema'] == 'golem.fixed-tool-catalog.v1'
            and type(value['profile']) is str and value['profile'] in PROFILES, 'CATALOG_FIELDS')
    tools = value['tools']
    require(type(tools) is list and 0 < len(tools) <= MAX_TOOLS, 'CATALOG_TOOLS')
    names = []
    for tool in tools:
        require(type(tool) is dict and set(tool) == {'name', 'inputSchema', 'description', 'annotations'},
                'TOOL_FIELDS')
        name = tool['name']
        require(type(name) is str and re.fullmatch(r'golem_[a-z0-9_]{1,120}', name), 'TOOL_NAME')
        require(type(tool['description']) is str and len(tool['description'].encode()) <= 16384,
                'TOOL_DESCRIPTION')
        schema = tool['inputSchema']
        direct = type(schema) is dict and schema.get('type') == 'object' and type(schema.get('properties')) is dict
        union = (type(schema) is dict and set(schema) == {'type', 'oneOf'}
                 and schema['type'] == 'object' and type(schema['oneOf']) is list
                 and 0 < len(schema['oneOf']) <= MAX_TOOLS and all(
                     type(branch) is dict and branch.get('type') == 'object'
                     and type(branch.get('properties')) is dict for branch in schema['oneOf']))
        require(direct or union, 'TOOL_INPUT_SCHEMA')
        annotations = tool['annotations']
        require(type(annotations) is dict and set(annotations) ==
                {'readOnlyHint', 'destructiveHint', 'idempotentHint', 'openWorldHint'}
                and all(type(item) is bool for item in annotations.values()), 'TOOL_ANNOTATIONS')
        names.append(name)
    require(names == sorted(names) and len(set(names)) == len(names), 'TOOL_ORDER_OR_DUPLICATE')
    require(_pin(value['tools_sha256']) and value['tools_sha256'] == digest(canonical(tools)),
            'CATALOG_TOOLS_DIGEST')
    _typed_catalog(value)
    return value


def _typed_catalog(catalog):
    index = _VERIFIED_TYPED_INDEX
    require(type(index) is dict and set(index) == {'schema', 'profiles', 'tools'}
            and index['schema'] == 'golem.typed-interface-inventory.v1', 'TYPED_INTERFACE_REQUIRED')
    profiles, tools = index['profiles'], index['tools']
    require(type(profiles) is dict and set(profiles) == PROFILES
            and type(tools) is dict and 0 < len(tools) <= MAX_TOOLS, 'TYPED_INTERFACE_FIELDS')
    require(all(type(name) is str and re.fullmatch(r'golem_[a-z0-9_]{1,120}', name)
                and type(tool) is dict and tool.get('name') == name for name, tool in tools.items()),
            'TYPED_INTERFACE_TOOLS')
    for names in profiles.values():
        require(type(names) is list and 0 < len(names) <= MAX_TOOLS
                and all(type(name) is str and name in tools for name in names)
                and names == sorted(names) and len(set(names)) == len(names), 'TYPED_INTERFACE_PROFILE')
    for tool in catalog['tools']:
        require(tool['name'] in profiles[catalog['profile']], 'TYPED_TOOL_OUTSIDE_PROFILE')
        require(tools.get(tool['name']) == tool, 'TYPED_TOOL_UNSUPPORTED_OR_CHANGED')


def validate_selection(raw, adapter):
    require(len(raw) <= SELECTION_LIMIT, 'SELECTION_SIZE')
    value = decode(raw)
    require(type(value) is dict and set(value) == SELECTION_FIELDS
            and value['schema'] == 'golem.stable-selection.v1'
            and type(value['client']) is str and value['client'] in CLIENTS,
            'SELECTION_FIELDS')
    revision = value['revision']
    require(type(revision) is int and 1 <= revision <= MAX_REVISIONS, 'SELECTION_REVISION')
    require((revision == 1 and value['previous_sha256'] is None) or
            (revision > 1 and _pin(value['previous_sha256'])), 'SELECTION_PREVIOUS')
    require(all(_pin(value[key]) for key in ('catalog_sha256', 'approval_sha256', 'launcher_sha256')),
            'SELECTION_DIGEST')
    require(type(value['adapter_state']) is str and
            str(adapter.canonical(value['adapter_state'])) == value['adapter_state'], 'SELECTION_STATE')
    return value


def _approved(selection, adapter):
    return adapter.inspect_state(Path(selection['adapter_state']), selection['client'],
        expected_approval_sha256=selection['approval_sha256'],
        expected_launcher_sha256=selection['launcher_sha256'])


def _write(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def _lock(store, adapter, write=False):
    store = adapter.directory(store, private=True)
    fd = os.open(store/'owner.lock', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600, 'UNSAFE_LOCK')
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ContractError('STORE_BUSY') from error
        require(not os.path.lexists(store/'pending.json'), 'PUBLICATION_UNKNOWN')
        yield store
    finally:
        os.close(fd)


def _read_store(store, client, adapter):
    require(type(client) is str and client in CLIENTS, 'CLIENT_REQUIRED')
    require({item.name for item in islice(store.iterdir(), 5)} == {'owner.lock', 'catalog.json', 'records', 'head.json'},
            'STORE_INCOMPLETE_OR_UNEXPECTED')
    catalog_raw = read(store/'catalog.json', CATALOG_LIMIT, adapter)
    catalog = validate_catalog(catalog_raw)
    head_raw = read(store/'head.json', SELECTION_LIMIT, adapter)
    head = decode(head_raw)
    require(type(head) is dict and set(head) == HEAD_FIELDS and head['schema'] == 'golem.stable-head.v1'
            and head['client'] == client and type(head['revision']) is int
            and 1 <= head['revision'] <= MAX_REVISIONS and _pin(head['selection_sha256'])
            and head['catalog_sha256'] == digest(catalog_raw), 'HEAD_FIELDS')
    directory = adapter.directory(store/'records', private=True)
    entries = list(islice(directory.iterdir(), MAX_REVISIONS+1))
    require(len(entries) == head['revision'] and len(entries) <= MAX_REVISIONS
            and {item.name for item in entries} == {f'{i:020d}.json' for i in range(1, head['revision']+1)},
            'RECORD_CHAIN_OR_HEAD_ROLLBACK')
    previous = None
    records = []
    for revision in range(1, head['revision']+1):
        raw = read(directory/f'{revision:020d}.json', SELECTION_LIMIT, adapter)
        selection = validate_selection(raw, adapter)
        require(selection['client'] == client and selection['revision'] == revision
                and selection['previous_sha256'] == previous
                and selection['catalog_sha256'] == head['catalog_sha256'], 'SELECTION_CHAIN')
        previous = digest(raw)
        records.append((selection, raw))
    require(previous == head['selection_sha256'], 'HEAD_SELECTION_DIGEST')
    return catalog, catalog_raw, head, head_raw, records


def _result(catalog, catalog_raw, head, head_raw, selection, raw):
    return {'selection': selection, 'selection_sha256': digest(raw), 'catalog': catalog,
            'catalog_sha256': digest(catalog_raw), 'head_sha256': digest(head_raw),
            'current_head_selection_sha256': head['selection_sha256'],
            'is_current': digest(raw) == head['selection_sha256'],
            'publication_state': 'SELECTED_NOT_LIVE_APPLIED', 'execution_authorized': False,
            'model_delivery_verified': False, 'automatic_retry_allowed': False}


def inspect(store, client, adapter):
    with _lock(store, adapter) as store:
        catalog, raw_catalog, head, raw_head, records = _read_store(store, client, adapter)
        selection, raw = records[-1]
        _approved(selection, adapter)
        return _result(catalog, raw_catalog, head, raw_head, selection, raw)


@contextmanager
def shared_admission(store, client, expected_selection_sha256, expected_head_sha256, adapter):
    """Keep exact current selection locked through one caller-controlled send.

    The consumer must release this context after its bounded transport write,
    not after native completion. A competing publication fails STORE_BUSY;
    this context neither dispatches a call nor approves one.
    """
    require(_pin(expected_selection_sha256) and _pin(expected_head_sha256), 'ADMISSION_DIGEST')
    with _lock(store, adapter) as store:
        catalog, raw_catalog, head, raw_head, records = _read_store(store, client, adapter)
        selection, raw = records[-1]
        require(digest(raw) == expected_selection_sha256 and digest(raw_head) == expected_head_sha256,
                'ADMISSION_SELECTION_CHANGED')
        _approved(selection, adapter)
        yield _result(catalog, raw_catalog, head, raw_head, selection, raw)


def inspect_record(store, client, revision, selection_sha256, adapter):
    """Recheck one immutable historical selection without selecting/replaying it."""
    require(type(revision) is int and 1 <= revision <= MAX_REVISIONS and _pin(selection_sha256),
            'RECORD_IDENTITY')
    with _lock(store, adapter) as store:
        catalog, raw_catalog, head, raw_head, records = _read_store(store, client, adapter)
        require(revision <= len(records), 'RECORD_NOT_FOUND')
        selection, raw = records[revision-1]
        require(digest(raw) == selection_sha256, 'RECORD_DIGEST')
        _approved(selection, adapter)
        return _result(catalog, raw_catalog, head, raw_head, selection, raw)


def _finish(store, pending_raw, adapter):
    # The final unlink/fsync can itself fail. Preserve uncertainty best-effort;
    # persistent storage failure cannot guarantee a new durable poison write.
    os.unlink(store/'pending.json')
    try:
        adapter.sync_directory(store)
    except OSError as error:
        try:
            _write(store/'pending.json', pending_raw)
            adapter.sync_directory(store)
        except OSError:
            pass
        raise ContractError('PUBLICATION_UNKNOWN') from error


def _commit(store, selection, selection_raw, catalog_raw, adapter, previous_head=None, records=()):
    pending_raw = canonical({'schema': 'golem.stable-publication-pending.v1',
        'selection_sha256': digest(selection_raw), 'revision': selection['revision'],
        'previous_head_sha256': digest(previous_head) if previous_head is not None else None})
    _write(store/'pending.json', pending_raw)
    adapter.sync_directory(store)
    if previous_head is None:
        _write(store/'catalog.json', catalog_raw)
        (store/'records').mkdir(mode=0o700)
    _write(store/'records'/f"{selection['revision']:020d}.json", selection_raw)
    adapter.sync_directory(store/'records')
    head = {'schema': 'golem.stable-head.v1', 'client': selection['client'],
            'revision': selection['revision'], 'selection_sha256': digest(selection_raw),
            'catalog_sha256': digest(catalog_raw)}
    head_raw = canonical(head)
    _write(store/'head.pending', head_raw)
    _approved(selection, adapter)
    require(read(store/'pending.json', SELECTION_LIMIT, adapter) == pending_raw, 'PENDING_CHANGED')
    require(read(store/'catalog.json', CATALOG_LIMIT, adapter) == catalog_raw, 'CATALOG_CHANGED')
    if previous_head is None:
        require(not os.path.lexists(store/'head.json'), 'HEAD_CHANGED')
    else:
        require(read(store/'head.json', SELECTION_LIMIT, adapter) == previous_head, 'HEAD_CHANGED')
        for revision, (_, raw) in enumerate(records, 1):
            require(read(store/'records'/f'{revision:020d}.json', SELECTION_LIMIT, adapter) == raw,
                    'RECORD_CHANGED')
        _approved(records[-1][0], adapter)
    os.replace(store/'head.pending', store/'head.json')
    adapter.sync_directory(store)
    _finish(store, pending_raw, adapter)
    return _result(validate_catalog(catalog_raw), catalog_raw, head, head_raw, selection, selection_raw)


def _publish(*args, **kwargs):
    try:
        return _commit(*args, **kwargs)
    except Exception as error:
        # Once publication was admitted, a failed write/fsync/last pin check is
        # not an idempotent failure receipt. Retain partial files and never retry.
        raise ContractError('PUBLICATION_UNKNOWN') from error


def create(store, catalog_path, catalog_sha, selection_path, selection_sha, approved, adapter):
    require(approved is True, 'OWNER_SELECTION_APPROVAL_REQUIRED')
    require(_pin(catalog_sha) and _pin(selection_sha), 'REVIEWED_DIGEST_REQUIRED')
    catalog_raw = read(catalog_path, CATALOG_LIMIT, adapter)
    selection_raw = read(selection_path, SELECTION_LIMIT, adapter)
    require(digest(catalog_raw) == catalog_sha and digest(selection_raw) == selection_sha, 'REVIEWED_BYTES_CHANGED')
    validate_catalog(catalog_raw)
    selection = validate_selection(selection_raw, adapter)
    require(selection['revision'] == 1 and selection['catalog_sha256'] == catalog_sha, 'INITIAL_SELECTION')
    _approved(selection, adapter)
    store = adapter.canonical(store)
    adapter.directory(store.parent)
    require(not os.path.lexists(store), 'STORE_EXISTS_NO_RETRY')
    store.mkdir(mode=0o700)
    adapter.sync_directory(store.parent)
    _write(store/'owner.lock', b'')
    with _lock(store, adapter, write=True):
        return _publish(store, selection, selection_raw, catalog_raw, adapter)


def publish(store, selection_path, selection_sha, expected_head_sha, approved, adapter):
    require(approved is True, 'OWNER_SELECTION_APPROVAL_REQUIRED')
    require(_pin(selection_sha) and _pin(expected_head_sha), 'REVIEWED_DIGEST_REQUIRED')
    raw = read(selection_path, SELECTION_LIMIT, adapter)
    require(digest(raw) == selection_sha, 'REVIEWED_BYTES_CHANGED')
    selection = validate_selection(raw, adapter)
    with _lock(store, adapter, write=True) as store:
        _, catalog_raw, head, head_raw, records = _read_store(store, selection['client'], adapter)
        require(digest(head_raw) == expected_head_sha, 'HEAD_CAS_MISMATCH')
        require(selection['revision'] == head['revision']+1
                and selection['previous_sha256'] == head['selection_sha256']
                and selection['catalog_sha256'] == head['catalog_sha256'], 'NEXT_SELECTION')
        _approved(records[-1][0], adapter)
        _approved(selection, adapter)
        return _publish(store, selection, raw, catalog_raw, adapter, head_raw, records)
