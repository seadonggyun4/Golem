"""Read-only adapters for explicitly supplied existing execution-record bytes.

No replay, path following, issuer authentication, test PASS or Work authority.
Format-specific limitations are returned, not normalized into product success.
"""
from dataclasses import dataclass
import hashlib
import re

from capability_record_input import decode_record_inputs, RecordInputError, NODES_MAX
from capability_record_inventory import compare_file_inventory
from capability_ledger import validate_relative_path


@dataclass(frozen=True)
class ExecutionObservation:
    format: str
    file_integrity_verified: bool
    blockers: tuple
    commands: tuple
    exits: tuple
    source_matches: bool | None
    authenticity_verified: bool = False
    test_execution_verified: bool = False
    sufficiency_verified: bool = False


class InvalidRecord(ValueError):
    pass


def _need(value, reason):
    if not value:
        raise InvalidRecord(reason)


def _object(value):
    _need(type(value) is dict, 'OBJECT_REQUIRED')
    return value


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _map(value):
    _object(value)
    for name in value:
        validate_relative_path(name)
    return value


def _metadata(raw, meta):
    _need(type(meta) is dict and set(meta) == {'sha256', 'bytes'} and
          type(meta['bytes']) is int and meta == {'sha256': _sha(raw), 'bytes': len(raw)}, 'FILE_DIGEST_MISMATCH')


def _argv(value):
    _need(type(value) is list and bool(value) and all(type(a) is str and '\0' not in a for a in value), 'ARGV_INVALID')
    return tuple(value)


def _exit(value):
    _object(value)
    code, reason = value.get('returncode'), value.get('reason')
    _need(code is None or type(code) is int, 'EXIT_INVALID')
    _need(type(reason) is str and bool(reason), 'EXIT_REASON_INVALID')
    return code, reason


def _node_count(values):
    pending, count = list(values), 0
    while pending:
        value = pending.pop(); count += 1
        if isinstance(value, dict): pending.extend(value.values())
        elif isinstance(value, list): pending.extend(value)
    return count


def _native(files, mapping, prefix='native/', budget=None):
    """Validate supplied native inventories; never follow source/executable paths."""
    expected, blockers, scopes = [], [], set()
    for name, value in mapping.items():
        _need(type(name) is str, 'NATIVE_NAME')
        parts = name.rstrip('/').split('/')
        _need(parts and re.fullmatch('[0-9a-f]{32}', parts[0]), 'NATIVE_SCOPE')
        if name.endswith('/'):
            _need(len(parts) == 1 and value == {'kind':'directory'}, 'NATIVE_DIRECTORY')
            scopes.add(parts[0])
        else:
            _need(len(parts) == 2 and parts[1] in ('started.json','result.json','manifest.json','.pending','stdout.log','stderr.log'), 'NATIVE_NAME')
            path = prefix+name
            expected.append(path)
            if path not in files:
                blockers.append(('MISSING_NATIVE_FILE', path))
            else:
                _metadata(files[path], value)
    for name in mapping:
        if not name.endswith('/'):
            _need(name.split('/')[0] in scopes, 'NATIVE_DIRECTORY_UNBOUND')
    json_names = [p for p in expected if p.endswith('.json') and p in files]
    decoded = decode_record_inputs(files, json_names)
    budget[0] += _node_count(decoded.values())
    _need(budget[0] <= NODES_MAX, 'JSON_NODE_LIMIT')
    for scope in sorted(scopes):
        stem = prefix+scope+'/'
        required = [stem+n for n in ('started.json','result.json','manifest.json')]
        if any(p not in decoded for p in required) or stem+'.pending' in expected:
            blockers.append(('NATIVE_INCOMPLETE', scope))
            continue
        start, finish, manifest = (_object(decoded[p]) for p in required)
        names = {p[len(stem):] for p in expected if p.startswith(stem)}
        _need(set(manifest) == names-{'manifest.json'}, 'NATIVE_MANIFEST_NAMES')
        for name, digest in manifest.items():
            _need(stem+name in files and _sha(files[stem+name]) == digest, 'NATIVE_DIGEST')
        _need(start.get('schema') == finish.get('schema') == 'golem.native-record.v1' and
              start.get('id') == finish.get('id') == scope and start.get('state') == 'STARTED', 'NATIVE_BINDING')
        if finish.get('state') != 'FINISHED' or type(finish.get('recording_status')) is not int or finish['recording_status'] != 0:
            blockers.append(('NATIVE_INCOMPLETE', scope))
    return expected, blockers


