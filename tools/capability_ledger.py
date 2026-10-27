"""Approved M0 field structure; NOT a complete ledger or coverage validator.

Pure in-memory checks grant no authority, read no files and emit no coverage
acceptance result. decode_ledger enforces adopted JSON/field bounds; partial
dict validators do not. Observation ID derivation uses a separate M0 domain.
File scan and evidence policies remain separate decisions. No CLI, MCP
registration, automatic ID rewriting or file writer is provided.
"""
import hashlib
import json
import re
from pathlib import PureWindowsPath

SCHEMA = 'golem.mcp-capability-ledger.v1'
ROOT_FIELDS = frozenset(('schema', 'sources', 'observations', 'capabilities'))
SOURCE_FIELDS = frozenset(('path', 'sha256'))
OBSERVATION_FIELDS = frozenset(('id', 'kind', 'source_path', 'entrypoint', 'selector'))
CAPABILITY_FIELDS = frozenset(('id', 'observation_ids', 'implementation', 'current_routes',
    'target_routes', 'authorities', 'effects', 'constraints', 'test_refs', 'doc_refs',
    'review_status', 'rationale'))
OBSERVATION_KINDS = frozenset(('C_PUBLIC_DECLARATION', 'CLI_ROUTE', 'NATIVE_OPERATION',
    'PYTHON_DECLARATION', 'MCP_TOOL_DECLARATION', 'UNRESOLVED'))
IMPLEMENTATIONS = frozenset(('UNVERIFIED', 'IMPLEMENTED', 'PARTIAL', 'PROPOSED', 'UNSUPPORTED'))
ROUTES = frozenset(('MCP_READ', 'MCP_REVIEWED_ACTION', 'OWNER_ONLY', 'HOST_INTERNAL'))
REVIEW_STATES = frozenset(('UNREVIEWED', 'REVIEWED'))
EFFECTS = frozenset(('NATIVE_READ', 'NATIVE_WRITE', 'AUDIT_WRITE', 'DISCLOSURE',
    'PROCESS', 'NETWORK', 'GIT', 'CLEANUP', 'UNVERIFIED'))
CONSTRAINT_FIELDS = frozenset(('platforms', 'limits', 'notes'))
TEST_REF_FIELDS = frozenset(('path', 'selector'))
DOC_REF_FIELDS = frozenset(('path', 'anchor'))
JSON_BYTES_MAX = 16 * 1024 * 1024
JSON_DEPTH_MAX = 16
ROOT_ARRAY_MAX = {'sources': 4096, 'observations': 16384, 'capabilities': 4096}
ITEM_ARRAY_MAX = 256
ID_BYTES_MAX = 256
TEXT_BYTES_MAX = 4096
LONG_TEXT_BYTES_MAX = 16 * 1024
OBSERVATION_ID_DOMAIN = b'golem.mcp-observation-id.v1\0'


class BaseFieldError(ValueError):
    """Failure in an approved field rule; messages contain no input data."""


def _require(condition, code):
    if not condition:
        raise BaseFieldError(code)


def _object(value, fields):
    _require(type(value) is dict and set(value) == fields, 'CLOSED_FIELDS')


def _text(value):
    _require(type(value) is str and bool(value), 'NONEMPTY_STRING')


def _path(value):
    _text(value)
    _require(not value.startswith('/') and '\\' not in value and '\0' not in value and
             not PureWindowsPath(value).drive and
             all(part not in ('', '.', '..') for part in value.split('/')), 'RELATIVE_SOURCE_PATH')


def validate_relative_path(value):
    """Adopted lexical relative-path and byte bounds; no filesystem access."""
    _path(value)
    _utf8_size(value, TEXT_BYTES_MAX)


