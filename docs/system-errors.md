# Scoped system failure observations

## Design and compatibility

The CLI's existing error envelope is a terminal command result, not a reliable
place to read `errno`: cleanup and unrelated successful operations may already
have changed it. Native code now records observations at selected failure
branches through `golem_system_error_note`. The return status and errno are
preserved. There is no automatic retry, repair, permission escalation, syscall
interposition, new logging service, or dependency.

`include/golem/system_error.h` provides a separate additive C API. Existing
`golem_diagnostic`, status enums, function signatures, storage bytes and success
protocols are unchanged. The collector performs no allocation, filesystem I/O,
clock read, callback or serialization. It is off unless a caller opens a scope.

```c
golem_system_error_scope errors;
golem_status st = golem_system_error_begin(&errors);
if (st == GOLEM_OK) {
    st = golem_evidence_verify(store, key, &size, &diagnostic);
    (void)golem_system_error_end(&errors);
    /* Inspect st and errors separately; observations are not causal proof. */
}
```

Scopes use caller-owned storage and a thread-local active pointer, not a
process-global last-error object. End them in same-thread LIFO order before
returning or unwinding storage. Repeated begin and out-of-order end are rejected.
Nested scopes are isolated, so callers must explicitly transfer any inner
observations they need. Other threads require their own scopes. Forked address
spaces are independent copies; there is no cross-process aggregation. Do not use
the API from signal handlers, across longjmp, or as asynchronous task context.

Each scope retains the first observation and the most recent seven. `omitted`
counts discarded intermediate observations and saturates at `SIZE_MAX`.
Component/operation labels are copied, bounded to 63 bytes, and normalized to
ASCII label characters; truncation is explicit. Internal callers use fixed
labels, never paths, argv, environments, request bodies, credentials or localized
`strerror` messages. This is not a sanitizer for arbitrary caller-supplied secrets.

An error number is recorded only where the failed operation establishes it is
valid. Successful `fstat` followed by a file-type/size violation, EOF, zero-byte
write progress and deadline checks use zero (JSON null), not ambient errno.
Existing EINTR loops and close/no-retry behavior remain unchanged. Helpers can
report failures later handled by a caller; a scope is therefore a bounded
observation sequence, never an automatically inferred root-cause chain.

## CLI extension

`golem.cli-error.v1` adds:

| Field | Contract |
| --- | --- |
| `system_errors` | Bounded observation array, in retained order |
| `system_errors_omitted` | Discarded intermediate count |
| `system_errors_role` | `OBSERVATIONS_NOT_INFERRED_CAUSES` |

Each observation has `component`, `operation`, native `status_code`, `kind`
(`system` or `validation`), `errno`, `errno_name`, `next_action`, and `truncated`.
Symbolic errno names are best-effort portable names; unknown numbers are retained
as `UNKNOWN_ERRNO`, and aliases such as EAGAIN/EWOULDBLOCK can share a name.
Recovery guidance is centralized and conservative, not execution authorization.

The envelope's original `code`, `errno`, domain diagnostic and exit status retain
their contracts. The top-level errno is NOT filled from an arbitrary observation.
Success emits no error envelope even if a fallback observed an earlier failure.
The existing minimal allocation-failure envelope remains available. Recording
finalization after successful dispatch starts a fresh CLI diagnostic scope.

## Applied boundaries

