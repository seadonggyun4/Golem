"""Opt-in command observations and derived views; never a Work authority or QA oracle."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

from verify_agent import LIMIT, capture, digest, private_directory, save, strict_json
from verify_environment import git, source_identity
import provider_usage

SCHEMA = "golem.agent-observation.v1"
PLAN_SCHEMA = "golem.agent-command-plan.v1"
ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
ROUTES = {
    "docs": ["document-registry.md", "workflow.md"],
    "code": ["document-registry.md", "workflow.md", "execution.md"],
    "deploy": ["document-registry.md", "workflow.md", "execution.md", "approvals.md"],
}
COMMON = ["agent-session.md", "reentry.md", "completion.md"]
PROCEDURES = {
    "docs": {"mode": "documents", "checks": ["document_qa", "review", "completion"]},
    "code": {"mode": "development", "checks": ["execution_contract", "observed_qa", "review", "completion"]},
    "deploy": {"mode": "development", "checks": ["execution_contract", "observed_qa", "review",
                "scoped_host_approval", "effect_reconciliation", "completion"]},
}
PROCEDURE_ORDER = ("docs", "code", "deploy")
PROCEDURE_STEPS = {
    "documents": ("register_selection", "workflow_next_and_inputs", "author_managed_documents",
                  "document_qa_and_review", "verify_completion"),
    "development": ("register_selection", "workflow_next_and_inputs", "review_execution_contract",
                    "claim_and_prepare", "edit_and_finish", "register_qa_plan", "run_observed_qa",
                    "register_results_and_review", "verify_completion"),
}
RECOVERY = {
    "INVALID_USAGE_EVIDENCE": "Inspect the preserved usage error and raw provider output; do not aggregate invalid usage records.",
    "USAGE_DUPLICATE_CALL_ID": "Assign a unique call ID to each invocation, including retries; do not reuse an ID within a plan.",
    "USAGE_CLI_FRESH_INVOCATION_REQUIRED": "Use a fresh dedicated CLI invocation with one unique invocation ID; resumed totals cannot be attributed safely.",
    "USAGE_WORK_MISMATCH": "Match the usage Work ID to the observation scope before execution.",
    "PROCEDURE_INTENT": "Use procedure-intent.v1 with unique docs/code/deploy activities and an exact scope reference.",
    "PROCEDURE_EVIDENCE": "Inspect the preserved selection logs and scope reference; refresh scope explicitly, never replay effects.",
    "PLAN_SCHEMA": "Use schema golem.agent-command-plan.v1, task docs/code/deploy and 1..32 commands.",
    "PLAN_COMMAND": "Use unique ASCII IDs, an absolute executable, string argv and timeout 1..3600.",
    "IDENTIFIER": "Use an ASCII Work/selection ID of 1..64 letters, digits, underscore or hyphen.",
    "SYMLINK": "Select original private evidence without symlink entries; do not rewrite evidence.",
    "INTEGRITY": "Locate an intact bundle or create a new observation; retain the corrupt evidence.",
    "SCHEMA": "Use a matching tooling revision or inspect the original record; do not infer success.",
    "STREAM": "Select a recorded step and stdout.log/stderr.log from the view.",
    "WINDOW": "Use a nonnegative byte offset and a byte count in 1..65536.",
    "OUTPUT_LOCATION": "Choose a new private output directory outside the repository and Work.",
    "REPOSITORY_ROOT": "Use the Git repository root, with an existing commit, as --cwd.",
    "WORK_RECORD": "Use an intact observation containing a successful work-record step; legacy bundles require a new observation.",
}


class ObservationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(RECOVERY[code])


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode()


def identity(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def select_procedure(intent):
    """Closed decision table: declarations select a route, not permissions."""
    if (not isinstance(intent, dict) or set(intent) != {"schema", "activities", "scope"}
            or intent.get("schema") != "golem.procedure-intent.v1"):
        raise ObservationError("PROCEDURE_INTENT")
    activities, scope = intent["activities"], intent["scope"]
    if (not isinstance(activities, list) or not 1 <= len(activities) <= len(PROCEDURE_ORDER)
            or any(not isinstance(a, str) or a not in PROCEDURE_ORDER for a in activities)
            or len(set(activities)) != len(activities)
            or not isinstance(scope, dict) or set(scope) != {"document_id", "revision", "digest"}
            or not isinstance(scope["document_id"], str) or not ID.fullmatch(scope["document_id"])
            or type(scope["revision"]) is not int or not 1 <= scope["revision"] <= 4096
            or not isinstance(scope["digest"], str) or not HEX.fullmatch(scope["digest"])):
        raise ObservationError("PROCEDURE_INTENT")
    task = next(a for a in reversed(PROCEDURE_ORDER) if a in activities)
    return {"schema": "golem.procedure-route.v1", "task": task,
            "activities": [a for a in PROCEDURE_ORDER if a in activities],
            "mode": PROCEDURES[task]["mode"], "required_checks": list(PROCEDURES[task]["checks"]),
            "scope": dict(scope), "intent_sha256": identity(intent),
            "policy_sha256": identity({"order": PROCEDURE_ORDER, "rules": PROCEDURES,
                                       "steps": PROCEDURE_STEPS}),
            "execution_authorized": False, "acceptance_verified": False}


def procedure_plan(cli, work, intent, output):
    route = select_procedure(intent)
    save(output / "procedure-intent.json", encoded(intent))
    save(output / "procedure-route.json", encoded(route))
    scope = route["scope"]
    return {"schema": PLAN_SCHEMA, "task": route["task"], "commands": [
        {"id": "selection", "argv": [str(cli), "--output-mode", "full", "workflow", "select",
         str(work), scope["document_id"], str(scope["revision"]), route["mode"]], "timeout": 30}]}


def procedure_view(output):
    record, revision = load_bundle(output)
    route = select_procedure(read_json(output / "procedure-intent.json"))
    if (read_json(output / "procedure-route.json") != route or record["status"] != "RECORDED"
            or record["task"] != route["task"] or len(record["steps"]) != 1
            or record["steps"][0]["id"] != "selection" or record["steps"][0]["status"] != "EXIT_OK"):
        raise ObservationError("PROCEDURE_EVIDENCE")
    selection = read_json(output / "selection/stdout.log")
    if (not isinstance(selection, dict) or type(selection.get("schema_version")) is not int
            or selection["schema_version"] != 1 or selection.get("mode") != route["mode"]
            or selection.get("scope") != route["scope"]):
        raise ObservationError("PROCEDURE_EVIDENCE")
    steps = list(PROCEDURE_STEPS[route["mode"]])
    if route["task"] == "deploy":
        steps[-1:-1] = ["describe_exact_external_action", "await_authenticated_host_approval",
                        "dispatch_through_receipted_host", "reconcile_external_effects"]
    return {**route, "schema": "golem.procedure-proposal.v1", "status": "PROPOSED",
            "procedure": [{"action": action, "state": "NOT_EVALUATED"} for action in steps],
            "observation_revision": revision, "selection": selection,
            "selection_sha256": record["steps"][0]["logs"]["stdout.log"]["sha256"],
            "next_action": "REGISTER_SELECTION_THROUGH_EXISTING_DOCUMENT_POLICY",
            "deployment": "BLOCKED_PENDING_SCOPED_HOST_INTEGRATION" if route["task"] == "deploy" else "NOT_REQUESTED",
            "freshness": "HISTORICAL_CAPTURE_REVALIDATE_AT_REGISTRATION"}


def producer():
    root = Path(__file__).resolve().parent
    return {"python": platform.python_version(), "system": platform.system(),
            "modules": {name: digest(root / name) for name in
                        ("agent_io.py", "verify_agent.py", "verify_environment.py", "verify_runtime.py",
                         "execution_record.py", "provider_usage.py", "hosted_usage.py", "usage_pipeline.py", "billing_evidence.py", "provider_costs.py", "context_resume.py", "judgment_record.py", "revision_status.py", "remote_status.py", "github_checks.py", "github_policy.py", "status_collector.py", "evidence_contract.py", "evidence_adapters.py", "evidence_export.py")}}


def read_json(path):
    with path.open("rb") as stream:
        return strict_json(stream.read(LIMIT + 1))


def validate_plan(plan):
    if (not isinstance(plan, dict) or set(plan) != {"schema", "task", "commands"}
            or plan["schema"] != PLAN_SCHEMA or plan["task"] not in ROUTES
            or not isinstance(plan["commands"], list) or not 1 <= len(plan["commands"]) <= 32):
        raise ObservationError("PLAN_SCHEMA")
    seen, usage_ids = set(), set()
    for row in plan["commands"]:
        if (not isinstance(row, dict) or set(row) - {"id", "argv", "timeout", "usage"}
                or not {"id", "argv", "timeout"} <= set(row)
                or not isinstance(row["id"], str) or not ID.fullmatch(row["id"])
                or row["id"] in seen or not isinstance(row["argv"], list)
                or not 1 <= len(row["argv"]) <= 256
                or any(not isinstance(s, str) or "\0" in s for s in row["argv"])
                or not Path(row["argv"][0]).is_absolute()
                or type(row["timeout"]) is not int or not 1 <= row["timeout"] <= 3600):
            raise ObservationError("PLAN_COMMAND")
        seen.add(row["id"])
        if "usage" in row:
            provider_usage.binding(row["usage"])
            for request in row["usage"]["request_ids"]:
                key = (row["usage"]["provider"], row["usage"]["account_id"], request)
                if key in usage_ids:
                    raise ObservationError("USAGE_DUPLICATE_CALL_ID")
                usage_ids.add(key)
            if row["usage"]["provider"] in ("codex.exec.v1", "claude.code.v1"):
                if len(row["usage"]["request_ids"]) != 1 or any(
                        arg in ("resume", "--resume", "-r", "--continue", "--fork-session")
                        or (arg == "-c" and row["usage"]["provider"] == "claude.code.v1")
                        or arg.startswith(("--resume=", "--continue=")) for arg in row["argv"][1:]):
                    raise ObservationError("USAGE_CLI_FRESH_INVOCATION_REQUIRED")
    return plan


def observe_plan(cli, work, work_id, selection, output, task):
    """One locked Work record, followed by independent next/completion queries."""
    if not ID.fullmatch(work_id) or not ID.fullmatch(selection):
        raise ObservationError("IDENTIFIER")
    commands = []
    for name, group, request in (
        ("work-record", "work", {"schema_version": 1, "work_id": work_id,
                                 "document_head": "", "agent_head": "", "byte_budget": LIMIT - 1}),
        ("next", "session", {"schema_version": 1, "operation": "next", "work_id": work_id}),
        ("completion", "completion", {"schema_version": 1, "operation": "resume", "selection_id": selection}),
    ):
        path = output / (name + "-request.json")
        save(path, encoded(request))
        commands.append({"id": name, "argv": [str(cli), "--output-mode", "full", group,
                         "record" if name == "work-record" else "call", str(work), str(path)], "timeout": 30})
    return {"schema": PLAN_SCHEMA, "task": task, "commands": commands}


def file_inventory(output):
    paths = list(output.rglob("*"))
    if output.is_symlink() or any(p.is_symlink() for p in paths):
        raise ObservationError("SYMLINK")
    return {p.relative_to(output).as_posix(): digest(p) for p in paths
            if p.is_file() and p != output / "manifest.json"}


def history_plan(cli, work, work_id, output, task, scope, since=None, revision=None, limit=64):
    """Pin the prior captured page; the engine independently verifies its prefixes."""
    if not ID.fullmatch(work_id):
        raise ObservationError("IDENTIFIER")
    if type(limit) is not int or not 1 <= limit <= 256:
        raise ValueError("history limit must be 1..256 per stream")
    cursor, baseline = None, "BASELINE_REQUIRED"
    if since is not None or revision is not None:
        cursor, baseline = {"invalid_baseline": True}, "BASELINE_UNAVAILABLE_OR_INCOMPATIBLE"
        try:
            if since is None or not isinstance(revision, str) or not HEX.fullmatch(revision):
                raise ValueError("pin the baseline observation revision")
            previous, key = load_bundle(since)
            if key != revision or previous["scope"] != scope or previous["status"] != "RECORDED":
                raise ValueError("baseline scope, revision or outcome mismatch")
            step = next(s for s in previous["steps"] if s["id"] == "history")
            if step["status"] != "EXIT_OK":
                raise ValueError("failed page")
            page = read_json(since / "history/stdout.log")
            if (not isinstance(page, dict) or type(page.get("schema_version")) is not int or page["schema_version"] != 2
                    or page.get("work_id") != work_id or not isinstance(page.get("cursor"), dict)):
                raise ValueError("unknown page")
            cursor, baseline = page["cursor"], "HASH_PINNED_CAPTURE"
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            pass
    save(output / "baseline.json", encoded({"status": baseline, "revision": revision,
                                           "path": str(since) if since else None}))
    request = output / "history-request.json"
    save(request, encoded({"schema_version": 2, "work_id": work_id, "limit": limit, "cursor": cursor}))
    return {"schema": PLAN_SCHEMA, "task": task, "commands": [
        {"id": "history", "argv": [str(cli), "--output-mode", "full", "work", "history",
                                     str(work), str(request)], "timeout": 30}]}


def load_bundle(output):
    manifest = read_json(output / "manifest.json")
    if (manifest.get("schema") != "golem.agent-observation-manifest.v1"
            or manifest.get("files") != file_inventory(output)):
        raise ObservationError("INTEGRITY")
    record = read_json(output / "record.json")
    if record.get("schema") != SCHEMA or not isinstance(record.get("steps"), list):
        raise ObservationError("SCHEMA")
    seen = set()
    for step in record["steps"]:
        if (not isinstance(step, dict) or not isinstance(step.get("id"), str)
                or not ID.fullmatch(step["id"]) or step["id"] in seen
                or not isinstance(step.get("logs"), dict)
                or set(step["logs"]) - {"stdout.log", "stderr.log", "usage.log"}):
            raise ObservationError("SCHEMA")
        seen.add(step["id"])
        for name, meta in step["logs"].items():
            path = output / step["id"] / name
            if meta != {"sha256": digest(path), "bytes": path.stat().st_size}:
                raise ObservationError("INTEGRITY")
    return record, digest(output / "record.json")


def run(plan, cwd, output, scope=None):
    validate_plan(plan)
    if scope and scope.get("work_id"):
        for command in plan["commands"]:
            if "usage" in command and command["usage"]["work_id"] != scope["work_id"]:
                raise ObservationError("USAGE_WORK_MISMATCH")
    save(output / "plan.json", encoded(plan))
    record = {"schema": SCHEMA, "started_at": datetime.now(timezone.utc).isoformat(),
              "cwd": str(cwd), "task": plan["task"], "scope": scope,
              "plan_sha256": identity(plan), "status": "INCOMPLETE", "steps": [],
              "producer": producer(),
              "execution_authorized": False, "product_acceptance": False,
              "token_usage": None, "cost": None}
    save(output / "started.json", encoded(record))
    try:
        if Path(git(cwd, "rev-parse", "--show-toplevel").decode().strip()).resolve() != cwd:
            raise ObservationError("REPOSITORY_ROOT")
        before = source_identity(cwd)
        save(output / "source-before.json", encoded(before))
        record["source_before"] = {k: v for k, v in before.items() if k != "files"}
        stopped = False
        for command in plan["commands"]:
            step = {"id": command["id"], "status": "NOT_RUN", "logs": {}}
            if "usage" in command:
                step["usage"] = provider_usage.collect(output / "missing-usage", command["usage"])
            record["steps"].append(step)
            if stopped:
                continue
            directory = private_directory(output / command["id"])
            executable = Path(command["argv"][0])
            try:
                step["executable_sha256"] = digest(executable)
                if "usage" in command:
                    import execution_record
                    environment = {k: v for k, v in os.environ.items()
                                   if not k.startswith("GIT_") and k not in ("PYTHONPATH", "PYTHONHOME")}
                    environment["GOLEM_USAGE_STREAM"] = str(directory / "usage.log")
                    result = execution_record.capture(
                        command["argv"], directory, command["timeout"], cwd,
                        env=environment, extra_logs=(() if command["usage"]["provider"] in
                            ("codex.exec.v1", "claude.code.v1") else ("usage.log",)))
                else:
                    result = capture(command["argv"], directory, command["timeout"], cwd)
                step.update(result)
                step["executable_unchanged"] = digest(executable) == step["executable_sha256"]
                step["status"] = ("EXIT_OK" if result["returncode"] == 0 and result["reason"] == "EXIT"
                                  and step["executable_unchanged"] else "FAILED")
            except (OSError, subprocess.SubprocessError) as error:
                step.update(status="FAILED", reason="LAUNCH_OR_CAPTURE_ERROR", returncode=None,
                            error_type=type(error).__name__, errno=getattr(error, "errno", None))
            if "usage" in command:
                try:
                    if command["usage"]["provider"] in ("codex.exec.v1", "claude.code.v1"):
                        step["cli_usage"] = provider_usage.collect_cli(
                            directory / "stdout.log", directory / "usage.log", command["usage"])
                    step["usage"] = provider_usage.collect(directory / "usage.log", command["usage"])
                except (ValueError, KeyError, TypeError, OSError) as error:
                    step.update(status="FAILED", usage_error=str(error)[:128])
                    step["usage"] = provider_usage.collect(directory / "missing-usage", command["usage"])
            step["logs"] = {p.name: {"sha256": digest(p), "bytes": p.stat().st_size}
                            for p in directory.iterdir() if p.is_file()}
            stopped = step["status"] != "EXIT_OK"
        after = source_identity(cwd)
        save(output / "source-after.json", encoded(after))
        record["source_after"] = {k: v for k, v in after.items() if k != "files"}
        record["source_changed"] = before != after
        record["status"] = "FAILED" if stopped else "RECORDED"
        if producer() != record["producer"]:
            record.update(status="INCOMPLETE", diagnostic="RECORDER_CHANGED")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        record.update(status="INCOMPLETE", error_type=type(error).__name__,
                      diagnostic=getattr(error, "code", "SOURCE_OR_CAPTURE_FAILURE"))
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    try:
        record["usage_accounting"] = provider_usage.totals(
            [step["usage"] for step in record["steps"] if "usage" in step])
    except ValueError as error:
        record.update(status="FAILED", diagnostic=str(error))
        record["usage_accounting"] = {"token_usage": None, "cost": None,
                                      "usage_complete": False, "cost_complete": False,
                                      "diagnostic": str(error)}
    record["token_usage"] = record["usage_accounting"]["token_usage"]
    record["cost"] = record["usage_accounting"]["cost"]
    save(output / "record.json", encoded(record))
    save(output / "manifest.json", encoded({"schema": "golem.agent-observation-manifest.v1",
                                           "files": file_inventory(output)}))
    return record


def comparable(record):
    # Generated request paths differ per observation; explicit scope binds their values.
    return (record["cwd"], record["task"], record["scope"] or record["plan_sha256"],
            record.get("source_after"), record.get("producer"))


def fingerprint(step):
    return {k: v for k, v in step.items() if k not in ("elapsed_seconds", "record_path")}


def observed_fields(path):
    """Display bounded machine fields, never prose summaries or instructions."""
    try:
        data = read_json(path)
        if isinstance(data, dict) and type(data.get("schema_version")) is int and data["schema_version"] == 2:
            if (data.get("mode") in ("FULL", "DELTA") and isinstance(data.get("cursor"), dict)
                    and isinstance(data.get("events"), list) and isinstance(data.get("fallback"), str)
                    and type(data.get("has_more")) is bool
                    and all(type(data.get(k)) is int for k in ("document_total", "agent_total"))):
                return {"projection": "LIVE_HISTORY_PAGE", "fields": {
                    k: data[k] for k in ("mode", "fallback", "has_more", "document_total", "agent_total")},
                    "returned_events": len(data["events"]), "raw_required": True}
        if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            return {"projection": "UNSUPPORTED_READ_RAW"}
        if data.get("schema") == "golem.work-record.v1":
            validate_work_record(data)
            return {"projection": "CONSOLIDATED_WORK_RECORD", "fields": {
                "document_head": data["document_head"], "agent_head": data["agent_head"],
                "sequence": data["status"]["sequence"], "lease_live": data["status"]["lease_live"]},
                "counts": {k: len(data[k]) for k in ("assessments", "documents", "journal")},
                "raw_required": True}
        keys = {"action", "reason", "sequence", "document_generation", "lease_live",
                "acceptance_verified", "execution_authorized", "remaining_attempts",
                "remaining_events", "remaining_document_revisions", "receipt_digest"}
        fields = {k: v for k, v in data.items() if k in keys and
                  (type(v) in (int, bool) or isinstance(v, str) and len(v) <= 256)}
        return {"projection": "PARTIAL_OBSERVATION", "fields": fields,
                "omitted_fields": sorted(set(data) - set(fields))}
    except (OSError, ValueError):
        return {"projection": "UNSUPPORTED_READ_RAW"}


def view(output, since=None, revision=None):
    record, key = load_bundle(output)
    mode, fallback, baseline = "FULL", None, {}
    if since is not None or revision is not None:
        try:
            if since is None or not isinstance(revision, str) or not HEX.fullmatch(revision):
                raise ValueError("baseline revision required")
            previous, old_key = load_bundle(since)
            if old_key != revision or comparable(previous) != comparable(record):
                raise ValueError("baseline identity mismatch")
            if previous["status"] != "RECORDED" or record["status"] != "RECORDED":
                raise ValueError("incomplete or failed observations require full review")
            baseline = {step["id"]: fingerprint(step) for step in previous["steps"]}
            mode = "DELTA"
        except (OSError, ValueError, KeyError, TypeError):
            fallback = "BASELINE_UNAVAILABLE_OR_INCOMPATIBLE"
    steps = []
    for step in record["steps"]:
        if mode == "DELTA" and baseline.get(step["id"]) == fingerprint(step):
            continue
        row = {"id": step["id"], "status": step["status"], "returncode": step.get("returncode"),
               "reason": step.get("reason"),
               "evidence": [{"path": step["id"] + "/" + name, "bytes": meta["bytes"]}
                            for name, meta in step["logs"].items()]}
        if "error_type" in step:
            row.update(error_type=step["error_type"], errno=step.get("errno"))
        if "cli_usage" in step:
            row["cli_usage"] = step["cli_usage"]
        if "usage_error" in step:
            row["usage_error"] = step["usage_error"]
        if record["scope"] and "stdout.log" in step["logs"]:
            row["observed"] = observed_fields(output / step["id"] / "stdout.log")
        # Keep bounded diagnostic data even on exit zero; warnings must remain visible.
        path = output / step["id"] / "stderr.log"
        if path.is_file() and path.stat().st_size:
            with path.open("rb") as stream:
                head = stream.read(256)
                stream.seek(max(256, path.stat().st_size - 256))
                tail = stream.read(256)
            row["stderr_preview"] = (head + tail).decode("utf-8", errors="replace")
            row["stderr_omitted_bytes"] = max(0, path.stat().st_size - len(head) - len(tail))
        steps.append(row)
    result = {"schema": "golem.agent-view.v1", "status": record["status"], "mode": mode,
              "fallback": fallback, "revision": key, "baseline_revision": revision if mode == "DELTA" else None,
              "diagnostic": record.get("diagnostic"),
              "steps": steps, "unchanged_steps": len(record["steps"]) - len(steps),
              "next_action": "INSPECT_FAILURE" if record["status"] != "RECORDED" else "READ_REQUIRED_OUTPUTS",
              "raw_required_before_effects": True, "execution_authorized": False,
              "product_acceptance": False, "source_changed": record.get("source_changed"),
              "raw_bytes": sum(log["bytes"] for step in record["steps"] for log in step["logs"].values()),
              "token_usage": record.get("token_usage"), "cost": record.get("cost"),
              "usage_accounting": record.get("usage_accounting")}
    return result


def read_raw(output, step_id, stream, offset, count):
    record, _ = load_bundle(output)
    if not any(s["id"] == step_id and stream in s["logs"] for s in record["steps"]):
        raise ObservationError("STREAM")
    if offset < 0 or not 1 <= count <= 65536:
        raise ObservationError("WINDOW")
    path = output / step_id / stream
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(count)
    return {"step": step_id, "stream": stream, "offset": offset, "bytes": len(data),
            "total_bytes": path.stat().st_size, "next_offset": offset + len(data),
            "eof": offset + len(data) >= path.stat().st_size,
            "text": data.decode("utf-8", errors="replace"), "sha256": digest(path)}


def report(output):
    record, key = load_bundle(output)
    lines = ["# Command Observation", "", f"- Evidence: `{key}`",
             f"- Recorded outcome: {record['status']}",
             "- Observation only: no QA PASS, DONE, or execution authority asserted.", ""]
    for step in record["steps"]:
        lines.append(f"- {step['id']}: {step['status']}; exit={step.get('returncode')}; reason={step.get('reason')}")
    if record["scope"] and any(s["id"] == "work-record" and s["status"] == "EXIT_OK"
                               for s in record["steps"]):
        value, record_digest = consolidated_value(output, record)
        lines.extend(["", "## Work Record", "",
                      f"- Record SHA256: `{record_digest}`",
                      f"- Document head: `{value['document_head']}`",
                      f"- Agent head: `{value['agent_head']}`",
                      "- Status and journal describe this capture, not current execution permission."])
        for section in ("work_specification", "assessments", "documents", "status", "journal"):
            # JSON quotes all source prose; never interpolate it as Markdown instructions.
            lines.extend(["", f"## {section.title()}", "",
                          "    " + encoded(value[section]).decode().rstrip(), ""])
    lines.extend(["", "Inspect original stdout/stderr and current engine state before effects.",
                  "Usage accounting: " + json.dumps(record.get("usage_accounting"), sort_keys=True),
                  "Provider reports use explicit caller attribution; semantic correctness is not inferred.", ""])
    return "\n".join(lines)


def validate_work_record(value):
    """Check projection links without reinterpreting native judgments or journal order."""
    if (not isinstance(value, dict) or value.get("schema") != "golem.work-record.v1"
            or type(value.get("schema_version")) is not int or value["schema_version"] != 1
            or value.get("derived_only") is not True
            or value.get("execution_authorized") is not False or value.get("acceptance_verified") is not False
            or any(not isinstance(value.get(k), str) or not HEX.fullmatch(value[k])
                   for k in ("document_head", "agent_head"))
            or not isinstance(value.get("work_specification"), dict)
            or not isinstance(value.get("assessments"), dict)
            or not isinstance(value.get("documents"), list)
            or not isinstance(value.get("journal"), list)
            or not isinstance(value.get("status"), dict)
            or type(value["status"].get("sequence")) is not int
            or type(value["status"].get("lease_live")) is not bool):
        raise ObservationError("WORK_RECORD")
    referenced = set()
    for document in value["documents"]:
        if not isinstance(document, dict) or not isinstance(document.get("metadata"), dict):
            raise ObservationError("WORK_RECORD")
        if "assessment" in document["metadata"]:
            raise ObservationError("WORK_RECORD")
        ref = document.get("assessment_ref")
        if ref is not None:
            if not isinstance(ref, str) or not HEX.fullmatch(ref) or ref not in value["assessments"]:
                raise ObservationError("WORK_RECORD")
            referenced.add(ref)
    if referenced != set(value["assessments"]):
        raise ObservationError("WORK_RECORD")
    return value


def consolidated_value(output, record):
    """Use only after load_bundle has verified this observation's inventory."""
    step = next((s for s in record["steps"] if s["id"] == "work-record"), None)
    if (step is None or step["status"] != "EXIT_OK" or "stdout.log" not in step["logs"]):
        raise ObservationError("WORK_RECORD")
    try:
        value = validate_work_record(read_json(output / "work-record/stdout.log"))
    except ValueError as error:
        raise ObservationError("WORK_RECORD") from error
    return value, step["logs"]["stdout.log"]["sha256"]


