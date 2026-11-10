"""Closed D1 contracts. The same definitions validate values and emit JSON Schema.

This deliberately supports only the bounded forms used here, not arbitrary or
remote JSON Schema execution. Native JSON contracts remain native-owned.
"""
import hashlib
import json
import re

from verify_agent import strict_json

LIMIT = 262144
MAX_NATIVE = 33554432
ID = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$", "maxLength": 64}
DIGEST = {"type": "string", "pattern": "^[a-f0-9]{64}$", "maxLength": 64}
PATH = {"type": "string", "minLength": 1, "maxLength": 4096, "pattern": "^[^\\x00-\\x1f\\x7f]+$"}
INTEGER = {"type": "integer", "minimum": 0, "maximum": 9007199254740991}


class IntegrationError(ValueError):
    def __init__(self, code, *, diagnostic=None):
        self.code = code
        self.diagnostic = _safe_diagnostic(diagnostic)
        super().__init__(code)


def require(condition, code, *, diagnostic=None):
    if not condition:
        raise IntegrationError(code, diagnostic=diagnostic)


DIAGNOSTIC_SCOPES = frozenset(('INPUT_SCHEMA', 'INPUT_CONTRACT', 'CONTRACT_SHAPE',
                              'NATIVE_OBSERVATION', 'OWNER_ACTION_CONTRACT'))
DIAGNOSTIC_REASONS = frozenset(('TYPE', 'MISSING_REQUIRED_FIELD', 'UNEXPECTED_FIELDS',
    'LENGTH', 'FORMAT', 'ENUM', 'CONST', 'RANGE', 'ARRAY_LENGTH', 'DUPLICATE_ITEMS',
    'ONE_OF', 'EMPTY_REQUIRED', 'NONEMPTY_REQUIRED', 'REQUIRED_JSON_OBJECT', 'FIELD_SCOPE'))
DIAGNOSTIC_TYPES = frozenset(('object', 'array', 'string', 'integer', 'boolean', 'null'))
DIAGNOSTIC_FORMATS = frozenset(('identifier', 'sha256', 'declared_pattern',
    'declared_enum', 'declared_constant', 'empty_string', 'nonempty_string', 'json_object'))


def _safe_diagnostic(value):
    """Project only bounded contract metadata, never values or arbitrary error text."""
    if not isinstance(value, dict) or set(value) != {'schema', 'scope', 'path', 'reason', 'expected', 'values_omitted'}:
        return None
    if (value['schema'] != 'golem.validation-diagnostic.v1'
            or not isinstance(value['scope'], str) or value['scope'] not in DIAGNOSTIC_SCOPES
            or not isinstance(value['reason'], str) or value['reason'] not in DIAGNOSTIC_REASONS
            or value['values_omitted'] is not True):
        return None
    path = value['path']
    if not isinstance(path, str) or len(path) > 1024 or re.fullmatch(
            r'\$(?:(?:\.[A-Za-z_][A-Za-z0-9_-]{0,63})|(?:\[\d{1,3}\])|(?:\.<field>)){0,48}', path) is None:
        return None
    expected = value['expected']
    numbers = {'minLength', 'maxLength', 'minimum', 'maximum', 'minItems', 'maxItems'}
    flags = {'uniqueItems', 'additionalProperties'}
    if not isinstance(expected, dict) or not set(expected) <= numbers | flags | {'type', 'format'}:
        return None
    for key, item in expected.items():
        if key in numbers and (type(item) is not int or not -9007199254740991 <= item <= 9007199254740991):
            return None
        if key in flags and type(item) is not bool:
            return None
        if key == 'format' and (not isinstance(item, str) or item not in DIAGNOSTIC_FORMATS):
            return None
        if key == 'type':
            kinds = item if isinstance(item, list) else [item]
            if not 1 <= len(kinds) <= 6 or any(not isinstance(k, str) or k not in DIAGNOSTIC_TYPES for k in kinds):
                return None
    return {**value, 'expected': {key: list(item) if isinstance(item, list) else item
                                  for key, item in expected.items()}}