def validate_base_fields(value):
    """Check adopted closed fields, base types, uniqueness and internal refs.

    Returns None on base-rule success, never VALID/COMPLETE/PASS. Empty arrays
    are structurally permitted. kind and remaining classification values are
    not validated, and no source hash is checked against actual file bytes.
    Original objects, strings and array order are unchanged on success/failure.
    Duplicate JSON keys cannot be detected after decoding: use decode_ledger
    for adopted raw JSON decoding and bounds, not this partial dict validator.
    """
    _object(value, ROOT_FIELDS)
    _require(type(value['schema']) is str and value['schema'] == SCHEMA, 'SCHEMA')
    for name in ('sources', 'observations', 'capabilities'):
        _require(type(value[name]) is list, 'ARRAY')

    paths = set()
    for source in value['sources']:
        _object(source, SOURCE_FIELDS)
        _path(source['path'])
        digest = source['sha256']
        _require(type(digest) is str and re.fullmatch(r'[a-f0-9]{64}', digest) is not None, 'SHA256')
        _require(source['path'] not in paths, 'DUPLICATE_SOURCE')
        paths.add(source['path'])

    observation_ids = set()
    for observation in value['observations']:
        _object(observation, OBSERVATION_FIELDS)
        _text(observation['id'])
        _text(observation['entrypoint'])
        _require(observation['id'] not in observation_ids, 'DUPLICATE_OBSERVATION_ID')
        observation_ids.add(observation['id'])
        _require(type(observation['source_path']) is str and observation['source_path'] in paths,
                 'SOURCE_REFERENCE')
        if observation['selector'] is not None:
            _text(observation['selector'])

    capability_ids = set()
    for capability in value['capabilities']:
        _object(capability, CAPABILITY_FIELDS)
        _text(capability['id'])
        _require(capability['id'] not in capability_ids, 'DUPLICATE_CAPABILITY_ID')
        capability_ids.add(capability['id'])
        refs = capability['observation_ids']
        _require(type(refs) is list, 'OBSERVATION_REFERENCES_ARRAY')
        seen = set()
        for ref in refs:
            _text(ref)
            _require(ref in observation_ids, 'OBSERVATION_REFERENCE')
            _require(ref not in seen, 'DUPLICATE_OBSERVATION_REFERENCE')
            seen.add(ref)


def _enum(value, choices, code):
    _require(type(value) is str and value in choices, code)


def validate_classification_fields(value):
    """Validate base and adopted enums/routes only, returning None.

    Unknown classification values fail; unresolved/unverified/unreviewed values
    are valid representations of blockers, not evidence of completed coverage.
    Remaining metadata, source bytes, bounds and complete gate are not checked.
    No inference is made from an IMPLEMENTED or REVIEWED declaration alone.
    """
    validate_base_fields(value)
    for observation in value['observations']:
        _enum(observation['kind'], OBSERVATION_KINDS, 'OBSERVATION_KIND')
    for capability in value['capabilities']:
        _enum(capability['implementation'], IMPLEMENTATIONS, 'IMPLEMENTATION')
        _enum(capability['review_status'], REVIEW_STATES, 'REVIEW_STATUS')
        for field in ('current_routes', 'target_routes'):
            routes = capability[field]
            _require(type(routes) is list, 'ROUTES_ARRAY')
            seen = set()
            for route in routes:
                _enum(route, ROUTES, 'ROUTE')
                _require(route not in seen, 'DUPLICATE_ROUTE')
                seen.add(route)


def classification_blockers(value):
    """Known classification blockers as internal (reason, id) pairs.

    Empty is NOT final coverage PASS: partial/proposed/unsupported capabilities,
    empty routes, unverified evidence and unclassified source scope still cannot
    be counted as fully provided. The complete gate remains unimplemented.
    Checks all observations, including ones not linked by a capability.
    """
    validate_classification_fields(value)
    blockers = []
    for observation in value['observations']:
        if observation['kind'] == 'UNRESOLVED':
            blockers.append(('UNRESOLVED', observation['id']))
    for capability in value['capabilities']:
        if capability['implementation'] == 'UNVERIFIED':
            blockers.append(('UNVERIFIED', capability['id']))
        if capability['review_status'] == 'UNREVIEWED':
            blockers.append(('UNREVIEWED', capability['id']))
    return tuple(blockers)


