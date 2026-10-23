"""Transport-independent D2 reads and explicit, non-authoritative handoffs."""
from pathlib import Path
import base64
import binascii
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
    "evidence_read": c.obj({**WORK_ARGS, "digest": c.DIGEST,
                            "max_bytes": {"type": "integer", "minimum": 1, "maximum": 1048576}}),
    "completion_check": c.obj({**WORK_ARGS, "selection_id": c.ID}),
}
AUDIT_READ_COST = {"work_inspect": 1, "history_read": 1, "context_get": 5,
                   "handoff_prepare": 5, "evidence_read": 3, "completion_check": 3}


def blocked(error):
    code = getattr(error, "code", "IO_OR_CONTRACT_ERROR")
    next_operation = {
        "NATIVE_FAILURE": "INSPECT_LOCAL_NATIVE_STDOUT_STDERR_NO_RETRY",
        "SOURCE_SNAPSHOT_MISMATCH": "READ_CURRENT_SELECTION_SNAPSHOT_AND_REVIEW_CONTEXT_NO_RETRY",
        "OBSERVATION_STALE": "READ_CURRENT_STATUS_NEXT_AND_REVIEW_CONTEXT",
        "RESULT_BUDGET_EXCEEDED": "OWNER_REVIEW_RESULT_BUDGET_NO_TRUNCATION",
        "AUDIT_QUOTA": "OWNER_REVIEW_PRIVATE_AUDIT_CAPACITY_NO_AUTOMATIC_DELETION",
        "GRANT_STALE": "OWNER_REVIEW_CURRENT_APPROVAL_GENERATION",
        "EVIDENCE_NOT_REFERENCED": "SELECT_COMMITTED_DOCUMENT_OR_JOURNAL_PAYLOAD_REFERENCE",
        "EVIDENCE_BINDING": "OWNER_INSPECT_LOCAL_NATIVE_EVIDENCE_NO_RETRY",
        "AUDIT_QUOTA": "OWNER_REVIEW_PRIVATE_AUDIT_CAPACITY_NO_AUTOMATIC_DELETION",
    }.get(code, "REVIEW_OWNER_POLICY_AND_LOCAL_NATIVE_EVIDENCE")
    response = {"schema": "golem.integration-error.v1", "state": "BLOCKED",
            "code": code,
            "native_state_changed": False, "execution_authorized": False,
            "automatic_retry_allowed": False,
            "next_operation": next_operation,
            "local_evidence_id": Path(error.evidence_path).name if getattr(error, "evidence_path", None) else None,
            "local_evidence_id_semantics": "IDENTIFIER_ONLY_NULL_DOES_NOT_PROVE_NO_AUDIT_RECORD",
            "work_outcome": "NOT_DETERMINED_BY_THIS_ERROR"}
    if code == "EVIDENCE_NOT_REFERENCED":
        response["explanation"] = "No supported committed document or journal reference matches this digest. Storage existence and content truth were not determined."
    if code == "AUDIT_QUOTA":
        response["explanation"] = "Private audit capacity or inventory safety checks blocked admission. This does not prove physical disk exhaustion or Work failure."
        if isinstance(getattr(error, "audit_capacity", None), dict):
            response["audit_capacity"] = error.audit_capacity
    return response


