"""Offline import of one exact Codex metadata-only exec receipt.

No model, MCP, native, network, subprocess, or Owner call occurs here. A local
rollout is caller-selected evidence, not a signed host attestation. Its original
timestamps and bytes remain provenance; agent final text is never evidence.
"""
import argparse
import calendar
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

import integration_stable_readiness as readiness


METADATA_SCHEMA = 'golem.external-tool-metadata.v1'
PROVENANCE_SCHEMA = 'golem.external-tool-metadata-provenance.v1'
MARKER_LINE = 'Fixed catalog observation only; no authority:'
MAX_TRACE_BYTES = 16 * 1024 * 1024
MAX_LINE_BYTES = 2 * 1024 * 1024
MAX_LINES = 100000
PIN = re.compile(r'[a-f0-9]{64}\Z')
PREFIX = re.compile(r'mcp__[a-z][a-z0-9_]{0,80}__\Z')
UTC = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z\Z')
HEADER = re.compile(r'Script completed\nWall time [0-9]+(?:\.[0-9]+)? seconds\nOutput:\n\Z')


class ObservationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise ObservationError(code)


def encoded(value):
    try:
        return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False, allow_nan=False)+'\n').encode()
    except (TypeError, ValueError, UnicodeError):
        raise ObservationError('CANONICAL_JSON_REQUIRED') from None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'DUPLICATE_JSON_FIELD')
        result[key] = value
    return result


def _json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ObservationError('INVALID_JSON_NUMBER')))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ObservationError('MALFORMED_OR_TRUNCATED_JSON') from None


def _utc(value):
    match = UTC.fullmatch(value) if type(value) is str else None
    require(match is not None, 'ORIGINAL_TIMESTAMP_REQUIRED')
    try:
        seconds = calendar.timegm(datetime.strptime(match[1], '%Y-%m-%dT%H:%M:%S').timetuple())
    except ValueError:
        raise ObservationError('ORIGINAL_TIMESTAMP_REQUIRED') from None
    return seconds * 10**9 + int((match[2] or '').ljust(9, '0'))


def metadata_script(prefix):
    """The one finite script: inspect metadata only; never dispatch a tool."""
    require(type(prefix) is str and PREFIX.fullmatch(prefix), 'EXACT_SERVER_PREFIX_REQUIRED')
    return ("const selected = ALL_TOOLS.filter(t => t.name.startsWith('"+prefix+"'));\n"
            "text({schema:'golem.external-tool-metadata.v1',entries:selected.map(t => ({name:t.name,"
            "description:t.description.split('\\n').filter(line => line.startsWith('"
            +MARKER_LINE+"')).join('\\n')}))});")


def _script(value):
    require(type(value) is str, 'METADATA_SCRIPT_MISMATCH')
    # Only leading/trailing blank space and trailing line spaces are immaterial.
    # Never strip comments, parse arbitrary JS, evaluate it, or accept a hash
    # chosen by the same model that supplies the output.
    return '\n'.join(line.rstrip() for line in value.strip().splitlines())


def _exec_declaration(payload):
    """Recognize the observed developer declaration, never a call or evidence.

    Keep this finite: unknown envelopes, tool kinds, namespaces and action
    fields still fail closed. Descriptions and grammar are not interpreted.
    """
    if not (set(payload) == {'type','id','role','tools'} and
            payload['type'] == 'additional_tools' and payload['role'] == 'developer' and
            readiness._identifier(payload['id']) and type(payload['tools']) is list and
            len(payload['tools']) == 1):
        return False
    namespace = payload['tools'][0]
    if not (type(namespace) is dict and
            set(namespace) == {'type','name','description','tools'} and
            namespace['type'] == 'namespace' and namespace['name'] == 'functions' and
            type(namespace['description']) is str and type(namespace['tools']) is list and
            len(namespace['tools']) == 1):
        return False
    entry = namespace['tools'][0]
    if not (type(entry) is dict and set(entry) == {'type','name','description','format'} and
            entry['type'] == 'custom' and entry['name'] == 'exec' and
            type(entry['description']) is str and type(entry['format']) is dict):
        return False
    grammar = entry['format']
    return (set(grammar) == {'type','syntax','definition'} and grammar['type'] == 'grammar' and
            grammar['syntax'] == 'lark' and type(grammar['definition']) is str)


