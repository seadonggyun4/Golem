"""Explicit Linux kernel resource fixture; never creates/delegates a cgroup."""
import argparse
import json
from pathlib import Path
import subprocess


def counters(scope, filename):
    result = {}
    for line in (scope / filename).read_text().splitlines():
        key, value = line.split()
        if key in result or not value.isdecimal():
            raise ValueError("invalid kernel counter")
        result[key] = int(value)
    return result


def verify(build, scope):
    build, scope = build.resolve(strict=True), scope.resolve(strict=True)
    if counters(scope, "cgroup.events")["populated"] != 0:
        raise ValueError("test scope is not empty")
    files = {"cpu.stat": "nr_throttled", "memory.events": "oom_kill", "pids.events": "max"}
    before = {name: counters(scope, name)[key] for name, key in files.items()}
    for mode in ("normal", "memory", "cpu", "tasks"):
        subprocess.run([str(build / "tests/c/golem_test_resource"),
                        str(build / "golem-cgroup-exec"), str(scope), mode],
                       check=True, timeout=15, capture_output=True)
        if counters(scope, "cgroup.events")["populated"] != 0:
            raise ValueError("test scope remains populated")
    delta = {name: counters(scope, name)[key] - before[name] for name, key in files.items()}
    if any(value <= 0 for value in delta.values()):
        raise ValueError("missing actual kernel enforcement evidence")
    return {"schema": "golem.resource-kernel-fixture.v1", "status": "PASS",
            "kernel_counter_deltas": delta, "scope_empty": True,
            "provider_invoked": False, "sandbox_verified": False,
            "candidate_integration_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path,
                        help="precreated empty private test cgroup, never a shared scope")
    args = parser.parse_args()
    try:
        report = verify(args.build, args.scope)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        print(json.dumps({"status": "FAIL", "scope_empty": False,
                          "reason": "kernel fixture incomplete; inspect dedicated scope"}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
