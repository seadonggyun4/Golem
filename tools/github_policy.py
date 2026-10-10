"""Bounded, read-only domain evaluators for GitHub branch policy evidence.

Transport and publication belong to github_checks/status_collector. These adapters
do not grant merge permission or infer application health from deployment records.
"""
import re
from datetime import datetime

import remote_status as remote


SUPPORTED = frozenset({"workflows", "code_scanning", "required_deployments"})
ALERTS = {"none": set(), "errors": {"error"},
          "errors_and_warnings": {"error", "warning"}, "all": {"error", "warning", "note"}}
SECURITY = {"none": set(), "critical": {"critical"}, "high_or_higher": {"critical", "high"},
            "medium_or_higher": {"critical", "high", "medium"},
            "all": {"critical", "high", "medium", "low"}}


def positive(value):
    remote.check(type(value) is int and value > 0, "INVALID_POLICY_RESOURCE_ID")
    return value


def timestamp(value):
    # Ruleset metadata uses offset/fractional RFC3339 timestamps, unlike the
    # second-resolution UTC deployment examples. Reject naive/ambiguous values.
    remote.check(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value),
        "INVALID_POLICY_TIMESTAMP")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def name(value):
    remote.check(isinstance(value, str) and 0 < len(value) <= 256
                 and all(ord(c) >= 32 and ord(c) != 127 for c in value), "INVALID_POLICY_NAME")
    return value


def unique(rows, key="id"):
    seen = set()
    for row in rows:
        identity = positive(row[key])
        remote.check(identity not in seen, "DUPLICATE_POLICY_RESOURCE")
        seen.add(identity)
    return rows


def latest(rows, key):
    if not rows:
        return None
    times = [(timestamp(r[key]), r) for r in rows]
    newest = max(t for t, _ in times)
    selected = [r for t, r in times if t == newest]
    remote.check(len(selected) == 1, "AMBIGUOUS_POLICY_RESOURCE_ORDER")
    return selected[0]


def outcome(status, evidence=(), **details):
    return {"status": status, "evidence": list(evidence), "evaluation_complete": True, **details}


