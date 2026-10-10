"""Immutable, fact-linked judgment deltas; not a native Work authority."""
from pathlib import Path

import agent_io as io
import evidence_contract as ec

SCHEMA = "golem.fact-judgment.v1"
DELTA = "golem.judgment-delta.v1"
MAX_ENTRIES = 256


class ContractError(ValueError):
    code = "JUDGMENT_CONTRACT"


def require(condition, message):
    if not condition:
        raise ContractError(message)


def identifier(value):
    return isinstance(value, str) and io.ID.fullmatch(value) is not None


def binding(value):
    require(isinstance(value, dict) and set(value) == {"project_id", "work_id"}
            and all(identifier(v) for v in value.values()), "Explicit project/Work binding required")


def facts(bundle, work):
    """Use recorder fields, never infer assertions from stdout or exit zero."""
    record, revision = io.load_bundle(bundle)
    plan = io.validate_plan(io.read_json(bundle / "plan.json"))
    require(io.identity(plan) == record["plan_sha256"], "Command plan revision mismatch")
    validate_binding(record, work)
    scope = record.get("scope") or {}
    value = {"observation_revision": revision, "record": record, "plan": plan,
             "raw_bundle": str(bundle.absolute()), "raw_available_at_capture": True,
             "attribution_basis": "DECLARED_BINDING" if "work_id" not in scope else "RECORDED_SCOPE",
             "authenticity_verified": False, "product_acceptance": False}
    return value


def validate_binding(record, work):
    scope = record.get("scope") or {}
    require(isinstance(scope, dict), "Invalid observation scope")
    require(scope.get("work_id", work["work_id"]) == work["work_id"], "Observation Work mismatch")
    require(scope.get("project_id", work["project_id"]) == work["project_id"], "Observation project mismatch")
    for step in record["steps"]:
        if "usage" in step:
            for call in step["usage"]["calls"]:
                attribution = call["attribution"]
                require(all(attribution.get(k) == v for k, v in work.items()), "Usage Work mismatch")


def fact_ids(observation):
    revision = observation["observation_revision"]
    steps, commands = observation["record"]["steps"], observation["plan"]["commands"]
    require(len(steps) <= len(commands), "Too many execution steps")
    result = {}
    for step, command in zip(steps, commands):
        require(step["id"] == command["id"], "Execution step does not match command")
        fact = {**step, "command": command}
        result[io.identity({"observation_revision": revision, "fact": fact})] = fact
    return result


def validate_delta(delta, available, state):
    require(isinstance(delta, dict) and set(delta) == {"schema", "actor", "set", "remove"}
            and delta["schema"] == DELTA and identifier(delta["actor"]), "Invalid judgment delta")
    updates, removals = delta["set"], delta["remove"]
    require(isinstance(updates, dict) and len(updates) <= 64
            and isinstance(removals, list) and len(removals) <= 64
            and all(identifier(k) for k in updates)
            and all(identifier(k) for k in removals)
            and len(set(removals)) == len(removals)
            and not set(updates).intersection(removals), "Invalid change keys")
    require(all(k in state for k in removals), "Cannot remove an unknown judgment")
    for value in updates.values():
        require(isinstance(value, dict) and set(value) == {"text", "fact_ids"}
                and isinstance(value["text"], str) and 0 < len(value["text"]) <= 8192
                and "\0" not in value["text"]
                and isinstance(value["fact_ids"], list) and 1 <= len(value["fact_ids"]) <= 32
                and all(isinstance(k, str) and k in available for k in value["fact_ids"])
                and len(set(value["fact_ids"])) == len(value["fact_ids"]),
                "Judgment must cite current execution facts")
    require(len((set(state) - set(removals)) | set(updates)) <= 64, "Too many active judgments")


