"""Restartable foreground GitHub collector; a supervisor owns its service lifetime."""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid

import agent_io as io
import execution_record as records
import github_checks as github
import remote_status as remote
import revision_status as rs


def atomic(path, value):
    temporary = path.parent / (".pending-" + uuid.uuid4().hex)
    records.save(temporary, io.encoded(value))
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def directory(path):
    path = path.absolute()
    for parent in (path, *path.parents):
        remote.check(not parent.is_symlink(), "SYMLINK_STATE_PATH")
    if not path.exists():
        records.private_directory(path)
    remote.check(path.is_dir() and path.stat().st_uid == os.getuid()
                 and path.stat().st_mode & 0o077 == 0, "STATE_DIRECTORY_NOT_PRIVATE")
    return path


@contextmanager
def lock(root):
    fd = os.open(root / "collector.lock", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        remote.check(os.fstat(fd).st_uid == os.getuid() and os.fstat(fd).st_mode & 0o077 == 0,
                     "LOCK_NOT_PRIVATE")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("COLLECTOR_ALREADY_RUNNING") from None
        yield
    finally:
        os.close(fd)


def credential(source, root, cwd):
    if source == "env":
        return os.environ.get("GH_TOKEN")
    # Explicit opt-in only; neither command output nor token is logged.
    result = records.run_private(["gh", "auth", "token", "--hostname", "github.com"],
        destination=root / ("credential-" + uuid.uuid4().hex), timeout=15,
        cwd=cwd, source=cwd, capture_output=True, output_limit=8192)
    remote.check(result.returncode == 0, "GH_CREDENTIAL_UNAVAILABLE")
    return result.stdout.decode().strip()


def config(index, cwd, branch, interval, ttl, candidate_context=None):
    rs.validate(index)
    github.text(branch)
    remote.check(type(interval) in (int, float) and 60 <= interval <= 86400,
                 "INTERVAL_MUST_BE_60_TO_86400_SECONDS")
    remote.check(type(ttl) in (int, float) and interval <= ttl <= 86400, "INVALID_FRESHNESS_TTL")
    result = {"index": index, "cwd": str(cwd.resolve()), "branch": branch, "interval": float(interval), "ttl": float(ttl)}
    if candidate_context is not None:
        result["candidate_context"] = github.github_policy.github_context.validate(candidate_context)
    return result


def private_json(path):
    records.metadata(path)
    remote.check(path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o077 == 0,
                 "STATE_FILE_NOT_PRIVATE")
    return io.read_json(path)


def collect(configured, root, token=None, timeout=120, credential_failure=False):
    """One durable cycle. Caller holds the single-writer lock."""
    index, cwd = configured["index"], Path(configured["cwd"])
    rs.target_source(cwd, index["repository"])
    cache = {}
    if (root / "cache.json").exists():
        try:
            cached = private_json(root / "cache.json")
            if (cached.get("repository") == index["repository"] and isinstance(cached.get("entries"), dict)
                    and len(cached["entries"]) <= 256):
                cache = cached["entries"]
        except (ValueError, OSError, TypeError):
            pass  # Cache is optional, never an acceptance source.
    client = github.Client(index["repository"], token, cache, timeout=timeout)
    started = time.time()
    snapshot = github.snapshot(index, cwd, configured["branch"], client, credential_failure,
                               candidate_context=configured.get("candidate_context"))
    deployment = (github.deployments(client, index, snapshot["target"]) if not credential_failure else
                  {"status": "QUERY_FAILED", "discovery_complete": False, "evidence": [],
                   "environments": [], "diagnostic": "CREDENTIAL_UNAVAILABLE"})
    snapshot["recommended_interval"] = max(snapshot["recommended_interval"], client.delay,
                                            deployment.get("retry_after", 0))
    if time.time() > started + configured["ttl"]:
        snapshot["status"] = "EXPIRED_CAPTURE"
    result = rs.projection(index, cwd, remote=deployment["evidence"], source_pin=snapshot["target"])
    result["required_checks"] = snapshot
    result["deployment_inventory"] = deployment
    if not deployment["discovery_complete"]:
        result["channels"]["deployment"]["status"] = "REMOTE_QUERY_FAILED"
    result["continuous_collection"] = {"schema": "golem.status-collector.v1",
        "config_sha256": io.identity(configured), "observed_at": started,
        "expires_at": started + configured["ttl"], "historical_capture": True,
        "collector_kind": "SUPERVISED_FOREGROUND", "deployment_health_verified": False}
    cycle = root / ("cycle-" + uuid.uuid4().hex)
    records.private_directory(cycle)
    responses = io.encoded(client.exchanges)
    remote.check(len(responses) <= 24 * 1024 * 1024, "ENCODED_CAPTURE_LIMIT")
    records.save(cycle / "responses.json", responses)
    encoded_result = io.encoded(result)
    remote.check(len(encoded_result) <= 4 * 1024 * 1024, "ENCODED_RESULT_LIMIT")
    records.save(cycle / "result.json", encoded_result)
    records.save(cycle / "manifest.json", io.encoded({p.name: io.digest(p) for p in sorted(cycle.iterdir())}))
    # Completed immutable cycle first, then atomic mutable pointer. A crash leaves
    # an orphan capture, never a pointer to an unfinished successful observation.
    previous = private_json(root / "latest.json") if (root / "latest.json").exists() else {}
    failed = (snapshot["status"] == "DISCOVERY_FAILED" or snapshot.get("policy_evidence_failed", False)
              or deployment["status"] == "QUERY_FAILED")
    failures = previous.get("consecutive_failures", 0) + 1 if failed else 0
    delay = max(configured["interval"], snapshot["recommended_interval"],
                min(3600, 60 * 2 ** min(failures, 6)) if failures else 0)
    atomic(root / "latest.json", {"cycle": cycle.name, "manifest_sha256": io.digest(cycle / "manifest.json"),
        "config_sha256": io.identity(configured), "not_before": time.time() + delay,
        "consecutive_failures": failures})
    if len(io.encoded(cache)) <= 16 * 1024 * 1024:
        atomic(root / "cache.json", {"repository": index["repository"], "entries": cache})
    return result


def read(configured, root, now=None):
    head = private_json(root / "latest.json")
    remote.check(isinstance(head.get("cycle"), str) and re.fullmatch(r"cycle-[0-9a-f]{32}", head["cycle"])
                 and head.get("config_sha256") == io.identity(configured), "COLLECTOR_SCOPE_MISMATCH")
    cycle = directory(root / head["cycle"])
    manifest = private_json(cycle / "manifest.json")
    remote.check(io.digest(cycle / "manifest.json") == head.get("manifest_sha256")
                 and set(manifest) == {"responses.json", "result.json"}, "MANIFEST_MISMATCH")
    for name, digest in manifest.items():
        records.metadata(cycle / name)
        remote.check(io.digest(cycle / name) == digest, "CAPTURE_INTEGRITY_FAILURE")
    result = private_json(cycle / "result.json")
    observation = result["continuous_collection"]
    current_time = time.time() if now is None else now
    fresh = observation["observed_at"] <= current_time <= observation["expires_at"]
    source = rs.target_source(Path(configured["cwd"]), configured["index"]["repository"])
    required = result["required_checks"]
    if source != required["target"]:
        required["status"] = "STALE_SOURCE"
    elif not fresh:
        required["status"] = "EXPIRED_CAPTURE"
    observation.update(freshness="WITHIN_TTL" if fresh else "EXPIRED_OR_CLOCK_ROLLBACK",
                       collector_liveness="NOT_INFERRED", cycle=str(cycle))
    # This reader never promotes saved evidence to native/live acceptance.
    deployment = result["deployment_inventory"]
    historical = [{**r, "freshness": "HISTORICAL_CAPTURE", "remote_latest_verified": False}
                  for r in deployment["evidence"]]
    if not fresh:
        historical = [{**r, "status": "EXPIRED_CAPTURE", "remote_latest_verified": False} for r in historical]
    deployment = {**deployment, "evidence": historical, "freshness": "WITHIN_TTL" if fresh else "EXPIRED_CAPTURE"}
    current = rs.projection(configured["index"], Path(configured["cwd"]), remote=historical, source_pin=source)
    current.update(required_checks=required, continuous_collection=observation, deployment_inventory=deployment)
    if not deployment["discovery_complete"]:
        current["channels"]["deployment"]["status"] = "REMOTE_QUERY_FAILED"
    if not current["source_stable"]:
        required["status"] = "SOURCE_CHANGED"
    return current


def run(configured, root, token_source="env", follow=False, max_cycles=0, stop=None,
        max_bytes=512 * 1024 * 1024):
    root = directory(root)
    cwd = Path(configured["cwd"])
    remote.check(root != cwd and cwd not in root.parents, "STATE_OVERLAPS_SOURCE")
    remote.check(type(max_cycles) is int and max_cycles >= 0, "INVALID_CYCLE_LIMIT")
    stop = stop or threading.Event()
    with lock(root):
        failures, count = 0, 0
        while not stop.is_set():
            if (root / "latest.json").exists():
                head = private_json(root / "latest.json")
                remote.check(type(head.get("not_before", 0)) in (float, int), "INVALID_RESTART_DELAY")
                remaining = head.get("not_before", 0) - time.time()
                if remaining > 0 and stop.wait(remaining):
                    break
            # Never erase audit history implicitly. An operator rotates the private root.
            total = 0
            for parent, dirs, files in os.walk(root, followlinks=False):
                remote.check(not any((Path(parent) / d).is_symlink() for d in dirs), "SYMLINK_STATE_PATH")
                for name in files:
                    file = Path(parent) / name
                    remote.check(not file.is_symlink(), "SYMLINK_STATE_FILE")
                    total += file.stat().st_size
            remote.check(total + 64 * 1024 * 1024 <= max_bytes, "CAPTURE_QUOTA_REACHED_ROTATE_STATE_ROOT")
            credential_failure = False
            try:
                token = credential(token_source, root, cwd)
                remote.check(not token or len(token) <= 4096 and all(32 < ord(c) < 127 for c in token),
                             "INVALID_CREDENTIAL")
            except (ValueError, OSError, subprocess.SubprocessError):
                token, credential_failure = None, True
            result = collect(configured, root, token, credential_failure=credential_failure)
            count += 1
            state = result["required_checks"]["status"]
            failures = failures + 1 if (state == "DISCOVERY_FAILED"
                or result["required_checks"].get("policy_evidence_failed", False)
                or result.get("deployment_inventory", {}).get("status") == "QUERY_FAILED") else 0
            sys.stdout.buffer.write(io.encoded({"schema": "golem.status-collector-progress.v1",
                "cycle": count, "status": state, "discovery_complete": result["required_checks"]["discovery_complete"],
                "evidence": str(root / "latest.json")}))
            sys.stdout.flush()
            if not follow or max_cycles and count >= max_cycles:
                return result
            delay = max(configured["interval"], result["required_checks"]["recommended_interval"],
                        min(3600, 60 * 2 ** min(failures, 6)) if failures else 0)
            stop.wait(delay)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("collect", "status"))
    parser.add_argument("index", type=Path)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--candidate-context", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=60)
    parser.add_argument("--ttl", type=float, default=180)
    parser.add_argument("--credentials", choices=("env", "gh"), default="env")
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        configured = config(io.read_json(args.index), args.cwd, args.branch, args.interval, args.ttl,
                            io.read_json(args.candidate_context) if args.candidate_context else None)
        if args.mode == "status":
            result = read(configured, directory(args.state))
            sys.stdout.buffer.write(io.encoded(result))
        else:
            stop = threading.Event()
            previous = {s: signal.signal(s, lambda *_: stop.set()) for s in (signal.SIGINT, signal.SIGTERM)}
            try:
                result = run(configured, args.state, args.credentials, args.follow, args.max_cycles, stop)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
        return 0 if result is None or (result["required_checks"]["status"] in (
            "PASS", "NOT_REQUIRED", "COMMIT_ONLY_DIRTY_SOURCE") and all(channel["status"] not in (
            "INVALID_EVIDENCE", "REMOTE_QUERY_FAILED") for channel in result["channels"].values())) else 1
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        sys.stderr.buffer.write(io.encoded({"schema": "golem.status-collector-error.v1",
            "diagnostic": "COLLECTOR_CONFIGURATION_ACCESS_OR_INTEGRITY_FAILURE", "execution_authorized": False}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
