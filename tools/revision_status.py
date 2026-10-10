"""Revision-scoped status projection; never a replacement completion predicate."""
import argparse
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import agent_io as io
import execution_record as records
import evidence_contract as ec
from evidence_adapters import process_assessment
from judgment_record import binding, require, validate_binding

SCHEMA = "golem.revision-status-index.v1"
CHANNELS = ("e2e", "local_qa", "remote_ci", "completion", "deployment")
ADAPTERS = {"command.v1": {"e2e", "local_qa"}, "junit.v1": {"e2e", "local_qa"},
            "github-run.v1": {"remote_ci"}, "github-deployment.v1": {"deployment"},
            "native-completion.v1": {"completion"}}
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")


def validate(index):
    require(isinstance(index, dict) and set(index) == {"schema", "binding", "repository", "entries"}
            and index["schema"] == SCHEMA, "Invalid status index")
    binding(index["binding"])
    require(isinstance(index["repository"], str) and REPOSITORY.fullmatch(index["repository"]),
            "Explicit GitHub repository identity required")
    require(all(part not in (".", "..") for part in index["repository"].split("/")),
            "Invalid repository path components")
    require(isinstance(index["entries"], list) and len(index["entries"]) <= 128, "Too many status entries")
    seen = set()
    for entry in index["entries"]:
        require(isinstance(entry, dict) and set(entry) == {
            "id", "channel", "adapter", "bundle", "revision", "step", "scope"}, "Invalid status entry")
        require(isinstance(entry["id"], str) and io.ID.fullmatch(entry["id"])
                and entry["id"] not in seen, "Unique evidence IDs required")
        seen.add(entry["id"])
        require(isinstance(entry["adapter"], str) and entry["adapter"] in ADAPTERS
                and isinstance(entry["channel"], str)
                and entry["channel"] in ADAPTERS[entry["adapter"]], "Unsupported channel/adapter")
        require(isinstance(entry["revision"], str) and io.HEX.fullmatch(entry["revision"])
                and isinstance(entry["bundle"], str) and Path(entry["bundle"]).is_absolute()
                and isinstance(entry["step"], str) and io.ID.fullmatch(entry["step"])
                and isinstance(entry["scope"], str) and 0 < len(entry["scope"]) <= 128,
                "Pin the evidence revision, step and exact suite/workflow/environment/selection scope")
    return index


def target_source(cwd, repository):
    cwd = cwd.resolve(strict=True)
    require(Path(records.git(cwd, "rev-parse", "--show-toplevel").decode().strip()).resolve() == cwd,
            "Repository root required")
    origin = records.git(cwd, "remote", "get-url", "origin").decode().strip()
    allowed = {f"https://github.com/{repository}", f"https://github.com/{repository}.git",
               f"git@github.com:{repository}.git", f"ssh://git@github.com/{repository}.git"}
    require(origin in allowed, "Index repository does not match origin")
    return {k: v for k, v in records.source_identity(cwd).items() if k != "files"}


def source_relation(record, target):
    before, after = record.get("source_before"), record.get("source_after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return "UNBOUND"
    if before != after or record.get("source_changed") is not False:
        return "CHANGED_DURING_EXECUTION"
    if any(after.get(k) != target.get(k) for k in ("commit", "tree_sha256", "dirty")):
        return "STALE"
    return "CURRENT"


def remote_relation(sha, target):
    require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha), "Invalid remote commit")
    if sha != target["commit"]:
        return "STALE"
    return "COMMIT_ONLY_DIRTY_SOURCE" if target["dirty"] else "CURRENT"


def github_run(data, repository, scope):
    require(isinstance(data, dict) and isinstance(data.get("repository"), dict)
            and data["repository"].get("full_name") == repository
            and type(data.get("workflow_id")) is int and data["workflow_id"] > 0
            and str(data["workflow_id"]) == scope and type(data.get("id")) is int
            and data["id"] > 0 and type(data.get("run_attempt")) is int and data["run_attempt"] > 0,
            "GitHub run repository/workflow identity mismatch")
    require(data.get("html_url") == f"https://github.com/{repository}/actions/runs/{data['id']}",
            "GitHub run URL mismatch")
    status = data.get("status")
    conclusion = data.get("conclusion")
    if status != "completed":
        require(status in ("queued", "in_progress", "waiting", "pending", "requested"), "Unknown run state")
        require(conclusion is None, "Nonterminal run has conclusion")
        state = "PENDING"
    else:
        mapping = {"success": "PASS", "failure": "FAIL", "timed_out": "FAIL",
                   "action_required": "BLOCKED", "cancelled": "CANCELLED", "skipped": "SKIPPED",
                   "neutral": "NEUTRAL", "stale": "STALE_RESULT", "startup_failure": "FAIL"}
        require(conclusion in mapping, "Unknown run conclusion")
        state = mapping[conclusion]
    return state, data["head_sha"], {"run_id": data["id"], "attempt": data["run_attempt"],
                                     "url": data["html_url"]}


