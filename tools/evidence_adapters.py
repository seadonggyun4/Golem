"""Domain adapters for the common evidence contract; no acceptance predicate."""
import argparse
from pathlib import Path
import sys

import agent_io as io
import evidence_contract as ec
from judgment_record import binding, validate_binding


def observation(bundle, revision, step_id, work):
    binding(work)
    record, actual = io.load_bundle(bundle)
    ec.require(actual == revision, "Observation revision mismatch")
    validate_binding(record, work)
    plan = io.validate_plan(io.read_json(bundle / "plan.json"))
    ec.require(io.identity(plan) == record["plan_sha256"], "Plan digest mismatch")
    ec.require(step_id in {c["id"] for c in plan["commands"]}, "Step not in command plan")
    step = next((s for s in record["steps"] if s["id"] == step_id), None)
    ec.require(step is not None, "Unrecorded step")
    return process_assessment(record, actual, step, work)


def process_assessment(record, revision, step, work):
    """Project an already inventory-validated recorder step; does not authenticate it."""
    log = step["logs"].get("stdout.log")
    subject = log["sha256"] if log else revision
    result = ec.assessment(subject, "PROCESS_STDOUT" if log else "OBSERVATION_RECORD", work)
    ec.set_check(result, "integrity", "MATCH", "SUBJECT_BYTES_AND_BUNDLE_INVENTORY", "SHA256", refs=[revision])
    ec.set_check(result, "parser", "VALID", "RECORDER_ENVELOPE_NOT_STDOUT_CONTENT", "agent-observation.v1", refs=[revision])
    if step["status"] != "NOT_RUN":
        state = "INCOMPLETE" if record["status"] == "INCOMPLETE" or step.get("reason") != "EXIT" else "OBSERVED"
        ec.set_check(result, "execution", state, "PROCESS_LIFECYCLE_NOT_PRODUCT_CORRECTNESS",
                     "RECORDER_CAPTURE", refs=[revision])
    return result


def declaration(data, actor, work=None):
    subject = ec.sha256(data)
    result = ec.assessment(subject, "DECLARED_TEXT", work)
    ec.set_check(result, "statement", "DECLARED", "AUTHOR_STATEMENT", "EXPLICIT_ATTRIBUTION",
                 actor=actor, refs=[subject])
    # Computing a self-hash does not check an independently supplied digest.
    return result


def review(artifact, payload, expected_digest, work):
    """Distinct IDs are a declaration of independence, not authenticated independence."""
    binding(work)
    ec.require(isinstance(payload, dict) and set(payload) == {
        "schema", "subject_sha256", "binding", "author", "reviewer", "scope", "decision"}
        and payload["schema"] == "golem.evidence-review.v1", "Invalid review statement")
    ec.require(payload["binding"] == work and payload["subject_sha256"] == expected_digest
               and all(ec.text(payload[k]) for k in ("author", "reviewer", "scope"))
               and payload["decision"] in ("APPROVE", "REJECT", "NEEDS_WORK"), "Review scope mismatch")
    actual = ec.sha256(artifact)
    result = ec.assessment(expected_digest, "REVIEWED_ARTIFACT", work)
    review_digest = io.identity(payload)
    ec.set_check(result, "integrity", "MATCH" if actual == expected_digest else "MISMATCH",
                 "REVIEW_SUBJECT_BYTES", "SHA256_EXPECTED_SUBJECT", refs=[review_digest])
    ec.set_check(result, "parser", "VALID", "REVIEW_STATEMENT_SHAPE", "evidence-review.v1", refs=[review_digest])
    ec.set_check(result, "statement", "DECLARED", "REVIEW_DECISION_NOT_ARTIFACT_TRUTH",
                 "EXPLICIT_ATTRIBUTION", actor=payload["reviewer"], refs=[review_digest])
    state = "REJECTED" if payload["author"] == payload["reviewer"] or actual != expected_digest else "DECLARED"
    ec.set_check(result, "independent_review", state, payload["scope"],
                 "DISTINCT_DECLARED_IDS_NOT_AUTHENTICATED_INDEPENDENCE",
                 actor=payload["reviewer"], refs=[review_digest])
    return result


