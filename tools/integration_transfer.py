"""D2 owner-reviewed disclosure policy; never grants native authority.

D1 LOCAL_HOST grants remain necessary. This separate, pinned policy authorizes
their disclosure to one declared MCP destination, not authenticated identity.
"""
import argparse
from pathlib import Path
import sys

import integration_contract as c
import integration_registry as r
from integration_read_resources import MODULES as READ_RESOURCE_MODULES

NAMES = ('projects_list', 'work_inspect', 'history_read', 'context_get', 'handoff_prepare', 'evidence_read', 'completion_check', 'workflow_read', 'template_read', 'role_read', 'session_read', 'binding_read', 'document_read', 'context_read', 'discovery_read', 'events_read', 'journal_read', 'profile_read', 'diagnostic_read', 'native_validate', 'report_read', 'approval_read', 'reentry_read', 'artifact_read', 'usage_read', 'revision_read', 'configuration_read', 'bundle_read', 'inputs_prepare', 'action_prepare', 'contract_prepare', 'approved_action_prepare', 'plan_read', 'action_confirm', 'proof_read', 'research_read', 'cost_read', 'execution_read', 'candidate_read', 'inventory_read', 'parallel_prepare', 'merge_prepare', 'workspace_read')
PRODUCER_NAMES = ("integration_contract.py", "integration_registry.py", "integration_backend.py",
                  "execution_record.py", "verify_agent.py", "integration_transfer.py",
                  "integration_service.py", "integration_mcp.py", "integration_reads.py", *READ_RESOURCE_MODULES)
SCOPE = c.obj({"binding": c.BINDING, "work_ids": c.array(c.ID),
               "tools": c.array(c.enum(*NAMES), len(NAMES)), "recipients": c.array(c.BINDING, 32, 0)})
POLICY = c.obj({"schema": {"const": "golem.integration-transfer.v1"},
    "registry": c.PATH, "registry_identity": c.IDENTITY,
    "destination": c.enum("LOCAL_HOST", "MODEL_SERVICE"), "destination_id": c.ID,
    "data_class": {"const": "APPROVED_WORK_CONTENT"},
    "max_result_bytes": {"type": "integer", "minimum": 4096, "maximum": 8388608},
    "scopes": c.array(SCOPE), "producer": c.obj({name: c.DIGEST for name in PRODUCER_NAMES})})


def producer():
    root = Path(__file__).resolve().parent
    return {**r.producer(), **{name: c.sha(r.regular(root / name)) for name in
        ("integration_transfer.py", "integration_service.py", "integration_mcp.py", "integration_reads.py", *READ_RESOURCE_MODULES)}}


def validate(value):
    c.bounded(value)
    c.require(len(c.encoded(value)) <= c.LIMIT, "JSON_SIZE")
    c._validate(value, POLICY)
    c.require(isinstance(value["producer"], dict) and value["producer"] == producer(), "PRODUCER_CHANGED")
    scopes = value["scopes"]
    c.require(len({s["binding"]["project_id"] for s in scopes}) == len(scopes), "DUPLICATE_PROJECT")
    c.require(len({(s["binding"]["principal_id"], s["binding"]["client_id"]) for s in scopes}) == 1,
              "SINGLE_CLIENT_REQUIRED")
    for scope in scopes:
        c.require(len({b["client_id"] for b in scope["recipients"]}) == len(scope["recipients"]),
                  "DUPLICATE_RECIPIENT")
        c.require(all(b["project_id"] == scope["binding"]["project_id"] for b in scope["recipients"]),
                  "RECIPIENT_PROJECT_SCOPE")
    return value


class Transfer:
    def __init__(self, path, reviewed_sha256, *, approve_data_transfer=False):
        c.require(approve_data_transfer is True, "OWNER_TRANSFER_APPROVAL_REQUIRED")
        c._validate(reviewed_sha256, c.DIGEST)
        self.path = r.real_path(str(path))
        self.digest = reviewed_sha256
        self.value = self.current()
        self.registry = r.Registry(Path(self.value["registry"]))
        c.require(self.registry.root_identity == self.value["registry_identity"], "REGISTRY_CHANGED")

    def current(self):
        data = r.regular(self.path, private=True)
        c.require(c.sha(data) == self.digest, "TRANSFER_POLICY_CHANGED")
        return validate(c.decode(data))

    def scope(self, project_id, work_id, tool):
        value = self.current()
        scope = next((s for s in value["scopes"] if s["binding"]["project_id"] == project_id), None)
        c.require(scope is not None and tool in scope["tools"] and work_id in scope["work_ids"], "TRANSFER_SCOPE")
        return scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("schema", "plan"))
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "schema":
            result = {"$schema": "https://json-schema.org/draft/2020-12/schema", **POLICY}
        else:
            c.require(args.input is not None, "INPUT_REQUIRED")
            result = c.decode(r.regular(args.input, private=True))
            c.require(isinstance(result, dict), "SCHEMA")
            result["producer"] = producer()
            validate(result)
        sys.stdout.buffer.write(c.encoded(result))
        return 0
    except (c.IntegrationError, OSError, ValueError) as error:
        sys.stderr.write(getattr(error, "code", "IO_OR_CONTRACT_ERROR") + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