| Source | Instrumented failure boundaries |
| --- | --- |
| `src/evidence/fs.c` | Secure path open/traversal; scan stat/read/write/restat; digest close |
| `src/evidence/cas.c` | Directory/object/temporary open; mkdir, sync, chmod, link, unlink, close, receipt reads |
| `src/evidence/read.c` | Stat, reads, unexpected EOF/tail, close |
| `src/document/storage.c`, `src/document/record_read.c` | Directory, immutable publication, file reads, replay directory operations |
| `src/journal/file.c` | Open/stat/flock, pread, append/write/fsync/close, recovery restat |
| `src/daemon/storage.c` | Shared daemon lock, read, immutable publication and listing |
| `src/agent_session/clock.c` | Boot identity syscall/read versus identity-size validation; monotonic clock |
| `src/cli/io.c` | Existing request diagnostics plus directory creation and immutable publication |
| `src/cli/candidate_host_transport.c` | Socket/connect/bind/listen, transfer, peer credential query, fcntl, clock |
| `src/cli/error.c` | Shared request/stdout errno reports enter the same observation schema |
| `src/daemon/supervisor.c` | Socket/pipe creation, descriptor preparation, spawn actions/attributes and launch, clock, send/read/poll, wait, group kill and descriptor/spawn-object cleanup |
| `src/daemon/resource.c`, `src/daemon/resource_io.c` | Platform/filesystem requirements, fixed cgroup control-file open/read/write/close, descriptor duplication, populated-state validation, cleanup sleep and exhaustion |
| `src/daemon/worker.c` | Clock and semantic clock validation, returned pthread create/join error numbers; completed per-job diagnostic snapshots |
| `src/inventory/capture.c`, `src/workspace/git.c` | Directory traversal/open/stat/read/readlink/close; errno-free identity/shape failures; expected missing content and successful EINTR retries excluded |
| `src/daemon/admission_storage.c`, `src/daemon/recovery.c`, `src/daemon/queue.c`, `src/daemon/scheduler.c` | Event/recovery reads, stat vs frame shape, directory iteration, append/fsync, queue publication, clock/sleep and cleanup |
| `src/common/record.c` | Recorder root permissions vs syscall failure, intent/result publication, stream open/write/sync/seek and close; no recursive recording |
| `src/adapter_protocol/descriptor_probe.c` | Monotonic clock failure vs invalid/overflowing clock value |
| `src/runtime/loop.c` | Monotonic clock syscall vs invalid value/overflow; callback errors remain callback statuses |
| `src/document/registry.c` | Empty-root scan, flock and store/scan close; primary and cleanup failures both retained |
| `src/daemon/cgroup_exec.c`, `cgroup_exec_internal.h` | Child stderr `golem.child-system-error.v1`: fstatfs/type, membership open/write/close, scope close, execve |

This is NOT all-syscall coverage. Unlisted direct OS calls still have their
previous diagnostic contracts; platform-dependent optional identity probes and
unreviewed CLI/helper cleanup sites have not been universally instrumented.
Cleanup errors and signal delivery outside the listed boundaries are not
comprehensively collected. Cgroup trampoline diagnostics are fixed-label child
stderr, never silently merged into parent TLS. An arbitrary child can emit the
same text, so this is not authenticated provenance. The parent's thread-local
scope does not capture child syscalls. [Explicit Linux tracing](syscall-recording.md)
provides separate raw evidence, with no automatic fallback on unsupported hosts.
An empty array means no collected observation, not absence of system failures.
The host transport's per-request response schema is unchanged; observations from
an earlier handled request can remain in its enclosing command scope.

To extend coverage, annotate a terminal failure branch with fixed labels before
cleanup, retain existing status/retry/ownership behavior, separate compound
syscall and validation checks, then add deterministic fault injection. Do not
wrap every syscall blindly: EEXIST, ENOENT probes, EINTR and timeouts can be
expected control flow. Do not turn this table into a claim of complete coverage.

### Process and resource extension

The 2026-10-04 extension distinguishes errno-based calls from `posix_spawn*`
functions, which return error numbers directly. `supervisor.spawn` observations
use that returned number, never ambient errno. Spawn destruction failures are
also observations. Pre-spawn failures still leave the caller's result unchanged;
post-spawn observations preserve the existing spawned/reaped/result contract.
An exit status of 126 or 127 alone does not establish which child syscall failed.

### Worker, traversal and recorder extension

