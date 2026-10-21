"""D4 owner-reviewed exact native actions, separate from D1 read grants."""
import argparse
import os
from pathlib import Path
import sys

import integration_contract as c
import integration_registry as r
import integration_transfer as transfer

NAMES = ("session_claim", "session_begin", "session_resume", "session_reconcile",
         "session_submit", "document_submit", "execution_request")
MODULES = ("integration_mutation_contract.py", "integration_mutations.py", "integration_mutation_mcp.py")
TEXT = {"type": "string", "maxLength": c.LIMIT}
LABEL = {"type": "string", "maxLength": 64, "pattern": "^[A-Za-z0-9_-]*$"}
TOKEN = c.obj({"epoch": {"type": "integer", "minimum": 1, "maximum": 4096},
               "attempt_id": c.ID, "session_id": c.ID})
REFERENCE = c.obj({"document_id": c.ID, "revision": c.INTEGER, "digest": c.DIGEST})
QA = c.obj({"host": c.PIN, "decision": c.PIN, "request_receipt": c.DIGEST,
            "contract": c.DIGEST, "shell_contract": {"type": "string", "maxLength": 64,
                                                      "pattern": "^(?:[a-f0-9]{64})?$"}})
ACTION = c.obj({"schema": {"const": "golem.integration-native-action.v1"},
    "native_json": TEXT, "body": TEXT, "context_json": TEXT, "count_json": TEXT,
    "approval": {**QA, "type": ["object", "null"]}})
ENTRY = c.obj({"action_id": c.ID, "project_id": c.ID, "work_id": c.ID,
    "tool": c.enum(*NAMES), "session_id": c.ID, "native_binding_id": LABEL, "action": c.PIN})
POLICY = c.obj({"schema": {"const": "golem.integration-mutations.v1"},
    "transfer_policy": c.PIN, "actions": c.array(ENTRY, 32),
    "producer": c.obj({name: c.DIGEST for name in (*transfer.PRODUCER_NAMES, *MODULES)})})
DECISION = c.obj({"schema": {"const": "golem.integration-local-decision.v1"},
    "action_digest": c.DIGEST, "issuer": c.DIGEST,
    "operation": {"const": "approve"},
    "policy_epoch": {"type": "integer", "minimum": 1, "maximum": c.INTEGER["maximum"]}})
ARGS = c.obj({"project_id": c.ID, "work_id": c.ID, "action_id": c.ID, "request_id": c.ID})
SCHEMAS = {name: ARGS for name in NAMES}


def producer():
    root = Path(__file__).resolve().parent
    return {**transfer.producer(), **{name: c.sha(r.regular(root / name)) for name in MODULES}}


def validate(value):
    c.bounded(value)
    c.require(len(c.encoded(value)) <= c.LIMIT, "JSON_SIZE")
    c._validate(value, POLICY)
    c.require(value["producer"] == producer(), "PRODUCER_CHANGED")
    c.require(len({a["action_id"] for a in value["actions"]}) == len(value["actions"]), "DUPLICATE_ACTION")
    return value


