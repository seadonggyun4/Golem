"""Non-ordinal verification dimensions. Integrity is never content truth."""
import hashlib
import re

SCHEMA = "golem.evidence-verification.v1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
STATES = {"integrity": {"MATCH", "MISMATCH", "NOT_CHECKED"},
          "statement": {"DECLARED", "NOT_PRESENT"},
          "parser": {"VALID", "INVALID", "NOT_RUN"},
          "execution": {"OBSERVED", "INCOMPLETE", "NOT_OBSERVED"},
          "independent_review": {"DECLARED", "REJECTED", "NOT_OBSERVED"},
          "authenticity": {"NOT_VERIFIED"}}
DEFAULTS = {"integrity": "NOT_CHECKED", "statement": "NOT_PRESENT", "parser": "NOT_RUN",
            "execution": "NOT_OBSERVED", "independent_review": "NOT_OBSERVED", "authenticity": "NOT_VERIFIED"}


def require(value, message):
    if not value:
        raise ValueError("EVIDENCE_CONTRACT: " + message)


def text(value):
    return isinstance(value, str) and 0 < len(value) <= 256 and "\0" not in value


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check(state, scope, method, actor=None, refs=()):
    return {"state": state, "scope": scope, "method": method,
            "actor": actor, "evidence_refs": list(refs)}


def assessment(subject, kind, binding=None):
    require(isinstance(subject, str) and HEX.fullmatch(subject), "Exact subject SHA-256 required")
    result = {"schema": SCHEMA, "subject": {"sha256": subject, "kind": kind},
              "binding": binding,
              "checks": {name: check(state, "NONE", "NONE") for name, state in DEFAULTS.items()},
              "content_truth": "NOT_ESTABLISHED", "acceptance_authorized": False}
    validate(result)
    return result


def set_check(result, dimension, state, scope, method, actor=None, refs=()):
    require(dimension in STATES, "Unknown verification dimension")
    previous = result["checks"][dimension]
    result["checks"][dimension] = check(state, scope, method, actor, refs)
    try:
        validate(result)
    except ValueError:
        result["checks"][dimension] = previous
        raise
    return result


def validate(result):
    require(isinstance(result, dict) and set(result) == {
        "schema", "subject", "binding", "checks", "content_truth", "acceptance_authorized"}
        and result["schema"] == SCHEMA, "Invalid envelope")
    subject = result["subject"]
    require(isinstance(subject, dict) and set(subject) == {"sha256", "kind"}
            and isinstance(subject["sha256"], str) and HEX.fullmatch(subject["sha256"])
            and text(subject["kind"]), "Invalid subject")
    binding = result["binding"]
    require(binding is None or isinstance(binding, dict) and set(binding) == {"project_id", "work_id"}
            and all(text(v) for v in binding.values()), "Invalid binding")
    require(result["content_truth"] == "NOT_ESTABLISHED" and result["acceptance_authorized"] is False,
            "Verification cannot grant truth or acceptance")
    checks = result["checks"]
    require(isinstance(checks, dict) and set(checks) == set(STATES), "Missing verification dimensions")
    for name, row in checks.items():
        require(isinstance(row, dict) and set(row) == {"state", "scope", "method", "actor", "evidence_refs"}
                and isinstance(row["state"], str) and row["state"] in STATES[name]
                and text(row["scope"]) and text(row["method"])
                and (row["actor"] is None or text(row["actor"])), "Invalid check")
        refs = row["evidence_refs"]
        require(isinstance(refs, list) and len(refs) <= 32
                and all(isinstance(ref, str) and HEX.fullmatch(ref) for ref in refs)
                and len(set(refs)) == len(refs), "Invalid evidence references")
        if row["state"].startswith("NOT_"):
            require(row["scope"] == "NONE" and row["method"] == "NONE"
                    and row["actor"] is None and not refs, "Unperformed checks cannot carry verification claims")
        else:
            require(row["scope"] != "NONE" and row["method"] != "NONE" and refs,
                    "Performed checks require scope, method and evidence")
        if name in ("statement", "independent_review") and not row["state"].startswith("NOT_"):
            require(row["actor"] is not None, "Declaration/review actor required")
    return result