def inspect_execution(files, format, *, expected_source=None, _budget=None):
    """Observe one explicit format. expected_source is caller-selected, not read.

    Source matching compares complete recorded objects, never commit alone.
    It is separate from record integrity and is not authenticated provenance.
    Malformed input raises with no partial success. Incomplete evidence returns
    blockers and cannot make file_integrity_verified true.
    """
    _need(format in ('execution', 'agent', 'private'), 'FORMAT_UNSUPPORTED')
    decode_record_inputs(files, [])
    blockers, commands, exits = [], [], []
    required = (['execution/'+n for n in ('manifest.json','started.json','result.json','source-before.json','source-after.json')]
                if format == 'execution' else ['started.json','result.json','source-before.json','source-after.json']
                if format == 'private' else ['manifest.json','plan.json','started.json','record.json','source-before.json','source-after.json'])
    missing = set(required) - files.keys()
    if missing:
        return ExecutionObservation(format, False, tuple(('MISSING_FILE', p) for p in sorted(missing)), (), (), None)
    data = decode_record_inputs(files, required)
    budget = [0] if _budget is None else _budget
    budget[0] += _node_count(data.values())
    _need(budget[0] <= NODES_MAX, 'JSON_NODE_LIMIT')
    for value in data.values():
        _object(value)
    prefix = 'execution/' if format == 'execution' else ''
    start = data[prefix+'started.json']
    before, after = data[prefix+'source-before.json'], data[prefix+'source-after.json']
    integrity = True
    if format == 'execution':
        manifest, finish = data['execution/manifest.json'], data['execution/result.json']
        _need(manifest.get('schema') == 'golem.execution-manifest.v1', 'MANIFEST_SCHEMA')
        meta = _map(manifest.get('files'))
        _need(set(meta) == {'started.json','result.json','source-before.json','source-after.json'}, 'EXECUTION_FILE_MAP')
        logs = _map(manifest.get('logs'))
        extras = start.get('extra_logs', [])
        _need(type(extras) is list and all(type(n) is str for n in extras) and len(extras) == len(set(extras)), 'EXTRA_LOGS')
        for n in extras:
            _need(re.fullmatch(r'[a-z][a-z0-9_-]{0,63}\.log', n) and n not in ('stdout.log','stderr.log'), 'EXTRA_LOG_NAME')
        _need(not (set(logs) - {'stdout.log','stderr.log',*extras}) and set(extras) <= set(logs), 'LOG_MAP')
        native = _object(manifest.get('native_files', {}))
        native_paths, native_blockers = _native(files, native, budget=budget)
        if not {'stdout.log','stderr.log'} <= logs.keys():
            blockers.append(('STREAMS_INCOMPLETE', 'logs'))
        blockers.extend(native_blockers)
        referenced = ['execution/'+n for n in meta] + list(logs) + native_paths
        inventory = compare_file_inventory(files, required, referenced)
        blockers.extend(('MISSING_FILE', p) for p in inventory.missing)
        blockers.extend(('EXTRA_OR_UNSUPPORTED_FILE', p) for p in inventory.extra)
        for name, m in list(('execution/'+n, v) for n,v in meta.items()) + list(logs.items()):
            if name in files:
                _metadata(files[name], m)
        _need(start.get('schema') == finish.get('schema') == 'golem.execution-observation.v1', 'EXECUTION_SCHEMA')
        _need(start.get('state') == 'STARTED' and finish.get('state') == 'FINISHED' and
              type(start.get('invocation_id')) is str and bool(start['invocation_id']) and
              start['invocation_id'] == finish.get('invocation_id'), 'INVOCATION_BINDING')
        commands.append(_argv(start.get('argv')))
        exits.append(_exit(finish.get('process')))
        if before.get('status') != 'OBSERVED' or after.get('status') != 'OBSERVED':
            blockers.append(('SOURCE_UNOBSERVED', 'source'))
    elif format == 'agent':
        manifest, record, plan = data['manifest.json'], data['record.json'], data['plan.json']
        _need(manifest.get('schema') == 'golem.agent-observation-manifest.v1', 'MANIFEST_SCHEMA')
        meta = _map(manifest.get('files'))
        _need('manifest.json' not in meta, 'SELF_REFERENCE')
        inventory = compare_file_inventory(files, ['manifest.json'], list(meta))
        blockers.extend(('MISSING_FILE', p) for p in inventory.missing)
        blockers.extend(('EXTRA_FILE', p) for p in inventory.extra)
        for name, digest in meta.items():
            _need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'DIGEST_INVALID')
            if name in files:
                _need(_sha(files[name]) == digest, 'FILE_DIGEST_MISMATCH')
        _need(set(required)-{'manifest.json'} <= set(meta), 'UNBOUND_REQUIRED_FILE')
        _need(start.get('schema') == record.get('schema') == 'golem.agent-observation.v1' and
              plan.get('schema') == 'golem.agent-command-plan.v1', 'AGENT_SCHEMA')
        # Reuse agent_io.identity byte encoding (sorted compact ASCII plus newline).
        import json
        plan_digest = _sha(json.dumps(plan, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()+b'\n')
        _need(start.get('plan_sha256') == record.get('plan_sha256') == plan_digest, 'PLAN_BINDING')
        steps, planned = record.get('steps'), plan.get('commands')
        _need(type(steps) is list and type(planned) is list, 'STEPS_INVALID')
        _need(len(steps) == len(planned), 'STEP_COUNT')
        seen = set()
        for command, step in zip(planned, steps):
            _object(command); _object(step)
            name = command.get('id')
            _need(type(name) is str and re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', name) and
                  name not in seen and step.get('id') == name, 'STEP_BINDING')
            seen.add(name)
            commands.append(_argv(command.get('argv')))
            if step.get('status') == 'NOT_RUN':
                exits.append((None, 'NOT_RUN'))
                blockers.append(('STEP_NOT_RUN', name))
            else:
                exits.append(_exit(step))
            for log, metadata in _map(step.get('logs')).items():
                _need(log in ('stdout.log','stderr.log','usage.log'), 'STEP_LOG_NAME')
                path = name+'/'+log
                if path not in files:
                    blockers.append(('MISSING_STEP_LOG', path))
                else:
                    _metadata(files[path], metadata)
            child_files = {p[len(name)+1:]: b for p, b in files.items() if p.startswith(name+'/')}
            if step.get('status') == 'NOT_RUN':
                _need(not child_files, 'NOT_RUN_CHILD_PRESENT')
                continue
            child = inspect_execution(child_files, 'execution', _budget=budget)
            if child.commands:
                _need(child.commands == (commands[-1],), 'CHILD_ARGV_MISMATCH')
            if child.exits:
                _need(child.exits == (exits[-1],), 'CHILD_EXIT_MISMATCH')
            for code, detail in child.blockers:
                # Child source observations remain separate from the outer source.
                # They must not be promoted to a source attestation.
                if code in ('TARGET_SOURCE_UNSPECIFIED', 'SOURCE_UNOBSERVED'):
                    blockers.append(('CHILD_'+code, name+'/'+detail))
                else:
                    blockers.append((code, name+'/'+detail))
            if not child.file_integrity_verified:
                blockers.append(('CHILD_INTEGRITY_UNVERIFIED', name))
        for path in files:
            if '/native/' in path and path.split('/')[0] not in seen:
                blockers.append(('NATIVE_REFERENCES_UNVERIFIED', path))
    else:
        finish = data['result.json']
        _need(start.get('schema') == 'golem.private-process-observation.v1' and
              finish.get('schema') == 'golem.private-process-result.v1', 'PRIVATE_SCHEMA')
        _need(start.get('argv_redacted') is True and start.get('streams_recorded') is False, 'PRIVATE_REDACTION')
        inventory = compare_file_inventory(files, required, [])
        blockers.extend(('EXTRA_FILE', p) for p in inventory.extra)
        blockers.extend((('COMMAND_REDACTED', 'argv'), ('STREAMS_NOT_RECORDED', 'logs'),
                         ('NO_MANIFEST_BINDING', 'private')))
        exits.append(_exit(finish))
        integrity = False
    if expected_source is not None:
        _need(type(expected_source) is dict and {'commit', 'files', 'tree_sha256'} <= expected_source.keys(), 'EXPECTED_SOURCE_INCOMPLETE')
    source_matches = None if expected_source is None else before == expected_source and after == expected_source
    if expected_source is None:
        blockers.append(('TARGET_SOURCE_UNSPECIFIED', 'source'))
    elif not source_matches:
        blockers.append(('TARGET_SOURCE_MISMATCH', 'source'))
    # Matching only a supplied complete object is not proof of authentic execution.
    integrity_blockers = [b for b in blockers if b[0] not in ('TARGET_SOURCE_UNSPECIFIED','TARGET_SOURCE_MISMATCH','SOURCE_UNOBSERVED','STEP_NOT_RUN','CHILD_TARGET_SOURCE_UNSPECIFIED','CHILD_SOURCE_UNOBSERVED')]
    return ExecutionObservation(format, integrity and not integrity_blockers, tuple(blockers),
                                tuple(commands), tuple(exits), source_matches)
