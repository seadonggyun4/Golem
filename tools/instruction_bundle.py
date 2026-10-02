"""Reviewed instruction migration for non-Git, multi-repository workspaces.

This installs prose, not engines or Work artifacts. A plan is not authorization.
"""
import argparse
from pathlib import Path, PurePosixPath
import os
import subprocess
import sys

from agent_entrypoint import (EntryError, atomic_write, encoded, git, locked,
                              no_symlinks, regular_bytes, sha)
from verify_agent import digest, strict_json

SCHEMA = "golem.instruction-bundle.v1"
HOME = ".golem/entrypoints/bundle"
TOOLS = ("instruction_bundle.py", "agent_entrypoint.py", "verify_agent.py", "execution_record.py")


def fail(code, recovery):
    raise EntryError(code, recovery)


def relative(name):
    if (not isinstance(name, str) or not name or PurePosixPath(name).is_absolute()
            or PurePosixPath(name).as_posix() != name or ".." in PurePosixPath(name).parts
            or "\\" in name or any(ord(c) < 32 for c in name)):
        fail("PATH", "Use normalized relative paths without traversal or control characters.")
    return name


def writable(name):
    relative(name)
    if name not in ("AGENTS.md", "CLAUDE.md") and not name.startswith(HOME + "/policies/"):
        fail("WRITE_SCOPE", "Only root entrypoints and private bundle policies can be replaced.")


def boundary(project, repositories):
    no_symlinks(project)
    if not project.is_dir():
        fail("PROJECT", "Select an existing workspace directory.")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    result = subprocess.run(["git", "-C", str(project), "rev-parse", "--show-toplevel"],
                            capture_output=True, timeout=30, env=env)
    if result.returncode == 0 or (project / ".git").exists():
        fail("WORKSPACE", "Use this tool only for a non-Git parent outside any Git worktree.")
    if not isinstance(repositories, list) or not 1 <= len(repositories) <= 16:
        fail("REPOSITORIES", "List the workspace's child Git roots explicitly.")
    if len(set(repositories)) != len(repositories):
        fail("REPOSITORIES", "Do not repeat repositories.")
    for name in repositories:
        relative(name)
        repo = project / name
        no_symlinks(repo)
        if project not in repo.parents or (project / ".golem") in repo.parents:
            fail("REPOSITORIES", "Repositories must be strict children outside the private runtime.")
        if Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve() != repo:
            fail("REPOSITORIES", "Each configured repository must be a Git root.")
    override = project / "AGENTS.override.md"
    if override.exists() or override.is_symlink():
        if regular_bytes(override).strip():
            fail("OVERRIDE", "Review the root override; it shadows AGENTS.md.")
    no_symlinks(project / HOME)


def observed(project, name):
    path = project / relative(name)
    no_symlinks(path)
    return sha(regular_bytes(path)) if path.exists() else None


def validate_manifest(value):
    fields = {"schema", "project", "repositories", "files", "pins", "cli"}
    if not isinstance(value, dict) or set(value) != fields or value["schema"] != SCHEMA:
        fail("SCHEMA", "Use the documented instruction-bundle.v1 manifest.")
    if not isinstance(value["project"], str) or not Path(value["project"]).is_absolute():
        fail("PROJECT", "Pin the absolute workspace path.")
    if not isinstance(value["files"], dict) or not {"AGENTS.md", "CLAUDE.md"} <= value["files"].keys():
        fail("FILES", "Supply both reviewed root entrypoints and optional policy files.")
    if len(value["files"]) > 64 or not isinstance(value["pins"], dict):
        fail("FILES", "Keep the reviewed bundle bounded.")
    for name, item in value["files"].items():
        writable(name)
        if (not isinstance(item, dict) or set(item) != {"before", "text"}
                or not isinstance(item["text"], str) or len(item["text"].encode()) > 1024 * 1024):
            fail("FILES", "Each file needs a prior SHA-256 (or null) and bounded UTF-8 text.")
        if item["before"] is not None:
            valid_hash(item["before"])
        if name in ("AGENTS.md", "CLAUDE.md") and len(item["text"].encode()) > 8192:
            fail("BUDGET", "Review instructions exceeding 8192 bytes; never truncate rules.")
    for name, expected in value["pins"].items():
        relative(name)
        if name in value["files"]:
            fail("PINS", "A read-only dependency cannot also be an output.")
        valid_hash(expected)
    relative(value["cli"])
    if value["cli"] not in value["pins"]:
        fail("PINS", "Pin the existing CLI without installing or replacing it.")