def _text_array(value):
    _require(type(value) is list, 'TEXT_ARRAY')
    seen = set()
    for text in value:
        _text(text)
        _require(text not in seen, 'DUPLICATE_TEXT')
        seen.add(text)


def _references(value, fields, selector_field):
    _require(type(value) is list, 'REFERENCES_ARRAY')
    seen = set()
    for ref in value:
        _object(ref, fields)
        _path(ref['path'])
        selector = ref[selector_field]
        if selector is not None:
            _text(selector)
        key = (ref['path'], selector)
        _require(key not in seen, 'DUPLICATE_REFERENCE')
        seen.add(key)


def validate_metadata_fields(value):
    """Check all adopted field structures, without reading or running references.

    Returns None, never evidence acceptance or coverage PASS. Does not establish
    source bytes, reference existence, test execution, constraint truth, authority
    or sufficiency. Use decode_ledger for raw JSON/field bounds and the separate
    ID validator for derivation. Scan scope and evidence sufficiency are separate.
    """
    validate_classification_fields(value)
    for capability in value['capabilities']:
        _text_array(capability['authorities'])
        effects = capability['effects']
        _require(type(effects) is list, 'EFFECTS_ARRAY')
        seen = set()
        for effect in effects:
            _enum(effect, EFFECTS, 'EFFECT')
            _require(effect not in seen, 'DUPLICATE_EFFECT')
            seen.add(effect)
        constraints = capability['constraints']
        _object(constraints, CONSTRAINT_FIELDS)
        _text_array(constraints['platforms'])
        _text_array(constraints['limits'])
        _text(constraints['notes'])
        _references(capability['test_refs'], TEST_REF_FIELDS, 'selector')
        _references(capability['doc_refs'], DOC_REF_FIELDS, 'anchor')
        _text(capability['rationale'])


def metadata_blockers(value):
    """Known uncertainty markers only; an empty tuple is not final gate success."""
    validate_metadata_fields(value)
    return (*classification_blockers(value),
        *(('EFFECTS_UNVERIFIED', capability['id']) for capability in value['capabilities']
          if 'UNVERIFIED' in capability['effects']))


def _json_depth(text):
    """Bound containers before json.loads; quoted/escaped brackets do not count."""
    stack, quoted, escaped = [], False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '{[':
            stack.append(char)
            _require(len(stack) <= JSON_DEPTH_MAX, 'JSON_DEPTH_LIMIT')
        elif char in '}]':
            _require(bool(stack) and stack.pop() == ('{' if char == '}' else '['), 'JSON_SYNTAX')
    _require(not quoted and not stack, 'JSON_SYNTAX')


def _unique_members(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, 'JSON_DUPLICATE_KEY')
        value[key] = item
    return value


def _no_constant(_value):
    raise BaseFieldError('JSON_NONFINITE')


def _no_number(_value):
    # Every adopted field is object/array/string/null; no numeric field exists.
    # Avoid constructing arbitrarily large integers/floats before schema rejection.
    raise BaseFieldError('JSON_NUMBER_NOT_IN_SCHEMA')


def _utf8_size(value, maximum):
    try:
        size = len(value.encode('utf-8', errors='strict'))
    except UnicodeEncodeError:
        raise BaseFieldError('JSON_SURROGATE') from None
    _require(size <= maximum, 'STRING_BYTES_LIMIT')


def _string_maximum(location):
    if len(location) == 3 and location[0] in ('observations', 'capabilities') and location[2] == 'id':
        return ID_BYTES_MAX
    if len(location) == 4 and location[0] == 'capabilities' and location[2] == 'observation_ids':
        return ID_BYTES_MAX
    if len(location) == 3 and location[0] == 'capabilities' and location[2] == 'rationale':
        return LONG_TEXT_BYTES_MAX
    if len(location) == 4 and location[0] == 'capabilities' and location[2:] == ('constraints', 'notes'):
        return LONG_TEXT_BYTES_MAX
    return TEXT_BYTES_MAX


