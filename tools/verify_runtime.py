"""30G local contract evidence. Fixture PASS never certifies release/agent readiness."""
import argparse
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from verify_agent import capture, digest, private_directory, save

# Exact required names, not a regex that can silently select no tests.
GROUPS = {
    "compatibility": ("adapter_descriptor_compatibility", "runtime_profile_cli",
                      "completion_historical_store", "runtime_canary"),
    "faults": ("admission_faults", "worker_fault_thread", "worker_fault_reap",
               "runtime_events_durable", "runtime_events_worker", "worker_cancel",
               "worker_recovery", "supervisor_exit_late-eof", "memory_core_oom",
               "journal_syscall_faults", "recovery_publication_faults"),
    "parsers": ("fuzz_seeds", "mutation_adapter_json", "mutation_adapter_msgpack",
                "mutation_document", "mutation_admission"),
    "model": ("admission_explore", "admission_fairness", "admission_recovery"),
    "projection": ("context_projection_cli", "runtime_events_cli"),
}


def adjudicate(path, expected):
    """Exit zero is insufficient: missing, duplicated, skipped cases fail closed."""
    if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
        return False
    try:
        cases = list(ET.parse(path).getroot().iter("testcase"))
    except ET.ParseError:
        return False
    names = [case.get("name") for case in cases]
    return (bool(expected) and all(isinstance(name, str) for name in names) and
            sorted(names) == sorted(expected) and
            all(case.get("status") == "run" and
                not any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
                for case in cases))


def run(build, output, ctest, timeout):
    build = build.resolve()
    cli = build / "golem"
    if not cli.is_file() or not (build / "CMakeCache.txt").is_file():
        raise ValueError("configured and built Golem directory required")
    inventory = subprocess.run([ctest, "--test-dir", str(build), "--show-only=json-v1"],
                               capture_output=True, check=True, timeout=30)
    tests = json.loads(inventory.stdout)["tests"]
    available = {test["name"] for test in tests}
    missing = sorted(set(sum(GROUPS.values(), ())) - available)
    if missing:
        raise ValueError("required tests missing: " + ", ".join(missing))
    inputs = {str(Path(arg).resolve()) for test in tests
              if test["name"] in set(sum(GROUPS.values(), ()))
              for arg in test.get("command", []) if Path(arg).is_file()}
    inputs.add(str(Path(__file__).resolve()))
    hashes = {path: digest(Path(path)) for path in sorted(inputs)}
    output = private_directory(output)
    report = {"schema": "golem.runtime-validation.v1", "authority": "DERIVED_ONLY",
              "platform": platform.platform(), "cli_sha256": digest(cli),
              "cmake_cache_sha256": digest(build / "CMakeCache.txt"),
              "runner_sha256": digest(Path(__file__)), "groups": {},
              "actual_agent_verified": False, "release_ready": False,
              "not_verified": ["old-binary downgrade rejection", "cross-host compatibility",
                               "live-agent canary", "stable-runner performance thresholds"]}
    report["input_files"] = hashes
    save(output / "inventory.json", inventory.stdout)
    for name, required in GROUPS.items():
        directory = private_directory(output / name)
        junit = directory / "results.xml"
        regex = "^(" + "|".join(re.escape(test) for test in required) + ")$"
        process = capture([ctest, "--test-dir", build, "-R", regex, "--output-on-failure",
                           "--output-junit", junit], directory, timeout)
        passed = (process["returncode"] == 0 and process["reason"] == "EXIT" and
                  adjudicate(junit, required))
        if junit.exists():
            junit.chmod(0o600)
        report["groups"][name] = {"status": "PASS" if passed else "FAIL",
                                  "required_tests": required, "process": process,
                                  "junit_sha256": digest(junit) if junit.is_file() else None}
        # Preserve each completed group even if a later invocation is interrupted.
        save(directory / "result.json", json.dumps(report["groups"][name], indent=2).encode())
    unchanged = (digest(cli) == report["cli_sha256"] and
                 all(Path(path).is_file() and digest(Path(path)) == value
                     for path, value in hashes.items()))
    report["status"] = "PASS" if unchanged and all(
        g["status"] == "PASS" for g in report["groups"].values()) else "FAIL"
    report["binary_unchanged"] = unchanged
    save(output / "report.json", json.dumps(report, indent=2).encode())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ctest", default="ctest")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 3600:
        parser.error("timeout must be 1..3600 seconds per group")
    try:
        report = run(args.build, args.output, args.ctest, args.timeout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "actual_agent_verified": False,
                      "release_ready": False}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