The second 2026-10-04 extension separates POSIX thread return codes from errno,
keeps an inactive bounded diagnostic snapshot per job, and publishes it through
the job's existing release/acquire completion flag. A running job cannot be read
prematurely. The parent scope is not implicitly filled with another thread's
observations; callers use `golem_worker_diagnostics`. No request bytes or paths
are added. The existing snapshot ABI is unchanged; getters are additive.

Inventory/workspace scans distinguish syscall failure from a changed inode or
size. Expected ENOENT deletions are not error observations. An unavailable initial
inventory clock now fails before scanning instead of manufacturing a deadline
from zero. Queue initialization refuses a failed format lookup other than ENOENT
before writing, rather than treating an unreadable format as absent. These two
changes are explicit fail-closed corrections, not merely additional diagnostics.

Recorder failures use the same allocation-free collector, never the recorder
itself. Closing after a primary error still records cleanup failure without
overriding that error. A failed nested process recording marks its live enclosing
record failed; this does not retroactively change a completed asynchronous parent.
Optional unavailable producer/source identity retains its existing explicit
status representation. Observations alone do not establish rollback or retry safety.

The supervisor records unexpected group-kill failures even when an earlier
operation already failed. Expected ESRCH is not recorded; Darwin's existing
exited-leader EPERM/pipe-drain policy remains intact. Descriptor close failures
are recorded once without retries or status replacement. Cleanup observations
can coexist with GOLEM_OK, and the CLI still emits no failure envelope on
success. They are not a newly inferred failure or a license to repeat execution.
No diagnostics are collected for successfully retried EINTR or normal
nonblocking EAGAIN. Invalid clock values have no errno observation.

Resource I/O is separated into a private POSIX module so error handling can be
tested without delegated controllers. Fixed control names (`cpu.max`,
`memory.max`, `cgroup.events`, etc.) identify components; paths and control
values are never collected. The Linux owner still checks cgroup-v2 identity,
empty/exclusive scope requirements and loader-variable policy before execution.
Short writes are not retried as partial cgroup commands. Failed reads/writes are
recorded before close, and malformed/empty event data uses errno zero. The
existing execution-versus-cleanup return-status precedence is unchanged.
Unsupported-platform and wrong-filesystem failures are semantic observations,
not fabricated permission errors. No host-wide limits or cgroup ownership are
changed by this extension.

## Verification

- `system_error_scope`: disabled collection, nested/LIFO behavior, reset,
  cross-thread isolation, errno preservation, label truncation, capacity and
  saturated omission count, unknown errno.
- `system_error_faults`: ten real publication scenarios with private syscall
  injection, including write versus cleanup error, zero progress with stale errno,
  open/chmod/link/unlink/close and pre/post-publication fsync failures.
- `system_error_clock`: four deterministic boot identity/clock scenarios;
  malformed successful output does not acquire a stale errno.
- `journal_syscall_faults`: existing partial write/EINTR/fsync tests now also
  assert observations and no diagnostic on successfully retried EINTR.
- `cli_error_contract`: additive fields, null validation errno, observation versus
  terminal status, missing-file origin, no path reflection, reset and allocation
  fallback alongside the existing catalog and stdout tests.
- `supervisor_diagnostics`: 29 deterministic scenarios on Darwin (28 on Linux),
  including returned spawn errors with stale errno, setup/I/O/wait/kill failures,
  primary-plus-cleanup failures, cleanup-only success, and successful EINTR
  retry. Test-local replacements never create or signal a real child.
- `resource_diagnostics`: 11 regular-file/fault-injection scenarios for control
  I/O, malformed populated state, primary/close error ordering and unchanged
  outputs. These do NOT exercise Linux cgroup kernel semantics.
- `supervisor_spawn_diagnostics` and `supervisor_stream`: actual missing-executable
  spawn diagnostics and streaming/cancellation/reaping contracts on a supported host. Existing
  supervisor exit-race/input-close tests retain real lifecycle coverage.
- `resource_api`: unsupported platform or ordinary-filesystem rejection retains
  output ownership and carries a semantic observation.

