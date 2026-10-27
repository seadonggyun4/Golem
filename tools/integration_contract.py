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
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise IntegrationError(code)


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


def _validate(value, rule):
    if 'oneOf' in rule:
        require(type(rule['oneOf']) is list and 1 <= len(rule['oneOf']) <= 16, 'SCHEMA')
        matches = 0
        for branch in rule['oneOf']:
            try:
                _validate(value, branch)
                matches += 1
            except IntegrationError:
                pass
        require(matches == 1, 'SCHEMA')
        return
    if "const" in rule:
        require(type(value) is type(rule["const"]) and value == rule["const"], "SCHEMA")
        return
    kind = rule["type"]
    if isinstance(kind, list):
        require(value is None or isinstance(value, dict), "SCHEMA")
        return
    if kind == "object":
        require(isinstance(value, dict) and set(value) == set(rule["required"]), "SCHEMA")
        for key, child in rule["properties"].items():
            _validate(value[key], child)
    elif kind == "array":
        require(isinstance(value, list) and rule["minItems"] <= len(value) <= rule["maxItems"], "SCHEMA")
        require(len({encoded(item) for item in value}) == len(value), "SCHEMA")
        for item in value:
            _validate(item, rule["items"])
    elif kind == "string":
        require(isinstance(value, str), "SCHEMA")
        require(rule.get("minLength", 0) <= len(value) <= rule.get("maxLength", LIMIT), "SCHEMA")
        if "pattern" in rule:
            require(re.fullmatch(rule["pattern"].removeprefix("^").removesuffix("$"), value) is not None, "SCHEMA")
        if "enum" in rule:
            require(value in rule["enum"], "SCHEMA")
    else:
        require(type(value) is int and rule["minimum"] <= value <= rule["maximum"], "SCHEMA")


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
