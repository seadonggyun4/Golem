"""Join JUnit failures with environment observations; never infer causal proof."""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

GROUPS = {
    "admission_open": "runtime_events_durable admission_faults admission_basic admission_fairness admission_nested admission_capacity admission_recovery admission_identity admission_corruption admission_ownership admission_guards event_reader_api worker_fault_thread worker_fault_reap worker_limits worker_overlap worker_reserve worker_echo worker_exit worker_signal worker_overflow worker_lease worker_timeout worker_missing worker_cancel worker_recovery",
    "qa_result": "execution_change_large_cli execution_cli",
    "environment": "workspace_lifecycle benchmark_contract",
    "session_bootstrap": "runtime_canary admission_work_integration agent_session_cli session_binding_cli approval_cli runtime_profile_cli",
    "completion_reentry": "outcome_cli outcome_bundle_cli outcome_metrics_cli reentry_cli completion_cli role_contract_cli agent_conformance_cli workflow_template_cli",
    "candidate_host": "candidate_cli_host runtime_events_cli orchestration_integration candidate_integration candidate_diff_integration orchestration_benchmark",
}
BY_TEST = {test: group for group, names in GROUPS.items() for test in names.split()}


def classify(environment, xml):
    if environment.get("schema") != "golem.environment.v1":
        raise ValueError("unsupported environment report")
    root = ET.fromstring(xml)
    seen, failures, skipped = set(), [], []
    for case in root.iter("testcase"):
        name = case.get("name")
        if not name or name in seen:
            raise ValueError("missing or duplicate testcase name")
        seen.add(name)
        if case.find("skipped") is not None:
            skipped.append(name)
        if case.find("failure") is not None or case.find("error") is not None:
            group = BY_TEST.get(name, "unclassified")
            failures.append({"test": name, "group": group, "cause": "UNDETERMINED",
                             "dependency_candidate": group in
                             ("admission_open", "session_bootstrap", "completion_reentry", "candidate_host")})
    if not seen:
        raise ValueError("empty test inventory")
    counts = {"tests": len(seen), "failures": sum(c.find("failure") is not None
              for c in root.iter("testcase")), "errors": sum(c.find("error") is not None
              for c in root.iter("testcase")), "skipped": len(skipped)}
    for key, observed in counts.items():
        if key in root.attrib and int(root.attrib[key]) != observed:
            raise ValueError("JUnit summary disagrees with testcase records")
    return {"schema": "golem.failure-triage.v1", "tests_observed": len(seen),
            "status": "REQUIRES_REVIEW" if failures or skipped or environment["status"] != "PASS"
                      else "OBSERVED_TESTS_PASS",
            "environment_status": environment["status"], "failures": failures,
            "skipped": skipped, "causality_proven": False,
            "limitation": "Grouping is a triage hypothesis. Inspect per-test output; no failure is excused."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True, type=Path)
    parser.add_argument("--junit", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = classify(json.loads(args.environment.read_text()), args.junit.read_bytes())
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        print(json.dumps({"status": "INVALID_EVIDENCE", "error": type(exc).__name__}))
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "OBSERVED_TESTS_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