def workflow_rule(client, rule, sha, branch, policy):
    """Use provider rule results, never similarly named jobs/reusable workflows.

    Rule suites are historical push evaluations. Match current ruleset identity,
    parameters and update time; an unpinned source ref remains historical-only.
    """
    definitions = rule["parameters"]["workflows"]
    remote.check(set(rule["parameters"]) <= {"workflows", "do_not_enforce_on_create"}
                 and type(rule["parameters"].get("do_not_enforce_on_create", False)) is bool,
                 "UNKNOWN_WORKFLOW_POLICY_PARAMETERS")
    remote.check(isinstance(definitions, list) and 0 < len(definitions) <= 128,
                 "INVALID_REQUIRED_WORKFLOWS")
    for item in definitions:
        remote.check(set(item) <= {"repository_id", "path", "ref", "sha"}, "UNKNOWN_WORKFLOW_DEFINITION_FIELDS")
        positive(item["repository_id"])
        path = name(item["path"])
        remote.check(path.startswith(".github/workflows/") and ".." not in path.split("/")
                     and path.endswith((".yml", ".yaml")), "INVALID_WORKFLOW_PATH")
        if item.get("ref") is not None:
            name(item["ref"])
        if item.get("sha") is not None:
            remote.check(isinstance(item["sha"], str) and re.fullmatch(r"[0-9a-f]{40}", item["sha"]),
                         "INVALID_WORKFLOW_SHA")
    if "ruleset_id" not in rule:
        return outcome("POLICY_IDENTITY_UNAVAILABLE")
    identity = positive(rule["ruleset_id"])
    current = client.one(f"/rulesets/{identity}", includes_parents="true")
    remote.check(current["id"] == identity and current["enforcement"] == "active"
                 and {"type": "workflows", "parameters": rule["parameters"]} in current["rules"],
                 "WORKFLOW_POLICY_MISMATCH")
    updated = timestamp(current["updated_at"])
    suites = unique(client.pages("/rulesets/rule-suites", ref="refs/heads/" + branch,
                                time_period="month", evaluate_status="active", rule_suite_result="all"))
    remote.check(len({positive(s["repository_id"]) for s in suites}) <= 1,
                 "RULE_SUITE_REPOSITORY_MISMATCH")
    candidates = [s for s in suites if s.get("after_sha") == sha
                  and s.get("ref") == "refs/heads/" + branch]
    chosen = latest(candidates, "pushed_at")
    if chosen is None:
        return outcome("EVALUATION_NOT_OBSERVED", retention_window="month")
    if timestamp(chosen["pushed_at"]) <= updated:
        return outcome("POLICY_NEWER_THAN_EVALUATION")
    detail = client.one(f"/rulesets/rule-suites/{chosen['id']}")
    remote.check(detail["result"] in ("pass", "fail", "bypass"), "UNKNOWN_RULE_SUITE_RESULT")
    remote.check(all(detail.get(k) == chosen.get(k) for k in
                     ("id", "after_sha", "ref", "repository_id", "pushed_at", "result")),
                 "RULE_SUITE_IDENTITY_CHANGED")
    if rule["parameters"].get("do_not_enforce_on_create", False):
        before = detail.get("before_sha")
        if not isinstance(before, str) or not re.fullmatch(r"[0-9a-f]{40}", before) or before == "0" * 40:
            return outcome("CREATION_EXEMPT_OR_UNVERIFIED")
    evidence = [{"kind": "rule_suite", "id": chosen["id"], "ruleset_id": identity,
                 "commit": sha, "pushed_at": chosen["pushed_at"]}]
    matches = [r for r in detail["rule_evaluations"] if r.get("rule_type") == "workflows"
               and r.get("enforcement") == "active"
               and r.get("rule_source", {}).get("type") == "ruleset"
               and r["rule_source"].get("id") == identity]
    remote.check(len(matches) <= 1, "AMBIGUOUS_WORKFLOW_EVALUATION")
    remote.check(current == client.one(f"/rulesets/{identity}", includes_parents="true")
                 and detail == client.one(f"/rulesets/rule-suites/{chosen['id']}")
                 and suites == client.pages("/rulesets/rule-suites", ref="refs/heads/" + branch,
                     time_period="month", evaluate_status="active", rule_suite_result="all"),
                 "WORKFLOW_POLICY_OR_EVALUATION_CHANGED")
    if detail["result"] == "bypass":
        return outcome("BYPASSED", evidence)
    if not matches:
        return outcome("EVALUATION_NOT_OBSERVED", evidence)
    state = matches[0]["result"]
    remote.check(state in ("pass", "fail", "bypass"), "UNKNOWN_RULE_EVALUATION")
    status = {"pass": "PASS", "fail": "FAIL", "bypass": "BYPASSED"}[state]
    if status == "PASS" and not all(d.get("sha") for d in definitions):
        status = "DEFINITION_REVISION_UNVERIFIED"
    return outcome(status, evidence, scope="EXACT_COMMIT_PROVIDER_PUSH_EVALUATION",
                   provider_historical_result=state, current_merge_authorized=False)


