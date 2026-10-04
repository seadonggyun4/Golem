# Native mechanical recording

The common recorder extends the Python execution boundary to direct native CLI
dispatch, reviewed public Work C APIs, and the single native supervisor. It is private, unsigned observation,
not a second execution receipt system, an authorization mechanism, or a replay
engine. Work journals, approvals, log-retention contracts and completion gates
remain authoritative and unchanged.

## Activation and ownership

Set `GOLEM_RECORD_ROOT` to an existing, absolute, user-owned 0700 directory with
no symlink path components. Once configured, every CLI dispatch and every native
supervisor launch boundary records automatically, including calls from C API users.
The 68 reviewed API boundaries below also record without a caller-written wrapper.
An absent/empty environment setting disables recording for compatibility and to
avoid silently retaining secrets. An invalid configured root blocks dispatch;
there is no fallback to unrecorded new execution. Required cancellation, lease
maintenance, release and recovery queries still run, with recording failure
reported separately as described below. The caller owns retention and disk
capacity. Do not point the root inside authoritative Work storage.

`execution_record.capture` now creates `native/` in its private observation
directory, configures the child root, and supplies its generated source-before
identity artifact through `GOLEM_RECORD_SOURCE_MANIFEST`. The Python manifest
binds every observed native artifact, including incomplete records. Legacy
records without a native inventory remain readable. An old/uninstrumented child
producing no native records is explicitly `NOT_OBSERVED`, never proof of complete
coverage. Existing Python stdout/stderr and command/source recording remain.

For an embedding host, `golem_record_call` wraps any synchronous C API operation
without duplicating receipt logic. Its versioned options select a root and an
operation name. The return value is recording status, while the output parameter
is the callback's operation status; a failed start never invokes the callback or
changes that output. A failed finish may follow successful effects. Never retry
merely because recording failed. Hosts may instead use begin/write/finish for
explicit byte observations. Scope handles belong to the creating thread and must
finish in LIFO order. Nested supervisor calls inherit that scope's root and source
artifact even with a fixed child environment. Independent threads do not share
scope state. Golem worker threads receive an owned immutable context snapshot,
not a pointer to their coordinator's active scope. Do not fork, longjmp, or mutate
environment/cwd across active calls.

## Observed scope

| Boundary | Automatically observed when enabled | Deliberate limit |
| --- | --- | --- |
| Direct CLI, including usage failures | argv, cwd, identity when available, intent, exit, duration | Does not intercept stdout/stderr descriptors; their framing, streaming and terminal behavior stay unchanged. Python capture retains these raw streams when used. |
| All supervisor variants, including C callers | executable before/after, argv, cwd, observed pipe bytes and SHA-256, spawn/reap, EOF, signal/exit/timeout, supervisor status | Only the directly supervised launch; inherited pipe data is not attributed to individual descendants |
| Reviewed Work C APIs | `c_api_auto` intent/result, exact API name, duration, independent operation/recording status, parent scope | No serialization of request bodies, signing keys, input/output objects, or host executable guessing |
| Supervisor adapter rejection | Named `c_api_auto` scope with invalid-argument status and no spawn/reap | Rejections before the common process boundary are not invented process executions |
| `golem_record_call` | Host-named operation and independent operation/recording outcomes, nested scope references | Arbitrary library functions are not globally interposed; the host supplies the wrapper boundary |
| Python capture | Existing source revision/worktree identity plus bound native artifact inventory | No record from an uninstrumented program means unknown coverage |
| Cgroup trampoline | Launcher outcome and fixed-label child stderr diagnostics | Not a parent TLS observation; existing resource evidence remains required |

The process-entry inventory still guards the sole native spawn boundary. An
external shell, compiler, CTest, or worker can launch uninstrumented descendants.
Their separate argv/exec/exit events are **not** reconstructed from parent logs.
The separate opt-in [syscall diagnostic runner](syscall-recording.md) follows
Linux descendants with strace. Native recording alone does not enable it.
No injected library, global Python monkeypatch or hidden privilege escalation is
installed. Neither mode claims complete auditing of arbitrary external services.
Invalid arguments rejected by a supervisor adapter before reaching the common
launch boundary create a named API rejection scope, not a process scope.
Cross-process parentage is not inferred from PID reuse; parent IDs describe
nested scopes or explicit Golem worker handoff. Native records under one Python bundle are related
by that bundle's inventory, not claimed as a complete causal tree.

