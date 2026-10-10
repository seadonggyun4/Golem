"""Explicit, bounded GitHub status refresh. No CI execution or deployment authority."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

import agent_io as io
import execution_record as records
import evidence_contract as ec
import revision_status as rs
from judgment_record import require
from verify_agent import strict_json

ORIGIN = "https://api.github.com"
MAX_BODY = 2 * 1024 * 1024
MAX_QUERIES = 16


class QueryError(ValueError):
    pass


def check(value, code):
    if not value:
        raise QueryError(code)


def decode(raw):
    try:
        data = strict_json(raw)
    except (ValueError, UnicodeError, RecursionError):
        raise QueryError("INVALID_OR_EXCESSIVELY_NESTED_JSON") from None
    pending, count = [(data, 0)], 0
    while pending:
        node, depth = pending.pop()
        count += 1
        check(depth <= 64 and count <= 100000, "JSON_STRUCTURE_LIMIT_EXCEEDED")
        children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
        pending.extend((child, depth + 1) for child in children)
        check(len(pending) <= 100000, "JSON_STRUCTURE_LIMIT_EXCEEDED")
    return data


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise QueryError("REDIRECT_REQUIRES_REPOSITORY_REVALIDATION")


def get(path, credential, deadline):
    """Only generated GitHub GET endpoints; credentials and error bodies never persist."""
    require(re.fullmatch(r"/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
                         r"(?:actions/runs/[1-9][0-9]*|deployments/[1-9][0-9]*(?:/statuses\?per_page=100)?)", path),
            "Unsafe endpoint")
    require(not credential or (len(credential) <= 4096 and all(32 < ord(c) < 127 for c in credential)),
            "Invalid credential")
    headers = {"Accept": "application/vnd.github+json", "Accept-Encoding": "identity",
               "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "golem-revision-status"}
    if credential:
        headers["Authorization"] = "Bearer " + credential
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    url = ORIGIN + path
    try:
        remaining = deadline - time.monotonic()
        check(remaining > 0, "QUERY_DEADLINE_EXCEEDED")
        with opener.open(urllib.request.Request(url, headers=headers), timeout=min(remaining, 20)) as response:
            check(response.status == 200 and response.geturl() == url, "UNEXPECTED_HTTP_RESPONSE")
            check(response.headers.get_content_type() == "application/json"
                    and response.headers.get("Content-Encoding", "identity") == "identity", "INVALID_CONTENT_TYPE")
            chunks, size = [], 0
            while True:
                check(time.monotonic() < deadline, "QUERY_DEADLINE_EXCEEDED")
                chunk = response.read1(min(65536, MAX_BODY + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                check(size <= MAX_BODY, "RESPONSE_TOO_LARGE")
                chunks.append(chunk)
            raw = b"".join(chunks)
            check(not credential or credential.encode() not in raw, "CREDENTIAL_ECHO_REJECTED")
            # Never assume list order or silently treat a truncated page as complete.
            check(not response.headers.get("Link"), "INCOMPLETE_PAGINATION")
            return decode(raw), raw
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
        raise QueryError(f"HTTP_{code}; NO_RETRY; CHECK_ACCESS_OR_RATE_LIMIT") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise QueryError("NETWORK_OR_TIMEOUT; NO_CACHED_PASS_FALLBACK") from None


def validate_queries(data):
    require(isinstance(data, dict) and set(data) == {"schema", "queries"}
            and data["schema"] == "golem.remote-status-query.v1", "Invalid remote query contract")
    require(isinstance(data["queries"], list) and 0 < len(data["queries"]) <= MAX_QUERIES,
            "Request between 1 and 16 explicit resources")
    ids, resources = set(), set()
    for query in data["queries"]:
        require(isinstance(query, dict) and set(query) == {"id", "channel", "scope", "resource_id"},
                "Invalid query")
        require(isinstance(query["id"], str) and io.ID.fullmatch(query["id"])
                and query["id"] not in ids, "Unique query IDs required")
        require(query["channel"] in ("remote_ci", "deployment")
                and type(query["resource_id"]) is int and query["resource_id"] > 0,
                "Explicit positive run/deployment ID required")
        require(isinstance(query["scope"], str) and 0 < len(query["scope"]) <= 128
                and all(ord(c) >= 32 and ord(c) != 127 for c in query["scope"]), "Invalid scope")
        if query["channel"] == "remote_ci":
            require(re.fullmatch(r"[1-9][0-9]*", query["scope"]), "Workflow ID required")
        key = query["channel"], query["resource_id"]
        require(key not in resources, "Duplicate remote resource")
        ids.add(query["id"])
        resources.add(key)
    return data["queries"]


def timestamp(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value),
            "Invalid deployment status timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def refresh(index, cwd, queries, output, credential=None, timeout=60):
    rs.validate(index)
    queries = validate_queries(queries)
    require(type(timeout) in (int, float) and 0 < timeout <= 300, "Timeout must be in (0,300]")
    before = rs.target_source(cwd, index["repository"])
    output = output.absolute()
    require(cwd.resolve() != output.resolve() and cwd.resolve() not in output.resolve().parents,
            "Evidence output overlaps repository")
    io.private_directory(output)
    records.save(output / "queries.json", io.encoded({"schema": "golem.remote-status-query.v1", "queries": queries}))
    rows, captures = [], []
    deadline = time.monotonic() + timeout
    base = f"/repos/{index['repository']}"
    halted = False
    for query in queries:
        is_run = query["channel"] == "remote_ci"
        resource = query["resource_id"]
        key = "run_id" if is_run else "deployment_id"
        row = {**query, "id": "remote-" + query["id"], "resource_key": key,
               "source_pin": before, "source_relation": "UNBOUND", "status": "QUERY_FAILED",
               "freshness": "LIVE_REMOTE_QUERY", "remote_latest_verified": False,
               "authenticity_verified": False, "details": {key: resource},
               "observed_at": datetime.now(timezone.utc).isoformat(), "bundle": str(output)}
        captured = []
        def fetch(path):
            if halted:
                raise QueryError("BATCH_STOPPED_AFTER_ACCESS_OR_RATE_LIMIT_ERROR")
            data, raw = get(path, credential, deadline)
            name = f"{query['id']}-{len(captured)}.json"
            records.save(output / name, raw)
            captured.append({"path": path, "file": name, "sha256": io.digest(output / name)})
            return data
        try:
            if is_run:
                data = fetch(f"{base}/actions/runs/{resource}")
                state, sha, details = rs.github_run(data, index["repository"], query["scope"])
                check(data["id"] == resource, "RUN_ID_MISMATCH")
            else:
                deployment = fetch(f"{base}/deployments/{resource}")
                check(isinstance(deployment, dict) and deployment.get("id") == resource, "DEPLOYMENT_ID_MISMATCH")
                statuses = fetch(f"{base}/deployments/{resource}/statuses?per_page=100")
                check(isinstance(statuses, list) and 0 < len(statuses) <= 100,
                      "MISSING_OR_OVERSIZED_DEPLOYMENT_STATUSES")
                parsed = []
                seen = set()
                for status in statuses:
                    rs.github_deployment({"deployment": deployment, "status": status},
                                         index["repository"], query["scope"])
                    check(status["id"] not in seen, "DUPLICATE_DEPLOYMENT_STATUS")
                    seen.add(status["id"])
                    parsed.append((timestamp(status.get("created_at")), status))
                newest = max(t for t, _ in parsed)
                latest = [s for t, s in parsed if t == newest]
                check(len(latest) == 1, "AMBIGUOUS_LATEST_DEPLOYMENT_STATUS")
                state, sha, details = rs.github_deployment({"deployment": deployment, "status": latest[0]},
                                                           index["repository"], query["scope"])
            row.update(status=state, source_relation=rs.remote_relation(sha, before), details=details,
                       remote_latest_verified=True, latest_scope="SELECTED_RESOURCE_AT_REQUEST_TIME")
        except (OSError, ValueError, TypeError, KeyError) as error:
            # Do not serialize arbitrary provider payloads or exception strings.
            row["diagnostic"] = "REMOTE_QUERY_OR_IDENTITY_VALIDATION_FAILED"
            if isinstance(error, QueryError):
                row["diagnostic"] = str(error)
                if str(error).startswith(("HTTP_403;", "HTTP_429;")):
                    halted = True
        rows.append(row)
        capture = {"id": query["id"], "responses": captured}
        captures.append(capture)
        revision = io.identity(capture)
        row["revision"] = revision
        verification = ec.assessment(revision, "REMOTE_RESPONSE_CAPTURE", index["binding"])
        ec.set_check(verification, "integrity", "MATCH", "CAPTURE_MANIFEST_BYTES", "SHA256", refs=[revision])
        if row["status"] != "QUERY_FAILED":
            ec.set_check(verification, "parser", "VALID", "SELECTED_PROVIDER_RESOURCE", "GITHUB_REST", refs=[revision])
            ec.set_check(verification, "execution", "OBSERVED", "READ_ONLY_PROVIDER_GET", "HTTPS_TLS", refs=[revision])
            ec.set_check(verification, "statement", "DECLARED", "PROVIDER_REPORTED_STATUS", "GITHUB_REST",
                         actor="github-response", refs=[revision])
        row["verification"] = verification
        row["finished_at"] = datetime.now(timezone.utc).isoformat()
    result = rs.projection(index, cwd, remote=rows, source_pin=before)
    result["remote_refresh"] = {"schema": "golem.remote-status-refresh.v1", "captures": captures,
                               "atomic_remote_snapshot": False, "continuous_monitoring": False}
    records.save(output / "result.json", io.encoded(result))
    records.save(output / "manifest.json", io.encoded({p.name: io.digest(p) for p in sorted(output.iterdir())}))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("queries", type=Path)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    try:
        result = refresh(io.read_json(args.index), args.cwd, io.read_json(args.queries), args.output,
                         os.environ.get("GH_TOKEN"), args.timeout)
        sys.stdout.buffer.write(io.encoded(result))
        return 0 if result["source_stable"] and all(c["status"] not in (
            "INVALID_EVIDENCE", "REMOTE_QUERY_FAILED") for c in result["channels"].values()) else 1
    except (OSError, ValueError, TypeError, KeyError):
        sys.stderr.buffer.write(io.encoded({"schema": "golem.remote-status-error.v1",
            "diagnostic": "INVALID_QUERY_OR_CAPTURE_FAILURE", "execution_authorized": False}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
