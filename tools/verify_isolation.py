"""31G fixture qualification: exact coverage, private receipts, no live-agent claim."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from verify_agent import digest, private_directory, save
from verify_runtime import run

GROUPS = {
    "git_matrix": ("workspace_lifecycle", "change_inventory_unit", "change_inventory_integration",
                   "execution_change_cli", "execution_change_large_cli"),
    "crash": ("proof_publication_faults", "candidate_model", "candidate_integration", "journal_syscall_faults"),
    "security": ("execution_boundary_cli", "execution_inventory", "execution_bundle_cli",
                 "fuzz_seeds", "mutation_document", "memory_core_oom", "supervisor_stream"),
    "compatibility": ("proof_cli", "completion_historical_store", "execution_cli",
                      "header_candidate", "header_workspace", "header_proof", "admission_work_integration",
                      "candidate_cli_host"),
}
BINDINGS = {"language_contracts": ("binding_abi", "binding_python", "binding_typescript")}
LIMITATIONS = ("actual-agent identity and billing", "physical power-loss/filesystem guarantees",
               "other operating systems", "production sandbox containment", "statistical performance improvement",
               "live-agent operation of the current-agent CLI host", "physical CPU/memory quota enforcement",
               "automatic selected patch application", "unbounded tracked repository inventory")


def qualify(build, bindings, output, ctest="ctest", timeout=900):
    output = private_directory(output)
    core = run(build, output / "core", ctest, timeout, groups=GROUPS,
               schema="golem.isolation-fixtures.v1", limitations=LIMITATIONS)
    languages = run(bindings, output / "bindings", ctest, timeout, groups=BINDINGS,
                    schema="golem.isolation-bindings.v1", limitations=LIMITATIONS)
    report = {"schema": "golem.isolation-validation.v1", "authority": "DERIVED_ONLY",
        "status": "PASS" if core["status"] == languages["status"] == "PASS" else "FAIL",
        "actual_agent_verified": False, "release_ready": False,
        "installation_verified": False, "provider_invoked": False,
        "production_candidate_host_verified": False,
        "physical_resource_limits_verified": False,
        "selected_patch_application_verified": False,
        "not_verified": list(LIMITATIONS),
        "reports": {name: digest(output / name / "report.json") for name in ("core", "bindings")}}
    save(output / "report.json", (json.dumps(report, indent=2) + "\n").encode())
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--bindings", type=Path, required=True, help="normal build with Python AND Node contracts")
    p.add_argument("--output", type=Path, required=True, help="new private directory; never upload raw logs")
    p.add_argument("--ctest", default="ctest")
    p.add_argument("--timeout", type=int, default=900)
    a = p.parse_args()
    if not 1 <= a.timeout <= 3600:
        p.error("timeout must be 1..3600 seconds per group")
    try:
        report = qualify(a.build, a.bindings, a.output, a.ctest, a.timeout)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print("31G qualification incomplete; inspect the private output directory.", file=sys.stderr)
        return 1
    print(json.dumps({k: report[k] for k in ("status", "actual_agent_verified", "release_ready")}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
