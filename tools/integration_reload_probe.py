"""Owner-only D5 actual SDK discovery/status/next probe, not desktop activation."""
import argparse
import asyncio
import os
from importlib.metadata import distribution, version
from pathlib import Path
import sys

import execution_record as records
import integration_backend as backend
import integration_contract as c
import integration_registry as r
import integration_transfer as transfer
import integration_hook_contract as hooks
import integration_lifecycle as life
import integration_update as update


def append_log(output, value):
    data = c.encoded(value)
    path = output / "probe.log"
    r.regular(path, private=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
    try:
        c.require(os.fstat(fd).st_size + len(data) <= c.LIMIT, "RELOAD_PROBE_OUTPUT_LIMIT")
        with os.fdopen(fd, "ab", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)


def runtime():
    root = r.real_path(str(Path(distribution("mcp").locate_file("")).resolve()))
    pins = {}
    for name in ("mcp", "mcp-types"):
        package = distribution(name)
        c.require(package.version == "2.3.0" and Path(package.locate_file("")).resolve() == root, "MCP_SDK_VERSION")
        for item in package.files or ():
            text = str(item)
            if text.startswith("mcp/") and text.endswith(".py") or text.endswith((".dist-info/RECORD", ".dist-info/METADATA")):
                path = r.real_path(str(root / text))
                c.require(path.is_relative_to(root), "MCP_SDK_SCOPE")
                pins[text] = r.file_pin(path)["sha256"]
    c.require(0 < len(pins) <= 256, "MCP_SDK_SCOPE")
    return {"python": hooks.executable_pin(Path(sys.executable).resolve()), "sdk_root": str(root),
            "sdk_identity": r.identity(root), "files": pins}


def validate_runtime(value):
    c._validate(value, c.obj({"python": c.PIN, "sdk_root": c.PATH, "sdk_identity": c.IDENTITY,
                             "files": {"type": ["object", "null"]}}))
    c.require(isinstance(value["files"], dict) and
              hooks.executable_pin(Path(value["python"]["path"])) == value["python"], "PROBE_RUNTIME_CHANGED")
    root = r.real_path(value["sdk_root"])
    c.require(r.identity(root) == value["sdk_identity"] and 0 < len(value["files"]) <= 256, "PROBE_RUNTIME_CHANGED")
    for name, digest in value["files"].items():
        c._validate(name, c.PATH)
        c._validate(digest, c.DIGEST)
        path = r.real_path(str(root / name))
        c.require(path.is_relative_to(root) and r.file_pin(path)["sha256"] == digest, "PROBE_RUNTIME_CHANGED")


def command(script, args, context=None):
    # A venv launcher can be a symlink. Execute its canonical D3-pinned Python
    # while explicitly carrying the reviewed SDK import roots, not PYTHONPATH.
    context = runtime() if context is None else context
    roots = [str(Path(__file__).resolve().parent), context["sdk_root"]]
    argv = [str(script), *args]
    bootstrap = "import runpy,sys;sys.path[:0]=" + repr(roots) + ";sys.argv=" + repr(argv) + ";runpy.run_path(sys.argv[0],run_name='__main__')"
    return [context["python"]["path"], "-I", "-B", "-c", bootstrap]


def worker_args(policy_pin, project_id, mode, output):
    return ["--worker", "--policy", policy_pin["path"], "--reviewed-policy-sha256", policy_pin["sha256"],
            "--project-id", project_id, "--mode", mode, "--output", str(output), "--approve-reload-probe"]


async def worker(policy_pin, project_id, mode, output):
    c.require(version("mcp") == "2.3.0" and version("mcp-types") == "2.3.0", "MCP_SDK_VERSION")
    runtime_before = runtime()
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    owner = transfer.Transfer(Path(policy_pin["path"]), policy_pin["sha256"], approve_data_transfer=True)
    registry = owner.registry
    selected = next((s for s in owner.value["scopes"] if s["binding"]["project_id"] == project_id), None)
    c.require(selected is not None, "TRANSFER_SCOPE")
    scope = owner.scope(project_id, selected["work_ids"][0], "work_inspect")
    with registry.locked():
        state, lifecycle_sha = life.current(registry, project_id)
        c.require(state is not None and state["phase"] == "RELOAD_REQUIRED", "MAINTENANCE_PHASE")
        project = registry.authorize(scope["binding"], scope["work_ids"][0], "record")
        enrollment, before = update.Manager(registry).enrollment(project_id)
        grant = next(g for g in enrollment["grants"] if g["principal_id"] == scope["binding"]["principal_id"] and
                     g["client_id"] == scope["binding"]["client_id"])
        c.require(set(grant["work_ids"]) == set(scope["work_ids"]), "RELOAD_SCOPE_INCOMPLETE")
        snapshots = {w["work_id"]: update.inventory(Path(w["path"])) for w in project["works"]}
    child = command(Path(__file__).resolve().with_name("integration_mcp.py"), ["--policy", policy_pin["path"],
              "--reviewed-policy-sha256", policy_pin["sha256"], "--approve-data-transfer"])
    params = StdioServerParameters(command=child[0], args=child[1:], cwd=str(output), env=backend.ENVIRONMENT)
    observations = {}
    async with Client(params, mode=mode, read_timeout_seconds=120) as client:
        listed = await client.list_tools()
        names = sorted(tool.name for tool in listed.tools)
        c.require("golem_work_inspect" in names, "RELOAD_DISCOVERY_FAILED")
        append_log(output, {"method": "tools/list", "tools": names})
        for work_id in scope["work_ids"]:
            views = {}
            for view in ("status", "next"):
                reply = await client.call_tool("golem_work_inspect", {"project_id": project_id, "work_id": work_id, "view": view})
                c.require(not reply.is_error and len(reply.content) == 1 and reply.content[0].type == "text", "RELOAD_READ_FAILED")
                raw = reply.content[0].text.encode()
                append_log(output, {"method": "tools/call", "project_id": project_id, "work_id": work_id,
                                    "view": view, "response": reply.content[0].text})
                value = c.decode(raw, c.MAX_NATIVE)
                c.require(value.get("state") == "AVAILABLE" and value.get("native_state_changed") is False, "RELOAD_READ_FAILED")
                views[view] = value["result"]
            c.require(views["status"]["sequence"] == views["next"]["sequence"] and
                (views["status"].get("state") or {}).get("active") is None, "NATIVE_OWNER_OR_RECOVERY_REQUIRED")
            observations[work_id] = {"sequence": views["status"]["sequence"],
                                    "views_sha256": c.sha(c.encoded(views))}
        protocol_version = client.protocol_version
    with registry.locked():
        owner.current()
        c.require(life.current(registry, project_id)[1] == lifecycle_sha and
                  update.Manager(registry).enrollment(project_id)[1] == before, "RELOAD_PROBE_STALE")
        for work in project["works"]:
            c.require(update.inventory(Path(work["path"])) == snapshots[work["work_id"]], "READ_ONLY_INVENTORY_CHANGED")
    c.require(runtime() == runtime_before, "PROBE_RUNTIME_CHANGED")
    return {"schema": "golem.integration-reload-probe.v1", "state": "READ_OBSERVED", "binding": scope["binding"],
        "registry_identity": registry.root_identity, "before": before, "lifecycle_sha256": lifecycle_sha,
        "work_ids": scope["work_ids"], "protocol": protocol_version, "observations": observations,
        "runtime": runtime_before, "policy": policy_pin, "mode": mode,
        "producer": update.producer(), "native_state_changed": False, "desktop_activation": "NOT_OBSERVED"}


def probe(policy_pin, project_id, mode, output, *, approve_reload_probe=False):
    c.require(approve_reload_probe is True, "OWNER_RELOAD_PROBE_APPROVAL_REQUIRED")
    c._validate(policy_pin, c.PIN)
    c._validate(project_id, c.ID)
    c.require(mode in ("auto", "legacy"), "PROTOCOL_MODE")
    owner = transfer.Transfer(Path(policy_pin["path"]), policy_pin["sha256"], approve_data_transfer=True)
    root = r.real_path(str(output.parent))
    r.Registry._private(root)
    with owner.registry.locked():
        work_ids = []
        for scope in owner.value["scopes"]:
            for work_id in scope["work_ids"]:
                project = owner.registry.authorize(scope["binding"], work_id, "record")
                c.require(not output.is_relative_to(Path(project["root"])), "RELOAD_OUTPUT_SCOPE")
            if scope["binding"]["project_id"] == project_id:
                work_ids = scope["work_ids"]
        c.require(work_ids, "TRANSFER_SCOPE")
    output = records.private_directory(output)
    context = runtime()
    argv = command(Path(__file__).resolve(), worker_args(policy_pin, project_id, mode, output), context)
    result = records.capture(argv, output, 240, cwd=output, observe_source=False,
        env=backend.ENVIRONMENT, limit=c.LIMIT,
        extra_logs=["probe.log"])
    c.require(result["returncode"] == 0 and result["recording"] == "RECORDED" and records.check(output)["integrity"] == "PASS",
              "RELOAD_PROBE_FAILED_INSPECT_LOCAL_LOGS")
    data = r.regular(output / "stdout.log", private=True)
    value = c.decode(data)
    c.require(value["state"] == "READ_OBSERVED" and value["producer"] == update.producer() and
              value["runtime"] == context and runtime() == context, "RELOAD_PROBE_FAILED")
    records.save(output / "probe.json", data)
    return r.file_pin(output / "probe.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--reviewed-policy-sha256", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--mode", choices=("auto", "legacy"), default="auto")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approve-reload-probe", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        c.require(args.approve_reload_probe, "OWNER_RELOAD_PROBE_APPROVAL_REQUIRED")
        pin = {"path": str(args.policy), "sha256": args.reviewed_policy_sha256}
        result = asyncio.run(asyncio.wait_for(worker(pin, args.project_id, args.mode, args.output), timeout=220)) if args.worker else {
            "probe": probe(pin, args.project_id, args.mode, args.output, approve_reload_probe=True)}
        sys.stdout.buffer.write(c.encoded(result))
        return 0
    except (c.IntegrationError, OSError, ValueError, KeyError, TypeError, TimeoutError) as error:
        sys.stderr.write(c.encoded({"state": "RELOAD_NOT_VERIFIED", "code": getattr(error, "code", "IO_OR_CONTRACT_ERROR"),
                                   "automatic_retry_allowed": False}).decode())
        return 1


if __name__ == "__main__":
    sys.exit(main())