def field_diagnostic(path, reason, expected, *, scope='CONTRACT_SHAPE'):
    """Only schema-defined paths and expected formats; never caller keys/values."""
    return _safe_diagnostic({'schema': 'golem.validation-diagnostic.v1', 'scope': scope,
        'path': path, 'reason': reason, 'expected': expected, 'values_omitted': True})


def validation_diagnostic(error):
    return _safe_diagnostic(getattr(error, 'diagnostic', None))


def _property_path(path, key):
    # Unknown input keys are never passed here. Schema-defined identifier keys
    # may be shown; non-identifier schema keys are deliberately unnamed.
    label = key if isinstance(key, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}', key) else '<field>'
    return path + '.' + label


def _expected(rule):
    result = {key: rule[key] for key in ('type', 'minLength', 'maxLength', 'minimum',
        'maximum', 'minItems', 'maxItems', 'uniqueItems', 'additionalProperties') if key in rule}
    if 'const' in rule:
        result['format'] = 'declared_constant'
    elif 'enum' in rule:
        result['format'] = 'declared_enum'
    elif 'pattern' in rule:
        result['format'] = ('identifier' if rule['pattern'] == ID['pattern'] else
                            'sha256' if rule['pattern'] == DIGEST['pattern'] else 'declared_pattern')
    return result


def _schema_require(condition, path, reason, rule, scope):
    if not condition:
        raise IntegrationError('SCHEMA', diagnostic=field_diagnostic(path, reason, _expected(rule), scope=scope))


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def array(items, maximum=32, minimum=1):
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum,
            "uniqueItems": True}


def enum(*values):
    return {"type": "string", "enum": list(values)}


IDENTITY = obj({"device": INTEGER, "inode": INTEGER})
PIN = obj({"path": PATH, "sha256": DIGEST})
WORK = obj({"work_id": ID, "path": PATH, "identity": IDENTITY, "genesis_sha256": DIGEST})
PROJECT = obj({"schema": {"const": "golem.integration-project.v1"}, "project_id": ID,
               "root": PATH, "identity": IDENTITY, "runtime_root": PATH,
               "runtime_identity": IDENTITY, "cli": PIN, "sdk_pins": array(PIN),
               "works": array(WORK)})
GRANT = obj({"schema": {"const": "golem.integration-grant.v1"}, "principal_id": ID,
             "client_id": ID, "operations": array(enum("status", "next", "record", "history"), 4),
             "work_ids": array(ID), "destination": {"const": "LOCAL_HOST"},
             "assurance": {"const": "LOCAL_COOPERATIVE"}})
BINDING = obj({"schema": {"const": "golem.integration-client-binding.v1"},
               "project_id": ID, "generation": INTEGER, "principal_id": ID,
               "client_id": ID, "assurance": {"const": "LOCAL_COOPERATIVE"}})
ENROLLMENT = obj({"schema": {"const": "golem.integration-enrollment.v1"},
                  "project": PROJECT, "grants": array(GRANT)})
DESCRIPTION = obj({"schema": {"const": "golem.integration-description.v1"},
                   "project_id": ID, "root": PATH, "cli": PATH, "sdk_files": array(PATH),
                   "works": array(obj({"work_id": ID, "path": PATH}))})
QUERY = obj({"schema": {"const": "golem.integration-read.v1"}, "binding": BINDING,
             "work_id": ID, "operation": enum("status", "next", "record", "history"),
             "limit": {"type": "integer", "minimum": 1, "maximum": 256},
             "cursor": {"type": ["object", "null"]}})
CONTRACTS = {"project": PROJECT, "grant": GRANT, "binding": BINDING,
             "enrollment": ENROLLMENT, "read": QUERY, "description": DESCRIPTION}


def bounded(value, depth=0):
    require(depth <= 24, "JSON_DEPTH")
    if isinstance(value, dict):
        require(len(value) <= 256, "JSON_SIZE")
        for key, item in value.items():
            require(isinstance(key, str) and "\0" not in key, "JSON_STRING")
            bounded(key, depth + 1)
            bounded(item, depth + 1)
    elif isinstance(value, list):
        require(len(value) <= 512, "JSON_SIZE")
        for item in value:
            bounded(item, depth + 1)
    elif isinstance(value, str):
        require("\0" not in value, "JSON_STRING")
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError:
            raise IntegrationError("JSON_STRING") from None