def _catalog(raw, expected):
    require(PIN.fullmatch(expected or '') and digest(raw) == expected, 'CATALOG_PIN_MISMATCH')
    value = _json(raw)
    require(type(value) is dict and encoded(value) == raw, 'CATALOG_NOT_CANONICAL')
    require(set(value) == {'schema','profile','tools','tools_sha256'} and
            value['schema'] == readiness.FRONTEND_ABI and
            value['profile'] in ('read','prepare','task','quality','parallel'), 'CATALOG_FORMAT')
    definitions = value['tools']
    require(type(definitions) is list and 0 < len(definitions) <= readiness.MAX_TOOLS and
            all(type(t) is dict and type(t.get('inputSchema')) is dict for t in definitions), 'CATALOG_FORMAT')
    names = [t.get('name') for t in definitions]
    require(readiness._tools(names) and names == sorted(names) and
            value['tools_sha256'] == readiness._canonical_digest(definitions), 'CATALOG_INVENTORY_INVALID')
    return names


def _metadata(output, prefix, catalog_names, catalog_sha256):
    require(type(output) is list and len(output) == 2 and all(
        type(block) is dict and set(block) == {'type','text'} and
        block['type'] == 'input_text' and type(block['text']) is str for block in output),
        'SINGLE_STRUCTURED_OUTPUT_REQUIRED')
    require(HEADER.fullmatch(output[0]['text']) is not None, 'EXEC_NOT_COMPLETED')
    try:
        raw = output[1]['text'].encode()
    except UnicodeError:
        raise ObservationError('MALFORMED_OR_TRUNCATED_JSON') from None
    require(len(raw) <= 65536, 'METADATA_OUTPUT_LIMIT')
    value = _json(raw)
    require(type(value) is dict and set(value) == {'schema','entries'} and
            value['schema'] == METADATA_SCHEMA and type(value['entries']) is list and
            0 < len(value['entries']) <= readiness.MAX_TOOLS, 'METADATA_FORMAT')
    names, markers = [], []
    for entry in value['entries']:
        require(type(entry) is dict and set(entry) == {'name','description'} and
                type(entry['name']) is str and entry['name'].startswith(prefix) and
                type(entry['description']) is str, 'METADATA_SERVER_OR_ENTRY_MISMATCH')
        name = entry['name'][len(prefix):]
        require(readiness.TOOL.fullmatch(name) is not None, 'METADATA_TOOL_NAME_INVALID')
        names.append(name)
        description = entry['description']
        if description:
            require(description.startswith(MARKER_LINE+' '), 'MARKER_LINE_INVALID')
            marker = description[len(MARKER_LINE)+1:]
            parsed = readiness.MARKER.fullmatch(marker)
            require(parsed is not None and parsed[2] == catalog_sha256, 'MARKER_CATALOG_MISMATCH')
            require(name == catalog_names[0], 'MARKER_TOOL_MISMATCH')
            markers.append(marker)
    require(readiness._tools(names) and sorted(names) == catalog_names, 'MODEL_FULL_TOOL_INVENTORY_MISMATCH')
    require(len(markers) == 1, 'EXACT_DEFINITION_MARKER_REQUIRED')
    return sorted(names), markers[0], digest(raw)


