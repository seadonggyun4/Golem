"""32G reproducible fixture evidence; never certifies live agents or migration safety."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from verify_runtime import run

GROUPS = {
    "migration": ("completion_historical_store", "workflow_cli", "workflow_template_cli"),
    "authority": ("role_contract_cli", "session_binding_cli", "approval_cli"),
    "recovery": ("orchestration_integration", "candidate_diff_integration"),
    "observation": ("event_reader_api", "event_bridge_backpressure", "event_bridge_http"),
    "hardening": ("orchestration_validation_report", "memory_core_oom", "fuzz_seeds", "mutation_document",
                  "header_workflow_template", "header_approval", "header_session_binding"),
}
LIMITATIONS = [
    "Synthetic fixtures are not live Codex/Claude validation.",
    "Historical fixture compatibility is not arbitrary old-binary downgrade safety.",
    "Process fault tests are not exhaustive power-loss or filesystem verification.",
    "This invocation verifies only its recorded host/configuration, not other platforms.",
    "Installed language bindings and stable-runner performance require separate checks.",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ctest", default="ctest")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 3600:
        parser.error("timeout must be 1..3600 seconds per group")
    try:
        report = run(args.build, args.output, args.ctest, args.timeout, groups=GROUPS,
                     schema="golem.orchestration-validation.v1", limitations=LIMITATIONS,
                     extra_inputs=(Path(__file__),))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"status": report["status"], "actual_agent_verified": False,
                      "release_ready": False}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
