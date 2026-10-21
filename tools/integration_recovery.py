"""Owner-only D5 quarantine clearance; never edits or redispatches native history."""
import argparse
from pathlib import Path
import sys
import tempfile

import execution_record as records
import integration_backend as backend
import integration_contract as c
import integration_registry as r
import integration_lifecycle as life
import integration_update as update

REVIEW = c.obj({"schema": {"const": "golem.integration-effect-review.v1"},
    "disposition": c.enum("NO_EFFECTS_CONFIRMED", "EFFECTS_RECONCILED"),
    "processes": {"const": "STOPPED_OWNER_ATTESTED"}, "reason": c.ID,
    "evidence": c.array(c.PIN)})
SPEC = c.obj({"project_id": c.ID, "work_id": c.ID, "evidence_id": {"type": "string",
    "pattern": "^mutation-[a-f0-9]{64}$", "maxLength": 73}, "binding": c.BINDING,
    "owner_review": c.PIN, "stopped": c.array(update.ACK)})


def audit_inventory(path):
    # Resolution publication is independent of the preserved D4 evidence.
    rows = {}
    for p in sorted(path.rglob("*")):
        if p.name in ("d5-resolution.json", "d5-resolution-ref.json"):
            continue
        c.require(len(rows) < 16384 and not p.is_symlink(), "AUDIT_QUOTA")
        rows[str(p.relative_to(path))] = [p.stat().st_mode, c.sha(r.regular(p, c.MAX_NATIVE)) if p.is_file() else None]
    return c.sha(c.encoded(rows))


def facts(manager, request):
    c.bounded(request)
    c._validate(request, SPEC)
    state, lifecycle_sha = manager.frozen(request["project_id"])
    enrollment, before = manager.enrollment(request["project_id"])
    update.acknowledge(enrollment, request["stopped"], "STOPPED_OWNER_ATTESTED")
    manager.quiet(enrollment)
    project = manager.registry.authorize(request["binding"], request["work_id"], "record")
    c.require(request["binding"]["project_id"] == request["project_id"], "RECOVERY_SCOPE")
    path = manager.registry.root / request["evidence_id"]
    intent = c.decode(r.regular(path / "intent.json", private=True))
    from integration_mutations import Service
    try:
        original_result = Service._result(path)
    except (OSError, ValueError):
        original_result = None
    c.require(original_result is None or original_result["state"] == "COMMIT_UNKNOWN", "NOT_QUARANTINED")
    c.require(intent["binding"]["project_id"] == request["project_id"] and intent["work_id"] == request["work_id"], "RECOVERY_SCOPE")
    work = next(w for w in project["works"] if w["work_id"] == request["work_id"])
    lineage = c.sha(c.encoded({"identity": work["identity"], "genesis": work["genesis_sha256"]}))
    c.require(intent["lineage"] == lineage, "RECOVERY_LINEAGE")
    native_bytes = r.regular(path / "request.json", private=True)
    c.require(c.sha(native_bytes) == intent["native_sha256"], "ORIGINAL_REQUEST_CHANGED")
    native = c.decode(native_bytes)
    review = c.decode(update.pinned(request["owner_review"]))
    c._validate(review, REVIEW)
    for pin in review["evidence"]:
        update.pinned(pin, c.MAX_NATIVE)
    # Safe native state is necessary, never sufficient evidence of no effects.
    observed = manager.observe(project)
    approval = None
    if intent["tool"] == "execution_request":
        action = c.decode(update.pinned(intent["action"]["action"]))
        c.require(c.sha(c.encoded(action)) == intent["action_sha256"], "ORIGINAL_ACTION_CHANGED")
        request_receipt = action["approval"]["request_receipt"]
        query = {"schema_version": 1, "operation": "recover", "request_receipt": request_receipt}
        output = Path(tempfile.mkdtemp(prefix="read-d5-recover-", dir=manager.registry.root))
        records.save(output / "request.json", c.encoded(query))
        process = records.capture([project["cli"]["path"], "--output-mode", "full", "approval", "call", work["path"],
            str(output / "request.json")], output, backend.TIMEOUT_SECONDS, cwd=output,
            observe_source=False, env=backend.ENVIRONMENT, limit=c.MAX_NATIVE)
        c.require(process["returncode"] == 0 and process["recording"] == "RECORDED", "NATIVE_RECOVERY_UNAVAILABLE")
        approval = c.decode(r.regular(output / "stdout.log", c.MAX_NATIVE, private=True), c.MAX_NATIVE)
        c.require(approval.get("state") in ("CONSUMED", "RECORDED", "REVOKED", "DENIED", "EXPIRED"), "APPROVAL_STILL_DISPATCHABLE")
    return {"before": before, "lifecycle_sha256": lifecycle_sha, "freeze_id": state["freeze_id"],
        "intent_sha256": c.sha(c.encoded(intent)), "lineage": lineage,
        "retired": life.retired_identity(intent["tool"], native), "audit_sha256": audit_inventory(path),
        "native_views": observed, "approval_observation_sha256": c.sha(c.encoded(approval))}