## Automatic C API contract

The selected boundaries are explicit, rather than a blanket interposer:

| Module | Automatically recorded symbols |
| --- | --- |
| Document | `golem_document_store_create`, `golem_document_store_open`, `golem_document_store_close`, `golem_document_submit` |
| Runtime lifecycle | create, recover, step, drive, cancel, report_get, lease_bind, checkpoint, heartbeat, free |
| Journal lifecycle | open, append, checkpoint_get, recover, close |
| Agent/session | `golem_agent_session_call`, `golem_session_binding_call` |
| Approval/execution | `golem_approval_call`, `golem_execution_call_receipted`, `golem_execution_call`, `golem_execution_call_authorized` |
| Work operations | `golem_role_call`, `golem_research_call`, `golem_completion_call`, `golem_reentry_call`, `golem_workspace_call`, `golem_candidate_call` |
| Runtime profile | `golem_runtime_profile_register`, `golem_runtime_link_run` |
| Publication | `golem_context_publish`, `golem_proof_publish`, `golem_admission_publish_work` |
| Admission | open, diagnostic open, identity, enqueue, lookup, grant, resize, begin, dispatch, cancel, settle, release, close |
| Worker | open, submit, start, events, inspect, cancel, heartbeat, acknowledge, close |
| Daemon | init, inspect, submit, open, tick, recover, close |
| Other execution boundaries | `golem_resource_run`, `golem_inventory_capture`, `golem_harness_probe` |

`GOLEM_RECORDED_API` declares the existing typed public signature and a private
body. All ordinary body returns flow through the same begin/finish implementation;
there is no per-return logging, GNU cleanup attribute, or generated build input.
Nested public calls deliberately have distinct IDs: an API invocation is not a
process invocation. Their parent links avoid copying observations between layers.
Disabled recording retains operation behavior and performs no recorder file I/O.
Wrappers preserve incoming errno across recorder setup and the body's errno
across finalization. API return statuses, not errno, remain the public contract.

`GOLEM_RECORDED_REQUIRED_API` is the explicit required-operation policy for 21 safety
and observation controls: admission close/cancel/settle/release/identity/lookup;
worker cancel/heartbeat/acknowledge/close/events/inspect; daemon close;
runtime cancel/report_get/checkpoint/heartbeat; journal append/checkpoint_get/close;
document store close. `GOLEM_RECORDED_RELEASE_API` additionally records the void
runtime destructor without suppressing release or changing its ABI.
Recorder start failure does not suppress these bodies. Their operation result
and ownership rules remain authoritative; the outcome accessor reports the
recording failure and `dispatched=true`. This is a failure state, not a successful
audit record. An active enclosing record is marked failed. New execution and
mutation boundaries retain fail-closed recorder setup, except journal append:
this is the mandatory domain durability sink, including cancellation after an
effect, and must not be suppressed by a second, observational storage failure.
Journal bytes, sequence allocation, poison semantics and replay remain unchanged.
This is failure isolation, not a wait-free or bounded-latency promise: configured
recording still performs synchronous filesystem I/O before/after the operation.

An intent failure returns a recording error before dispatch, leaving outputs
untouched, with diagnostic `record.begin_dispatch_not_started` where supported.
Once dispatched, **the original operation return and output ownership are
preserved**, including when final recording fails. This avoids leaking an output
handle by presenting a successful operation as an ordinary operation failure.
Enabled C callers must immediately inspect `golem_record_last_api_outcome` and
match its operation name. It copies thread-local `dispatched`, `operation_status`,
and `recording_status` without file I/O, even if the result file could not be
written. Initialize the output's `struct_size` and `version=1`; unsupported layout
or version returns false without touching output. Before the first automatic
boundary it returns false; unrelated APIs do not reset it. A nested call's outcome
is replaced by the enclosing API on return.
The operation status is undefined as an observation when `dispatched` is false.