def valid_hash(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        fail("HASH", "Use a lowercase SHA-256 digest.")


def dependencies(project, pins):
    for name, expected in pins.items():
        path = project / relative(name)
        # Executables may have a deliberate local symlink; bind both resolved path
        # and content in the plan. Instruction outputs never allow symlinks.
        if not path.is_file() or digest(path) != expected:
            fail("DEPENDENCY_DRIFT", "Review the changed dependency; never auto-upgrade or auto-repin.")
    return {name: str((project / name).resolve(strict=True)) for name in pins}


def plan(value):
    validate_manifest(value)
    project = Path(value["project"])
    boundary(project, value["repositories"])
    resolved = dependencies(project, value["pins"])
    for name, item in value["files"].items():
        if observed(project, name) != item["before"]:
            fail("STALE", "The original changed; review a new migration, not a force apply.")
    toolkit = {name: sha(regular_bytes(Path(__file__).parent / name)) for name in TOOLS}
    return {"manifest": value, "resolved": resolved, "toolkit": toolkit}


def identity(value):
    return sha(encoded(value))


def check(project):
    state = strict_json(regular_bytes(project / HOME / "state.json"))
    if state.get("schema") != SCHEMA or state.get("project") != str(project):
        fail("STATE", "Review the installed bundle's identity and workspace path.")
    boundary(project, state["repositories"])
    if dependencies(project, state["pins"]) != state["resolved"]:
        fail("DEPENDENCY_DRIFT", "The dependency path changed; review a new baseline.")
    for name, expected in state["installed"].items():
        if observed(project, name) != expected:
            fail("DRIFT", "Review changed instructions/tools; do not rebind silently.")
    return {"schema": SCHEMA, "status": "READY", "project": str(project),
            "plan_sha256": state["plan_sha256"], "bytes": state["bytes"],
            "runtime_environment": "NOT_CHECKED", "product_acceptance": False,
            "model_instruction_loading_verified": False, "token_savings_verified": False}


def apply(value, expected):
    project = Path(value["project"])
    state_path = project / HOME / "state.json"
    if state_path.exists():
        state = strict_json(regular_bytes(state_path))
        if state.get("plan_sha256") == expected and state.get("manifest_sha256") == sha(encoded(value)):
            return check(project)
        fail("INSTALLED", "Review an explicit new migration; existing receipts are not overwritten.")
    initial = plan(value)
    if identity(initial) != expected:
        fail("STALE", "Review the plan and supply its exact digest.")
    with locked(project):
        if plan(value) != initial:
            fail("STALE", "An input changed after review.")
        home = project / HOME
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
        installed, counts = {}, {}
        # Preserve every original before publishing any changed entrypoint.
        for name, item in value["files"].items():
            if item["before"] is not None:
                old = regular_bytes(project / name)
                backup = home / (item["before"] + ".before")
                if backup.exists() and regular_bytes(backup) != old:
                    fail("BACKUP", "Inspect the conflicting backup; never overwrite it.")
                if not backup.exists():
                    atomic_write(backup, old)
                installed[str(backup.relative_to(project))] = sha(old)
            if name in ("AGENTS.md", "CLAUDE.md"):
                counts[name] = {"before": len(regular_bytes(project / name, missing=True)),
                                "after": len(item["text"].encode())}
        for name, expected_hash in initial["toolkit"].items():
            content = regular_bytes(Path(__file__).parent / name)
            if sha(content) != expected_hash:
                fail("STALE", "The installer changed during migration.")
            target = home / name
            if target.exists() and regular_bytes(target) != content:
                fail("TOOL_CONFLICT", "Review the existing private tool; never replace it implicitly.")
            atomic_write(target, content)
            installed[str(target.relative_to(project))] = sha(content)
        for name, item in sorted(value["files"].items(), key=lambda row: not row[0].startswith(HOME)):
            if observed(project, name) != item["before"]:
                fail("STALE", "A target changed during migration; preserve backup and inspect partial publication.")
            target = project / name
            mode = target.stat().st_mode & 0o777 if target.exists() else 0o600
            no_symlinks(target)
            target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            atomic_write(target, item["text"].encode(), mode)
            installed[name] = sha(item["text"].encode())
        if dependencies(project, value["pins"]) != initial["resolved"]:
            fail("DEPENDENCY_DRIFT", "Inspect partial publication and restore reviewed originals if needed.")
        state = {"schema": SCHEMA, "project": str(project), "repositories": value["repositories"],
                 "pins": value["pins"], "resolved": initial["resolved"], "installed": installed,
                 "bytes": counts, "plan_sha256": expected, "manifest_sha256": sha(encoded(value))}
        atomic_write(state_path, encoded(state))
    return check(project)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "check"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--expected")
    args = parser.parse_args()
    try:
        if args.command == "check":
            if args.project is None:
                parser.error("check requires --project")
            result = check(args.project.absolute())
        else:
            if args.manifest is None:
                parser.error("plan/apply requires --manifest")
            value = strict_json(regular_bytes(args.manifest))
            if args.command == "plan":
                result = {"status": "REVIEW_REQUIRED", "plan_sha256": identity(plan(value)),
                          "files": value["files"]}
            else:
                result = apply(value, args.expected)
        print(encoded(result).decode(), end="")
    except (EntryError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(encoded({"status": "BLOCKED", "code": getattr(exc, "code", type(exc).__name__),
                       "recovery": getattr(exc, "recovery", "Inspect the input/path; no automatic recovery.")}).decode(), end="")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