def github_deployment(data, repository, scope):
    require(isinstance(data, dict) and set(data) == {"deployment", "status"}, "Deployment/status pair required")
    deployment, status = data["deployment"], data["status"]
    require(isinstance(deployment, dict) and isinstance(status, dict)
            and type(deployment.get("id")) is int and deployment["id"] > 0
            and type(status.get("id")) is int and status["id"] > 0
            and deployment.get("environment") == scope and status.get("environment") == scope,
            "Deployment environment mismatch")
    url = f"https://api.github.com/repos/{repository}/deployments/{deployment['id']}"
    require(deployment.get("url") == url and status.get("deployment_url") == url
            and status.get("url") == f"{url}/statuses/{status['id']}", "Deployment/status identity mismatch")
    mapping = {"success": "PASS", "failure": "FAIL", "error": "FAIL", "inactive": "INACTIVE",
               "queued": "PENDING", "pending": "PENDING", "in_progress": "PENDING"}
    require(status.get("state") in mapping, "Unknown deployment state")
    return mapping[status["state"]], deployment["sha"], {
        "deployment_id": deployment["id"], "status_id": status["id"], "environment": scope,
        "url": status["url"], "serving_currently_verified": False}


def junit(data):
    text = data.decode("utf-8-sig")
    require(len(data) <= io.LIMIT and "<!DOCTYPE" not in text and "<!ENTITY" not in text,
            "Unsafe or oversized JUnit")
    root = ET.fromstring(text)
    require(root.tag in ("testsuites", "testsuite"), "Unsupported JUnit root")
    cases = list(root.iter("testcase"))
    require(len(cases) <= 100000, "JUnit case limit exceeded")
    counts = {"tests": len(cases), "failures": sum(c.find("failure") is not None for c in cases),
              "errors": sum(c.find("error") is not None for c in cases),
              "skipped": sum(c.find("skipped") is not None for c in cases)}
    # Reported counters cannot hide missing cases or failing descendants.
    for suite in root.iter():
        if suite.tag not in ("testsuites", "testsuite"):
            continue
        descendants = list(suite.iter("testcase"))
        expected = {"tests": len(descendants),
                    "failures": sum(c.find("failure") is not None for c in descendants),
                    "errors": sum(c.find("error") is not None for c in descendants),
                    "skipped": sum(c.find("skipped") is not None for c in descendants)}
        for key, value in expected.items():
            require(key not in suite.attrib or suite.attrib[key] == str(value), "Contradictory JUnit counters")
    state = "FAIL" if counts["failures"] or counts["errors"] else (
        "NOT_RUN" if not cases else "PARTIAL" if counts["skipped"] else "PASS")
    return state, counts


def native_completion(data, selection):
    require(isinstance(data, dict) and type(data.get("schema_version")) is int
            and data["schema_version"] == 1 and data.get("execution_authorized") is False
            and isinstance(data.get("selection"), dict)
            and data["selection"].get("document_id") == selection
            and isinstance(data.get("action"), str), "Invalid native completion response")
    done = data["action"] == "DONE"
    require(data.get("acceptance_verified") is done, "Inconsistent native completion response")
    details = {"action": data["action"], "scope": data.get("scope"),
               "receipt_digest": data.get("receipt_digest")}
    if done:
        completion = data.get("completion")
        require(isinstance(completion, dict) and isinstance(completion.get("record"), dict),
                "Missing completion record")
        root = completion["record"].get("evidence_root")
        require(isinstance(root, str) and io.HEX.fullmatch(root)
                and isinstance(details["receipt_digest"], str) and io.HEX.fullmatch(details["receipt_digest"]),
                "Missing durable completion identity")
        details["evidence_root"] = root
    return "PASS" if done else "BLOCKED", details