def research_outcome(payload, actor, work=None):
    """Legacy native fields are authored observations, not proof of execution."""
    ec.require(isinstance(payload, dict) and isinstance(payload.get("observations"), list)
               and len(payload["observations"]) <= 64, "Expected bounded research observations")
    rows, seen = [], set()
    for item in payload["observations"]:
        ec.require(isinstance(item, dict) and set(item) == {"id", "status", "failure_domain", "evidence_digest"}
                   and isinstance(item["id"], str) and io.ID.fullmatch(item["id"])
                   and item["id"] not in seen and item["status"] in (
                       "PASS", "FAIL", "ERROR", "SKIPPED", "NOT_EXECUTED", "UNKNOWN")
                   and item["failure_domain"] in ("NONE", "PRODUCT", "HARNESS", "ENVIRONMENT", "UNKNOWN"),
                   "Invalid legacy research observation")
        seen.add(item["id"])
        ec.require((item["status"] == "PASS") == (item["failure_domain"] == "NONE")
                   and (item["failure_domain"] != "PRODUCT" or item["status"] == "FAIL"),
                   "Inconsistent research observation")
        result = ec.assessment(item["evidence_digest"], "RESEARCH_OBSERVATION_REFERENCE", work)
        ref = io.identity(item)
        ec.set_check(result, "statement", "DECLARED", "RESEARCH_CASE_STATUS", "LEGACY_NATIVE_FIELDS",
                     actor=actor, refs=[ref])
        ec.set_check(result, "parser", "VALID", "OBSERVATION_FIELDS_ONLY_NOT_FULL_NATIVE_MODEL",
                     "research-observation.v1", refs=[ref])
        rows.append({"id": item["id"], "declared_status": item["status"], "verification": result})
    return rows


def read_bytes(path):
    ec.require(not path.is_symlink(), "Symlink input")
    with path.open("rb") as stream:
        data = stream.read(io.LIMIT + 1)
    ec.require(len(data) <= io.LIMIT, "Input too large")
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("observation")
    p.add_argument("bundle", type=Path)
    p.add_argument("--revision", required=True)
    p.add_argument("--step", required=True)
    for name in ("declaration", "research-outcome", "review"):
        p = sub.add_parser(name)
        p.add_argument("file", type=Path)
        if name == "review":
            p.add_argument("--statement", type=Path, required=True)
            p.add_argument("--sha256", required=True)
        else:
            p.add_argument("--actor", required=True)
    for p in sub.choices.values():
        p.add_argument("--project-id", required=True)
        p.add_argument("--work-id", required=True)
    args = parser.parse_args(argv)
    try:
        work = {"project_id": args.project_id, "work_id": args.work_id}
        binding(work)
        if args.command == "observation":
            result = observation(args.bundle, args.revision, args.step, work)
        else:
            raw = read_bytes(args.file)
            if args.command == "declaration":
                result = declaration(raw, args.actor, work)
            elif args.command == "review":
                payload = io.strict_json(read_bytes(args.statement))
                verification = review(raw, payload, args.sha256, work)
                result = {"schema": "golem.evidence-review-view.v1", "declared_decision": payload["decision"],
                          "author": payload["author"], "reviewer": payload["reviewer"],
                          "statement_sha256": io.identity(payload), "verification": verification}
            else:
                payload = io.strict_json(raw)
                ec.require(payload.get("work_id") == work["work_id"], "Research Work mismatch")
                result = {"schema": "golem.research-evidence-view.v1", "binding": work,
                          "observations": research_outcome(payload, args.actor, work), "acceptance_authorized": False}
        sys.stdout.buffer.write(io.encoded(result))
        verification = result.get("verification", result)
        return 1 if "checks" in verification and (
            verification["checks"]["integrity"]["state"] == "MISMATCH"
            or verification["checks"]["independent_review"]["state"] == "REJECTED") else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        sys.stderr.buffer.write(io.encoded({"schema": "golem.evidence-error.v1", "error_type": type(error).__name__,
            "diagnostic": str(error)[:512], "acceptance_authorized": False}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
