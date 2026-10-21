"""D3 advisory SessionStart hook: native reads only, no transcript scraping."""
import argparse
from pathlib import Path
import sys
import tempfile

import execution_record as records
import integration_backend as backend
import integration_contract as c
import integration_hook_contract as contract
import integration_registry as r
import integration_service as service

NOTICE_LIMIT = 2000
REASONS = ("CURRENT", "DONE", "POLICY_REQUIRES_PERMISSION", "START_REQUIRED", "WORKFLOW_UNAVAILABLE",
           "BOOT_CHANGED", "CLOCK_REGRESSED", "LEASE_EXPIRED", "RECONCILIATION_REQUIRED", "ACTIVE_CLAIM")
OPERATIONS = ("READ_NEXT", "NONE", "REVIEW_POLICY", "SESSION_START", "INSPECT_WORKFLOW", "SESSION_RESUME",
              "CONTEXT_THEN_RECONCILE", "OWNER_CONTINUE_OR_RESUME")
FLAGS = ("boot_changed", "clock_regressed", "lease_live", "resume_required", "reconciliation_required", "binding_required")


def event(value, profile):
    # Host extensions are bounded metadata, never authority or filesystem input.
    c.bounded(value)
    c.require(isinstance(value, dict) and value.get("hook_event_name") == "SessionStart", "HOOK_EVENT")
    c.require(value.get("source") in profile.value["sources"], "HOOK_SOURCE_NOT_ENABLED")
    c.require(isinstance(value.get("session_id"), str) and 0 < len(value["session_id"]) <= 256, "HOOK_SESSION")
    c.require(value.get("cwd") == profile.project_root and
              str(r.real_path(value["cwd"])) == profile.project_root, "HOOK_PROJECT_MISMATCH")
    return value["source"]


def preflight(value):
    c.require(isinstance(value, dict) and value.get("reason") in REASONS and
              value.get("next_operation") in OPERATIONS, "HOOK_NATIVE_CONTRACT")
    c.require(all(type(value.get(key)) is bool for key in FLAGS), "HOOK_NATIVE_CONTRACT")
    return {"reason": value["reason"], "next_operation": value["next_operation"],
            **{key: value[key] for key in FLAGS}}


def envelope(notice, warning=None):
    text = c.encoded(notice).decode()
    c.require(len(text.encode()) <= NOTICE_LIMIT, "HOOK_NOTICE_LIMIT")
    value = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
    if warning:
        value["systemMessage"] = warning
    return value


def failure(error, diagnostic=None):
    detail = service.blocked(error)
    next_operation = {
        "HOOK_PROFILE_CHANGED": "REVIEW_NEW_PROFILE_AND_CLIENT_HOOK_TRUST",
        "CLIENT_OR_INTERPRETER_CHANGED": "OWNER_REPIN_OR_USE_EXPLICIT_D2_MCP",
        "CLIENT_PROFILE_UNSUPPORTED": "USE_EXPLICIT_D2_MCP_AND_REVIEW_CLIENT_PROFILE",
        "CLIENT_VERSION_MISMATCH": "USE_EXPLICIT_D2_MCP_AND_REVIEW_CLIENT_PROFILE",
        "HOOK_PROJECT_MISMATCH": "START_CLIENT_AT_APPROVED_PROJECT_ROOT",
        "HOOK_SOURCE_NOT_ENABLED": "REVIEW_OWNER_OPT_IN_SOURCES",
        "CLIENT_EXECUTABLE": "OWNER_REVIEW_SINGLE_LINK_CLIENT_SNAPSHOT",
    }.get(detail["code"], detail["next_operation"])
    return envelope({"schema": "golem.integration-hook-notice.v1", "context_state": "BLOCKED",
        "code": detail["code"], "next_operation": next_operation,
        "automatic_retry_allowed": False, "execution_authorized": False,
        "native_state_changed": False, "model_consumption": "NOT_OBSERVED", **(diagnostic or {})},
        "Golem context unavailable: " + detail["code"] + ". Review the hook policy and local evidence; no Work was resumed.")


def observe(profile, value):
    source = event(value, profile)
    registry = profile.transfer.registry
    with registry.locked():
        backend._quota(registry.root)
        output = Path(tempfile.mkdtemp(prefix="read-hook-", dir=registry.root))
        records.save(output / "started.json", c.encoded({"schema": "golem.integration-hook-observation.v1",
            "state": "STARTED", "profile_sha256": profile.digest, "source": source,
            "host_session_sha256": c.sha(value["session_id"].encode()), "native_state_changed": False}))
        diagnostic = None
        try:
            args = profile.value["context"]
            selected = {key: args[key] for key in ("project_id", "work_id")}
            status = profile.service.call("work_inspect", {**selected, "view": "status"})["result"]
            next_view = profile.service.call("work_inspect", {**selected, "view": "next"})["result"]
            c._validate(status["sequence"], c.INTEGER)
            c.require(status["sequence"] == next_view["sequence"], "OBSERVATION_STALE")
            hint = preflight(status.get("resume_preflight"))
            diagnostic = {"sequence": status["sequence"], "resume_preflight": hint}
            result = profile.service.call("context_get", args)
            payload = result["payload"]
            current, next_view = payload["preflight"]["status"], payload["preflight"]["next"]
            c.require(status["sequence"] == current["sequence"] == next_view["sequence"], "OBSERVATION_STALE")
            hint = preflight(current.get("resume_preflight"))
            for key in ("projection_digest", "work_record_sha256"):
                c._validate(payload[key], c.DIGEST)
            notice = {"schema": "golem.integration-hook-notice.v1", "context_state": "AVAILABLE_FOR_EXPLICIT_FETCH",
                "source": source, "scope": {"project_id": args["project_id"], "work_id": args["work_id"]},
                "sequence": status["sequence"], "resume_preflight": hint,
                "projection_digest": payload["projection_digest"], "work_record_sha256": payload["work_record_sha256"],
                "fetch": {"server": profile.value["mcp_server"], "tool": "golem_context_get", "arguments": args},
                "context_role": "READING_AID", "complete_context_delivered": False,
                "mcp_connection": "NOT_OBSERVED",
                "provider_budget": "UNKNOWN", "execution_authorized": False, "native_state_changed": False,
                "model_consumption": "NOT_OBSERVED"}
            profile.current()
            profile.transfer.current()
            result = envelope(notice)
            records.save(output / "output.json", c.encoded(result))
            records.save(output / "observation.json", c.encoded({"state": "OUTPUT_PREPARED",
                "output_sha256": c.sha(c.encoded(result)), "host_delivery": "NOT_OBSERVED",
                "complete_context_delivered": False, "native_state_changed": False}))
            return result
        except (c.IntegrationError, OSError, ValueError, KeyError, TypeError) as error:
            if isinstance(error, (KeyError, TypeError)):
                error = c.IntegrationError("HOOK_NATIVE_CONTRACT")
            result = failure(error, diagnostic)
            records.save(output / "failure.json", c.encoded(result))
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--reviewed-profile-sha256", required=True)
    parser.add_argument("--approve-hooks", action="store_true")
    args = parser.parse_args()
    try:
        profile = contract.Profile(args.profile, args.reviewed_profile_sha256, approve_hooks=args.approve_hooks)
        value = c.decode(sys.stdin.buffer.read(c.LIMIT + 1))
        result = observe(profile, value)
    except (c.IntegrationError, OSError, ValueError) as error:
        result = failure(error)
    # Exit zero means the advisory response is well formed, not that context or
    # product QA passed. Domain BLOCKED remains explicit to host and model.
    sys.stdout.buffer.write(c.encoded(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