def scanning_tool(client, requirement, sha, branch):
    remote.check(set(requirement) == {"tool", "alerts_threshold", "security_alerts_threshold"},
                 "UNKNOWN_SCANNING_TOOL_PARAMETERS")
    tool = name(requirement["tool"])
    ordinary, security = requirement["alerts_threshold"], requirement["security_alerts_threshold"]
    remote.check(ordinary in ALERTS and security in SECURITY, "UNKNOWN_SCANNING_THRESHOLD")
    ref = "refs/heads/" + branch
    analyses = unique(client.pages("/code-scanning/analyses", ref=ref, tool_name=tool))
    groups = {}
    for row in analyses:
        remote.check(row["tool"]["name"] == tool and row["ref"] == ref,
                     "SCANNING_ANALYSIS_IDENTITY_MISMATCH")
        # Keep matrix categories/environments distinct; one language cannot stand
        # in for another, and a failed newer upload cannot expose an old PASS.
        key = (row["tool"].get("guid"), name(row["analysis_key"]),
               row.get("category"), row["environment"])
        remote.check(all(v is None or isinstance(v, str) for v in key), "INVALID_ANALYSIS_CATEGORY")
        groups.setdefault(key, []).append(row)
    selected = [latest(rows, "created_at") for rows in groups.values()]
    evidence = [{"kind": "code_scanning_analysis", "id": r["id"], "category": r.get("category"),
                 "commit": r["commit_sha"]} for r in selected]
    if not selected:
        return outcome("ANALYSIS_NOT_OBSERVED", evidence, tool=tool)
    if any(r["commit_sha"] != sha for r in selected):
        return outcome("ANALYSIS_REVISION_MISMATCH", evidence, tool=tool)
    remote.check(all(isinstance(r.get("error"), str) and isinstance(r.get("warning"), str)
                     for r in selected), "SCANNING_ANALYSIS_COMPLETENESS_UNKNOWN")
    if any(r["error"] for r in selected):
        return outcome("ANALYSIS_FAILED", evidence, tool=tool)
    if any(r["warning"] for r in selected):
        return outcome("ANALYSIS_WARNING", evidence, tool=tool)
    alerts = unique(client.pages("/code-scanning/alerts", ref=ref, tool_name=tool), "number")
    blocking = []
    for alert in alerts:
        instance, rule = alert["most_recent_instance"], alert["rule"]
        remote.check(alert["tool"]["name"] == tool and instance["ref"] == ref,
                     "SCANNING_ALERT_IDENTITY_MISMATCH")
        remote.check(alert["state"] in ("open", "dismissed", "fixed")
                     and instance["state"] in ("open", "dismissed", "fixed"), "UNKNOWN_ALERT_STATE")
        # Repository-wide state must not conceal an open instance on this ref.
        if instance["state"] != "open":
            continue
        remote.check(instance["commit_sha"] == sha, "SCANNING_ALERT_REVISION_MISMATCH")
        level, security_level = rule["severity"], rule.get("security_severity_level")
        remote.check(level in ("error", "warning", "note", "none")
                     and security_level in (None, "critical", "high", "medium", "low"),
                     "UNKNOWN_ALERT_SEVERITY")
        if security_level is None:
            remote.check(not (security != "none" and "security" in rule.get("tags", [])),
                         "SECURITY_SEVERITY_UNAVAILABLE")
            blocked = level in ALERTS[ordinary]
        else:
            blocked = security_level in SECURITY[security]
        if blocked:
            blocking.append(alert["number"])
    # Analysis/alert queries are not a transaction. Detect uploads during the read.
    remote.check(analyses == client.pages("/code-scanning/analyses", ref=ref, tool_name=tool)
                 and alerts == client.pages("/code-scanning/alerts", ref=ref, tool_name=tool),
                 "SCANNING_ANALYSIS_CHANGED_DURING_QUERY")
    return outcome("FAIL" if blocking else "PASS", evidence, tool=tool,
                   blocking_alerts=blocking, observed_alerts=len(alerts),
                   scope="OBSERVED_REFERENCE_ANALYSIS_CATEGORIES", vulnerability_free_verified=False)


def scanning_rule(client, rule, sha, branch, policy):
    remote.check(set(rule["parameters"]) == {"code_scanning_tools"}, "UNKNOWN_SCANNING_POLICY_PARAMETERS")
    tools = rule["parameters"]["code_scanning_tools"]
    remote.check(isinstance(tools, list) and 0 < len(tools) <= 32, "INVALID_SCANNING_TOOLS")
    # This collector observes a branch, not a PR diff. Never apply branch-head
    # alerts to a candidate/merge-group SHA that needs another reference context.
    if sha != policy["branch_sha"]:
        return outcome("REFERENCE_CONTEXT_REQUIRED")
    rows = [scanning_tool(client, item, sha, branch) for item in tools]
    return outcome("PASS" if all(r["status"] == "PASS" for r in rows) else "BLOCKED",
                   [e for r in rows for e in r["evidence"]], tools=rows)