Host regressions remain separate from restricted diagnostics. These tests do not
prove all filesystem crash behavior, all platform branches, or all syscall
coverage; Linux execution and remote CI require separate validation.

## Research

Relevant sections and primary-source examples were inspected on 2026-10-02,
not entire books. Implementation is original; no reference implementation code
was copied. These are design deductions, not empirical Golem effectiveness claims.

| Reference and inspected scope | Application |
| --- | --- |
| Michael Kerrisk, *The Linux Programming Interface* (2010), author's [Listing 3-3, error handling](https://man7.org/tlpi/code/online/dist/lib/error_functions.c.html) and [chapter 3 contents](https://man7.org/tlpi/toc-detailed.html) | Capture and preserve errno before reporting; distinguish explicit error numbers from semantic failures. Only the public listing and contents were inspected, not the complete chapter/book. |
| Yuan et al., [Simple Testing Can Prevent Most Critical Failures](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf), OSDI 2014, abstract, sections 3.4 and 4 | Test failure handlers, not only success paths; retain useful evidence without promoting logs to causal proof. Published failure rates do not transfer to Golem. |
| The Open Group, [Error Numbers, Issue 6 section 2.3](https://pubs.opengroup.org/onlinepubs/009696799/functions/xsh_chap02_03.html) | Inspect errno only after a return value establishes validity. Indexed text was available; current Issue 8 pages returned 403, so no full current-standard conformance claim is made. |
| Linux man-pages, [close(2), dealing with error returns](https://man7.org/linux/man-pages/man2/close.2.html) | Keep close failures observable without adding blind retries; preserve uncertainty after publication. Platform-specific EINTR semantics must not be generalized. |
| [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html), sections 3.1, 3.2 and 5 | Extend stable machine-readable envelopes without changing existing meanings or exposing arbitrary inputs. This CLI is not an HTTP Problem Details implementation. |
| OWASP, [Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html), data exclusion, collection and verification | Bound collection, avoid secret-bearing fields, exercise logging failure and side effects. Existing raw diagnostics are not retroactively redacted. |

For the process/resource extension, the public TLPI Listing 3-3 (saved errno
versus explicit error number), Yuan sections 3.4 and 4, and close(2)'s error-return
discussion were rechecked on 2026-10-04. Relevant additional primary sources:

| Reference and inspected scope | Application |
| --- | --- |
| Linux man-pages, [posix_spawn(3)](https://man7.org/linux/man-pages/man3/posix_spawn.3.html), return value and errors; Open Group [posix_spawn](https://pubs.opengroup.org/onlinepubs/9799919799/functions/posix_spawn.html), indexed return-value text | Capture returned error numbers and distinguish parent launch failure from a child's eventual exit. The full Issue 8 page again returned 403; no claim of reading inaccessible text. |
| Linux kernel, [Control Group v2](https://docs.kernel.org/admin-guide/cgroup-v2.html), cgroup.events and cgroup.kill | Keep kill-request success distinct from an empty scope; preserve the existing populated-state check and delegation requirements. Portable I/O tests are not kernel enforcement tests. |

These are design inferences from scoped readings, not whole-book coverage,
published error-rate predictions for Golem, or proof of universal OS behavior.

The worker/traversal extension additionally checked the Linux man-pages
[pthread_create](https://man7.org/linux/man-pages/man3/pthread_create.3.html) and
[pthread_join](https://man7.org/linux/man-pages/man3/pthread_join.3.html) return/error
sections and [readdir](https://man7.org/linux/man-pages/man3/readdir.3.html)'s
EOF/error distinction. Tests deliberately make errno disagree with pthread's
return value. `worker_diagnostics_*` covers clock failure/invalid time, completed
cross-thread snapshots, queued cancellation and join failure; the existing
`worker_fault_thread` now verifies the saved create error. `traversal_diagnostics`
covers 21 inventory/workspace cases plus queue format lookup denial with no
format/job publication. Native recording tests assert collector observations
on failed record publication as well as independent operation/recording outcomes.
