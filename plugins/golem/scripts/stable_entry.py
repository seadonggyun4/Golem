"""Opt-in, pinned stable Golem transport entry. Never updates a client or grants Work access."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

FILES = ('LICENSE', 'connection_relay.py', 'launcher.py', 'stable_contract.py',
         'stable_entry.py', 'stable_relay.py', 'stable_readiness.py', 'typed-interface.json')
CLIENTS = ('codex', 'claude-desktop')


def require(ok, code):
    if not ok:
        raise ValueError(code)


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode()


def pairs(items):
    value = {}
    for key, item in items:
        require(key not in value, 'STABLE_BUNDLE_DUPLICATE')
        value[key] = item
    return value


def checked_file(path, limit):
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)),
            'STABLE_BUNDLE_PATH')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and
                before.st_nlink == 1 and before.st_mode & 0o022 == 0 and before.st_size <= limit,
                'STABLE_BUNDLE_FILE')
        raw = os.read(fd, limit + 1)
        after = os.fstat(fd)
        require(len(raw) == before.st_size and len(raw) <= limit and
                (before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns) ==
                (after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns), 'STABLE_BUNDLE_CHANGED')
        return raw
    finally:
        os.close(fd)


def verified_bundle(reviewed_sha256):
    require(type(reviewed_sha256) is str and re.fullmatch('[0-9a-f]{64}', reviewed_sha256),
            'STABLE_BUNDLE_PIN_REQUIRED')
    directory = Path(__file__).absolute().parent
    raw = checked_file(directory / 'broker-manifest.json', 16384)
    require(hashlib.sha256(raw).hexdigest() == reviewed_sha256, 'STABLE_BUNDLE_PIN_CHANGED')
    manifest = json.loads(raw.decode(), object_pairs_hook=pairs)
    require(type(manifest) is dict and set(manifest) == {'schema','files'} and
            manifest['schema'] == 'golem.stable-broker-bundle.v1' and
            type(manifest['files']) is dict and set(manifest['files']) == set(FILES), 'STABLE_BUNDLE_FIELDS')
    require(encode(manifest) == raw, 'STABLE_BUNDLE_CANONICAL')
    payloads = {}
    for name in FILES:
        payloads[name] = checked_file(directory / name, 1024 * 1024)
        require(hashlib.sha256(payloads[name]).hexdigest() == manifest['files'][name],
                'STABLE_BUNDLE_PAYLOAD_CHANGED')
    require(checked_file(directory / 'broker-manifest.json',16384) == raw, 'STABLE_BUNDLE_CHANGED')
    return directory, payloads


def module(directory, payloads, name, injections=None):
    """Load the exact verified snapshot, not a second disk read or search path."""
    filename = name + '.py'
    path = directory / filename
    identity = '_golem_stable_' + name
    spec = importlib.util.spec_from_loader(identity, loader=None, origin=str(path))
    value = importlib.util.module_from_spec(spec)
    value.__file__ = str(path)
    value.__dict__.update(injections or {})
    sys.modules[identity] = value
    exec(compile(payloads[filename], str(path), 'exec'), value.__dict__)
    return value


def observation(path, pin):
    """Read exact external evidence bytes; this never manufactures model proof."""
    require(path is not None and type(pin) is str and re.fullmatch('[0-9a-f]{64}', pin),
            'STABLE_OBSERVATION_PIN_REQUIRED')
    raw = checked_file(path, 65536)
    require(hashlib.sha256(raw).hexdigest() == pin, 'STABLE_OBSERVATION_CHANGED')
    value = json.loads(raw.decode(), object_pairs_hook=pairs)
    require(type(value) is dict and encode(value) == raw, 'STABLE_OBSERVATION_CANONICAL')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('create','publish','inspect','serve','status','refresh','readiness'))
    parser.add_argument('--client', choices=CLIENTS, required=True)
    parser.add_argument('--reviewed-bundle-sha256', required=True)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--catalog', type=Path)
    parser.add_argument('--catalog-sha256')
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--selection-sha256')
    parser.add_argument('--expected-head-sha256')
    parser.add_argument('--approve-selection', action='store_true')
    parser.add_argument('--connection-instance')
    parser.add_argument('--connection-marker')
    parser.add_argument('--expected-selection-sha256')
    parser.add_argument('--target-selection-sha256')
    parser.add_argument('--approve-refresh', action='store_true')
    parser.add_argument('--model-observation', type=Path)
    parser.add_argument('--model-observation-sha256')
    parser.add_argument('--refresh-evidence', type=Path)
    parser.add_argument('--refresh-evidence-sha256')
    parser.add_argument('--require-tool', action='append')
    args = parser.parse_args()
    try:
        directory, payloads = verified_bundle(args.reviewed_bundle_sha256)
        adapter = module(directory, payloads, 'launcher')
        inventory = json.loads(payloads['typed-interface.json'].decode(), object_pairs_hook=pairs)
        require(encode(inventory) == payloads['typed-interface.json'], 'STABLE_INTERFACE_CANONICAL')
        contract = module(directory, payloads, 'stable_contract', {'_VERIFIED_TYPED_INDEX':inventory})
        require(args.store.is_absolute(), 'STABLE_STORE_PATH')
        if args.operation == 'create':
            require(args.catalog is not None and args.selection is not None,
                    'STABLE_REVIEWED_INPUTS_REQUIRED')
            proposed = contract.read(args.selection, contract.SELECTION_LIMIT, adapter)
            require(contract.digest(proposed) == args.selection_sha256, 'STABLE_SELECTION_PIN')
            require(contract.validate_selection(proposed, adapter)['client'] == args.client, 'STABLE_CLIENT')
            result = contract.create(args.store, args.catalog, args.catalog_sha256,
                                     args.selection, args.selection_sha256, args.approve_selection, adapter)
        elif args.operation == 'publish':
            require(args.selection is not None, 'STABLE_REVIEWED_INPUTS_REQUIRED')
            # Validate client before publication; CLI selector never changes it.
            contract.inspect(args.store, args.client, adapter)
            result = contract.publish(args.store, args.selection, args.selection_sha256,
                                      args.expected_head_sha256, args.approve_selection, adapter)
        elif args.operation == 'inspect':
            result = contract.inspect(args.store, args.client, adapter)
        else:
            legacy = module(directory, payloads, 'connection_relay')
            transport = module(directory, payloads, 'stable_relay', {'_VERIFIED_LEGACY':legacy})
            if args.operation == 'serve':
                transport.serve(adapter, contract, args.store, args.client)
                return 0
            require(args.connection_instance is not None, 'STABLE_EXACT_CONNECTION_REQUIRED')
            if args.operation == 'status':
                result = transport.request(args.client, args.connection_instance, 'status', {})
            elif args.operation == 'readiness':
                model = observation(args.model_observation, args.model_observation_sha256)
                require(bool(args.refresh_evidence) == bool(args.refresh_evidence_sha256),
                        'STABLE_REFRESH_EVIDENCE_ARGUMENTS')
                refresh = (observation(args.refresh_evidence, args.refresh_evidence_sha256)
                           if args.refresh_evidence else None)
                require(args.require_tool is not None, 'STABLE_REQUIRED_TOOLS')
                selected = contract.inspect(args.store, args.client, adapter)
                reply = transport.request(args.client, args.connection_instance, 'status', {})
                require(reply.get('ok') is True, 'STABLE_STATUS_UNAVAILABLE')
                live = {**reply['value'], 'observed_at_ns':time.time_ns()}
                require(contract.inspect(args.store, args.client, adapter) == selected,
                        'STABLE_SELECTION_CHANGED_DURING_OBSERVATION')
                result = module(directory, payloads, 'stable_readiness').classify(
                    selected, live, model, args.require_tool, time.time_ns(), refresh)
            else:
                require(args.approve_refresh, 'STABLE_OWNER_REFRESH_REQUIRED')
                marker = transport.parse_definition_marker(args.connection_marker)
                require(marker['instance'] == args.connection_instance, 'STABLE_TARGET_MARKER')
                current = contract.inspect(args.store, args.client, adapter)
                require(marker['catalog_sha256'] == current['catalog_sha256'], 'STABLE_CATALOG_CHANGED')
                require(args.target_selection_sha256 == current['selection_sha256'], 'STABLE_TARGET_SELECTION')
                result = transport.request(args.client,args.connection_instance,'refresh',{
                    'expected_selection_sha256':args.expected_selection_sha256,
                    'target_selection_sha256':args.target_selection_sha256,
                    'expected_definition_marker':args.connection_marker})
        print(encode(result).decode(), end='')
        return 1 if result.get('ok') is False or result.get('state') == 'BLOCKED' else 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        unknown = ('UNKNOWN' in str(error) or
                   isinstance(error,OSError) and args.operation in ('create','publish','refresh'))
        result = {'state':'RESULT_UNKNOWN' if unknown else 'BLOCKED',
                  'code':str(error) if isinstance(error,ValueError) else 'STABLE_ENTRY_FAILED',
                  'automatic_retry_allowed':False, 'execution_authorized':False}
        print(encode(result).decode(), end='', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
