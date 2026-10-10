"""Reviewed API boundary inventory; source tripwire, not arbitrary-C proof."""
from pathlib import Path
import re
import sys

CORE_APIS = {
    "golem_document_store_create", "golem_document_submit", "golem_agent_session_call",
    "golem_agent_session_resume_context",
    "golem_session_binding_call", "golem_approval_call", "golem_execution_call_receipted",
    "golem_execution_call", "golem_execution_call_authorized", "golem_role_call",
    "golem_research_call", "golem_completion_call", "golem_reentry_call",
    "golem_workspace_call", "golem_candidate_call", "golem_runtime_profile_register",
    "golem_runtime_link_run", "golem_context_publish", "golem_proof_publish",
    "golem_admission_publish_work",
}
CONTROL_APIS = {
    "golem_admission_close", "golem_admission_cancel", "golem_admission_settle",
    "golem_admission_release", "golem_worker_cancel", "golem_worker_heartbeat",
    "golem_worker_acknowledge", "golem_worker_close", "golem_daemon_close",
    "golem_admission_identity", "golem_admission_lookup", "golem_worker_events", "golem_worker_inspect",
}
EXTENDED_APIS = CONTROL_APIS | {
    "golem_admission_open", "golem_admission_open_diagnostic", "golem_admission_identity",
    "golem_admission_enqueue", "golem_admission_lookup", "golem_admission_grant",
    "golem_admission_resize", "golem_admission_begin", "golem_admission_dispatch",
    "golem_worker_open", "golem_worker_submit", "golem_worker_start", "golem_worker_events",
    "golem_worker_inspect", "golem_daemon_open", "golem_daemon_tick", "golem_daemon_init",
    "golem_daemon_inspect", "golem_daemon_submit", "golem_daemon_recover",
    "golem_resource_run", "golem_inventory_capture", "golem_harness_probe",
}
LIFECYCLE_REQUIRED = {
    "golem_runtime_cancel", "golem_runtime_report_get", "golem_runtime_checkpoint",
    "golem_runtime_heartbeat", "golem_journal_checkpoint_get", "golem_journal_append",
    "golem_journal_close", "golem_document_store_close",
}
RELEASE_APIS = {"golem_runtime_free"}
LIFECYCLE_APIS = LIFECYCLE_REQUIRED | RELEASE_APIS | {
    "golem_runtime_create", "golem_runtime_recover", "golem_runtime_step",
    "golem_runtime_drive", "golem_runtime_lease_bind", "golem_journal_open",
    "golem_journal_recover", "golem_document_store_open",
}
REQUIRED_APIS = CONTROL_APIS | LIFECYCLE_REQUIRED
APIS = CORE_APIS | EXTENDED_APIS | LIFECYCLE_APIS
REVIEWED_HEADERS = {"admission.h", "daemon.h", "worker.h", "resource.h", "inventory.h", "runtime.h"}
UNRECORDED = {
    "golem_worker_diagnostics": "I/O-free recovery observation accessor",
    "golem_worker_recording_status": "I/O-free recorder outcome accessor",
    "golem_inventory_policy_validate": "Pure in-memory validation",
    "golem_inventory_compare": "Pure in-memory comparison",
}

def check(root):
    observed = []
    required = []
    released = []
    for path in (root / "src").rglob("*.c"):
        source = path.read_text()
        observed.extend(re.findall(r"GOLEM_RECORDED_(?:(?:REQUIRED|RELEASE)_)?API\(\s*(golem_\w+)\s*,", source))
        required.extend(re.findall(r"GOLEM_RECORDED_REQUIRED_API\(\s*(golem_\w+)\s*,", source))
        released.extend(re.findall(r"GOLEM_RECORDED_RELEASE_API\(\s*(golem_\w+)\s*,", source))
    if set(released) != RELEASE_APIS or len(released) != len(RELEASE_APIS):
        raise AssertionError(f"Review changed destructor boundaries: {released!r}")
    if set(required) != REQUIRED_APIS or len(required) != len(REQUIRED_APIS):
        raise AssertionError(f"Review changed required-operation recording boundaries: {required!r}")
    if set(observed) != APIS or len(observed) != len(APIS):
        raise AssertionError(f"Review changed recording boundaries: {observed!r}")
    declared = set()
    for path in (root / "include/golem").glob("*.h"):
        header = path.read_text()
        declared.update(re.findall(r"(?:golem_status|void)\s+(golem_\w+)\s*\(", header))
        if path.name in REVIEWED_HEADERS:
            exports = set(re.findall(r"golem_status\s+(golem_\w+)\s*\(", header))
            if exports - APIS - UNRECORDED.keys():
                raise AssertionError(f"Unreviewed API in {path.name}: {exports - APIS - UNRECORDED.keys()}")
        calls = set(re.findall(r"golem_status\s+(golem_\w+_call(?:_authorized|_receipted)?)\s*\(", header))
        missing = calls - APIS - {"golem_record_call"}
        if missing:
            raise AssertionError(f"Unreviewed public command API: {missing}")
    if APIS - declared:
        raise AssertionError(f"Recorded API missing public declaration: {APIS - declared}")
    if UNRECORDED.keys() - declared or UNRECORDED.keys() & APIS:
        raise AssertionError("Stale/overlapping explicit recording exclusions")
    print(f"{len(APIS)} automatic API boundaries match")

if __name__ == "__main__":
    check(Path(sys.argv[1]))