Finish failure emits `record.finish_effects_uncertain` when the operation succeeded
and a diagnostic output exists, retains an existing operation failure, and marks
the enclosing recorder failed. CLI/explicit host record finalization therefore
also reports recording failure. Use the normal API contract to release successful
outputs. Neither a diagnostic nor an incomplete record authorizes replay or
rollback. A standalone caller that ignores the outcome accessor cannot claim
recording success from `GOLEM_OK` alone.

Low-level CAS/digest/recorder primitives remain outside this boundary to prevent
self-instrumentation. Destructors and resource release remain unconditional.
Pure inventory validation/comparison and the worker diagnostic/recording-status
accessors deliberately perform no recording. The runtime loop, journal file and
document-store create/open/close lifecycle boundaries are now connected.
Other public model, prepared/profile-cache lifecycle and document read/projection
helpers are **not all automatically wrapped**; use an explicit host scope for
their logical operation. These unreviewed operational helpers remain work, not
retroactively classified as pure primitives.
The reviewed inventory is not a claim that every exported C symbol or arbitrary
descendant execution is traced.

### Worker handoff

Before admission publication, worker start copies the selected record root,
optional source manifest path and parent ID. Copy failure prevents dispatch;
publication/thread-creation failure disposes the copy. The worker attaches it to
its own thread, records `golem.worker.execute` including pre-spawn cancellation
or expiry, then detaches and frees it before publishing completion. The parent
record may already have finished: no cross-thread scope pointers or JSON objects
are shared. Arbitrary host-created threads and subprocesses do not inherit this
private mechanism automatically.

`golem_worker_recording_status` exposes the completed worker's recording result
separately from its operation snapshot. Disabled recording and no worker attempt
return OK; inspect the job snapshot as well. An asynchronous failure cannot rewrite
an already-finished parent. Nested process-record finalization failure marks its
still-active worker record failed. `golem_worker_diagnostics` copies the completed
worker's bounded system-error observations, including thread creation failures.
Both getters reject unfinished jobs without modifying output and perform no I/O.

## Persistence and failure semantics

Each invocation gets a random 128-bit directory identity, not a timestamp/PID
filename. Intent is published before dispatch. New files use exclusive creation,
0600 permissions, held directory descriptors, and no-replace link publication.
Files and directories are fsynced. Existing observations are never overwritten.
`result.json` is followed by a SHA-256 inventory `manifest.json`; only a verified
manifest supports an integrity claim. `.pending`, an absent result, or an absent
manifest requires inspection, not execution replay. SIGKILL can leave only intent.
The operation and filesystem publication are not one atomic transaction.

Captured streams are limited to 64 MiB each, independently of existing supervisor
protocol and bulk limits (which are unchanged). A record-write failure aborts
supervision through the existing reap path; partial evidence remains. Hashes
cover retained bytes, not unseen output. Slow filesystem I/O can delay heartbeats;
this synchronous recorder is not a real-time or disk-quota facility. Evidence
hashing and fsync add work and are not represented as a performance improvement.

Executable/source artifact hash failures have explicit status codes rather than
invented hashes. A supplied source artifact is hashed before/after, not asserted
to describe the live source tree. Without the Python collector or a host source
manifest there is no native Git revision claim. Hashing does not bind exec to an
immutable file descriptor, eliminate TOCTOU, or capture runtime dependencies.

Environment values and stdin are not copied. argv and observed logs can contain
secrets. Restrict access, set a reviewed retention policy, and never publish raw
bundles automatically. A same-user writer can rewrite both records and hashes;
these files provide neither authentication nor an independent audit authority.

Read-only verification:

```sh
python3 tools/native_record.py /absolute/private-root/RECORD_ID
python3 tools/execution_record.py /absolute/python-observation
```

`integrity: PASS` can accompany a failed operation or `RECORDING_FAILED`; inspect
those fields separately. Missing/truncated/extra artifacts and digest changes fail
verification. No verification command executes the recorded argv.

## Research trace

Reviewed on 2026-10-02 and extended on 2026-10-03. Selected sections below informed design; no whole-book
review, standards conformance, measured savings or formal proof is claimed.

