"""Reviewed source export policy shared by clean builds and Conan (not runtime)."""
from pathlib import Path, PurePosixPath
import os
import shutil
import subprocess

PRIVATE = frozenset({"project-docs", "credentials", "secrets", "reports", "workspace",
    "workspaces", "worktrees", "objects", "events", "candidate-groups", "execution-attempts",
    "build", "dist", "node_modules", "__pycache__"})
BASE = frozenset({"CMakeLists.txt", "LICENSE", "NOTICE", "COMMERCIAL-LICENSE.md"})
TOOLS = frozenset({"verify_runtime.py", "test_verify_runtime.py", "verify_agent.py",
    "doctor_environment.py", "test_doctor_environment.py", "classify_failures.py",
    "test_classify_failures.py", "verify_environment.py", "test_verify_environment.py",
    "benchmark_runtime.py", "verify_isolation.py", "test_verify_isolation.py",
    "verify_resource.py", "test_verify_resource.py", "event_bridge.c", "event_bridge_limits.h",
    "verify_orchestration.py", "test_verify_orchestration.py", "benchmark_orchestration.py"})
# Every data fixture is deliberately reviewed. New local .json/.md files do not
# become public just because their directory or extension looks like a sample.
FIXTURES = frozenset("""
fuzz/corpus/adapter_json/capability.json
fuzz/corpus/adapter_json/request.json
fuzz/corpus/adapter_json/result.json
samples/adapter-descriptor.json
samples/agent-session/AGENTS.fragment.md
samples/agent-session/AGENTS.quickstart.ko.md
samples/agent-session/AGENTS.quickstart.md
samples/agent-session/CLAUDE.quickstart.ko.md
samples/agent-session/CLAUDE.quickstart.md
samples/agent-session/start.json
samples/agent-session/status.json
samples/candidates/group.json
samples/completion/finalize.json
samples/completion/resume.json
samples/context-request.json
samples/discovery/assessment.json
samples/discovery/discovery.md
samples/discovery/plan.json
samples/discovery/research.md
samples/discovery/scope.md
samples/documents/planning.json
samples/documents/planning.md
samples/documents/work.json
samples/execution/contract-v2.json
samples/execution/contract-v3.json
samples/execution/contract.json
samples/reentry/decision.json
samples/research/adjudication-request.json
samples/research/attempt-request.json
samples/research/case.json
samples/research/cohort-observe-request.json
samples/research/cohort-request.json
samples/research/outcome-enroll-request.json
samples/research/redaction-linkable.json
samples/research/redaction-minimal.json
samples/research/request.json
samples/runtime-profile.json
samples/work-capsules/basic.json
tests/c/fixtures/completion/v1-store.json
tests/c/fixtures/journal/v1_cancelled.hex
tests/c/fixtures/journal/v1_default.hex
tests/c/fixtures/journal/v1_invalid_transition.hex
tests/c/fixtures/journal/v1_reentry.hex
""".split())


def selected(name, profile="validation"):
    if profile not in ("validation", "conan"):
        raise ValueError("unknown export profile")
    p = PurePosixPath(name)
    if (not name or p.is_absolute() or ".." in p.parts or "\\" in name or
            p.as_posix() != name or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError("unsafe source path")
    components = p.parts[2:] if p.parts[:2] == ("src", "workspace") else p.parts
    if any(part.startswith(".") or part.casefold() in PRIVATE for part in components):
        return False
    if name in BASE:
        return True
    types = {"src": {".c", ".h"}, "include": {".h"}, "cmake": {".in"}}
    if profile == "validation":
        if name in FIXTURES or name in ("CMakePresets.json", "source_policy.py"):
            return True
        if p.parts[0] == "tools":
            return len(p.parts) == 2 and p.name in TOOLS
        types.update(src={".c", ".h", ".py"}, tests={".c", ".h", ".py", ".cmake"},
                     fuzz={".c", ".h"}, cmake={".cmake", ".in"})
    return (p.parts[0] in types and
            (p.suffix in types[p.parts[0]] or p.name == "CMakeLists.txt"))


def export_sources(root, destination, profile="validation"):
    """Copy reviewed regular files; honor ignores and pending deletions in Git.

    An exported Conan recipe may no longer have .git: the same closed path policy
    still applies. Source roots must be quiescent; this is not a secret scanner.
    """
    root, destination = Path(root).resolve(strict=True), Path(destination)
    if (root / ".git").exists():
        def listing(*args):
            return set(subprocess.check_output(["git", "ls-files", "-z", *args],
                cwd=root, timeout=30,
                env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
                ).decode("utf-8").split("\0")) - {""}
        names = listing("--cached", "--others", "--exclude-standard")
        names -= listing("--cached", "--ignored", "--exclude-standard")
    else:
        names = {p.relative_to(root).as_posix() for p in root.rglob("*") if not p.is_dir()}
    copied = []
    for name in sorted(names):
        if not selected(name, profile):
            continue
        source = root / name
        if source.is_symlink() or any(p.is_symlink() for p in source.parents if p != root.parent):
            raise ValueError("symlink source is not supported")
        if not source.exists():
            continue
        if not source.is_file():
            raise ValueError("non-file source is not supported")
        target = destination / name
        if any(p.is_symlink() for p in (target, *target.parents)):
            raise ValueError("symlink destination is not supported")
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as src, target.open("xb") as dst:
            shutil.copyfileobj(src, dst)
        copied.append(name)
    return copied