def native_action(entry, value):
    """Only the envelope is ours; native parsers and reducers remain authoritative."""
    c.bounded(value)
    c.require(len(c.encoded(value)) <= c.LIMIT, "JSON_SIZE")
    c._validate(value, ACTION)
    request = c.decode(value["native_json"].encode())
    c.require(isinstance(request, dict), "NATIVE_ACTION")
    name, owner = entry["tool"], entry["session_id"]
    if name.startswith("session_"):
        operation = name.removeprefix("session_")
        fields = {"schema_version": {"type": "integer", "minimum": 1, "maximum": 2},
            "operation": {"const": operation}, "work_id": {"const": entry["work_id"]},
            "key": c.ID, "expected_sequence": {"type": "integer", "minimum": 0, "maximum": 4096}}
        if operation in ("claim", "resume"):
            fields.update(session_id={"const": owner}, ttl_ms={"type": "integer", "minimum": 1, "maximum": 3600000})
            if entry["native_binding_id"]:
                fields.update(schema_version={"const": 2}, binding_id={"const": entry["native_binding_id"]})
                if operation == "resume":
                    fields["token"] = {"type": ["object", "null"]}
                    if request.get("token") is not None:
                        c._validate(request["token"], TOKEN)
            else:
                fields["schema_version"] = {"const": 1}
        else:
            fields.update(schema_version={"const": 1}, token=TOKEN, input_digest=c.DIGEST)
        if operation == "claim":
            fields.update(expected_generation={"type": "integer", "minimum": 1, "maximum": 4097},
                source_snapshot=c.DIGEST, byte_budget={"type": "integer", "minimum": 1, "maximum": 16777216})
        if operation in ("submit", "reconcile"):
            fields.update(source_snapshot=c.DIGEST, output={"type": ["object", "null"]}, evidence=c.array(c.DIGEST, 64))
            if request.get("output") is not None:
                c._validate(request["output"], REFERENCE)
            if operation == "reconcile":
                fields["resolution"] = c.enum("ADOPT_OUTPUT", "NO_EFFECTS")
            else:
                c.require(request.get("output") is not None, "NATIVE_ACTION")
        c._validate(request, c.obj(fields))
        if operation not in ("claim", "resume"):
            c.require(request["token"]["session_id"] == owner, "NATIVE_OWNER_MAPPING")
    elif name == "document_submit":
        # Metadata is validated by the existing native document parser/replay.
        c.require(request.get("schema_version") in (3, 4, 5) and
                  request.get("work_id") == entry["work_id"], "NATIVE_ACTION")
    else:
        c.require(request.get("operation") in ("prepare", "finish", "run"), "NATIVE_ACTION")
        fields = {"schema_version": {"const": 1}, "operation": {"const": request["operation"]}}
        fields.update({"contract": {"type": ["object", "null"]}} if request["operation"] == "prepare" else
                      {"checkpoint": c.DIGEST})
        if request["operation"] == "run":
            fields["attempt_id"] = c.ID
        if "token" in request:
            fields["token"] = TOKEN
            c._validate(request["token"], TOKEN)
            c.require(request["token"].get("session_id") == owner, "NATIVE_OWNER_MAPPING")
        c._validate(request, c.obj(fields))
    c.require((name == "document_submit") == bool(value["body"]), "ACTION_BODY_SCOPE")
    if name == "session_resume":
        context, count = c.decode(value["context_json"].encode()), c.decode(value["count_json"].encode())
        c.require(isinstance(context, dict) and isinstance(count, dict) and
                  type(context.get("token_budget")) is int and context["token_budget"] > 0 and
                  type(context.get("renderer_version")) is int and context["renderer_version"] == 2 and
                  context.get("recipe") in ("current-v1", "original-v1") and
                  type(context.get("excerpt_bytes")) is int and context["excerpt_bytes"] == 0,
                  "RESUME_COUNT_REQUIRED")
    else:
        c.require(not value["context_json"] and not value["count_json"], "ACTION_CONTEXT_SCOPE")
    if name == "execution_request":
        c.require(value["approval"] is not None, "PENDING_APPROVAL")
        c._validate(value["approval"], QA)
        shell = value["approval"]["shell_contract"]
        c.require(not shell or len(shell) == 64, "SCHEMA")
        if shell:
            c._validate(shell, c.DIGEST)
        decision_pin = value["approval"]["decision"]
        c.require(Path(decision_pin["path"]).exists(), "PENDING_APPROVAL")
        data = r.regular(Path(decision_pin["path"]), private=True)
        c.require(c.sha(data) == decision_pin["sha256"], "DECISION_CHANGED")
        c._validate(c.decode(data), DECISION)
        c.require(r.file_pin(Path(value["approval"]["host"]["path"])) == value["approval"]["host"], "PIN_MISMATCH")
        c.require(os.access(value["approval"]["host"]["path"], os.X_OK), "CLI_NOT_EXECUTABLE")
    else:
        c.require(value["approval"] is None, "ACTION_APPROVAL_SCOPE")
    return request


class Policy:
    def __init__(self, path, digest, *, approve_mutations=False):
        c.require(approve_mutations is True, "OWNER_MUTATION_APPROVAL_REQUIRED")
        c._validate(digest, c.DIGEST)
        self.path, self.digest = r.real_path(str(path)), digest
        self.value = self.current()
        pin = self.value["transfer_policy"]
        self.transfer = transfer.Transfer(Path(pin["path"]), pin["sha256"], approve_data_transfer=True)
        self.registry = self.transfer.registry
        with self.registry.locked():
            for entry in self.value["actions"]:
                self.authorize(entry)

    def current(self):
        data = r.regular(self.path, private=True)
        c.require(c.sha(data) == self.digest, "MUTATION_POLICY_CHANGED")
        return validate(c.decode(data))

    def authorize(self, entry):
        self.current()
        scope = self.transfer.scope(entry["project_id"], entry["work_id"], "work_inspect")
        project = None
        for operation in ("record", "status", "next"):
            project = self.registry.authorize(scope["binding"], entry["work_id"], operation)
        for path in (self.path, self.transfer.path, Path(entry["action"]["path"])):
            c.require(not path.is_relative_to(Path(project["root"])), "MUTATION_POLICY_SCOPE")
        return project, scope

    def action(self, entry):
        data = r.regular(Path(entry["action"]["path"]), private=True)
        c.require(c.sha(data) == entry["action"]["sha256"], "ACTION_CHANGED")
        value = c.decode(data)
        return value, native_action(entry, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("schema", "plan", "check"))
    parser.add_argument("--kind", choices=("policy", "action", "decision"), default="policy")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--reviewed-policy-sha256")
    parser.add_argument("--approve-mutations", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "schema":
            result = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                      **{"policy": POLICY, "action": ACTION, "decision": DECISION}[args.kind]}
        else:
            c.require(args.input is not None, "INPUT_REQUIRED")
            if args.operation == "plan":
                result = c.decode(r.regular(args.input, private=True))
                c.require(isinstance(result, dict), "SCHEMA")
                result["producer"] = producer()
                validate(result)
                # Plan only fills module pins; check performs live authorization.
            else:
                policy = Policy(args.input, args.reviewed_policy_sha256, approve_mutations=args.approve_mutations)
                for entry in policy.value["actions"]:
                    policy.action(entry)
                result = {"state": "CONFIGURATION_CHECKED", "native_state_changed": False}
        sys.stdout.buffer.write(c.encoded(result))
        return 0
    except (c.IntegrationError, OSError, ValueError) as error:
        sys.stderr.write(getattr(error, "code", "IO_OR_CONTRACT_ERROR") + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
