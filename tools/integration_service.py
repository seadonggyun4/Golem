"""Transport-independent D2 reads and explicit, non-authoritative handoffs."""
from pathlib import Path
import tempfile
import threading

import execution_record as records
import integration_backend as backend
import integration_contract as c
import integration_registry as r
from integration_transfer import NAMES

WORK_ARGS = {"project_id": c.ID, "work_id": c.ID}
CONTEXT_ARGS = {**WORK_ARGS, "selection_id": c.ID, "source_snapshot": c.DIGEST,
                "target_kind": c.ID, "recipe": c.enum("current-v1", "original-v1")}
SCHEMAS = {
    "projects_list": c.obj({}),
    "work_inspect": c.obj({**WORK_ARGS, "view": c.enum("status", "next", "record")}),
    "history_read": c.obj({**WORK_ARGS, "limit": {"type": "integer", "minimum": 1, "maximum": 256},
                            "cursor": {"type": ["object", "null"]}}),
    "context_get": c.obj(CONTEXT_ARGS),
    "handoff_prepare": c.obj({**CONTEXT_ARGS, "recipient_client_id": c.ID}),
}


def blocked(error):
    code = getattr(error, "code", "IO_OR_CONTRACT_ERROR")
    next_operation = {
        "NATIVE_FAILURE": "INSPECT_LOCAL_NATIVE_STDOUT_STDERR_NO_RETRY",
        "OBSERVATION_STALE": "READ_CURRENT_STATUS_NEXT_AND_REVIEW_CONTEXT",
        "RESULT_BUDGET_EXCEEDED": "OWNER_REVIEW_RESULT_BUDGET_NO_TRUNCATION",
        "AUDIT_QUOTA": "OWNER_REVIEW_PRIVATE_AUDIT_CAPACITY_NO_AUTOMATIC_DELETION",
        "GRANT_STALE": "OWNER_REVIEW_CURRENT_APPROVAL_GENERATION",
    }.get(code, "REVIEW_OWNER_POLICY_AND_LOCAL_NATIVE_EVIDENCE")
    return {"schema": "golem.integration-error.v1", "state": "BLOCKED",
            "code": code,
            "native_state_changed": False, "execution_authorized": False,
            "automatic_retry_allowed": False,
            "next_operation": next_operation,
            "local_evidence_id": Path(error.evidence_path).name if getattr(error, "evidence_path", None) else None}


