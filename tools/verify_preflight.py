"""Bounded pre-use audit of phases 30-32. Never a production-readiness certificate."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from verify_runtime import GROUPS as RUNTIME, run
from verify_isolation import GROUPS as ISOLATION
from verify_orchestration import GROUPS as ORCHESTRATION


def audit_groups():
    groups = {"independent-contracts": ("json_contract", "admission_contract")}
    seen = set(groups["independent-contracts"])
    for phase, source in (("30", RUNTIME), ("31", ISOLATION), ("32", ORCHESTRATION)):
        for name, tests in source.items():
            selected = tuple(test for test in tests if test not in seen)
            if selected:
                groups[f"{phase}-{name}"] = selected
                seen.update(selected)
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 3600:
        parser.error("timeout must be 1..3600 seconds per group")
    try:
        report = run(args.build, args.output, "ctest", args.timeout,
                     groups=audit_groups(), schema="golem.preflight-validation.v1",
                     extra_inputs=(Path(__file__),), limitations=[
                         "Bounded tests, not exhaustive interleavings or a formal proof.",
                         "No live provider, billing, production deployment or physical power loss.",
                         "Only the recorded host and build; no cross-platform claim.",
                         "Curated mutation experiments must be run and reported separately.",
                     ])
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "actual_agent_verified": False,
                      "release_ready": False}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
