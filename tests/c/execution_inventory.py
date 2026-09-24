"""Source architecture tripwire, not a sandbox or arbitrary-C security proof."""
from pathlib import Path
import re
import sys

source = Path(sys.argv[1]) / "src"
allowed = {
    "daemon/supervisor.c": {"posix_spawn", "golem_supervisor_run", "golem_supervisor_run_at",
                            "golem_supervisor_run_observed", "golem_supervisor_run_streamed",
                            "golem_supervisor_run_bulk", "golem_supervisor_run_joined"},
    "execution/runner.c": {"golem_supervisor_run_at", "golem_supervisor_run_streamed"},
    "discovery/snapshot.c": {"golem_supervisor_run_at"},
    "workspace/git.c": {"golem_supervisor_run_at", "golem_supervisor_run_bulk"},
    "daemon/resource.c": {"golem_supervisor_run_joined"},
    "daemon/cgroup_exec.c": {"execve"},
    "adapter_protocol/descriptor_probe.c": {"golem_supervisor_run_at"},
    "daemon/worker.c": {"golem_supervisor_run_observed"},
    "cli/daemon_worker.c": {"golem_supervisor_run"},
}
pattern = re.compile(r"\b(posix_spawnp?|fork|vfork|execve|execv|execvp|execvpe|execl|execle|"
                     r"execlp|system|popen|golem_supervisor_run\w*)\s*\(")
observed = {}
for path in source.rglob("*.c"):
    names = set(pattern.findall(path.read_text()))
    if names:
        observed[path.relative_to(source).as_posix()] = names
if observed != allowed:
    raise AssertionError(f"Process boundary changed; review inventory: {observed!r}")
print("Reviewed process-entry inventory matches")