def context_failure(process, output):
    """Promote only the pinned native context diagnostic, never free-form stderr."""
    fallback = "NATIVE_FAILURE"
    if (process.get("returncode") != 1 or process.get("reason") != "EXIT" or
            process.get("recording") != "RECORDED"):
        return fallback
    try:
        lines = r.regular(Path(output) / "stderr.log", c.LIMIT, private=True).splitlines()
        records_json = [c.decode(line) for line in lines if line.startswith(b"{")]
        if len(records_json) != 1:
            return fallback
        diagnostic = records_json[0]
        expected = {"schema": "golem.cli-error.v1", "code": "GOLEM_ERR_STALE_RESULT",
                    "category": "state", "status_code": 11, "exit_code": 1,
                    "command": "context", "phase": "command", "errno": None,
                    "retry_effect": False, "execution_authorized": False,
                    "system_errors_omitted": 0,
                    "system_errors_role": "OBSERVATIONS_NOT_INFERRED_CAUSES"}
        if not isinstance(diagnostic, dict) or any(
                type(diagnostic.get(k)) is not type(v) or diagnostic.get(k) != v
                for k, v in expected.items()):
            return fallback
        observations = diagnostic.get("system_errors")
        if not isinstance(observations, list) or len(observations) != 1:
            return fallback
        observation = observations[0]
        expected = {"component": "workflow", "operation": "source_snapshot_mismatch",
                    "status_code": 11, "kind": "validation", "errno": None, "truncated": False}
        if isinstance(observation, dict) and all(
                type(observation.get(k)) is type(v) and observation.get(k) == v
                for k, v in expected.items()):
            return "SOURCE_SNAPSHOT_MISMATCH"
    except (c.IntegrationError, OSError, ValueError):
        pass
    return fallback


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
            if result["projects"]:
                result["audit_capacity"] = backend.audit_capacity(self.registry.root)
                result["audit_read_directory_cost"] = {
                    tool: AUDIT_READ_COST.get(tool, 0)
                    for tool in sorted({t for v in result["projects"] for t in v["tools"]})}
                result["capacity_semantics"] = "READ_SLOTS_ONLY_BYTES_AND_ENTRIES_RECHECKED_NO_ADMISSION_GUARANTEE"
        else:
            scope = self.transfer.scope(args["project_id"], args["work_id"], name)
            if name in ("context_get", "handoff_prepare"):
                for operation in ("record", "status", "next"):
                    self._authorize(scope, args["work_id"], operation)
                backend._quota(self.registry.root, AUDIT_READ_COST[name])
                result = self._context(scope, args, name)
            elif name in ("evidence_read", "completion_check"):
                for operation in (("record", "status", "next") if name == "completion_check" else ("record",)):
                    self._authorize(scope, args["work_id"], operation)
                backend._quota(self.registry.root, AUDIT_READ_COST[name])
                result = self._verified_query(scope, args, name)
            else:
                operation = args["view"] if name == "work_inspect" else "history"
                self._authorize(scope, args["work_id"], operation)
                observed = self._read(scope, args["work_id"], operation, args.get("limit", 64), args.get("cursor"))
                # Never expose private audit paths or sibling observations.
                result = {"view": operation, "result": observed["result"],
                          "observation_sha256": c.sha(c.encoded(observed["result"]))}
        self.transfer.current()
        response = {"schema": "golem.integration-delivery.v1", "state": "AVAILABLE",
            "state_scope": "DELIVERY_ONLY", "work_completion_inferred": False,
            "native_state_changed": False, "execution_authorized": False,
            "ownership_transferred": False, "observations_atomic": False,
            "assurance": "LOCAL_COOPERATIVE", "model_consumption": "NOT_OBSERVED",
            "destination": self.transfer.value["destination"],
            "destination_id": self.transfer.value["destination_id"], **result}
        c.require(len(c.encoded(response)) <= self.transfer.value["max_result_bytes"], "RESULT_BUDGET_EXCEEDED")
        return response

    def _verified_query(self, scope, args, tool):
        """Only fixed native read commands; no caller-selected paths or operations."""
        work_id = args["work_id"]
        before = self._read(scope, work_id, "record")["result"]
        references = []
        if tool == "evidence_read":
            # Explicit committed CAS roles, not arbitrary hex found in prose,
            # frame hashes, assessment hashes, raw log hashes or orphan objects.
            for row in before.get("documents", []):
                for field, role in (("digest", "DOCUMENT_MANIFEST"), ("body_digest", "DOCUMENT_BODY")):
                    if row.get(field) == args["digest"]:
                        references.append({"role": role, "document_id": row["document_id"],
                                           "revision": row["revision"], "freshness": row["freshness"]})
            for row in before.get("journal", []):
                if row.get("payload_digest") == args["digest"]:
                    references.append({"role": "JOURNAL_PAYLOAD", "stream": row["stream"],
                                       "sequence": row["sequence"]})
            c.require(bool(references), "EVIDENCE_NOT_REFERENCED")
        project = self._authorize(scope, work_id, "record")
        work = next(w for w in project["works"] if w["work_id"] == work_id)
        backend._quota(self.registry.root)
        output = Path(tempfile.mkdtemp(prefix="read-verified-", dir=self.registry.root))
        if tool == "evidence_read":
            command = ["evidence", "read", work["path"], args["digest"], str(args["max_bytes"])]
        else:
            request = {"schema_version": 1, "operation": "resume", "selection_id": args["selection_id"]}
            records.save(output / "request.json", c.encoded(request))
            command = ["completion", "check", work["path"], str(output / "request.json")]
        try:
            process = records.capture([project["cli"]["path"], "--output-mode", "full", *command],
                output, backend.TIMEOUT_SECONDS, cwd=output, observe_source=False,
                env=backend.ENVIRONMENT, limit=c.MAX_NATIVE)
            c.require(process["returncode"] == 0 and process["reason"] == "EXIT" and
                      process["recording"] == "RECORDED", "NATIVE_FAILURE")
            value = c.decode(r.regular(output / "stdout.log", c.MAX_NATIVE, private=True), c.MAX_NATIVE)
            c.require(isinstance(value, dict), "NATIVE_RESPONSE")
            if tool == "evidence_read":
                c.require(set(value) == {"schema_version", "algorithm", "digest", "size", "encoding", "data", "verified"}
                          and type(value["schema_version"]) is int and value["schema_version"] == 1
                          and value["algorithm"] == "sha256"
                          and value["digest"] == args["digest"] and value["encoding"] == "base64"
                          and value["verified"] is True and type(value["size"]) is int
                          and isinstance(value["data"], str), "EVIDENCE_BINDING")
                try:
                    raw = base64.b64decode(value["data"], validate=True)
                except (ValueError, binascii.Error):
                    raise c.IntegrationError("EVIDENCE_BINDING") from None
                c.require(len(raw) == value["size"] and len(raw) <= args["max_bytes"]
                          and base64.b64encode(raw).decode() == value["data"]
                          and c.sha(raw) == args["digest"], "EVIDENCE_BINDING")
                result = {"view": tool, "result": value, "references": references,
                          "verification": "SHA256_INTEGRITY_NOT_CONTENT_TRUTH",
                          "content_role": "UNTRUSTED_DATA"}
            else:
                selection = value.get("selection")
                c.require(isinstance(selection, dict)
                          and selection.get("document_id") == args["selection_id"]
                          and any(all(row.get(key) == selection.get(key)
                                      for key in ("document_id", "revision", "digest"))
                                  for row in before.get("documents", [])), "COMPLETION_BINDING")
                c.require(type(value.get("schema_version")) is int and value["schema_version"] == 1
                          and value.get("execution_authorized") is False
                          and type(value.get("acceptance_verified")) is bool
                          and isinstance(value.get("action"), str)
                          and value["acceptance_verified"] == (value["action"] == "DONE"), "COMPLETION_BINDING")
                result = {"view": tool, "selection_id": args["selection_id"], "result": value,
                          "completion_authority": "NATIVE_CURRENT_SELECTION",
                          "action_semantics": "NATIVE_ACTION_ONLY_NOT_PROOF_ALL_DOCUMENTS_EXIST_OR_OF_A_UNIQUE_CAUSE",
                          "next_operation": "REVIEW_NATIVE_ACTION_NO_AUTOMATIC_EXECUTION"}
            r.check_project(project)
            after = self._read(scope, work_id, "record")["result"]
            c.require(c.encoded(before) == c.encoded(after), "OBSERVATION_STALE")
            result["work_record_sha256"] = c.sha(c.encoded(after))
            result["observation_sha256"] = c.sha(c.encoded(value))
            records.save(output / "delivery.json", c.encoded(result))
            return result
        except (c.IntegrationError, OSError, ValueError) as error:
            records.save(output / "failure.json", c.encoded(blocked(error)))
            error.evidence_path = str(output)
            raise

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
                          process["recording"] == "RECORDED", context_failure(process, output))
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