def evidence(entry, index, target):
    verification = ec.assessment(entry["revision"], "OBSERVATION_RECORD", index["binding"])
    parser_scope, parser_method = "OBSERVATION_ENVELOPE", io.SCHEMA
    result = {"id": entry["id"], "channel": entry["channel"], "scope": entry["scope"],
              "revision": entry["revision"], "status": "INVALID", "source_relation": "UNBOUND",
              "freshness": "HISTORICAL_CAPTURE", "authenticity_verified": False,
              "remote_latest_verified": False, "bundle": entry["bundle"], "verification": verification}
    try:
        bundle = Path(entry["bundle"])
        record, revision = io.load_bundle(bundle)
        if revision != entry["revision"]:
            ec.set_check(verification, "integrity", "MISMATCH", "EXPECTED_OBSERVATION_REVISION",
                         "SHA256_PINNED_RECORD", refs=[entry["revision"], revision])
        require(revision == entry["revision"], "Observation revision mismatch")
        ec.set_check(verification, "integrity", "MATCH", "OBSERVATION_BYTES_AND_INVENTORY",
                     "SHA256_PINNED_RECORD", refs=[revision])
        validate_binding(record, index["binding"])
        result["attribution_basis"] = "RECORDED_SCOPE" if (record.get("scope") or {}).get("work_id") else "DECLARED_INDEX_BINDING"
        plan = io.validate_plan(io.read_json(bundle / "plan.json"))
        require(io.identity(plan) == record["plan_sha256"], "Command identity mismatch")
        step = next(s for s in record["steps"] if s["id"] == entry["step"])
        verification = process_assessment(record, revision, step, index["binding"])
        result["verification"] = verification
        parser_scope = "RECORDER_ENVELOPE_NOT_STDOUT_CONTENT"
        result.update(source_relation=source_relation(record, target),
                      captured_at=record.get("finished_at"),
                      process={k: step.get(k) for k in ("returncode", "reason", "status")})
        if record["status"] == "INCOMPLETE":
            result.update(status="INCOMPLETE_CAPTURE", source_relation="UNBOUND")
            return result
        if step["status"] == "NOT_RUN":
            result["status"] = "NOT_RUN"
            return result
        if (step["status"] != "EXIT_OK" or step.get("reason") != "EXIT"
                or step.get("returncode") != 0 or step.get("executable_unchanged") is not True):
            result["status"] = "PROCESS_FAILED"
            return result
        adapter = entry["adapter"]
        if adapter != "command.v1":
            parser_scope, parser_method = "DOMAIN_RESULT_SHAPE_NOT_CONTENT_TRUTH", adapter
        result["scope_basis"] = "DECLARED_INDEX_LABEL" if adapter in ("command.v1", "junit.v1") else "PARSED_RESPONSE_IDENTITY"
        if adapter == "command.v1":
            result["status"] = "OBSERVED_EXIT_OK"
        elif adapter == "junit.v1":
            with (bundle / entry["step"] / "stdout.log").open("rb") as stream:
                result["status"], result["details"] = junit(stream.read(io.LIMIT + 1))
        elif adapter == "native-completion.v1":
            require((record.get("scope") or {}).get("work_id") == index["binding"]["work_id"]
                    and record["scope"].get("selection") == entry["scope"], "Completion Work/selection unbound")
            result["status"], result["details"] = native_completion(
                io.read_json(bundle / entry["step"] / "stdout.log"), entry["scope"])
        else:
            decode = github_run if adapter == "github-run.v1" else github_deployment
            state, commit, details = decode(io.read_json(bundle / entry["step"] / "stdout.log"),
                                            index["repository"], entry["scope"])
            result.update(status=state, source_relation=remote_relation(commit, target), details=details)
        ec.set_check(verification, "parser", "VALID", parser_scope, parser_method, refs=[revision])
        if adapter in ("github-run.v1", "github-deployment.v1"):
            ec.set_check(verification, "statement", "DECLARED", "CAPTURED_PROVIDER_STATUS_NOT_AUTHENTICATED",
                         adapter, actor="github-response", refs=[revision])
    except (OSError, ValueError, KeyError, TypeError, StopIteration, ET.ParseError) as error:
        if verification["checks"]["integrity"]["state"] == "MATCH":
            ec.set_check(verification, "parser", "INVALID", parser_scope, parser_method, refs=[entry["revision"]])
        elif getattr(error, "code", None) == "INTEGRITY":
            ec.set_check(verification, "integrity", "MISMATCH", "OBSERVATION_INVENTORY",
                         "SHA256_MANIFEST", refs=[entry["revision"]])
        result.update(status="INVALID", diagnostic=str(error)[:256], error_type=type(error).__name__)
    return result