def collect(raw, catalog_raw, *, trace_sha256, catalog_sha256, thread_id, turn_id,
            server_name, prefix, started_not_before_ns, now_ns, input_format='codex-rollout'):
    """Return a legacy observation and separate, non-authoritative provenance.

    Only the selected completed turn's receipt is extracted. Other turns and
    reasoning/final messages are never included in outputs. read_thread is not
    an alternate proof path: the observed supported response omits exec output.
    """
    require(type(raw) is bytes and len(raw) <= MAX_TRACE_BYTES and
            PIN.fullmatch(trace_sha256 or '') and digest(raw) == trace_sha256, 'TRACE_PIN_OR_LIMIT')
    if input_format == 'read-thread':
        raise ObservationError('MISSING_MACHINE_RECEIPT')
    require(input_format == 'codex-rollout', 'UNSUPPORTED_TRACE_FORMAT')
    for value in (thread_id, turn_id, server_name):
        require(readiness._identifier(value), 'EXACT_TARGET_REQUIRED')
    require(readiness._positive(started_not_before_ns) and readiness._positive(now_ns) and
            started_not_before_ns <= now_ns, 'OBSERVATION_CLOCK')
    expected_script = metadata_script(prefix)
    catalog_names = _catalog(catalog_raw, catalog_sha256)
    require(raw.endswith(b'\n'), 'TRUNCATED_ROLLOUT')
    lines = raw.splitlines(keepends=True)
    require(len(lines) <= MAX_LINES, 'TRACE_LINE_LIMIT')
    session_seen = False
    active = None
    began = ended = context = call = reply = None
    control_receipts = 0
    tool_declarations = 0
    line_refs = []
    for number, line in enumerate(lines, 1):
        require(len(line) <= MAX_LINE_BYTES, 'TRACE_LINE_LIMIT')
        record = _json(line)
        require(type(record) is dict and type(record.get('payload')) is dict, 'ROLLOUT_RECORD_FORMAT')
        kind, payload = record.get('type'), record['payload']
        if kind == 'session_meta':
            require(not session_seen and payload.get('id') == thread_id, 'TRACE_THREAD_MISMATCH')
            session_seen = True
            continue
        event = payload.get('type')
        if kind == 'event_msg' and event == 'task_started':
            require(active != turn_id or ended is not None, 'MIXED_OR_INCOMPLETE_TURN')
            active = payload.get('turn_id')
            if active == turn_id:
                require(session_seen and began is None, 'DUPLICATE_TARGET_TURN')
                began = _utc(record.get('timestamp'))
                require(started_not_before_ns <= began <= now_ns, 'TURN_OUTSIDE_SELECTED_WINDOW')
                line_refs.append({'line':number,'kind':'task_started','sha256':digest(line)})
            continue
        if active != turn_id:
            continue
        stamp = _utc(record.get('timestamp'))
        require(began <= stamp <= now_ns, 'TURN_TIMESTAMP_ORDER')
        if kind == 'event_msg' and event in ('turn_aborted','error'):
            raise ObservationError('TURN_NOT_COMPLETED')
        if kind == 'event_msg' and event == 'task_complete':
            require(payload.get('turn_id') == turn_id and ended is None and reply is not None,
                    'TURN_NOT_COMPLETED')
            require(reply[0] <= stamp, 'TURN_TIMESTAMP_ORDER')
            ended = stamp
            line_refs.append({'line':number,'kind':'task_complete','sha256':digest(line)})
            active = None
            continue
        if kind == 'turn_context':
            require(payload.get('turn_id') == turn_id and context is None and call is None,
                    'TURN_CONTEXT_MISMATCH')
            context = stamp
            line_refs.append({'line':number,'kind':'turn_context','sha256':digest(line)})
            continue
        if kind != 'response_item' or event in ('message','reasoning'):
            continue
        if event == 'additional_tools':
            # A pre-context functions.exec definition is not a dispatched tool.
            # It supplies no names, marker, script, receipt, timestamp or authority.
            require(context is None and call is None and reply is None and
                    tool_declarations == 0 and _exec_declaration(payload), 'NON_METADATA_TOOL_CALL')
            tool_declarations += 1
            line_refs.append({'line':number,'kind':event,'sha256':digest(line)})
            continue
        if event not in ('custom_tool_call','custom_tool_call_output','function_call_output'):
            # Unknown/action/function calls are not an observation-only turn.
            raise ObservationError('NON_METADATA_TOOL_CALL')
        meta = payload.get('internal_chat_message_metadata_passthrough')
        require(type(meta) is dict and meta.get('turn_id') == turn_id, 'RECEIPT_TURN_MISMATCH')
        require(context is not None and context <= stamp, 'TURN_CONTEXT_MISSING')
        if event == 'function_call_output':
            # Actual rollout inserts this host-origin conversation-dispatch
            # result before the model runs; it has no paired in-turn call.
            require(call is None and control_receipts == 0 and 'call_id' not in payload and
                    payload.get('namespace') == 'codex_app' and
                    payload.get('name') in ('create_thread','send_message_to_thread'), 'NON_METADATA_TOOL_CALL')
            control_receipts += 1
            continue
        call_id = payload.get('call_id')
        require(readiness._identifier(call_id), 'RECEIPT_CALL_ID_REQUIRED')
        if event == 'custom_tool_call':
            require(call is None and reply is None and payload.get('name') == 'exec' and
                    payload.get('status') == 'completed', 'SINGLE_METADATA_EXEC_REQUIRED')
            require(_script(payload.get('input')) == expected_script, 'METADATA_SCRIPT_MISMATCH')
            call = (stamp, call_id)
        else:
            require(call is not None and reply is None and call_id == call[1] and
                    call[0] <= stamp, 'MISSING_OR_DUPLICATE_MACHINE_RECEIPT')
            reply = (stamp, payload.get('output'))
        line_refs.append({'line':number,'kind':event,'sha256':digest(line)})
    require(session_seen and began is not None and context is not None and call is not None and
            reply is not None and ended is not None, 'MISSING_MACHINE_RECEIPT')
    require(readiness._fresh(reply[0], now_ns), 'MODEL_OBSERVATION_STALE_OR_UNDATED')
    names, marker, metadata_sha = _metadata(reply[1], prefix, catalog_names, catalog_sha256)
    observation = {'source':readiness.MODEL_SOURCE,
        'target':{'thread_id':thread_id,'server_name':server_name},
        'thread_id':thread_id,'turn_id':turn_id,'server_name':server_name,
        'observed_at_ns':reply[0],'marker':marker,'tools':names}
    provenance = {'schema':PROVENANCE_SCHEMA,'source_format':'CODEX_LOCAL_ROLLOUT_RECEIPT',
        'source_authentication':'CALLER_SELECTED_LOCAL_BYTES_NOT_HOST_SIGNATURE',
        'trace_sha256':trace_sha256,'catalog_sha256':catalog_sha256,'thread_id':thread_id,
        'turn_id':turn_id,'server_name':server_name,
        'server_name_source':'CALLER_SELECTED_LABEL_NOT_HOST_AUTHENTICATION',
        'server_prefix':prefix,'server_prefix_source':'EXACT_OBSERVED_ENTRY_PREFIX', 'call_id':call[1],
        'script_sha256':digest(expected_script.encode()),'metadata_output_sha256':metadata_sha,
        'observation_sha256':digest(encoded(observation)),'original_observed_at_ns':reply[0],
        'turn_started_at_ns':began,'turn_completed_at_ns':ended,'source_records':line_refs,
        'tool_count':len(names),'inventory_source':'EXACT_EXEC_ALL_TOOLS_METADATA',
        'full_input_schema_delivery_verified':False,'agent_final_used':False,
        'execution_authorized':False,'automatic_retry_allowed':False,'actual_execution':'HOLD'}
    return observation, provenance