def decode(data, limit=LIMIT):
    require(len(data) <= limit, "JSON_SIZE")
    try:
        data.decode("utf-8", errors="strict")
        value = strict_json(data)
        bounded(value)
        return value
    except IntegrationError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise IntegrationError("JSON_INVALID") from None


def _validate(value, rule, *, path='$', scope='CONTRACT_SHAPE'):
    if 'oneOf' in rule:
        require(type(rule['oneOf']) is list and 1 <= len(rule['oneOf']) <= 16, 'SCHEMA')
        matches = 0
        for branch in rule['oneOf']:
            try:
                _validate(value, branch, path=path, scope=scope)
                matches += 1
            except IntegrationError:
                pass
        _schema_require(matches == 1, path, 'ONE_OF', rule, scope)
        return
    if "const" in rule:
        _schema_require(type(value) is type(rule["const"]) and value == rule["const"], path, 'CONST', rule, scope)
        return
    kind = rule["type"]
    if isinstance(kind, list):
        _schema_require(value is None or isinstance(value, dict), path, 'TYPE', rule, scope)
        return
    if kind == "object":
        _schema_require(isinstance(value, dict), path, 'TYPE', rule, scope)
        if set(value) != set(rule['required']):
            missing = next((key for key in rule['required'] if key not in value), None)
            if missing is not None:
                _schema_require(False, _property_path(path, missing), 'MISSING_REQUIRED_FIELD',
                                rule['properties'][missing], scope)
            _schema_require(False, path, 'UNEXPECTED_FIELDS', rule, scope)
        for key, child in rule["properties"].items():
            _validate(value[key], child, path=_property_path(path, key), scope=scope)
    elif kind == "array":
        _schema_require(isinstance(value, list), path, 'TYPE', rule, scope)
        _schema_require(rule["minItems"] <= len(value) <= rule["maxItems"], path, 'ARRAY_LENGTH', rule, scope)
        _schema_require(len({encoded(item) for item in value}) == len(value), path, 'DUPLICATE_ITEMS', rule, scope)
        for index, item in enumerate(value):
            _validate(item, rule["items"], path=path+'['+str(index)+']', scope=scope)
    elif kind == "string":
        _schema_require(isinstance(value, str), path, 'TYPE', rule, scope)
        _schema_require(rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", LIMIT), path, 'LENGTH', rule, scope)
        if "pattern" in rule:
            _schema_require(re.fullmatch(rule["pattern"].removeprefix("^").removesuffix("$"), value) is not None,
                            path, 'FORMAT', rule, scope)
        if "enum" in rule:
            _schema_require(value in rule["enum"], path, 'ENUM', rule, scope)
    else:
        _schema_require(type(value) is int, path, 'TYPE', rule, scope)
        _schema_require(rule["minimum"] <= value <= rule["maximum"], path, 'RANGE', rule, scope)


def validate(kind, value):
    require(kind in CONTRACTS, "UNSUPPORTED_CONTRACT")
    bounded(value)
    require(len(encoded(value)) <= LIMIT, "JSON_SIZE")
    _validate(value, CONTRACTS[kind])
    if kind == "project":
        require(len({w["work_id"] for w in value["works"]}) == len(value["works"]), "SCHEMA")
        require(len({w["path"] for w in value["works"]}) == len(value["works"]), "SCHEMA")
        require(len({p["path"] for p in value["sdk_pins"]}) == len(value["sdk_pins"]), "SCHEMA")
    elif kind == "enrollment":
        validate("project", value["project"])
        require(len({(g["principal_id"], g["client_id"]) for g in value["grants"]}) == len(value["grants"]), "SCHEMA")
        for grant in value["grants"]:
            require(set(grant["work_ids"]) <= {w["work_id"] for w in value["project"]["works"]}, "SCHEMA")
    elif kind == "read":
        require(value["operation"] == "history" or value["cursor"] is None, "SCHEMA")
    return value


def schema(kind):
    require(kind in CONTRACTS, "UNSUPPORTED_CONTRACT")
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Golem D1 " + kind, **CONTRACTS[kind]}
