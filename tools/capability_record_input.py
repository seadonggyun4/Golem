"""Bounded explicit execution-record bytes. No filesystem or execution authority.

JSON names are selected explicitly, never inferred from manifest references.
Success validates input syntax/limits only, not any record schema or evidence.
"""
import json
import math
from decimal import Decimal
from capability_ledger import validate_relative_path

FILE_MAX = 32 * 1024 * 1024
TOTAL_MAX = 128 * 1024 * 1024
FILES_MAX = 4096
DEPTH_MAX = 32
NODES_MAX = 1_000_000
STRING_MAX = 1024 * 1024


class RecordInputError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise RecordInputError(code)


def _string(value):
    try:
        size = len(value.encode('utf-8', errors='strict'))
    except UnicodeError:
        raise RecordInputError('JSON_SURROGATE') from None
    require(size <= STRING_MAX, 'JSON_STRING_LIMIT')


def _depth(text):
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
        elif char in '[{':
            stack.append(char)
            require(len(stack) <= DEPTH_MAX, 'JSON_DEPTH_LIMIT')
        elif char in ']}':
            require(bool(stack) and stack.pop() == ('[' if char == ']' else '{'), 'JSON_SYNTAX')
    require(not quoted and not stack, 'JSON_SYNTAX')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _string(key)
        require(key not in result, 'JSON_DUPLICATE_KEY')
        result[key] = value
    return result


def _constant(value):
    raise RecordInputError('JSON_NONFINITE')


def _float(value):
    result = float(value)
    require(math.isfinite(result), 'JSON_NONFINITE')
    return result


def _integer(value):
    # Preserve arbitrary finite JSON integers without interpreter digit-limit
    # changes or lossy conversion to float. Ordinary record integers remain int.
    return int(value) if len(value) < 1000 else Decimal(value)


def decode_record_inputs(files, json_names):
    """Return decoded explicitly selected JSON; leave all input bytes untouched.

    Value nodes count root, containers and values; object keys are checked as
    strings but are not value nodes. This is not a peak-memory guarantee.
    """
    require(type(files) is dict and len(files) <= FILES_MAX, 'FILE_COUNT_OR_TYPE')
    require(type(json_names) in (list, tuple), 'JSON_SELECTION_TYPE')
    total = 0
    for name, raw in files.items():
        validate_relative_path(name)
        require(type(raw) is bytes, 'FILE_BYTES_TYPE')
        require(len(raw) <= FILE_MAX, 'FILE_BYTES_LIMIT')
        total += len(raw)
        require(total <= TOTAL_MAX, 'TOTAL_BYTES_LIMIT')
    selected = set()
    for name in json_names:
        validate_relative_path(name)
        require(name not in selected and name in files, 'JSON_SELECTION_DUPLICATE_OR_MISSING')
        selected.add(name)
    result, count = {}, 0
    for name in json_names:
        try:
            text = files[name].decode('utf-8', errors='strict')
        except UnicodeError:
            raise RecordInputError('JSON_UTF8') from None
        require(not text.startswith('\ufeff'), 'JSON_BOM')
        _depth(text)
        try:
            value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant,
                               parse_float=_float, parse_int=_integer)
        except (json.JSONDecodeError, RecursionError):
            raise RecordInputError('JSON_SYNTAX') from None
        pending = [value]
        while pending:
            item = pending.pop()
            count += 1
            require(count <= NODES_MAX, 'JSON_NODE_LIMIT')
            if isinstance(item, str):
                _string(item)
            elif isinstance(item, dict):
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        result[name] = value
    return result
