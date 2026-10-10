"""Read-only GitHub policy discovery and revision-bound check observation."""
from datetime import datetime, timezone
import hashlib
import re
import ssl
import time
import urllib.error
import urllib.parse as url
import urllib.request

import agent_io as io
import github_policy
import remote_status as remote
import revision_status as rs

NON_CHECK_RULES = frozenset({"creation", "update", "deletion", "required_linear_history",
    "required_signatures", "pull_request", "non_fast_forward", "merge_queue",
    "commit_message_pattern", "commit_author_email_pattern", "committer_email_pattern",
    "branch_name_pattern", "tag_name_pattern", "file_path_restriction", "max_file_path_length",
    "file_extension_restriction", "max_file_size", "copilot_code_review"})


class APIError(remote.QueryError):
    def __init__(self, code, retry_after=60):
        super().__init__(code)
        self.retry_after = retry_after


class Client:
    """Bounded serial GETs, verified cache revalidation, and fixed-origin pagination."""
    def __init__(self, repository, credential=None, cache=None, timeout=120, budget=128):
        remote.check(isinstance(repository, str) and rs.REPOSITORY.fullmatch(repository)
                     and all(p not in (".", "..") for p in repository.split("/")), "INVALID_REPOSITORY")
        remote.check(not credential or (len(credential) <= 4096 and
                     all(32 < ord(c) < 127 for c in credential)), "INVALID_CREDENTIAL")
        remote.check(type(timeout) in (int, float) and 0 < timeout <= 300
                     and type(budget) is int and 0 < budget <= 128, "INVALID_REQUEST_BUDGET")
        self.base = remote.ORIGIN + "/repos/" + repository
        self.credential, self.cache = credential, cache if cache is not None else {}
        self.deadline, self.budget = time.monotonic() + timeout, budget
        self.exchanges, self.delay = [], 0
        self.bytes_received = 0
        self.halted = False
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), remote.NoRedirect())

    def endpoint(self, path, **params):
        remote.check(path.startswith("/") and "?" not in path and "#" not in path
                     and not any(p in (".", "..") for p in path.split("/")), "INVALID_ENDPOINT")
        return self.base + path + ("?" + url.urlencode(params) if params else "")

    def get(self, address):
        if self.halted:
            raise APIError("BATCH_STOPPED_AFTER_RATE_OR_ACCESS_ERROR", max(60, self.delay))
        remote.check(isinstance(address, str) and all(32 < ord(c) < 127 for c in address)
                     and address.startswith(self.base + "/") and url.urlsplit(address).netloc == "api.github.com",
                     "INVALID_API_ORIGIN")
        remote.check(self.budget > 0 and time.monotonic() < self.deadline, "REQUEST_BUDGET_EXHAUSTED")
        self.budget -= 1
        headers = {"Accept": "application/vnd.github+json", "Accept-Encoding": "identity",
                   "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "golem-required-checks"}
        if self.credential:
            headers["Authorization"] = "Bearer " + self.credential
        cached = self.cache.get(address)
        if cached:
            try:
                remote.check(set(cached) == {"etag", "raw", "sha256", "link"}
                             and isinstance(cached["raw"], str) and isinstance(cached["etag"], str)
                             and 0 < len(cached["etag"]) <= 512
                             and all(32 <= ord(c) < 127 for c in cached["etag"])
                             and hashlib.sha256(cached["raw"].encode()).hexdigest() == cached["sha256"],
                             "INVALID_CACHE")
                remote.decode(cached["raw"].encode())
                remote.check(not self.credential or self.credential not in
                             cached["raw"] + cached["etag"] + cached["link"], "CREDENTIAL_ECHO_REJECTED")
                headers["If-None-Match"] = cached["etag"]
            except (ValueError, TypeError, KeyError):
                cached = None
                self.cache.pop(address, None)
        request = urllib.request.Request(address, headers=headers)
        try:
            response = self.opener.open(request, timeout=min(20, max(.01, self.deadline - time.monotonic())))
        except urllib.error.HTTPError as error:
            status = error.code
            if status == 304 and cached:
                error.close()
                self.exchanges.append({"url": address, "http_status": 304, "sha256": cached["sha256"],
                                       "conditional_revalidation": True, "response": cached["raw"]})
                return remote.decode(cached["raw"].encode()), cached["link"]
            wait = max(60, self.delay)
            for name in ("Retry-After", "X-Poll-Interval"):
                value = error.headers.get(name, "") if error.headers else ""
                if value.isdecimal():
                    wait = max(wait, int(value))
            reset = error.headers.get("X-RateLimit-Reset", "") if error.headers else ""
            if reset.isdecimal():
                wait = max(wait, int(reset) - int(time.time()) + 1)
            error.close()
            self.exchanges.append({"url": address, "http_status": status})
            if status in (403, 429):
                self.halted, self.delay = True, max(self.delay, wait)
            raise APIError(f"HTTP_{status}", wait) from None
        except (urllib.error.URLError, OSError, TimeoutError):
            self.exchanges.append({"url": address, "http_status": None, "diagnostic": "NETWORK_OR_TIMEOUT"})
            raise APIError("NETWORK_OR_TIMEOUT") from None
        with response:
            remote.check(response.status == 200 and response.geturl() == address, "INVALID_HTTP_RESPONSE")
            remote.check(response.headers.get_content_type() == "application/json"
                         and response.headers.get("Content-Encoding", "identity") == "identity", "INVALID_CONTENT_TYPE")
            chunks, size = [], 0
            while True:
                remote.check(time.monotonic() < self.deadline, "QUERY_DEADLINE_EXCEEDED")
                chunk = response.read1(min(65536, remote.MAX_BODY + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                remote.check(size <= remote.MAX_BODY, "RESPONSE_TOO_LARGE")
                chunks.append(chunk)
            raw = b"".join(chunks)
            self.bytes_received += len(raw)
            remote.check(self.bytes_received <= 16 * 1024 * 1024, "CYCLE_RESPONSE_LIMIT")
            remote.check(not self.credential or self.credential.encode() not in raw, "CREDENTIAL_ECHO_REJECTED")
            data = remote.decode(raw)
            link, etag = response.headers.get("Link", ""), response.headers.get("ETag", "")
            remote.check(len(link) <= 8192, "LINK_HEADER_LIMIT")
            remote.check(not self.credential or self.credential not in link + etag, "CREDENTIAL_ECHO_REJECTED")
            wait = response.headers.get("X-Poll-Interval", "")
            if wait.isdecimal():
                self.delay = max(self.delay, int(wait))
            raw_text = raw.decode("utf-8")
            digest = hashlib.sha256(raw).hexdigest()
            self.exchanges.append({"url": address, "http_status": 200, "sha256": digest,
                                   "conditional_revalidation": False, "response": raw_text})
            if (etag and len(etag) <= 512 and all(32 <= ord(c) < 127 for c in etag)
                    and (address in self.cache or len(self.cache) < 256)):
                self.cache[address] = {"etag": etag, "raw": raw_text, "sha256": digest, "link": link}
            return data, link

    def one(self, path, **params):
        data, link = self.get(self.endpoint(path, **params))
        remote.check(not link, "UNEXPECTED_PAGINATION")
        return data

    def pages(self, path, key=None, **params):
        address = self.endpoint(path, **params, per_page=100)
        initial, seen, rows, expected = url.urlsplit(address), set(), [], None
        for _ in range(20):
            remote.check(address not in seen, "PAGINATION_CYCLE")
            seen.add(address)
            data, link = self.get(address)
            values = data.get(key) if key and isinstance(data, dict) else data
            remote.check(isinstance(values, list) and len(values) <= 100, "INVALID_PAGE")
            if key:
                total = data.get("total_count")
                remote.check(type(total) is int and 0 <= total <= 2000 and
                             (expected is None or total == expected), "UNSTABLE_OR_OVERSIZED_TOTAL")
                expected = total
            rows.extend(values)
            remote.check(len(rows) <= 2000, "ROW_LIMIT_EXCEEDED")
            if not link:
                remote.check(expected is None or len(rows) == expected, "INCOMPLETE_PAGE_COUNT")
                return rows
            links = []
            for part in link.split(","):
                match = re.fullmatch(r'\s*<([^>]+)>\s*;\s*rel="([a-z ]+)"\s*', part)
                remote.check(match is not None, "INVALID_LINK_HEADER")
                links.append(match.groups())
            next_urls = [value for value, rel in links if "next" in rel.split()]
            if not next_urls:
                remote.check(expected is None or len(rows) == expected, "INCOMPLETE_PAGE_COUNT")
                return rows
            remote.check(len(next_urls) == 1, "AMBIGUOUS_NEXT_PAGE")
            next_url = url.urlsplit(next_urls[0])
            query = url.parse_qs(next_url.query, keep_blank_values=True)
            original = url.parse_qs(initial.query)
            page = query.pop("page", [""])
            current_page = url.parse_qs(url.urlsplit(address).query).get("page", ["1"])[0]
            remote.check(next_url.scheme == initial.scheme and next_url.netloc == initial.netloc
                         and next_url.path == initial.path and not next_url.fragment
                         and all(len(v) == 1 for v in query.values())
                         and len(page) == 1 and page[0].isdecimal()
                         and int(page[0]) == int(current_page) + 1 and query == original,
                         "UNSAFE_NEXT_PAGE")
            address = next_urls[0]
        raise APIError("PAGE_LIMIT_EXCEEDED")


def text(value):
    remote.check(isinstance(value, str) and 0 < len(value) <= 256
                 and all(ord(c) >= 32 and ord(c) != 127 for c in value), "INVALID_CHECK_NAME")
    return value


def discover(client, branch):
    branch = url.quote(text(branch), safe="")
    metadata = client.one("/branches/" + branch)
    remote.check(isinstance(metadata, dict) and type(metadata.get("protected")) is bool,
                 "INVALID_BRANCH_METADATA")
    legacy = None
    protection = metadata.get("protection")
    explicitly_disabled = isinstance(protection, dict) and protection.get("enabled") is False
    if explicitly_disabled:
        summary = protection.get("required_status_checks", {})
        remote.check(isinstance(summary, dict) and summary.get("contexts", []) == []
                     and summary.get("checks", []) == []
                     and summary.get("enforcement_level", "off") == "off",
                     "CONTRADICTORY_DISABLED_LEGACY_PROTECTION")
    if metadata["protected"] and not explicitly_disabled:
        # A 404 here is ambiguous (ruleset-only protection or missing access), not no requirements.
        legacy = client.one("/branches/" + branch + "/protection")
        remote.check(isinstance(legacy, dict), "INVALID_PROTECTION")
        legacy = legacy.get("required_status_checks")
    rules = client.pages("/rules/branches/" + branch)
    checks, workflows, other, workflow_rules = {}, [], [], []
    def add(name, app_id, source):
        text(name)
        remote.check(app_id is None or type(app_id) is int and (app_id == -1 or app_id > 0), "INVALID_REQUIRED_APP")
        app_id = None if app_id in (None, -1) else app_id
        checks.setdefault((name, app_id), {"context": name, "app_id": app_id, "sources": []})["sources"].append(source)
    if legacy is not None:
        remote.check(isinstance(legacy, dict) and isinstance(legacy.get("contexts"), list)
                     and isinstance(legacy.get("checks", []), list), "INVALID_REQUIRED_CHECKS")
        named = set()
        for item in legacy.get("checks", []):
            add(item["context"], item.get("app_id"), "branch_protection")
            named.add(item["context"])
        for name in legacy["contexts"]:
            if name not in named:
                add(name, None, "branch_protection")
    for rule in rules:
        remote.check(isinstance(rule, dict) and isinstance(rule.get("type"), str), "INVALID_RULE")
        kind = rule["type"]
        if kind == "required_status_checks":
            values = rule["parameters"]["required_status_checks"]
            remote.check(isinstance(values, list), "INVALID_RULE_CHECKS")
            for item in values:
                add(item["context"], item.get("integration_id"), "ruleset")
        elif kind == "workflows":
            workflow_rules.append(rule)
            values = rule["parameters"]["workflows"]
            remote.check(isinstance(values, list), "INVALID_REQUIRED_WORKFLOWS")
            for item in values:
                remote.check(isinstance(item, dict) and type(item.get("repository_id")) is int
                             and item["repository_id"] > 0, "INVALID_WORKFLOW_REPOSITORY")
                text(item.get("path"))
                workflows.append(item)
        else:
            other.append(rule)
    remote.check(len(checks) + len(workflows) + len(other) <= 512, "REQUIREMENT_LIMIT")
    return {"checks": list(checks.values()), "workflows": workflows,
            "workflow_rules": workflow_rules,
            "other_rules": other, "discovery_complete": True,
            "policy_sha256": io.identity({"legacy": legacy, "rules": rules}),
            "branch_sha": metadata["commit"]["sha"]}


def check_state(row):
    if row.get("status") != "completed":
        remote.check(row.get("status") in ("queued", "in_progress", "waiting", "pending", "requested")
                     and row.get("conclusion") is None, "INVALID_CHECK_STATE")
        return "PENDING"
    mapping = {"success": "PASS", "failure": "FAIL", "timed_out": "FAIL", "cancelled": "CANCELLED",
               "action_required": "BLOCKED", "neutral": "NEUTRAL", "skipped": "SKIPPED",
               "stale": "STALE_RESULT", "startup_failure": "FAIL"}
    remote.check(row.get("conclusion") in mapping, "INVALID_CHECK_CONCLUSION")
    return mapping[row["conclusion"]]


def evaluate(policy, checks, statuses, sha, domain_results=None):
    by_check, by_status, ids = {}, {}, set()
    for row in checks:
        remote.check(isinstance(row, dict) and type(row.get("id")) is int and row["id"] > 0
                     and row["id"] not in ids and row.get("head_sha") == sha
                     and isinstance(row.get("app"), dict) and type(row["app"].get("id")) is int
                     and row["app"]["id"] > 0,
                     "INVALID_OR_DUPLICATE_CHECK_IDENTITY")
        ids.add(row["id"])
        check_state(row)
        by_check.setdefault(text(row.get("name")), []).append(row)
    ids = set()
    for row in statuses:
        remote.check(isinstance(row, dict) and type(row.get("id")) is int and row["id"] > 0
                     and row["id"] not in ids and row.get("state") in ("success", "failure", "error", "pending"),
                     "INVALID_OR_DUPLICATE_COMMIT_STATUS")
        ids.add(row["id"])
        by_status.setdefault(text(row.get("context")), []).append(row)
    observed = []
    for requirement in policy["checks"]:
        name, app_id = requirement["context"], requirement["app_id"]
        matching = [r for r in by_check.get(name, []) if app_id is None or r["app"]["id"] == app_id]
        values, evidence = [], []
        if matching:
            # The provider's filter=latest selects attempts. Multiple providers remain distinct.
            values.extend(check_state(r) for r in matching)
            evidence.extend({"kind": "check_run", "id": r["id"], "app_id": r["app"]["id"]} for r in matching)
        legacy = by_status.get(name, [])
        if legacy:
            if app_id is not None:
                values.append("UNVERIFIED_STATUS_PRODUCER")
            else:
                values.append({"success": "PASS", "failure": "FAIL", "error": "FAIL", "pending": "PENDING"}[legacy[0]["state"]])
            evidence.append({"kind": "commit_status", "id": legacy[0]["id"]})
        state = "MISSING" if not values else values[0] if len(set(values)) == 1 else "CONFLICT"
        observed.append({**requirement, "status": state, "evidence": evidence})
    if domain_results is None:
        for workflow in policy["workflows"]:
            observed.append({"workflow": workflow, "status": "WORKFLOW_EVIDENCE_NOT_QUERIED",
                             "evaluation_complete": False})
    else:
        expected = policy.get("workflow_rules", []) + [r for r in policy["other_rules"]
                                                       if r["type"] in github_policy.SUPPORTED]
        remote.check([r["rule"] for r in domain_results] == expected, "POLICY_RESULT_BINDING_MISMATCH")
        observed.extend(domain_results)
    gates = [r for r in policy["other_rules"] if r["type"] not in NON_CHECK_RULES]
    for rule in gates:
        if domain_results is None or rule["type"] not in github_policy.SUPPORTED:
            observed.append({"rule": rule, "status": "POLICY_GATE_EVALUATION_REQUIRED",
                             "evaluation_complete": False})
    state = ("NOT_REQUIRED" if not observed else "PASS" if all(r["status"] == "PASS" for r in observed)
             else "BLOCKED")
    return {"status": state, "requirements": observed,
            "evaluation_complete": all(r.get("evaluation_complete", True) for r in observed),
            "observed_check_runs": len(checks),
            "observed_commit_statuses": len(statuses)}


def snapshot(index, cwd, branch, client, credential_failure=False, candidate_context=None):
    rs.validate(index)
    before = rs.target_source(cwd, index["repository"])
    result = {"schema": "golem.github-required-checks.v1", "binding": index["binding"],
              "repository": index["repository"], "branch": branch, "target": before,
              "observed_at": datetime.now(timezone.utc).isoformat(), "status": "DISCOVERY_FAILED",
              "discovery_complete": False, "evaluation_complete": False,
              "overall_completion": "NOT_INFERRED", "execution_authorized": False,
              "native_acceptance_verified": False, "authenticity_verified": False}
    try:
        if credential_failure:
            raise APIError("CREDENTIAL_UNAVAILABLE")
        policy = discover(client, branch)
        if candidate_context is not None:
            github_policy.github_context.validate(candidate_context)
            policy["candidate_context"] = candidate_context
        sha = before["commit"]
        remote.check(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha), "INVALID_SOURCE_SHA")
        if candidate_context is not None:
            candidate = github_policy.github_context.resolve(client, candidate_context, branch, policy["branch_sha"])
            remote.check(candidate["sha"] == sha, "CANDIDATE_SOURCE_REVISION_MISMATCH")
            result["candidate"] = candidate
        checks = client.pages(f"/commits/{sha}/check-runs", "check_runs", filter="latest")
        # A terminal latest-by-completion filter must not conceal an unfinished rerun.
        unfinished = []
        for state in ("queued", "in_progress"):
            unfinished.extend(client.pages(f"/commits/{sha}/check-runs", "check_runs", filter="all", status=state))
        # Waiting/requested/pending attempts can also coexist with a completed
        # latest result. Read all attempts within the shared pagination budget.
        unfinished.extend(r for r in client.pages(f"/commits/{sha}/check-runs", "check_runs", filter="all")
                          if r.get("status") != "completed")
        known = {r["id"]: r for r in checks}
        remote.check(len(known) == len(checks), "DUPLICATE_CHECK_RUN")
        for row in unfinished:
            remote.check(row["id"] not in known or known[row["id"]] == row, "CHECK_CHANGED_DURING_QUERY")
            known[row["id"]] = row
        checks = list(known.values())
        statuses = client.pages(f"/commits/{sha}/statuses")
        domain_results = github_policy.collect(client, policy, sha, branch, checks=checks)
        # Policy and branch movement during observation cannot turn into a current PASS.
        after_policy = discover(client, branch)
        if candidate_context is not None:
            after_policy["candidate_context"] = candidate_context
            remote.check(candidate == github_policy.github_context.resolve(client, candidate_context,
                         branch, after_policy["branch_sha"]), "CANDIDATE_CHANGED_DURING_QUERY")
        remote.check(policy == after_policy, "POLICY_OR_BRANCH_CHANGED_DURING_QUERY")
        result.update(evaluate(policy, checks, statuses, sha, domain_results))
        result["policy_evidence_failed"] = any(r["status"] == "QUERY_OR_VALIDATION_FAILED" for r in domain_results)
        result["retry_after"] = max((r.get("retry_after", 0) for r in domain_results), default=0)
        result.update(policy=policy, discovery_complete=True)
        result["commit_status"] = result["status"]
        result["source_relation"] = "COMMIT_ONLY_DIRTY_SOURCE" if before["dirty"] else "CURRENT"
        if before["dirty"]:
            if result["status"] in ("PASS", "NOT_REQUIRED"):
                result["status"] = "COMMIT_ONLY_DIRTY_SOURCE"
    except (ValueError, KeyError, TypeError, OSError) as error:
        result["diagnostic"] = str(error) if isinstance(error, APIError) else "POLICY_OR_RESPONSE_VALIDATION_FAILED"
        result["retry_after"] = error.retry_after if isinstance(error, APIError) else 60
    result["source_stable"] = before == rs.target_source(cwd, index["repository"])
    if not result["source_stable"]:
        result["status"] = "SOURCE_CHANGED"
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    result["recommended_interval"] = max(60, client.delay, result.get("retry_after", 0))
    return result


def deployments(client, index, target):
    """Discover environments from complete deployment inventory; never assert serving health."""
    result = {"schema": "golem.github-deployment-inventory.v1", "status": "QUERY_FAILED",
              "discovery_complete": False, "environments": [], "evidence": []}
    try:
        values = client.pages("/deployments")
        environments, seen = {}, set()
        for value in values:
            remote.check(isinstance(value, dict) and type(value.get("id")) is int and value["id"] > 0
                         and value["id"] not in seen, "INVALID_DEPLOYMENT_IDENTITY")
            seen.add(value["id"])
            name = text(value.get("environment"))
            created = remote.timestamp(value.get("created_at"))
            environments.setdefault(name, []).append((created, value))
        remote.check(len(environments) <= 32, "ENVIRONMENT_LIMIT_EXCEEDED")
        for name, candidates in sorted(environments.items()):
            newest = max(t for t, _ in candidates)
            latest = [v for t, v in candidates if t == newest]
            remote.check(len(latest) == 1, "AMBIGUOUS_LATEST_DEPLOYMENT")
            deployment = latest[0]
            statuses = client.pages(f"/deployments/{deployment['id']}/statuses")
            remote.check(bool(statuses), "DEPLOYMENT_STATUS_UNAVAILABLE")
            parsed, status_ids = [], set()
            for status in statuses:
                rs.github_deployment({"deployment": deployment, "status": status}, index["repository"], name)
                remote.check(status["id"] not in status_ids, "DUPLICATE_DEPLOYMENT_STATUS")
                status_ids.add(status["id"])
                parsed.append((remote.timestamp(status.get("created_at")), status))
            newest = max(t for t, _ in parsed)
            latest = [s for t, s in parsed if t == newest]
            remote.check(len(latest) == 1, "AMBIGUOUS_LATEST_DEPLOYMENT_STATUS")
            state, sha, details = rs.github_deployment({"deployment": deployment, "status": latest[0]},
                                                       index["repository"], name)
            row = {"id": f"discovered-deployment-{deployment['id']}", "channel": "deployment", "scope": name,
                   "resource_id": deployment["id"], "resource_key": "deployment_id", "details": details,
                   "status": state, "source_relation": rs.remote_relation(sha, target), "source_pin": target,
                   "freshness": "LIVE_REMOTE_QUERY", "remote_latest_verified": True,
                   "latest_scope": "LATEST_CREATED_DEPLOYMENT_IN_DISCOVERED_ENVIRONMENT_AT_QUERY",
                   "authenticity_verified": False}
            result["environments"].append({"environment": name, "status": state, "commit": sha,
                                           "serving_currently_verified": False})
            result["evidence"].append(row)
        result.update(status="OBSERVED" if environments else "NOT_OBSERVED", discovery_complete=True)
    except (ValueError, TypeError, KeyError, OSError) as error:
        result["diagnostic"] = str(error) if isinstance(error, APIError) else "DEPLOYMENT_INVENTORY_VALIDATION_FAILED"
        result["retry_after"] = error.retry_after if isinstance(error, APIError) else 60
        # Partial inventory cannot support a convenient PASS from its successful prefix.
        for row in result["evidence"]:
            row.update(status="QUERY_FAILED", remote_latest_verified=False)
    return result
