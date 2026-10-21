"""D6 owner-reviewed resource-server policy. No token issuance or discovery fetch."""
import argparse
import ipaddress
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import integration_contract as c
import integration_registry as r
import integration_update as updates
import integration_transfer as transfer
import integration_mutation_contract as mutations

TEXT = {"type": "string", "minLength": 1, "maxLength": 1024, "pattern": "^[^\\x00-\\x20\\x7f]+$"}
MODULES = ("integration_gateway_contract.py", "integration_gateway_auth.py", "integration_gateway.py", "requirements-gateway.txt")
DELEGATE = c.obj({"delegate_id": c.ID, "subject": TEXT, "oauth_client_id": TEXT,
    "destination_id": c.ID, "transfer_policy": c.PIN, "mutation_policy": {**c.PIN, "type": ["object", "null"]},
    "tools": c.array(c.enum(*transfer.NAMES, *mutations.NAMES), 12)})
REVOCATIONS = c.obj({"schema": {"const": "golem.integration-remote-revocations.v1"}, "epoch": c.INTEGER,
    "disabled": {"type": "boolean"}, "not_before": c.INTEGER,
    "revoked_jtis": c.array(TEXT, 1024, 0), "revoked_delegates": c.array(c.ID, 32, 0)})
POLICY = c.obj({"schema": {"const": "golem.integration-gateway.v1"},
    "issuer": TEXT, "resource": TEXT, "jwks": c.PIN, "revocation_file": c.PATH,
    "tls_cert": c.PIN, "tls_key": c.PIN,
    "origins": c.array(TEXT, 16, 0), "delegates": c.array(DELEGATE),
    "max_token_seconds": {"type": "integer", "minimum": 30, "maximum": 300},
    "requests_per_minute": {"type": "integer", "minimum": 1, "maximum": 120},
    "max_inflight": {"type": "integer", "minimum": 1, "maximum": 8},
    "producer": c.obj({name: c.DIGEST for name in (*updates.producer(), *MODULES)})})


def producer():
    root = Path(__file__).resolve().parent
    return {**updates.producer(), **{name: c.sha(r.regular(root / name)) for name in MODULES}}


def https(value, *, origin=False):
    c._validate(value, TEXT)
    url = urlsplit(value)
    c.require(value.isascii() and value == url.geturl() and url.scheme == "https" and url.hostname and not url.username and not url.password and
              not url.query and not url.fragment and "*" not in value and "%" not in value and
              "\\" not in value and value == value.strip() and url.netloc == url.netloc.lower(), "HTTPS_URL")
    c.require(url.port is None or 1 <= url.port <= 65535, "HTTPS_URL")
    c.require(url.port != 443 and (url.port is None or url.netloc.endswith(":" + str(url.port))), "HTTPS_URL")
    try:
        ipaddress.ip_address(url.hostname)
    except ValueError:
        c.require(len(url.hostname) <= 253 and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                  for label in url.hostname.split(".")), "HTTPS_URL")
    c.require(re.fullmatch(r"[A-Za-z0-9/._~!$&'()*+,;=:@-]*", url.path) is not None, "HTTPS_URL")
    if origin:
        c.require(value == "https://" + url.netloc, "HTTPS_ORIGIN")
    return url


def validate(value):
    c.bounded(value)
    c.require(len(c.encoded(value)) <= c.LIMIT, "JSON_SIZE")
    c._validate(value, POLICY)
    c.require(value["producer"] == producer(), "PRODUCER_CHANGED")
    c.require(https(value["resource"]).path == "/mcp", "RESOURCE_PATH")
    https(value["issuer"])
    for origin in value["origins"]:
        https(origin, origin=True)
    delegates = value["delegates"]
    c.require(len({d["delegate_id"] for d in delegates}) == len(delegates) and
              len({(d["subject"], d["oauth_client_id"]) for d in delegates}) == len(delegates), "DUPLICATE_DELEGATE")
    for delegate in delegates:
        if delegate["mutation_policy"] is not None:
            c._validate(delegate["mutation_policy"], c.PIN)
        c.require(len(set(delegate["tools"])) == len(delegate["tools"]), "DUPLICATE_TOOL")
        c.require(delegate["mutation_policy"] is not None or not set(delegate["tools"]) & set(mutations.NAMES),
                  "REMOTE_MUTATION_APPROVAL_REQUIRED")
    return value


def validate_revocations(value):
    c.require(isinstance(value, dict) and type(value.get("disabled")) is bool, "SCHEMA")
    # Reuse the unchanged D1 validator's supported closed-schema subset; its
    # public schema intentionally has no generic boolean-rule implementation.
    rule = {**REVOCATIONS, "properties": {**REVOCATIONS["properties"], "disabled": {"const": value["disabled"]}}}
    c._validate(value, rule)
    return value


class Policy:
    def __init__(self, path, digest, *, approve_remote_gateway=False):
        c.require(approve_remote_gateway is True, "OWNER_REMOTE_GATEWAY_APPROVAL_REQUIRED")
        c._validate(digest, c.DIGEST)
        self.path, self.digest = r.real_path(str(path)), digest
        self.value = self.current()
        revocation = r.real_path(self.value["revocation_file"])
        r.Registry._private(revocation.parent)

    def current(self):
        data = r.regular(self.path, private=True)
        c.require(c.sha(data) == self.digest, "REMOTE_POLICY_CHANGED")
        return validate(c.decode(data))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("schema", "plan"))
    parser.add_argument("--kind", choices=("policy", "revocations"), default="policy")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    try:
        schema = POLICY if args.kind == "policy" else REVOCATIONS
        if args.operation == "schema":
            value = {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}
        else:
            c.require(args.input is not None, "INPUT_REQUIRED")
            value = c.decode(r.regular(args.input, private=True))
            if args.kind == "policy":
                value["producer"] = producer()
                validate(value)
            else:
                validate_revocations(value)
        sys.stdout.buffer.write(c.encoded(value))
        return 0
    except (c.IntegrationError, OSError, ValueError, TypeError) as error:
        sys.stderr.write(getattr(error, "code", "IO_OR_CONTRACT_ERROR") + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
