"""Bounded prepare/execute/finalize orchestration; never replay uncertain effects."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import agent_io as io
import execution_record as records

SCHEMA = "golem.agent-lifecycle-plan.v1"
PHASES = ("prepare", "execute", "finalize")


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(path, value):
    """Single reservation owner publishes JSON atomically to concurrent readers."""
    pending = path.with_name("." + path.name + ".pending")
    records.save(pending, io.encoded(value))
    os.replace(pending, path)
    sync_directory(path.parent)


def validate(plan):
    if (not isinstance(plan, dict) or set(plan) != {"schema", "run_id", "cwd", "inputs", "phases"}
            or plan["schema"] != SCHEMA or not isinstance(plan["run_id"], str)
            or not io.ID.fullmatch(plan["run_id"]) or not isinstance(plan["cwd"], str)
            or not Path(plan["cwd"]).is_absolute() or "\0" in plan["cwd"]
            or not isinstance(plan["inputs"], dict) or len(plan["inputs"]) > 64
            or not isinstance(plan["phases"], dict) or set(plan["phases"]) != set(PHASES)):
        raise ValueError("LIFECYCLE_PLAN: closed schema and all three phases required")
    for path, key in plan["inputs"].items():
        if (not isinstance(path, str) or not Path(path).is_absolute() or "\0" in path
                or not isinstance(key, str) or not io.HEX.fullmatch(key)):
            raise ValueError("LIFECYCLE_INPUT: absolute immutable input and SHA-256 required")
    seen = set()
    for phase in PHASES:
        commands = plan["phases"][phase]
        if not isinstance(commands, list) or not 1 <= len(commands) <= 16:
            raise ValueError("LIFECYCLE_PHASE: each phase requires 1..16 commands")
        for command in commands:
            if (not isinstance(command, dict) or set(command) !=
                    {"id", "argv", "timeout", "executable_sha256", "expect"}):
                raise ValueError("LIFECYCLE_COMMAND: unsupported fields")
            io.validate_plan({"schema": io.PLAN_SCHEMA, "task": "code", "commands": [
                {k: command[k] for k in ("id", "argv", "timeout")}]})
            if (command["id"] in seen or not isinstance(command["executable_sha256"], str)
                    or not io.HEX.fullmatch(command["executable_sha256"])):
                raise ValueError("LIFECYCLE_COMMAND: duplicate ID or invalid executable digest")
            seen.add(command["id"])
            checks = command["expect"]
            if not isinstance(checks, list) or not 1 <= len(checks) <= 16:
                raise ValueError("LIFECYCLE_EXPECT: explicit JSON result checks required")
            for check in checks:
                if (not isinstance(check, dict) or set(check) != {"path", "equals"}
                        or not isinstance(check["path"], list) or not 1 <= len(check["path"]) <= 16
                        or any(not isinstance(key, str) or not key or len(key) > 128 for key in check["path"])
                        or type(check["equals"]) not in (str, int, bool, type(None))):
                    raise ValueError("LIFECYCLE_EXPECT: bounded object-key path and scalar required")
    if len(seen) > 32 or len(io.encoded(plan)) > 256 * 1024:
        raise ValueError("LIFECYCLE_LIMIT: at most 32 commands and 256 KiB plan")
    return plan


def check_result(value, checks):
    for check in checks:
        current = value
        for key in check["path"]:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        if type(current) is not type(check["equals"]) or current != check["equals"]:
            return False
    return True


def check_pins(plan, command):
    for name, expected in [(command["argv"][0], command["executable_sha256"]), *plan["inputs"].items()]:
        if records.digest(Path(name)) != expected:
            raise ValueError("LIFECYCLE_INPUT_CHANGED")


def inspect(output):
    """Read only: an unfinished reservation never causes dispatch."""
    records._private_existing(output)
    manifest_path = output / "manifest.json"
    if not manifest_path.exists():
        return {"schema": "golem.agent-lifecycle-result.v1", "status": "RECONCILE_REQUIRED",
                "evidence": str(output), "execution_authorized": False, "product_acceptance": False,
                "next_action": "INSPECT_EFFECTS_AND_CHILD_PROCESSES; DO_NOT_REPLAY"}
    manifest = io.read_json(manifest_path)
    if (manifest.get("schema") != "golem.agent-lifecycle-manifest.v1"
            or manifest.get("files") != io.file_inventory(output)):
        raise ValueError("LIFECYCLE_INTEGRITY: retain corrupt evidence; do not replay")
    result = io.read_json(output / "result.json")
    plan = validate(io.read_json(output / "plan.json"))
    if (result.get("schema") != "golem.agent-lifecycle-result.v1"
            or result.get("plan_sha256") != io.identity(plan)):
        raise ValueError("LIFECYCLE_INTEGRITY: result does not match plan")
    return result


def run(plan, store, reviewed_digest):
    # Freeze caller-owned objects before any command can run.
    plan = validate(io.strict_json(io.encoded(plan)))
    key = io.identity(plan)
    if reviewed_digest != key:
        raise ValueError("LIFECYCLE_REVIEW_REQUIRED: inspect the exact plan and supply its digest")
    cwd = Path(plan["cwd"]).resolve(strict=True)
    if str(cwd) != plan["cwd"]:
        raise ValueError("LIFECYCLE_CWD: use the canonical repository root")
    store = Path(store).absolute()
    if store.resolve() == cwd or cwd in store.resolve().parents:
        raise ValueError("LIFECYCLE_STORE: evidence must be outside the repository")
    try:
        records.private_directory(store)
        sync_directory(store.parent)
    except FileExistsError:
        records._private_existing(store)
    output = store / plan["run_id"]
    try:
        records.private_directory(output)
    except FileExistsError:
        result = inspect(output)
        if (output / "plan.json").exists() and io.read_json(output / "plan.json") != plan:
            raise ValueError("LIFECYCLE_ID_CONFLICT: same run ID, different intent")
        return result
    sync_directory(store)
    # Exclusive directory reservation is the only dispatch entry. Even a crash
    # before the first durable event leaves a non-reusable run ID in this store.
    publish(output / "plan.json", plan)
    producer = {**io.producer(), "lifecycle_sha256": records.digest(Path(__file__))}
    records.save(output / "producer.json", io.encoded(producer))
    rows = [{"phase": phase, "id": c["id"], "status": "NOT_RUN"}
            for phase in PHASES for c in plan["phases"][phase]]
    result = {"schema": "golem.agent-lifecycle-result.v1", "run_id": plan["run_id"],
              "plan_sha256": key, "status": "INCOMPLETE", "steps": rows,
              "evidence": str(output), "execution_authorized": False, "product_acceptance": False,
              "next_action": "INSPECT_EVIDENCE", "controller_invocations": 1}
    index = 0
    try:
        if Path(records.git(cwd, "rev-parse", "--show-toplevel").decode().strip()).resolve() != cwd:
            raise ValueError("LIFECYCLE_CWD: repository root required")
        for phase in PHASES:
            for command in plan["phases"][phase]:
                check_pins(plan, command)
        records.save(output / "source-before.json", io.encoded(records.source_identity(cwd)))
        for phase in PHASES:
            for command in plan["phases"][phase]:
                row = rows[index]
                row["status"] = "CHECKING"
                check_pins(plan, command)
                if producer != {**io.producer(), "lifecycle_sha256": records.digest(Path(__file__))}:
                    raise ValueError("LIFECYCLE_PRODUCER_CHANGED")
                directory = records.private_directory(output / command["id"])
                row["status"] = "DISPATCH_UNCERTAIN"
                records.save(output / f"{index:02d}-dispatch.json", io.encoded(row))
                process = records.capture(command["argv"], directory, command["timeout"], cwd)
                row.update(returncode=process["returncode"], reason=process["reason"],
                           evidence=command["id"], status="FAILED")
                verified = records.check(directory)
                if (process["returncode"] != 0 or process["reason"] != "EXIT"
                        or process["recording"] != "RECORDED" or verified["executable_unchanged"] is not True):
                    raise ValueError("LIFECYCLE_PROCESS_FAILED")
                check_pins(plan, command)
                if not check_result(io.read_json(directory / "stdout.log"), command["expect"]):
                    row["status"] = "BLOCKED"
                    raise ValueError("LIFECYCLE_RESULT_BLOCKED")
                row["status"] = "CHECKS_PASSED"
                records.save(output / f"{index:02d}-complete.json", io.encoded(row))
                index += 1
        records.save(output / "source-after.json", io.encoded(records.source_identity(cwd)))
        if producer != {**io.producer(), "lifecycle_sha256": records.digest(Path(__file__))}:
            raise ValueError("LIFECYCLE_PRODUCER_CHANGED")
        result.update(status="FINISHED", next_action="RECHECK_NATIVE_COMPLETION_BEFORE_CLAIMING_DONE")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        if index < len(rows) and rows[index]["status"] == "CHECKING":
            rows[index]["status"] = "NOT_DISPATCHED"
        result.update(status="STOPPED", diagnostic=str(error)[:512], error_type=type(error).__name__,
                      next_action="INSPECT_FAILED_STEP_AND_RECONCILE_EFFECTS; DO_NOT_REPLAY")
    records.save(output / "result.json", io.encoded(result))
    publish(output / "manifest.json", {"schema": "golem.agent-lifecycle-manifest.v1",
                                       "files": io.file_inventory(output)})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate")
    p.add_argument("plan", type=Path)
    p = sub.add_parser("run")
    p.add_argument("plan", type=Path)
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--reviewed-plan", required=True, help="exact plan digest; not native execution approval")
    p = sub.add_parser("inspect")
    p.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            plan = validate(io.read_json(args.plan))
            value = {"schema": SCHEMA, "plan_sha256": io.identity(plan), "execution_authorized": False}
        elif args.command == "run":
            value = run(io.read_json(args.plan), args.store, args.reviewed_plan)
        else:
            value = inspect(args.output)
        sys.stdout.buffer.write(io.encoded(value))
        return 0 if value.get("status", "FINISHED") == "FINISHED" else 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        sys.stderr.buffer.write(io.encoded({"schema": "golem.agent-lifecycle-error.v1",
            "diagnostic": str(error)[:512], "error_type": type(error).__name__,
            "next_action": "INSPECT_PLAN_AND_EXISTING_EVIDENCE; DO_NOT_RETRY_EFFECTS",
            "execution_authorized": False}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