def deployment_rule(client, rule, sha, branch, policy):
    remote.check(set(rule["parameters"]) == {"required_deployment_environments"},
                 "UNKNOWN_DEPLOYMENT_POLICY_PARAMETERS")
    environments = rule["parameters"]["required_deployment_environments"]
    remote.check(isinstance(environments, list) and 0 < len(environments) <= 32
                 and len(set(environments)) == len(environments), "INVALID_REQUIRED_ENVIRONMENTS")
    rows = []
    for environment in environments:
        name(environment)
        deployments = unique(client.pages("/deployments", sha=sha, environment=environment))
        remote.check(all(d["sha"] == sha and d["environment"] == environment for d in deployments),
                     "REQUIRED_DEPLOYMENT_IDENTITY_MISMATCH")
        chosen = latest(deployments, "created_at")
        if chosen is None:
            rows.append(outcome("MISSING", environment=environment))
            continue
        statuses = unique(client.pages(f"/deployments/{chosen['id']}/statuses"))
        selected = latest(statuses, "created_at")
        if selected is None:
            rows.append(outcome("PENDING", environment=environment))
            continue
        remote.check(selected.get("deployment_url") == client.endpoint(f"/deployments/{chosen['id']}")
                     and selected.get("environment") == environment, "DEPLOYMENT_STATUS_IDENTITY_MISMATCH")
        states = {"success": "PASS", "failure": "FAIL", "error": "FAIL", "pending": "PENDING",
                  "queued": "PENDING", "in_progress": "PENDING", "inactive": "INACTIVE"}
        remote.check(selected["state"] in states, "UNKNOWN_DEPLOYMENT_STATE")
        remote.check(statuses == client.pages(f"/deployments/{chosen['id']}/statuses")
                     and deployments == client.pages("/deployments", sha=sha, environment=environment),
                     "REQUIRED_DEPLOYMENT_CHANGED_DURING_QUERY")
        rows.append(outcome(states[selected["state"]], [{"kind": "deployment", "id": chosen["id"],
                            "status_id": selected["id"], "commit": sha}], environment=environment))
    return outcome("PASS" if all(r["status"] == "PASS" for r in rows) else "BLOCKED",
                   [e for r in rows for e in r["evidence"]], environments=rows,
                   serving_currently_verified=False, scope="LATEST_ATTEMPT_PER_REQUIRED_ENVIRONMENT_AND_SHA")


EVALUATORS = {"workflows": workflow_rule, "code_scanning": scanning_rule,
              "required_deployments": deployment_rule}


def collect(client, policy, sha, branch, checks=None):
    results = []
    rules = policy.get("workflow_rules", []) + [r for r in policy["other_rules"] if r["type"] in SUPPORTED]
    for rule in rules:
        try:
            result = EVALUATORS[rule["type"]](client, rule, sha, branch, policy)
            if result["status"] == "PASS" and checks is not None:
                # Scanner/job names do not establish tool identity. Conservatively
                # wait for every observed unfinished attempt, including unrelated
                # checks, rather than hide a possible scan/workflow rerun.
                pending = [r["id"] for r in checks if r["status"] != "completed"]
                if pending:
                    result.update(status="EXECUTION_PENDING", observed_domain_status="PASS",
                                  pending_check_ids=pending)
        except (ValueError, KeyError, TypeError, OSError) as error:
            # Controlled provider errors have a code; never expose response text,
            # arbitrary parser exceptions or credentials through diagnostics.
            diagnostic = str(error) if isinstance(error, remote.QueryError) else "POLICY_EVIDENCE_INVALID"
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", diagnostic):
                diagnostic = "POLICY_EVIDENCE_INVALID"
            result = outcome("QUERY_OR_VALIDATION_FAILED", diagnostic=diagnostic,
                             retry_after=getattr(error, "retry_after", 60), evaluation_complete=False)
        results.append({"rule": rule, **result})
    return results
