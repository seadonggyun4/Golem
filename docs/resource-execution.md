# Managed Linux Resource Execution

`<golem/resource.h>` provides `golem_resource_run` for a trusted host executing a
managed command. This is separate from the current-agent connector: Golem does
not own an already-running GUI agent's complete process tree.

## Contract

The caller supplies an open descriptor for an **empty, dedicated cgroup v2
directory**, an immutable trusted `golem-cgroup-exec` helper, an absolute target
executable, argv, child cwd, explicit environment, deadline and optional pulse.
The caller owns controller delegation, exclusive scope access and policy/lease/
shell approval. Do not pass the host's root or a shared service scope. The API
does not create scopes, change global controller configuration or acquire root.

Before launch it requires cgroup-v2 identity and an empty hierarchy, then applies:

| Setting | Meaning |
| --- | --- |
| `cpu.max` | Aggregate CPU bandwidth quota/period in microseconds, not CPU affinity. |
| `memory.max` | Kernel cgroup memory charge limit, not virtual address space. |
| `memory.swap.max=0` | No additional swap allowance. |
| `memory.oom.group=1` | Treat the workload as an OOM group. |
| `pids.max` | Task limit, including threads. |

The trusted trampoline joins the scope through inherited descriptor 3 before
`execve` of the target. No user command is run and then retroactively migrated.
All other supervisor APIs retain their original behavior and descriptor policy.
The helper is built/installed on Linux when `GOLEM_BUILD_CLI=ON`; it is not setuid.
The passed environment must be a trusted allowlist; `LD_*` and `DYLD_*` are denied.

After supervision, `cgroup.kill` terminates remaining members and descendants.
The API checks `cgroup.events` for `populated=0`, polling at most 500 times with
10 ms delays. Signalling alone is not considered termination. The caller retains
the scope and can collect kernel counters before removing its own directory.
Failure does not release admission reservations automatically. A nonempty/error
scope needs reconciliation; never infer termination from a failed return.

All arguments are borrowed for the synchronous call. `empty` is initialized false;
the supervisor result is unchanged before spawn. Partial limit configuration can
remain after a setup error: the caller still owns the dedicated empty scope.
There is no automatic retry, QA receipt, acceptance or billing attestation.
Missing controllers, a normal filesystem directory, a populated scope or a
non-Linux platform fails closed. No fallback to unconstrained execution occurs.

## Threat Model

Kernel limits are not a malicious-code sandbox. A process with permission to
rewrite controllers or migrate itself can escape. The host must prevent that
through its separate security boundary before using this for untrusted code.
There is no filesystem/network/UID isolation in this API. Parent cgroup limits
may be stricter than requested. Remote services and already-running agents are
outside scope. CPU/RSS benchmarks and all-platform containment are not claimed.

## Verification

`golem_test_resource` always tests invalid-argument behavior. Real kernel tests
are explicit, because ordinary CTest must not silently create privileged scopes:

```sh
golem_test_resource /absolute/golem-cgroup-exec /delegated/empty-scope normal
golem_test_resource /absolute/golem-cgroup-exec /delegated/empty-scope memory
golem_test_resource /absolute/golem-cgroup-exec /delegated/empty-scope cpu
golem_test_resource /absolute/golem-cgroup-exec /delegated/empty-scope tasks
```

Use only an isolated test scope. Tests use a 32 MiB memory cap, 10% CPU bandwidth,
four tasks and a two-second deadline. Check `cpu.stat`, `memory.events`,
`pids.events` and `cgroup.events` as independent kernel observations. These
controlled fixtures are not live-provider or full candidate-host qualification.

## References

- [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html): controller
  hierarchy, fork inheritance, migration, `cgroup.kill`, populated and OOM events.
- [OSTEP, Limited Direct Execution](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-mechanisms.pdf):
  distinguishes OS enforcement from cooperative application policy.
- [Build Systems a la Carte](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems-final.pdf):
  input identity/freshness remains a separate verification obligation; resource
  enforcement alone is not evidence that a result satisfies acceptance.