class Service:
    def __init__(self, transfer):
        self.transfer = transfer
        self.registry = transfer.registry
        # Native document locks and spool admission are serialized within a host.
        self._lock = threading.Lock()

    def _read(self, scope, work_id, operation, limit=64, cursor=None):
        return backend.read(self.registry, {"schema": "golem.integration-read.v1",
            "binding": scope["binding"], "work_id": work_id, "operation": operation,
            "limit": limit, "cursor": cursor})

    def _authorize(self, scope, work_id, operation):
        project = self.registry.authorize(scope["binding"], work_id, operation)
        c.require(not self.transfer.path.is_relative_to(Path(project["root"])), "TRANSFER_POLICY_SCOPE")
        return project

    def available(self):
        """Recheck every scope; list no unapproved project or filesystem name."""
        result = []
        with self.registry.locked():
            for scope in self.transfer.current()["scopes"]:
                for work_id in scope["work_ids"]:
                    try:
                        self._authorize(scope, work_id, "record")
                    except (c.IntegrationError, OSError, ValueError):
                        continue
                    result.append({"project_id": scope["binding"]["project_id"], "work_id": work_id,
                                   "tools": scope["tools"]})
        return result

    def tools(self):
        return sorted({name for item in self.available() for name in item["tools"]})

    def call(self, name, args):
        c.require(name in NAMES, "UNSUPPORTED_TOOL")
        c.bounded(args)
        c.require(len(c.encoded(args)) <= c.LIMIT, "JSON_SIZE")
        c._validate(args, SCHEMAS[name])
        c.require(self._lock.acquire(blocking=False), "SERVICE_BUSY")
        try:
            with self.registry.locked():
                return self._call_locked(name, args)
        finally:
            self._lock.release()

    def _call_locked(self, name, args):
        if name == "projects_list":
            result = {"projects": [v for v in self.available() if name in v["tools"]]}
        else:
            scope = self.transfer.scope(args["project_id"], args["work_id"], name)
            if name in ("context_get", "handoff_prepare"):
                for operation in ("record", "status", "next"):
                    self._authorize(scope, args["work_id"], operation)
                result = self._context(scope, args, name)
            else:
                operation = args["view"] if name == "work_inspect" else "history"
                self._authorize(scope, args["work_id"], operation)
                observed = self._read(scope, args["work_id"], operation, args.get("limit", 64), args.get("cursor"))
                # Never expose private audit paths or sibling observations.
                result = {"view": operation, "result": observed["result"],
                          "observation_sha256": c.sha(c.encoded(observed["result"]))}
        self.transfer.current()
        response = {"schema": "golem.integration-delivery.v1", "state": "AVAILABLE",
            "native_state_changed": False, "execution_authorized": False,
            "ownership_transferred": False, "observations_atomic": False,
            "assurance": "LOCAL_COOPERATIVE", "model_consumption": "NOT_OBSERVED",
            "destination": self.transfer.value["destination"],
            "destination_id": self.transfer.value["destination_id"], **result}
        c.require(len(c.encoded(response)) <= self.transfer.value["max_result_bytes"], "RESULT_BUDGET_EXCEEDED")
        return response

    def _context(self, scope, args, tool):
        work_id = args["work_id"]
        recipient = None
        if tool == "handoff_prepare":
            recipient = next((b for b in scope["recipients"] if b["client_id"] == args["recipient_client_id"]), None)
            c.require(recipient is not None, "RECIPIENT_APPROVAL_REQUIRED")
            for operation in ("record", "status", "next"):
                self.registry.authorize(recipient, work_id, operation)
        before = self._read(scope, work_id, "record")["result"]
        status = self._read(scope, work_id, "status")["result"]
        next_view = self._read(scope, work_id, "next")["result"]
        c.require(type(status.get("sequence")) is int and status["sequence"] == next_view.get("sequence"),
                  "OBSERVATION_STALE")
        with self.registry.locked():
            project = self._authorize(scope, work_id, "record")
            work = next(w for w in project["works"] if w["work_id"] == work_id)
            backend._quota(self.registry.root)
            output = Path(tempfile.mkdtemp(prefix="read-context-", dir=self.registry.root))
            request = {"schema_version": 1, "renderer_version": 2, "recipe": args["recipe"],
                "selection_id": args["selection_id"], "target_kind": args["target_kind"],
                "source_snapshot": args["source_snapshot"], "byte_budget": 2097152,
                "excerpt_bytes": 0, "token_budget": 0, "tokenizer_id": "none", "agent_note": ""}
            records.save(output / "request.json", c.encoded(request))
            try:
                process = records.capture([project["cli"]["path"], "--output-mode", "full", "context", "candidate",
                    work["path"], str(output / "request.json")], output, backend.TIMEOUT_SECONDS,
                    cwd=output, observe_source=False, env=backend.ENVIRONMENT, limit=c.MAX_NATIVE)
                c.require(process["returncode"] == 0 and process["reason"] == "EXIT" and
                          process["recording"] == "RECORDED", "NATIVE_FAILURE")
                candidate = c.decode(r.regular(output / "stdout.log", c.MAX_NATIVE, private=True), c.MAX_NATIVE)
                c.require(isinstance(candidate, dict), "CONTEXT_CANDIDATE_BINDING")
                text = candidate.get("candidate_json")
                c.require(isinstance(text, str) and c.sha(text.encode()) == candidate.get("projection_digest") and
                          c.decode(text.encode(), c.MAX_NATIVE) == candidate.get("candidate") and
                          candidate.get("budget_verified") is False, "CONTEXT_CANDIDATE_BINDING")
                projection = candidate["candidate"]
                c.require(isinstance(projection, dict) and projection.get("schema_version") == 2 and
                          projection.get("request") == request,
                          "CONTEXT_REPRESENTATION_VERSION")
                sources = projection.get("sources")
                c.require(isinstance(sources, list) and sources and all(isinstance(s, dict) and
                          type(s.get("omitted_bytes")) is int and s["omitted_bytes"] == 0 for s in sources),
                          "CONTEXT_INCOMPLETE_SOURCE")
                r.check_project(project)
            except (c.IntegrationError, OSError, ValueError) as error:
                records.save(output / "failure.json", c.encoded(blocked(error)))
                error.evidence_path = str(output)
                raise
        after = self._read(scope, work_id, "record")["result"]
        c.require(c.encoded(before) == c.encoded(after), "OBSERVATION_STALE")
        payload = {"schema": "golem.integration-handoff.v1" if tool == "handoff_prepare" else "golem.integration-context.v1",
            "project_id": args["project_id"], "work_id": work_id, "binding": scope["binding"],
            "recipient_binding": recipient,
            "context_role": "READING_AID", "projection_digest": candidate["projection_digest"],
            "candidate_json": text, "preflight": {"status": status, "next": next_view},
            "work_record_sha256": c.sha(c.encoded(after)), "transfer_policy_sha256": self.transfer.digest,
            "provider_budget": "UNKNOWN", "execution_ready": False,
            "next_operation": "RECEIVER_REAUTHORIZE_AND_READ_CURRENT_STATUS_NEXT",
            "ownership_transferred": False, "execution_authorized": False}
        data = c.encoded(payload)
        c.require(len(data) <= self.transfer.value["max_result_bytes"], "RESULT_BUDGET_EXCEEDED")
        # An immutable integration artifact, not a native receipt or checkpoint.
        records.save(output / "delivery.json", data)
        return {"payload": payload, "payload_sha256": c.sha(data)}