def plan(manager, request):
    with manager.registry.locked():
        return {"schema": "golem.integration-recovery-plan.v1", "request": request,
            "facts": facts(manager, request), "registry": str(manager.registry.root),
            "registry_identity": manager.registry.root_identity, "producer": update.producer()}


def apply(manager, value, digest, *, approve_recovery=False):
    c.require(approve_recovery is True, "OWNER_RECOVERY_APPROVAL_REQUIRED")
    c.require(c.sha(c.encoded(value)) == digest, "PLAN_DIGEST")
    with manager.registry.locked(exclusive=True):
        expected = {"schema": "golem.integration-recovery-plan.v1", "request": value["request"],
            "facts": facts(manager, value["request"]), "registry": str(manager.registry.root),
            "registry_identity": manager.registry.root_identity, "producer": update.producer()}
        c.require(value == expected, "RECOVERY_PLAN_STALE")
        retained = manager.registry.root / ("d5-recovery-plan-" + digest + ".json")
        if retained.exists():
            c.require(r.regular(retained, private=True) == c.encoded(value), "RECOVERY_PLAN_CORRUPT")
        else:
            manager.registry._publish(retained, c.encoded(value))
        request, observed = value["request"], value["facts"]
        certificate = {"schema": "golem.integration-resolution.v1", "intent_sha256": observed["intent_sha256"],
            "retired": observed["retired"], "freeze_id": observed["freeze_id"], "lineage": observed["lineage"],
            "work_id": request["work_id"], "owner_review": request["owner_review"],
            "audit_sha256": observed["audit_sha256"], "native_views_sha256": c.sha(c.encoded(observed["native_views"])),
            "approval_observation_sha256": observed["approval_observation_sha256"],
            "plan_sha256": digest, "native_result_promoted": False, "execution_authorized": False}
        target = manager.registry.root / request["evidence_id"]
        for name, data in (("d5-resolution.json", c.encoded(certificate)),
                           ("d5-resolution-ref.json", c.encoded({"sha256": c.sha(c.encoded(certificate))}))):
            path = target / name
            if path.exists():
                c.require(r.regular(path, private=True) == data, "RECOVERY_PUBLICATION_CONFLICT")
            else:
                records.save(path, data)
        return {"state": "QUARANTINE_CLEARED_ORIGINAL_RESULT_UNCHANGED", "certificate": r.file_pin(target / "d5-resolution.json"),
            "native_state_changed": False, "native_result_promoted": False, "automatic_retry_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("schema", "plan", "apply"))
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--reviewed-plan-sha256")
    parser.add_argument("--approve-recovery", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "schema":
            result = {"$schema": "https://json-schema.org/draft/2020-12/schema", **SPEC}
        else:
            c.require(args.registry is not None and args.input is not None, "INPUT_REQUIRED")
            manager = update.Manager(r.Registry(args.registry))
            value = c.decode(r.regular(args.input, private=True))
            result = plan(manager, value) if args.command == "plan" else apply(manager, value,
                args.reviewed_plan_sha256, approve_recovery=args.approve_recovery)
        sys.stdout.buffer.write(c.encoded(result))
        return 0
    except (c.IntegrationError, OSError, ValueError, KeyError, TypeError) as error:
        sys.stderr.write(c.encoded({"state": "QUARANTINE_RETAINED", "code": getattr(error, "code", "IO_OR_CONTRACT_ERROR"),
            "automatic_retry_allowed": False, "next_operation": "INSPECT_ORIGINAL_REQUEST_EFFECTS_AND_OWNER_REVIEW"}).decode())
        return 1


if __name__ == "__main__":
    sys.exit(main())
