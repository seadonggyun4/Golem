# Bounded Worker Executor (Version 1)

[Runtime diagnostics](runtime-events.md) expose bounded read-only event pages
without giving observers execution callbacks or release authority.

The optional C API in `golem/worker.h` runs external processes without making the
coordinator wait for their exit. Existing synchronous supervisor and daemon tick
APIs remain available and are **not automatically enrolled**. This is an executor,
not a new provider, authorization service, durable queue, or sandbox.

## Ownership and Scheduling

One coordinator thread owns a pool. All public calls must come from that thread
in the creating process; callback reentry and inherited post-fork handles fail.
`submit` copies argv, environment, cwd, executable and stdin. No Work store handle,
allocator callback, or agent callback is invoked on a supervisor thread.

Each launched job has a bounded supervisor thread that uses `posix_spawn` and the
existing supervisor. Long waits, pipe draining and child reaping happen there.
Control calls inspect atomically published state; they never join a running child.
This is not a lock-free/real-time latency promise: allocation, thread creation,
publication and admission fsync can block. Schedule durable disk work accordingly.
`close` joins only supervisors that have returned their result, not running work.

The host chooses queued jobs using the admission arbiter; there is no second
competing FIFO inside the executor. `LEASE_BUSY` means local resources are still
reserved; the job stays queued. Each pool retains at most 64 job IDs, never reused.
Drain/close and open a new pool for the next batch; keep the same admission authority.
Nested admission tickets are rejected by this first executor backend.

## Resource Contract

| Field | Meaning |
| --- | --- |
| `worker_slots` | 1..32 active or unsettled worker reservations; helper default 1 |
| `cpu_units` | Positive reservation budget; same unit as admission `cpu_millis` |
| `memory_bytes` | Positive reservation budget, not measured RSS |
| `io_slots` | Positive concurrent I/O reservation count, not kernel throughput |
| `queue_bytes` | Positive outstanding copied-input budget, maximum 64 x 32 KiB |
| `foreground_slots` | 0..worker_slots-1; slots withheld from background jobs |
| `timeout_ns`, `lease_ns` | Positive monotonic duration, maximum one hour |

Missing/zero capacities are invalid, not unlimited. `options_default` is the only
defaulting helper. A request larger than total capacity fails immediately. Runtime
fit checks subtract reservations from capacity, avoiding sum overflow. Finished but
unacknowledged jobs still reserve execution resources. Idempotent acknowledgment
subtracts exactly once.

QA and background are scheduling classes, **not permissions**. The foreground
reserve protects slots only, not CPU/memory/I/O headroom. The coordinator itself
never acquires a worker slot; a one-slot configuration must use reserve=0.
No CPU/memory OS-enforcement capability is asserted. Use an independently verified
host containment backend where strict enforcement is required.

Storage is fixed and allocator-owned: 64 payload buffers of 32 KiB, 64 pairs of
16 KiB output buffers, vector storage, metadata, and at most 64 retained thread
handles/stacks. Only up to worker_slots supervisors execute concurrently. The
logical queue-byte cap does not reduce this fixed allocation. Default allocator
may be replaced; its context must outlive close. Allocator calls are coordinator-only.

## Durable Launch and Evidence

1. Submit the copied request, enqueue/grant the matching 30C admission request.
2. Call `golem_worker_start(pool, job, admission, operation, publish, context)`.
3. Executor checks local capacity, GRANTED state, root ticket, exact CPU/memory
   reservation and foreground class. Its publisher must check current policy,
   lease, runtime binding, and enrolled harness capabilities. Production Work
   publication uses `golem_admission_publish_work`; close that writer afterward.
4. Admission commits BIND, STARTING and RUNNING before any supervisor thread launch.
   Existing RUNNING/uncertain tickets cannot be launched again, even in a new pool.
5. Inspect until FINISHED or ATTENTION. Record command identity, status, stdout,
   stderr, timeout/cancellation/lease state and termination observations in evidence.
   A zero exit alone is not QA or completion acceptance.
