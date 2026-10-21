"""D4 typed, explicit mutations with durable intent and no automatic retries."""
from contextlib import nullcontext
from pathlib import Path
import threading
import os

import execution_record as records
import integration_backend as backend
import integration_contract as c
import integration_registry as r
import integration_service as reads
import integration_mutation_contract as contract
import integration_lifecycle as lifecycle


def blocked(error, *, uncertain=False, evidence_id=None):
    return {"schema": "golem.integration-mutation-result.v1",
        "state": "COMMIT_UNKNOWN" if uncertain else
                 "PENDING_APPROVAL" if getattr(error, "code", None) == "PENDING_APPROVAL" else "NOT_DISPATCHED",
        "code": getattr(error, "code", "IO_OR_CONTRACT_ERROR"),
        "native_state_changed": "UNKNOWN" if uncertain else False,
        "automatic_retry_allowed": False, "execution_authorized": False,
        "acceptance_verified": False, "local_evidence_id": evidence_id,
        "next_operation": "INSPECT_ORIGINAL_INTENT_NATIVE_STATUS_AND_EFFECTS_NO_REDISPATCH" if uncertain else
                          "REVIEW_OWNER_ACTION_POLICY_AND_CURRENT_NATIVE_STATE"}


class Service:
    def __init__(self, policy):
        self.policy, self.registry = policy, policy.registry
        self.reads = reads.Service(policy.transfer)
        self._lock = threading.Lock()

    def tools(self):
        result = set(self.reads.tools())
        with self.registry.locked():
            for entry in self.policy.current()["actions"]:
                try:
                    self.policy.authorize(entry)
                except (c.IntegrationError, OSError, ValueError):
                    continue
                result.add(entry["tool"])
        return sorted(result)

    def call(self, name, args):
        if name in reads.SCHEMAS:
            return self.reads.call(name, args)
        c.require(name in contract.NAMES, "UNSUPPORTED_TOOL")
        c.bounded(args)
        c.require(len(c.encoded(args)) <= c.LIMIT, "JSON_SIZE")
        c._validate(args, contract.SCHEMAS[name])
        c.require(self._lock.acquire(blocking=False), "SERVICE_BUSY")
        try:
            return self._mutate(name, args)
        finally:
            self._lock.release()

    def _admit(self, name, args):
        lifecycle.fence(self.registry, args["project_id"])
        entry = next((v for v in self.policy.current()["actions"] if v["action_id"] == args["action_id"]), None)
        c.require(entry is not None and entry["tool"] == name and
                  entry["project_id"] == args["project_id"] and entry["work_id"] == args["work_id"], "MUTATION_SCOPE")
        project, scope = self.policy.authorize(entry)
        value, native = self.policy.action(entry)
        if value["approval"]:
            c.require(not Path(value["approval"]["decision"]["path"]).is_relative_to(Path(project["root"])),
                      "MUTATION_POLICY_SCOPE")
        work = next(w for w in project["works"] if w["work_id"] == entry["work_id"])
        lineage = c.sha(c.encoded({"identity": work["identity"],
                                   "genesis": work["genesis_sha256"]}))
        identity = {"binding": scope["binding"], "work_id": entry["work_id"],
                    "lineage": lineage, "request_id": args["request_id"]}
        key = c.sha(c.encoded(identity))
        intent = {"schema": "golem.integration-mutation-intent.v1", **identity,
            "tool": name, "action": entry, "native_sha256": c.sha(value["native_json"].encode()),
            "action_sha256": c.sha(c.encoded(value)), "policy_sha256": self.policy.digest}
        output = self.registry.root / ("mutation-" + key)
        if output.exists():
            old = c.decode(r.regular(output / "intent.json", private=True))
            # New owner-reviewed policies may add unrelated actions. Keep the
            # original policy evidence, but compare actual request identity.
            c.require({k: v for k, v in old.items() if k != "policy_sha256"} ==
                      {k: v for k, v in intent.items() if k != "policy_sha256"}, "REQUEST_CONFLICT")
            if (output / "result.json").exists():
                try:
                    previous = self._result(output)
                except (c.IntegrationError, OSError, ValueError):
                    previous = blocked(c.IntegrationError("MUTATION_RECORD_CORRUPT"), uncertain=True, evidence_id=output.name)
                return entry, project, work, value, native, output, previous
            return entry, project, work, value, native, output, blocked(
                c.IntegrationError("ORIGINAL_RESULT_NOT_RECORDED"), uncertain=True, evidence_id=output.name)
        pending = list(self.registry.root.glob("mutation-*"))
        c.require(len(pending) < 128, "MUTATION_QUOTA")
        for directory in pending:
            previous = c.decode(r.regular(directory / "intent.json", private=True))
            if previous["lineage"] == lineage:
                resolution = lifecycle.clearance(directory, previous)
                if resolution is not None:
                    c.require(resolution["retired"] != lifecycle.retired_identity(name, native), "RESOLVED_ACTION_REUSE_FORBIDDEN")
                    continue
                c.require((directory / "result.json").is_file(), "WORK_MUTATION_UNRESOLVED")
                try:
                    result = self._result(directory)
                except (c.IntegrationError, OSError, ValueError):
                    raise c.IntegrationError("WORK_MUTATION_UNRESOLVED") from None
                c.require(result["state"] != "COMMIT_UNKNOWN", "WORK_MUTATION_UNRESOLVED")
        backend._quota(self.registry.root)
        output.mkdir(mode=0o700)
        records.save(output / "intent.json", c.encoded(intent))
        records.save(output / "request.json", value["native_json"].encode())
        return entry, project, work, value, native, output, None

    @staticmethod
    def _result(output):
        data = r.regular(output / "result.json", c.MAX_NATIVE, private=True)
        pointer = c.decode(r.regular(output / "result-ref.json", private=True))
        c.require(pointer == {"sha256": c.sha(data)}, "MUTATION_RECORD_CORRUPT")
        result = c.decode(data, c.MAX_NATIVE)
        c.require(isinstance(result, dict) and result.get("schema") == "golem.integration-mutation-result.v1" and
                  result.get("state") in ("NOT_DISPATCHED", "PENDING_APPROVAL", "COMMIT_UNKNOWN", "NATIVE_RESULT_RECORDED"), "MUTATION_RECORD_CORRUPT")
        return result

    def _preflight(self, entry, native):
        selected = {"project_id": entry["project_id"], "work_id": entry["work_id"]}
        status = self.reads.call("work_inspect", {**selected, "view": "status"})["result"]
        following = self.reads.call("work_inspect", {**selected, "view": "next"})["result"]
        c._validate(status["sequence"], c.INTEGER)
        c._validate(following["sequence"], c.INTEGER)
        c.require(status["sequence"] == following["sequence"], "OBSERVATION_STALE")
        if entry["tool"].startswith("session_"):
            c.require(status["sequence"] == native["expected_sequence"], "OBSERVATION_STALE")
        if entry["tool"] == "session_resume":
            hint = status["resume_preflight"]
            c.require(hint["reason"] != "DONE", "RESUME_DONE_READ_NEXT")
            c.require(not hint["lease_live"] or hint["owner_session_id"] == entry["session_id"], "LIVE_OWNER_WAIT")
        return {"status": status, "next": following}

    def _argv(self, entry, project, work, value, output):
        argv = [project["cli"]["path"], "--output-mode", "full"]
        request = str(output / "request.json")
        tool = entry["tool"]
        if tool == "session_resume":
            for key in ("context", "count"):
                records.save(output / (key + ".json"), value[key + "_json"].encode())
            return [*argv, "session", "resume", work["path"], request,
                    str(output / "context.json"), str(output / "count.json")]
        if tool.startswith("session_"):
            return [*argv, "session", "call", work["path"], request]
        if tool == "document_submit":
            records.save(output / "body.md", value["body"].encode())
            return [*argv, "document", "submit", work["path"], request, str(output / "body.md"),
                    c.decode(r.regular(output / "intent.json", private=True))["request_id"]]
        approval = value["approval"]
        scope = self.policy.transfer.scope(entry["project_id"], entry["work_id"], "work_inspect")
        pointer = self.registry._pointer(scope["binding"]["project_id"])
        guards = {"pins": [{"path": str(path), "sha256": c.sha(r.regular(path, private=True))} for path in
                            (self.policy.path, self.policy.transfer.path, pointer)]}
        guard_data = c.encoded(guards)
        records.save(output / "guards.json", guard_data)
        return [approval["host"]["path"], "execute", work["path"], request, approval["decision"]["path"],
            approval["decision"]["sha256"], approval["request_receipt"], approval["contract"],
            approval["shell_contract"] or "-", str(output / "guards.json"), c.sha(guard_data)]

    @staticmethod
    def _approval_preflight(project, work, approval, output):
        query = {"schema_version": 1, "operation": "status", "request_receipt": approval["request_receipt"]}
        path = output / "approval-status.json"
        records.save(path, c.encoded(query))
        process_path = output / "approval-status-process"
        process_path.mkdir(mode=0o700)
        process = records.capture([project["cli"]["path"], "--output-mode", "full", "approval", "call",
            work["path"], str(path)], process_path, backend.TIMEOUT_SECONDS, cwd=process_path,
            observe_source=False, env=backend.ENVIRONMENT, limit=c.MAX_NATIVE)
        c.require(process["returncode"] == 0 and process["reason"] == "EXIT" and
                  process["recording"] == "RECORDED", "APPROVAL_STATUS_UNAVAILABLE")
        status = c.decode(r.regular(process_path / "stdout.log", c.MAX_NATIVE, private=True), c.MAX_NATIVE)
        c.require(isinstance(status, dict), "APPROVAL_STATUS_UNAVAILABLE")
        c.require(status.get("state") == "APPROVED", "PENDING_APPROVAL" if status.get("state") == "PENDING" else
                  "APPROVAL_NOT_DISPATCHABLE_INSPECT_RECOVERY")

    def _publish(self, output, result):
        data = c.encoded(result)
        c.require(len(data) <= c.MAX_NATIVE, "NATIVE_OUTPUT_LIMIT")
        records.save(output / "result.json", data)
        records.save(output / "result-ref.json", c.encoded({"sha256": c.sha(data)}))
        return result

    def _mutate(self, name, args):
        # Durable unfinished intent excludes other D4 writers for this Work.
        # Long QA releases admission and uses native live authority callbacks.
        with self.registry.locked(exclusive=True):
            entry, project, work, value, native, output, previous = self._admit(name, args)
            if previous is not None:
                return previous
            writer = lifecycle.lock(output / "writer.lock", create=True)
        dispatched = False
        try:
            preflight = self._preflight(entry, native)
            records.save(output / "preflight.json", c.encoded(preflight))
            if value["approval"]:
                self._approval_preflight(project, work, value["approval"], output)
            argv = self._argv(entry, project, work, value, output)
            with self.registry.locked(exclusive=True):
                lifecycle.fence(self.registry, args["project_id"])
                self.policy.authorize(entry)
                c.require(self.policy.action(entry)[0] == value, "ACTION_CHANGED")
                # Last integration fence. The native reducer rechecks its own
                # lease/owner/sequence/source/input/binding under its store lock.
                records.save(output / "dispatch-intent.json", c.encoded({"state": "COMMIT_UNKNOWN"}))
                dispatched = True
            admission = nullcontext() if value["approval"] else self.registry.locked()
            with admission:
                if not value["approval"]:
                    lifecycle.fence(self.registry, args["project_id"])
                    self.policy.authorize(entry)
                process = records.capture(argv, output, 540 if value["approval"] else backend.TIMEOUT_SECONDS,
                    cwd=output, observe_source=False, env=backend.ENVIRONMENT, limit=c.MAX_NATIVE)
            c.require(process["returncode"] == 0 and process["reason"] == "EXIT" and
                      process["recording"] == "RECORDED", "NATIVE_FAILURE")
            raw = r.regular(output / "stdout.log", c.MAX_NATIVE, private=True)
            reply = c.decode(raw, c.MAX_NATIVE)
            c.require(isinstance(reply, dict), "NATIVE_CONTRACT")
            # Immutable historical response, not a new lease/current PASS.
            result = {"schema": "golem.integration-mutation-result.v1", "state": "NATIVE_RESULT_RECORDED",
                "native_state_changed": "POSSIBLE", "native_reply": reply, "native_stdout_sha256": c.sha(raw),
                "local_evidence_id": output.name, "automatic_retry_allowed": False,
                "execution_authorized": False, "acceptance_verified": False,
                "assurance": "LOCAL_COOPERATIVE", "next_operation": "READ_CURRENT_STATUS_NEXT_AND_NATIVE_RESULT"}
            with self.registry.locked():
                self.policy.authorize(entry)
            c.require(len(c.encoded(result)) <= self.policy.transfer.value["max_result_bytes"], "RESULT_BUDGET_EXCEEDED")
            return self._publish(output, result)
        except (c.IntegrationError, OSError, ValueError, KeyError, TypeError) as error:
            result = blocked(error, uncertain=dispatched, evidence_id=output.name)
            try:
                return self._publish(output, result)
            except (OSError, ValueError):
                return blocked(c.IntegrationError("RESULT_RECORDING_FAILED"), uncertain=dispatched, evidence_id=output.name)
        finally:
            os.close(writer)