def projection(index, cwd, fresh=None, remote=None, source_pin=None):
    validate(index)
    target = target_source(cwd, index["repository"])
    rows = [evidence(entry, index, target) for entry in index["entries"]]
    if fresh is not None:
        if fresh["source_pin"] != target:
            fresh = {**fresh, "source_relation": "STALE", "status": "BLOCKED"}
        rows.append(fresh)
    for row in remote or []:
        require(row["channel"] in ("remote_ci", "deployment"), "Invalid remote channel")
        if row["source_pin"] != target:
            row = {**row, "source_relation": "STALE", "status": "BLOCKED",
                   "remote_latest_verified": False}
        # A new query replaces only this exact resource, not another run in the workflow.
        for previous in rows:
            if (previous["channel"] == row["channel"] and previous["scope"] == row["scope"]
                    and previous.get("details", {}).get(row["resource_key"]) == row["resource_id"]):
                previous["superseded_by"] = row["id"]
        rows.append(row)
    after = target_source(cwd, index["repository"])
    stable = target == after and (source_pin is None or source_pin == target)
    channels = {}
    for channel in CHANNELS:
        selected = [r for r in rows if r["channel"] == channel]
        applicable = [r for r in selected if r["source_relation"] == "CURRENT"
                      and "superseded_by" not in r]
        if channel == "completion":
            applicable = [r for r in applicable if r.get("freshness") == "LIVE_NATIVE_QUERY"]
        states = {r["status"] for r in applicable}
        status = "SOURCE_CHANGED" if not stable else (
            "INVALID_EVIDENCE" if any(r["status"] == "INVALID" for r in selected) else
            "REMOTE_QUERY_FAILED" if any(r["status"] == "QUERY_FAILED" for r in selected) else
            "NOT_OBSERVED" if not selected else "NO_CURRENT_EVIDENCE" if not applicable else
            "CONFLICT" if len(states) > 1 else next(iter(states)))
        if (stable and channel == "completion"
                and not any(r.get("freshness") == "LIVE_NATIVE_QUERY" for r in applicable)):
            status = "REVALIDATE_REQUIRED" if selected else "NOT_OBSERVED"
        scopes = {}
        for scope in sorted({r.get("scope", "UNSPECIFIED") for r in selected}):
            values = {r["status"] for r in applicable if r.get("scope", "UNSPECIFIED") == scope}
            scopes[scope] = ("SOURCE_CHANGED" if not stable else
                             "REMOTE_QUERY_FAILED" if any(r.get("scope", "UNSPECIFIED") == scope and r["status"] == "QUERY_FAILED"
                                                          for r in selected) else
                             "NO_CURRENT_EVIDENCE" if not values else
                             "CONFLICT" if len(values) > 1 else next(iter(values)))
        channels[channel] = {"status": status, "scopes": scopes, "evidence": selected}
    native = stable and fresh is not None and fresh["source_relation"] == "CURRENT" and fresh["status"] == "PASS"
    return {"schema": "golem.revision-status.v1", "binding": index["binding"],
            "repository": index["repository"], "target": target, "source_stable": stable,
            "channels": channels, "native_acceptance_verified": native,
            "overall_completion": "NOT_INFERRED", "execution_authorized": False,
            "deployment_authorized": False, "remote_latest_verified": False}


def observe(index, cwd, cli, work, selection, output):
    validate(index)
    before = target_source(cwd, index["repository"])
    require(isinstance(selection, str) and io.ID.fullmatch(selection), "Invalid selection")
    output = output.absolute()
    for root in (cwd.resolve(), work.resolve()):
        require(root != output.resolve() and root not in output.resolve().parents, "Output overlaps repository or Work")
    io.private_directory(output)
    plan = io.observe_plan(cli.resolve(strict=True), work.resolve(strict=True), index["binding"]["work_id"],
                           selection, output, "code")
    record = io.run(plan, cwd.resolve(), output, {"work_id": index["binding"]["work_id"],
        "project_id": index["binding"]["project_id"], "work": str(work.resolve()), "selection": selection})
    entry = {"id": "live-completion", "channel": "completion", "adapter": "native-completion.v1",
             "bundle": str(output), "revision": io.digest(output / "record.json"),
             "step": "completion", "scope": selection}
    fresh = evidence(entry, index, before)
    fresh["freshness"] = "LIVE_NATIVE_QUERY"
    fresh["source_pin"] = before
    if record["status"] != "RECORDED" or target_source(cwd, index["repository"]) != before:
        fresh.update(source_relation="CHANGED_OR_INCOMPLETE_QUERY", status="BLOCKED")
    return projection(index, cwd, fresh)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--selection")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        index = io.read_json(args.index)
        requested = (args.cli, args.work, args.selection, args.output)
        require(all(v is not None for v in requested) or all(v is None for v in requested),
                "Live completion requires cli, work, selection and new output together")
        result = observe(index, args.cwd, *requested) if args.cli is not None else projection(index, args.cwd)
        sys.stdout.buffer.write(io.encoded(result))
        return 0 if result["source_stable"] and all(c["status"] != "INVALID_EVIDENCE"
                  for c in result["channels"].values()) else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.stderr.buffer.write(io.encoded({"schema": "golem.revision-status-error.v1",
            "diagnostic": str(error)[:512], "error_type": type(error).__name__,
            "next_action": "INSPECT_INDEX_AND_ORIGINAL_EVIDENCE; DO_NOT_REPLAY_EFFECTS",
            "execution_authorized": False}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