| Primary reference / reading scope | Design application |
| --- | --- |
| Chirigati, Shasha, Freire, [ReproZip, TaPP 2013](https://www.usenix.org/system/files/conference/tapp13/tapp13-final16.pdf), introduction and section 3 | Automatic capture is distinct from a full reproducible environment. Explicitly separate instrumented launches from syscall-level dependency/process tracing. |
| Sigelman et al., [Dapper, 2010 technical report abstract](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/) | Instrument the common library boundary instead of duplicating logging in every caller. This recorder does not adopt Dapper sampling or claim its distributed coverage. |
| W3C [PROV-DM](https://www.w3.org/TR/prov-dm/), 2.1, 5.1.2, 5.1.6-5.1.7 and 5.4 | Keep invocation activities, their starts/ends, byte identities, and observation bundles distinct; a shared digest is not authorization or proof of causality. |
| Ross Anderson, *Security Engineering*, third edition (2020), [chapter 6, access-control matrix and Unix access-control discussion](https://www.cl.cam.ac.uk/archive/rja14/Papers/SEv3-ch06.pdf) | Use private storage and distinguish integrity checks from independent audit trust; same-user control remains a limitation. |
| Linux man-pages, [posix_spawn](https://man7.org/linux/man-pages/man3/posix_spawn.3.html), pre-exec file actions and return/error semantics | Preserve argv/environment contracts, CLOEXEC descriptors and supervisor outcome observations; do not infer descendant completion from a successful spawn. |

## Regression and extension

The 2026-10-04 extension rechecked the Dapper publisher abstract (common-library
instrumentation; its linked PDF was inaccessible), ReproZip sections 1 and 3
(syscall provenance differs from owned API scopes), and the
[W3C Trace Context processing model](https://www.w3.org/TR/trace-context-1/#processing-model).
The design inference is to propagate an explicit owned correlation context, not
infer causality from PID/timestamps or share mutable thread-local scope storage.
This is not an implementation of the HTTP traceparent protocol or a claim of W3C
conformance. No remote header, child environment, or secret-bearing argument is
injected for propagation. The existing private storage/unsigned-evidence boundary
from the Security Engineering reading above is unchanged.

Michael Kerrisk's *The Linux Programming Interface*,
[Listing 3-3](https://man7.org/tlpi/code/online/dist/lib/error_functions.c.html),
informed errno preservation versus explicit returned error numbers. Yuan et al.,
[OSDI 2014](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf),
sections 3.4-3.5 and 4, motivated tests of failure handling and state preservation,
not just the presence of log messages. These are scoped readings and engineering
inferences, not a whole-book review, formal completeness proof, or predicted
failure/token reduction for Golem. No reference implementation was copied.

`native_recording` checks CLI protocol equivalence, C API wrapper nesting, raw
streams, normal/nonzero/signal/timeout/cancellation/overflow paths, invalid and
symlink roots, crash-incomplete records, independent threads/processes, incorrect
scope order, recorder failure distinct from operation failure, tamper detection,
and the Python source-identity bridge. Existing supervisor, execution and resource
tests remain necessary. New launch sites must enter the supervisor inventory;
new record fields need a schema/version and explicit unavailable semantics.

`native_api_recording` directly invokes all 68 APIs on rejected-input/null-close paths,
checks real document creation and blocked dispatch, secret-input omission,
explicit-root inheritance, thread-local isolation, and injected finalization
failure (including nested failure and preserved operation status), required
cancel/inspect/acknowledge/close with unavailable recording storage, and owned
cross-thread context surviving destruction of its parent scope.
`native_api_scenarios` runs completion/binding/approval, worker and daemon workflows with recording enabled
and verifies successful observations, every generated manifest, and parent links.
`native_api_inventory` checks the reviewed source wrappers exactly once and
flags new public `golem_status ..._call` command APIs for review. It also requires
an explicit recording policy for every status-returning export in admission,
daemon, worker, resource and inventory headers, with exact required-control and
intentional-exclusion lists. This is a source
tripwire, not a C parser or proof of coverage of arbitrary new naming patterns.
To extend coverage, review the ownership/dispatch contract, add the wrapper and
inventory entry together, and add a direct enabled-recording regression. Do not
gate cleanup or instrument recorder dependencies merely to increase a symbol count.