6. After verifying termination and persisting the receipt, settle and release the
   **exact** admission token. Then acknowledge the worker. Acknowledgment verifies
   authority digest, ticket, epoch, instance, boot identity and RELEASED state.

Publisher failure produces no executor launch; inspect the admission ledger before
retrying after uncertain I/O. Thread creation failure after committed RUNNING is a
FINISHED result with `spawned=false`, not implicit admission release or retry.
The API is a trusted host boundary; it does not authenticate arbitrary receipt hashes.

For cancellation, commit `golem_admission_cancel` and request `golem_worker_cancel`.
The latter is immediate on the control thread; the supervisor notices it on its
pulse and kills/reaps according to the existing supervisor contract. Canceling a
queued job proves nonexecution. A cancel flag alone never returns a running slot.

Heartbeat only extends an unexpired local watchdog after the host renews its real
lease. It cannot revive a canceled, expired, finished or acknowledged job. The
initial deadline includes publication time. Cancellation racing natural completion
is reported separately from the actual exit status; no successful exit is invented.

## IPC, Termination and Recovery Limits

IPC is existing bounded raw stdin/stdout/stderr, not a new message protocol:
32 KiB total copied request, <=64 argv and environment entries each, <=16 KiB stdin,
and <=16 KiB per output stream. Oversized output fails, never becomes success.
Explicit executable/cwd and environment avoid shell/PATH resolution. Linux creates
internal descriptors with atomic CLOEXEC; Darwin spawn closes descriptors not
explicitly mapped by file actions. The host must also use CLOEXEC for its own fds.

The additive `golem_supervisor_run_observed` API exposes `spawned` and `reaped`
without changing the legacy result layout. A missing direct-child reap produces
ATTENTION, refuses acknowledgment, and retains capacity. Killing a process group
is **not** proof that escaped descendants, remote effects, or detached jobs ended.
The host must obtain stronger containment receipts if its workload requires them.
No automatic PID-based orphan killing, exactly-once external effect claim, or
reuse after timeout is provided.

After coordinator death, the durable admission replay retains RUNNING attempts as
RECONCILE_REQUIRED. A new executor refuses them. Even a late file marker is not a
termination receipt. External reconciliation must prove termination/nonexecution
before settlement. Closing a pool with returned results can discard local buffers,
but never releases admission reservations. Closing with queued/running jobs fails.

## Verification and Research

Worker tests cover two-process rendezvous (actual overlap), reservations, request
bounds, foreground exclusion, cancellation, lease expiry, timeouts, exit/signal,
output overflow, spawn failure, OOM, thread creation failure, unobserved reaping,
publisher reentry and owner SIGKILL/replay without redispatch. Fault observations
are injected in a separate test translation unit, not a production fault switch.
These are deterministic fixtures, not a live agent canary or power-loss proof.

Design references and deliberately limited applications:

- [SEDA, SOSP 2001, sections 3 and 4.2](https://www.cs.princeton.edu/courses/archive/fall04/cos518/papers/seda.pdf):
  bounded stages and offloading blocking work. We use a fixed bound, not its adaptive controller.
- [Site Reliability Engineering, Handling Overload](https://sre.google/sre-book/handling-overload/):
  resource accounting and criticality motivate explicit resource dimensions/classes.
- [OSTEP, Condition Variables, sections 30.1-30.2](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-cv.pdf):
  completion and bounded-buffer synchronization. Our single-owner queue and C11
  release/acquire publication avoid sharing mutable result buffers before completion.
- [Borg, EuroSys 2015, official abstract](https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/):
  admission and process isolation are separate concerns; no cluster scheduler is imported.
- [Linux man-pages: wait](https://man7.org/linux/man-pages/man2/waitpid.2.html)
  and [posix_spawn](https://man7.org/linux/man-pages/man3/posix_spawn.3.html):
  child observation/reaping and process setup contracts. Platform tests remain necessary.

No cited performance result is claimed as a measured improvement in Golem.
