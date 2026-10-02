"""Render, apply and check a small project entrypoint without rewriting user rules."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import tempfile

from verify_agent import capture, digest, save, strict_json

SCHEMA = "golem.agent-entrypoint.v1"
BEGIN = b"<!-- golem:entrypoint:v1 -->\n"
END = b"<!-- /golem:entrypoint -->\n"
LIMIT = 1024 * 1024
MAX_BLOCK = 4096
MAX_TOTAL = 32768
DOCS = ("agent-efficiency.md", "discovery.md", "workflow.md", "document-registry.md",
        "agent-session.md", "execution.md", "reentry.md", "completion.md", "approvals.md")
PLACEHOLDERS = ("GOLEM_EXECUTABLE", "GOLEM_WORK_ROOT", "GOLEM_DOCS_DIR", "TARGET_REPOSITORIES")


class EntryError(ValueError):
    def __init__(self, code, recovery):
        self.code, self.recovery = code, recovery
        super().__init__(code)


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def regular_bytes(path, missing=False):
    if path.is_symlink():
        raise EntryError("SYMLINK", "Select regular files, not symlink instruction or configuration files.")
    if not path.exists() and missing:
        return b""
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > LIMIT:
        raise EntryError("UNSAFE_FILE", "Use a bounded regular file with one hard link.")
    return path.read_bytes()


def no_symlinks(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise EntryError("SYMLINK", "Use a real path without symlink components.")


def git(project, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", str(project), *args], capture_output=True,
                          check=True, timeout=30, env=env).stdout


def split_block(data):
    # Malformed/duplicate markers must not turn a replacement into a deletion.
    if data.count(BEGIN.rstrip()) != data.count(END.rstrip()) or data.count(BEGIN.rstrip()) > 1:
        raise EntryError("MARKERS", "Repair duplicate or incomplete managed markers after reviewing the original.")
    if BEGIN.rstrip() not in data:
        if re.search(rb"(?im)^#{1,6}\s+Golem(?:\s|$)", data) or b"<GOLEM_" in data:
            raise EntryError("UNMANAGED_GOLEM", "Review existing Golem rules; do not append a second conflicting block.")
        return data, None, b""
    start = data.find(BEGIN)
    end = data.find(END)
    if start < 0 or end < start or (start and data[start - 1:start] != b"\n"):
        raise EntryError("MARKERS", "Use complete v1 markers on separate LF-terminated lines.")
    return data[:start], data[start:end + len(END)], data[end + len(END):]


def read_setup(project):
    project = project.resolve(strict=True)
    if Path(git(project, "rev-parse", "--show-toplevel").decode().strip()).resolve() != project:
        raise EntryError("PROJECT_ROOT", "Select the target Git repository root.")
    config_bytes = regular_bytes(project / ".golem-agent.json")
    config = strict_json(config_bytes)
    fields = {"schema", "language", "sdk", "cli", "work_root", "repositories"}
    if (not isinstance(config, dict) or set(config) != fields or config["schema"] != SCHEMA
            or config["language"] not in ("en", "ko") or not isinstance(config["repositories"], list)
            or not config["repositories"] or len(config["repositories"]) > 16):
        raise EntryError("CONFIG", "Use the documented v1 config with language en/ko and explicit target repositories.")

    def location(value):
        if (not isinstance(value, str) or not value or any(ord(c) < 32 for c in value)
                or any(c in value for c in "`<>")):
            raise EntryError("PATH", "Use literal paths without control characters, backticks or template placeholders.")
        resolved = (project / value).resolve()
        if any(ord(c) < 32 or c in "`<>" for c in str(resolved)):
            raise EntryError("PATH", "Use resolved paths that can be represented safely in the entrypoint.")
        return resolved

    sdk, cli, work = (location(config[k]) for k in ("sdk", "cli", "work_root"))
    repos = [location(value) for value in config["repositories"]]
    if len(set(repos)) != len(repos) or any(not p.is_dir() for p in repos):
        raise EntryError("REPOSITORIES", "Select unique existing repository directories.")
    for repo in repos:
        if Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve() != repo:
            raise EntryError("REPOSITORIES", "Each target must be a Git repository root.")
    runtime = project / ".golem"
    no_symlinks(runtime)
    # A lexical check rejects a work symlink even if it resolves inside .golem.
    no_symlinks((project / config["work_root"]).absolute())
    if runtime not in work.parents or work == runtime / "entrypoints" or runtime / "entrypoints" in work.parents:
        raise EntryError("WORK_ROOT", "Choose a Work directory below this project's .golem, outside entrypoints.")
    if git(project, "ls-files", "--", ".golem/"):
        raise EntryError("TRACKED_RUNTIME", "Review tracked private runtime files; this tool never removes them from Git.")
    for private_path in (".golem/entrypoints/state.json", str(work / "probe")):
        git(project, "check-ignore", "--", private_path)
    if not cli.is_file() or not os.access(cli, os.X_OK):
        raise EntryError("CLI_MISSING", "Install/build the explicitly selected CLI; no installation is performed here.")
    language = config["language"]
    template_path = sdk / "samples/agent-session" / ("AGENTS.minimal.ko.md" if language == "ko" else "AGENTS.minimal.md")
    template = regular_bytes(template_path).decode("utf-8")
    required = {"samples/agent-session/" + template_path.name: sha(template.encode())}
    for name in DOCS:
        required["docs/" + name] = sha(regular_bytes(sdk / "docs" / name))
    tool = sdk / "tools/agent_entrypoint.py"
    required["tools/agent_entrypoint.py"] = sha(regular_bytes(tool))
    required["tools/verify_agent.py"] = sha(regular_bytes(sdk / "tools/verify_agent.py"))
    required["tools/execution_record.py"] = sha(regular_bytes(sdk / "tools/execution_record.py"))
    for name in ("agent_entrypoint.py", "verify_agent.py", "execution_record.py"):
        if required["tools/" + name] != digest(Path(__file__).resolve().parent / name):
            raise EntryError("SDK_TOOL_MISMATCH", "Run this SDK's matching entrypoint tool and helpers; do not mix revisions.")
    for name in PLACEHOLDERS:
        if template.count("<" + name + ">") != 1:
            raise EntryError("TEMPLATE", "Use a reviewed minimal template with each required placeholder once.")
    paths = [cli, work, sdk / "docs"]
    displays = [os.path.relpath(p, project) if p.is_relative_to(project) else str(p) for p in paths]
    displays.append(", ".join(os.path.relpath(p, project) if p.is_relative_to(project) else str(p) for p in repos))
    for name, value in zip(PLACEHOLDERS, displays):
        template = template.replace("<" + name + ">", value)
    command_path = os.path.relpath(tool, project) if tool.is_relative_to(project) else str(tool)
    command = shlex.join(["python3", command_path, "check", "--project", "."])
    entry = ("\n### Entry\n\nRun from this project root before Golem-managed work:\n\n"
             f"```sh\n{command}\n```\n\n"
             "Paths above are relative to this root unless absolute. Resolve SDK filenames under the docs directory.\n"
             "A failed check blocks Golem-managed effects; inspect its diagnostic, never auto-repin or bypass.\n"
             "READY checks configuration only, not runtime permission, QA, or Work completion.\n")
    block = BEGIN + (template.rstrip() + "\n" + entry).encode() + END
    if len(block) > MAX_BLOCK:
        raise EntryError("BLOCK_BUDGET", "Shorten paths or review the minimal template; safety rules are never truncated.")
    override = project / "AGENTS.override.md"
    if override.exists() or override.is_symlink():
        if regular_bytes(override).strip():
            raise EntryError("OVERRIDE", "Review AGENTS.override.md, which shadows this root entrypoint; do not delete it automatically.")
    bindings = {"config_sha256": sha(config_bytes), "sdk": str(sdk), "cli": str(cli),
                "cli_sha256": digest(cli), "sdk_files": required, "work_root": str(work),
                "repositories": list(map(str, repos)), "language": language,
                "renderer_sha256": digest(Path(__file__).resolve())}
    return project, block, bindings


def plan(project):
    project, block, bindings = read_setup(project)
    path = project / "AGENTS.md"
    old = regular_bytes(path, missing=True)
    old.decode("utf-8")
    prefix, previous, suffix = split_block(old)
    if previous is None and prefix:
        prefix += b"\n" if prefix.endswith(b"\n") else b"\n\n"
    new = prefix + block + suffix
    if len(new) > MAX_TOTAL:
        raise EntryError("TOTAL_BUDGET", "Review project instructions explicitly; this tool never truncates existing rules.")
    return {"project": project, "old": old, "new": new, "bindings": bindings,
            "before": sha(old) if path.exists() else "absent", "block": block,
            "outside_sha256": sha(prefix + suffix)}


def plan_identity(value):
    return sha(encoded({"project": str(value["project"]), "before": value["before"],
                        "after": sha(value["new"]), "bindings": value["bindings"]}))


def atomic_write(path, data, mode=0o600):
    no_symlinks(path)
    fd, name = tempfile.mkstemp(prefix=".entrypoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def locked(project):
    directory = project / ".golem/entrypoints"
    no_symlinks(directory)
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    path = directory / "apply.lock"
    try:
        save(path, encoded({"pid": os.getpid()}))
    except FileExistsError:
        raise EntryError("BUSY", "Inspect the existing apply process/lock; never remove a live lock automatically.") from None
    try:
        yield directory
    finally:
        path.unlink()


def apply(project, expected):
    project = project.resolve(strict=True)
    # Validate before creating even the private lock directory.
    planned = plan(project)
    with locked(project) as directory:
        current = plan(project)
        if current != planned or expected != plan_identity(current):
            raise EntryError("STALE", "Review a fresh plan and pass its plan_sha256; no file was replaced.")
        target = project / "AGENTS.md"
        state_path = directory / "state.json"
        if current["old"] == current["new"] and state_path.exists():
            previous = strict_json(regular_bytes(state_path))
            if (previous.get("schema") == SCHEMA and previous.get("bindings") == current["bindings"]
                    and previous.get("agents_sha256") == sha(current["new"])
                    and previous.get("block_sha256") == sha(current["block"])
                    and previous.get("outside_sha256") == current["outside_sha256"]):
                return check(project)
        backup = None
        if current["before"] != "absent":
            backup = directory / (current["before"] + ".before.md")
            if not backup.exists():
                save(backup, current["old"])
            elif regular_bytes(backup) != current["old"]:
                raise EntryError("BACKUP", "Preserve and inspect the mismatched backup before retrying.")
        mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
        work = Path(current["bindings"]["work_root"])
        work.mkdir(parents=True, mode=0o700, exist_ok=True)
        if regular_bytes(target, missing=True) != current["old"]:
            raise EntryError("STALE", "The file changed during application; inspect it and make a fresh plan.")
        if current["old"] != current["new"]:
            atomic_write(target, current["new"], mode)
        state = {"schema": SCHEMA, "bindings": current["bindings"],
                 "agents_sha256": sha(current["new"]), "block_sha256": sha(current["block"]),
                 "outside_sha256": current["outside_sha256"], "before_sha256": current["before"],
                 "backup": str(backup) if backup else None}
        if state_path.exists():
            previous = strict_json(regular_bytes(state_path))
            if all(previous.get(k) == state[k] for k in ("schema", "bindings", "agents_sha256", "block_sha256", "outside_sha256")):
                return check(project)
        atomic_write(state_path, encoded(state))
    return check(project)


def check(project, probe=False):
    current = plan(project)
    project = current["project"]
    directory = project / ".golem/entrypoints"
    no_symlinks(directory)
    state = strict_json(regular_bytes(directory / "state.json"))
    if (state.get("schema") != SCHEMA or state.get("bindings") != current["bindings"]
            or current["old"] != current["new"] or state.get("agents_sha256") != sha(current["old"])
            or state.get("block_sha256") != sha(current["block"])
            or state.get("outside_sha256") != current["outside_sha256"]):
        raise EntryError("DRIFT", "Inspect changed instructions, config, SDK or binary; reapply only after explicit review.")
    if not Path(current["bindings"]["work_root"]).is_dir():
        raise EntryError("WORK_ROOT", "Restore the selected private Work root; do not discard existing runtime state.")
    result = {"schema": SCHEMA, "status": "READY", "agents_sha256": sha(current["old"]),
              "entry_bytes": len(current["old"]), "managed_bytes": len(current["block"]),
              "discovery": "ROOT_STATIC_CHECK_ONLY", "cli_probe": "NOT_RUN",
              "build_provenance_verified": False, "runtime_environment": "NOT_CHECKED",
              "model_instruction_loading_verified": False, "product_acceptance": False}
    if probe:
        tmp = Path(tempfile.mkdtemp(prefix="probe-", dir=directory))
        outcome = capture([current["bindings"]["cli"], "--version"], tmp, 10, project)
        version = (tmp / "stdout.log").read_bytes()
        if (outcome["reason"] != "EXIT" or outcome["returncode"] != 0
                or not re.fullmatch(rb"(?:golem )?\d+\.\d+\.\d+\r?\n", version)
                or digest(Path(current["bindings"]["cli"])) != current["bindings"]["cli_sha256"]):
            raise EntryError("CLI_PROBE", "Inspect retained probe records at " + str(tmp) + "; do not rerun effects.")
        result["cli_probe"] = "PASS"
        result["probe_records"] = str(tmp)
        result["version"] = version.decode("utf-8").strip()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "check"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--expected", help="reviewed plan_sha256 binding config, SDK, binary and AGENTS; required for apply")
    parser.add_argument("--probe", action="store_true", help="check only: explicitly run selected CLI --version")
    args = parser.parse_args(argv)
    if (args.command == "apply" and args.expected is None) or (args.probe and args.command != "check"):
        parser.error("apply requires --expected; --probe is check-only")
    try:
        if args.command == "plan":
            value = plan(args.project)
            result = {"schema": SCHEMA, "before_sha256": value["before"],
                      "plan_sha256": plan_identity(value),
                      "after_sha256": sha(value["new"]), "before_bytes": len(value["old"]),
                      "after_bytes": len(value["new"]), "managed_bytes": len(value["block"]),
                      "candidate": value["new"].decode(), "product_acceptance": False}
        elif args.command == "apply":
            result = apply(args.project, args.expected)
        else:
            result = check(args.project, args.probe)
        print(encoded(result).decode(), end="")
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        result = {"schema": SCHEMA, "status": "BLOCKED", "code": getattr(error, "code", "CONFIG_OR_FILES_UNAVAILABLE"),
                  "recovery": getattr(error, "recovery", "Inspect selected paths, Git ignore rules and config; do not bypass or auto-retry effects."),
                  "error_type": type(error).__name__, "product_acceptance": False}
        print(encoded(result).decode(), end="")
        return 1


if __name__ == "__main__":
    sys.exit(main())