def work_record(output, section="all"):
    record, revision = load_bundle(output)
    value, record_digest = consolidated_value(output, record)
    if section not in ("all", "assessments", "documents", "status", "journal"):
        raise ObservationError("WORK_RECORD")
    return {"schema": "golem.work-record-view.v1", "observation_revision": revision,
            "sha256": record_digest, "section": section,
            "value": value if section == "all" else value[section],
            "document_head": value["document_head"], "agent_head": value["agent_head"],
            "execution_authorized": False, "acceptance_verified": False,
            "freshness": "HISTORICAL_CAPTURE_NOT_LIVE_STATE"}


def measure(output, since=None, revision=None):
    record, key = load_bundle(output)
    rendered = view(output, since, revision)
    raw = rendered["raw_bytes"]
    size = len(encoded(rendered))
    return {"schema": "golem.agent-io-measurement.v1", "revision": key,
            "renderer_sha256": digest(Path(__file__).resolve()),
            "mode": rendered["mode"], "raw_bytes": raw, "view_bytes": size,
            "byte_difference": raw - size, "view_to_raw_ratio": size / raw if raw else None,
            "commands_planned": len(record["steps"]),
            "commands_run": sum(s["status"] != "NOT_RUN" for s in record["steps"]),
            "process_seconds": sum(s.get("elapsed_seconds", 0) for s in record["steps"]),
            "token_usage": record.get("token_usage"), "cost": record.get("cost"),
            "usage_accounting": record.get("usage_accounting"), "agent_success": None,
            "basis": "Recorded streams versus serialized view only; excludes subsequent raw reads and prompts."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("judgment-write")
    p.add_argument("bundle", type=Path)
    p.add_argument("--project-id", required=True)
    p.add_argument("--work-id", required=True)
    p.add_argument("--delta", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--since", type=Path)
    p.add_argument("--revision")
    p = commands.add_parser("judgment-view")
    p.add_argument("bundle", type=Path)
    p = commands.add_parser("judgment-facts")
    p.add_argument("bundle", type=Path)
    p.add_argument("--project-id", required=True)
    p.add_argument("--work-id", required=True)
    p = commands.add_parser("usage-total")
    p.add_argument("bundles", nargs="+", type=Path)
    for name in ("run", "observe", "observe-history", "procedure"):
        p = commands.add_parser(name)
        p.add_argument("--cwd", type=Path, required=True, help="Git repository root")
        p.add_argument("--output", type=Path, required=True, help="new private directory outside repository/Work")
        if name == "run":
            p.add_argument("--plan", type=Path, required=True, help="explicitly approved argv; not authorization")
        else:
            p.add_argument("--cli", type=Path, required=True)
            p.add_argument("--work", type=Path, required=True)
            if name == "procedure":
                p.add_argument("--intent", type=Path, required=True)
            else:
                p.add_argument("--work-id", required=True)
            if name == "observe":
                p.add_argument("--selection", required=True)
            elif name == "observe-history":
                p.add_argument("--since", type=Path)
                p.add_argument("--revision")
                p.add_argument("--limit", type=int, choices=range(1, 257), default=64, metavar="1..256")
            if name != "procedure":
                p.add_argument("--task", choices=ROUTES, default="code")
    for name in ("view", "raw", "report", "measure", "record-view", "procedure-view"):
        p = commands.add_parser(name)
        p.add_argument("bundle", type=Path)
        if name == "record-view":
            p.add_argument("--section", choices=("all", "assessments", "documents", "status", "journal"), default="all")
        if name in ("view", "measure"):
            p.add_argument("--since", type=Path)
            p.add_argument("--revision")
        if name == "raw":
            p.add_argument("--step", required=True)
            p.add_argument("--stream", choices=("stdout.log", "stderr.log"), default="stdout.log")
            p.add_argument("--offset", type=int, default=0)
            p.add_argument("--bytes", type=int, default=4096)
    p = commands.add_parser("guide")
    p.add_argument("task", choices=ROUTES)
    args = parser.parse_args(argv)
    try:
        if args.command.startswith("judgment-"):
            import judgment_record as judgments
            if args.command == "judgment-view":
                result = judgments.view(args.bundle)
            else:
                work = {"project_id": args.project_id, "work_id": args.work_id}
                judgments.binding(work)
                if args.command == "judgment-facts":
                    observation = judgments.facts(args.bundle, work)
                    result = {"schema": "golem.judgment-facts.v1", "binding": work,
                              "observation_revision": observation["observation_revision"],
                              "facts": judgments.fact_ids(observation),
                              "attribution_basis": observation["attribution_basis"],
                              "authenticity_verified": False, "product_acceptance": False}
                else:
                    result = judgments.write(args.bundle, work, read_json(args.delta),
                                             args.output, args.since, args.revision)
        elif args.command == "usage-total":
            usage = []
            for path in args.bundles:
                if (path / "usage.json").is_file():
                    from billing_evidence import load_records
                    records, _ = load_records([path])
                    usage.extend(records)
                    continue
                record, _ = load_bundle(path)
                if any(step.get("usage_error") for step in record["steps"]) or record.get("diagnostic") == "USAGE_CONFLICT":
                    raise ObservationError("INVALID_USAGE_EVIDENCE")
                usage.extend(step["usage"] for step in record["steps"] if "usage" in step)
            # Union first so a request cannot be assigned to different Works.
            aggregate = provider_usage.totals(usage)
            def work_key(call):
                a = call["attribution"]
                return (a["project_id"], a["work_id"])
            works = sorted({work_key(call) for item in usage for call in item["calls"]})
            result = {"schema": "golem.work-usage-totals.v1", "aggregate": aggregate,
                      "works": [{"project_id": work[0], "work_id": work[1],
                                 "totals": provider_usage.totals([
                          {"calls": [call for call in item["calls"] if work_key(call) == work]}
                          for item in usage])} for work in works]}
        elif args.command == "guide":
            result = {"task": args.task, "read_on_demand": ROUTES[args.task] + COMMON,
                      "procedure_entrypoint": "agent_io.py procedure --intent INTENT --cli CLI --work WORK --cwd REPOSITORY --output NEW_BUNDLE",
                      "stage_selection": "Use workflow policy; task labels never waive required gates.",
                      "execution_authorized": False}
        elif args.command in ("run", "observe", "observe-history", "procedure"):
            cwd = args.cwd.resolve(strict=True)
            output = args.output.absolute()
            if output == cwd or cwd in output.resolve().parents:
                raise ObservationError("OUTPUT_LOCATION")
            scope = None
            if args.command in ("observe", "observe-history", "procedure"):
                work = args.work.resolve(strict=True)
                cli = args.cli.resolve(strict=True)
                if output == work or work in output.resolve().parents:
                    raise ObservationError("OUTPUT_LOCATION")
                if args.command == "procedure":
                    intent = read_json(args.intent)
                    route = select_procedure(intent)
                    scope = {"cli": str(cli), "work": str(work), "query": "procedure-v1",
                             "intent_sha256": route["intent_sha256"]}
                elif not ID.fullmatch(args.work_id) or (args.command == "observe" and not ID.fullmatch(args.selection)):
                    raise ObservationError("IDENTIFIER")
                else:
                    scope = {"cli": str(cli), "work": str(work), "work_id": args.work_id}
                    scope.update({"selection": args.selection} if args.command == "observe" else {"query": "history-v2"})
            else:
                plan = validate_plan(read_json(args.plan))
            output = private_directory(output)
            if args.command == "observe":
                plan = observe_plan(cli, work, args.work_id, args.selection, output, args.task)
            elif args.command == "observe-history":
                plan = history_plan(cli, work, args.work_id, output, args.task, scope,
                                    args.since, args.revision, args.limit)
            elif args.command == "procedure":
                plan = procedure_plan(cli, work, intent, output)
            run(plan, cwd, output, scope)
            result = procedure_view(output) if args.command == "procedure" else view(output)
        elif args.command == "view":
            result = view(args.bundle, args.since, args.revision)
        elif args.command == "measure":
            result = measure(args.bundle, args.since, args.revision)
        elif args.command == "raw":
            result = read_raw(args.bundle, args.step, args.stream, args.offset, args.bytes)
        elif args.command == "record-view":
            result = work_record(args.bundle, args.section)
        elif args.command == "procedure-view":
            result = procedure_view(args.bundle)
        else:
            print(report(args.bundle), end="")
            return 0
        sys.stdout.buffer.write(encoded(result))
        return 1 if result.get("status") in ("FAILED", "INCOMPLETE") else 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        code = getattr(error, "code", "INVALID_OR_UNAVAILABLE_EVIDENCE")
        sys.stderr.buffer.write(encoded({"schema": "golem.agent-io-error.v1", "code": code,
            "error_type": type(error).__name__, "errno": getattr(error, "errno", None),
            "detail": str(error) if code == "JUDGMENT_CONTRACT" else None,
            "next_action": RECOVERY.get(code, "Inspect arguments and private evidence; do not retry effects automatically."),
            "execution_authorized": False}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