def read_pinned(path, pin, limit):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path,*path.parents)), 'UNSAFE_INPUT_PATH')
    require(type(pin) is str and PIN.fullmatch(pin), 'EXACT_INPUT_PIN_REQUIRED')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        # Existing Codex rollouts can be 0644. Do not chmod them or claim OS
        # privacy; require ownership and no group/other write, plus exact pin.
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and
                before.st_nlink == 1 and before.st_mode & 0o022 == 0 and before.st_size <= limit,
                'UNSAFE_INPUT_FILE')
        chunks, remaining = [], limit + 1
        while remaining:
            chunk = os.read(fd, min(remaining,65536))
            if not chunk:
                break
            chunks.append(chunk);remaining -= len(chunk)
        after = os.fstat(fd);raw = b''.join(chunks)
        require(all(getattr(before,key) == getattr(after,key) for key in
                    ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')) and
                len(raw) == before.st_size <= limit and digest(raw) == pin, 'INPUT_CHANGED_OR_PIN_MISMATCH')
        return raw
    finally:
        os.close(fd)


def write_result(directory, observation, provenance):
    directory = Path(directory)
    require(directory.is_absolute() and '..' not in directory.parts and
            not any(p.is_symlink() for p in (directory,*directory.parents)), 'UNSAFE_OUTPUT_PATH')
    directory.mkdir(mode=0o700)  # Exclusive new directory; partial output is preserved.
    for name, value in (('observation.json',observation),('provenance.json',provenance)):
        fd = os.open(directory/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
    fd = os.open(directory,os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace',required=True,type=Path)
    parser.add_argument('--trace-sha256',required=True)
    parser.add_argument('--catalog',required=True,type=Path)
    parser.add_argument('--catalog-sha256',required=True)
    parser.add_argument('--thread-id',required=True)
    parser.add_argument('--turn-id',required=True)
    parser.add_argument('--server-name',required=True)
    parser.add_argument('--server-prefix',required=True)
    parser.add_argument('--started-not-before-ns',required=True,type=int)
    parser.add_argument('--input-format',choices=('codex-rollout','read-thread'),default='codex-rollout')
    parser.add_argument('--output-directory',required=True,type=Path)
    args = parser.parse_args(argv)
    try:
        raw = read_pinned(args.trace,args.trace_sha256,MAX_TRACE_BYTES)
        catalog = read_pinned(args.catalog,args.catalog_sha256,MAX_LINE_BYTES)
        observation, provenance = collect(raw,catalog,trace_sha256=args.trace_sha256,
            catalog_sha256=args.catalog_sha256,thread_id=args.thread_id,turn_id=args.turn_id,
            server_name=args.server_name,prefix=args.server_prefix,
            started_not_before_ns=args.started_not_before_ns,now_ns=time.time_ns(),input_format=args.input_format)
        provenance['input_trace_path'] = str(args.trace)
        provenance['input_catalog_path'] = str(args.catalog)
        require(readiness._fresh(observation['observed_at_ns'],time.time_ns()),
                'MODEL_OBSERVATION_STALE_OR_UNDATED')
        write_result(args.output_directory,observation,provenance)
        print(json.dumps({'state':'EXACT_METADATA_RECEIPT_COLLECTED','output_directory':str(args.output_directory),
            'observation_sha256':digest(encoded(observation)),'provenance_sha256':digest(encoded(provenance)),
            'tool_count':len(observation['tools']),'actual_execution':'HOLD'}))
        return 0
    except (ObservationError,OSError) as error:
        print(json.dumps({'state':'BLOCKED','code':getattr(error,'code','LOCAL_IO_FAILED'),
            'automatic_retry_allowed':False,'actual_execution':'HOLD'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