def replay(record):
    require(isinstance(record, dict) and set(record) == {"schema", "binding", "entries"}
            and record["schema"] == SCHEMA, "Invalid judgment record")
    binding(record["binding"])
    entries = record["entries"]
    require(isinstance(entries, list) and 1 <= len(entries) <= MAX_ENTRIES, "History limit exceeded")
    state, previous = {}, None
    for index, entry in enumerate(entries):
        require(isinstance(entry, dict) and set(entry) == {"parent", "observation", "delta"}
                and entry["parent"] == previous, "Broken entry chain")
        observation = entry["observation"]
        require(isinstance(observation, dict) and set(observation) == {
            "observation_revision", "record", "plan", "raw_bundle", "raw_available_at_capture",
            "attribution_basis", "authenticity_verified", "product_acceptance"}, "Invalid facts")
        require(isinstance(observation["record"], dict)
                and observation["record"].get("schema") == io.SCHEMA
                and isinstance(observation["record"].get("steps"), list)
                and observation["authenticity_verified"] is False
                and observation["product_acceptance"] is False
                and observation["raw_available_at_capture"] is True
                and observation["attribution_basis"] in ("DECLARED_BINDING", "RECORDED_SCOPE")
                and isinstance(observation["raw_bundle"], str), "Invalid observation snapshot")
        # The original record uses the recorder's canonical serialization.
        require(io.identity(observation["record"]) == observation["observation_revision"], "Fact revision mismatch")
        io.validate_plan(observation["plan"])
        require(io.identity(observation["plan"]) == observation["record"]["plan_sha256"],
                "Command plan revision mismatch")
        validate_binding(observation["record"], record["binding"])
        available = fact_ids(observation)
        validate_delta(entry["delta"], available, state)
        for key in entry["delta"]["remove"]:
            del state[key]
        for key, value in entry["delta"]["set"].items():
            state[key] = {**value, "actor": entry["delta"]["actor"], "entry": index + 1,
                          "observation_revision": observation["observation_revision"]}
        previous = io.identity(entry)
    return state


def load(bundle):
    require(not bundle.is_symlink(), "Symlink bundle")
    manifest = io.read_json(bundle / "manifest.json")
    require(isinstance(manifest, dict) and manifest == {
        "schema": "golem.fact-judgment-manifest.v1", "files": io.file_inventory(bundle)}, "Judgment integrity failure")
    record = io.read_json(bundle / "record.json")
    replay(record)
    return record, io.digest(bundle / "record.json")


def write(observation, work, delta, output, baseline=None, revision=None):
    binding(work)
    require((baseline is None) == (revision is None), "Baseline requires exact revision")
    entries = []
    if baseline is not None:
        prior, key = load(baseline)
        require(key == revision and prior["binding"] == work, "Baseline revision or Work mismatch")
        entries = prior["entries"]
    snapshot = facts(observation, work)
    entry = {"parent": io.identity(entries[-1]) if entries else None,
             "observation": snapshot, "delta": delta}
    record = {"schema": SCHEMA, "binding": dict(work), "entries": entries + [entry]}
    replay(record)
    require(len(io.encoded(record)) <= io.LIMIT, "Record size limit exceeded")
    output = output.absolute()
    # Never put derived evidence inside original bundles or mutate their inventory.
    for original in (observation, baseline):
        if original is not None:
            root = original.resolve()
            require(root != output.resolve() and root not in output.resolve().parents, "Output overlaps evidence")
    for location in (snapshot["record"].get("cwd"),
                     (snapshot["record"].get("scope") or {}).get("work")):
        if location:
            root = Path(location).resolve()
            require(root != output.resolve() and root not in output.resolve().parents,
                    "Output must be outside repository and Work")
    io.private_directory(output)
    io.save(output / "record.json", io.encoded(record))
    io.save(output / "manifest.json", io.encoded({"schema": "golem.fact-judgment-manifest.v1",
                                                "files": io.file_inventory(output)}))
    return view(output)


def view(bundle):
    record, revision = load(bundle)
    state = replay(record)
    current = record["entries"][-1]
    observation = current["observation"]
    judgments = {}
    for key, value in state.items():
        verification = ec.assessment(io.identity(value), "DECLARED_JUDGMENT", record["binding"])
        ec.set_check(verification, "integrity", "MATCH", "JUDGMENT_BUNDLE_NOT_REFERENCED_RAW_LOGS",
                     "SHA256_AND_CHAIN", refs=[revision])
        ec.set_check(verification, "parser", "VALID", "DELTA_SHAPE_AND_FACT_REFERENCES",
                     DELTA, refs=[revision])
        ec.set_check(verification, "statement", "DECLARED", "AUTHOR_JUDGMENT_NOT_EXECUTION",
                     "EXPLICIT_ATTRIBUTION", actor=value["actor"], refs=value["fact_ids"])
        judgments[key] = {**value, "verification": "DECLARED_NOT_VERIFIED",
                         "evidence_verification": verification,
                         "freshness": "CURRENT_OBSERVATION" if value["entry"] == len(record["entries"])
                         else "HISTORICAL_REQUIRES_REVIEW"}
    return {"schema": "golem.fact-judgment-view.v1", "revision": revision,
            "binding": record["binding"], "entries": len(record["entries"]),
            "execution": {"status": observation["record"]["status"],
                          "source_before": observation["record"].get("source_before"),
                          "source_after": observation["record"].get("source_after"),
                          "facts": fact_ids(observation)},
            "changes": current["delta"],
            "judgments": judgments,
            "raw_bundle": observation["raw_bundle"], "raw_embedded": False,
            "authenticity_verified": False, "execution_authorized": False,
            "native_work_updated": False, "product_acceptance": False}