def _decoded_limits(value):
    # Private: json.loads produces an acyclic tree with JSON value types only.
    pending = [((), value)]
    while pending:
        location, item = pending.pop()
        if type(item) is str:
            _utf8_size(item, _string_maximum(location))
        elif type(item) is dict:
            for key, child in item.items():
                _utf8_size(key, TEXT_BYTES_MAX)
                pending.append(((*location, key), child))
        elif type(item) is list:
            maximum = ROOT_ARRAY_MAX.get(location[0], ITEM_ARRAY_MAX) if len(location) == 1 else ITEM_ARRAY_MAX
            _require(len(item) <= maximum, 'ARRAY_LIMIT')
            pending.extend(((*location, index), child) for index, child in enumerate(item))


def decode_ledger(raw):
    """Decode adopted bounded JSON structure into a new owned Python value.

    No file reads/writes, authority changes or normalization. Preserves array
    order and strings; rejects duplicates, rather than silently dropping them.
    This is NOT ID/source/evidence verification or final coverage acceptance.
    Use decode_identified_ledger when observation ID binding is also required.
    Raw-byte/depth limits are checked before json.loads; decoded limits before
    structural validation. Limits do not guarantee physical memory or CPU use.
    """
    _require(type(raw) is bytes, 'LEDGER_BYTES')
    _require(len(raw) <= JSON_BYTES_MAX, 'JSON_BYTES_LIMIT')
    _require(not raw.startswith(b'\xef\xbb\xbf'), 'JSON_BOM')
    try:
        text = raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        raise BaseFieldError('JSON_UTF8') from None
    _json_depth(text)
    try:
        value = json.loads(text, object_pairs_hook=_unique_members,
                           parse_constant=_no_constant, parse_int=_no_number, parse_float=_no_number)
    except BaseFieldError:
        raise
    except (ValueError, RecursionError):
        raise BaseFieldError('JSON_SYNTAX') from None
    _decoded_limits(value)
    validate_metadata_fields(value)
    return value


def observation_identity(*, kind, source_path, entrypoint, selector):
    """Adopted deterministic M0 observation ID, not native CAS or authority.

    No source hash, line number, array order, existing ID or capability grouping
    enters this identity. Does not normalize text or infer semantic equivalence.
    """
    _enum(kind, OBSERVATION_KINDS, 'OBSERVATION_KIND')
    _path(source_path)
    _text(entrypoint)
    _utf8_size(source_path, TEXT_BYTES_MAX)
    _utf8_size(entrypoint, TEXT_BYTES_MAX)
    if selector is not None:
        _text(selector)
        _utf8_size(selector, TEXT_BYTES_MAX)
    value = {'kind': kind, 'source_path': source_path,
             'entrypoint': entrypoint, 'selector': selector}
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    return 'obs-' + hashlib.sha256(OBSERVATION_ID_DOMAIN + payload).hexdigest()


def validate_observation_ids(value):
    """Check declared observation IDs without rewriting IDs or references.

    Manual stable capability IDs stay untouched. No source hash drift/evidence
    sufficiency/previous-review validity is determined without their contracts.
    Successful return is None, not final coverage acceptance.
    """
    validate_metadata_fields(value)
    _decoded_limits(value)
    for observation in value['observations']:
        expected = observation_identity(**{key: observation[key] for key in
            ('kind', 'source_path', 'entrypoint', 'selector')})
        _require(observation['id'] == expected, 'OBSERVATION_ID_MISMATCH')


def decode_identified_ledger(raw):
    """Bounded structural decode plus observation ID binding, not coverage PASS."""
    value = decode_ledger(raw)
    validate_observation_ids(value)
    return value
