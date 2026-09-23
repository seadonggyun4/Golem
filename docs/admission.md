# Session / Global Admission

`golem/admission.h` provides an opt-in, durable local admission coordinator. It
does not launch another agent, grant shell permissions, or replace the adapter,
autonomy, capability, budget, lease, or acceptance gates. It is not a worker pool.
The existing daemon CLI and synchronous tick retain their existing contracts;
using them alone does not enroll them in this API.

## Authority And Ownership

Use one dedicated, private, existing directory as the repository's admission
authority, shared by all participating callers. Its immutable INIT record contains
a random 256-bit namespace ID. Work and session IDs, not workspace paths, identify
lanes inside that namespace. Directory renames preserve identity; symlink path
components are rejected. Copying/deleting a ledger to create another authority
is unsupported. Limits are global **within this coordinator**, not across hosts or
independently initialized directories. No distributed consensus is provided.

Open takes a lifetime exclusive owner flock and commits a new fencing epoch and
random instance nonce together with the OS boot-identity digest. Every ticket
mutation checks all three, not just a PID. A handle inherited by `fork` cannot
mutate the coordinator. The host must serialize calls; this is not a thread-safe
shared handle. No mutation mutex spans host callbacks. The leadership flock
remains held to prevent a second coordinator while work is executing.

Options/requests are borrowed during calls. The allocator descriptor is copied;
its context outlives close. Results and tokens are caller-owned values. Error
returns leave outputs untouched. Close consumes a handle, including on close I/O
failure, except when callback reentry is rejected. NULL close is a no-op.

## Admission Rules

- A root grant atomically checks one Work writer, one session lane, slot count,
  CPU milliunits and memory bytes. No partial reservation is exposed.
- Limits use checked unsigned arithmetic, positive CPU/memory and 1-32 slots.
  Resource quantities are reservations, not OS-enforced CPU/memory isolation.
- Requests over the current total budget are rejected immediately. Durable resize
  may shrink below active usage; no new root grant is possible until it drains.
  A queued request larger than a reduced limit needs explicit cancel or resize.
- Operation keys are immutable and idempotent. Same key/different request fails.
  ASCII letters, digits, hyphen and underscore only; operation length <64,
  Work/session length <96. IDs are case-sensitive and must not contain secrets.
- Maximum 256 **retained tickets**, including terminal ones. Thus waiting requests
  are also bounded by 256. Full returns `GOLEM_ERR_QUEUE_FULL`; no hidden eviction.
- FIFO can allow up to `foreground_burst` newer foreground grants (0-32) before
  the oldest queued root becomes a barrier. Later roots then cannot pass even if
  it is blocked. This deliberately trades utilization for eventual service.
- Liveness requires eventual completion/reconciliation of active reservations,
  repeated scheduling, and a budget large enough for the request. A permanently
  uncertain execution or explicit capacity shrink can block progress; timeout
  does not silently override safety. Aging counts grants, not wall-clock time.

## Nested Reservations

A child is declared before the root starts, uses the same Work/session, and draws
only from that root's reserved CPU/memory. Its demand cannot exceed the parent's.
Depth is one; one child executes at a time. The parent cannot start, settle, cancel,
or release while any child is queued or active. Nested grants do not request a new
global slot and are drained before root grants. A child cannot parent another child.

This is a pre-dispatch handoff, not dynamic recursive spawning from a running
callback. The synchronous callback cannot reenter the coordinator. Repeated
release does not return another unit; usage is derived from live root tickets.

## Work And Dispatch

Host call sequence:

```text
open -> enqueue(operation key, Work, session, runtime_binding, resources)
     -> grant -> dispatch(publish, execute) -> close
```

`dispatch` performs these durable boundaries:

```text
GRANTED
  -> host publishes Work binding receipt
  -> BIND event records that receipt
  -> STARTING event
  -> RUNNING event
  -> host execute callback, once
  -> SETTLING with observed termination receipt
  -> RELEASED
```

Inside `publish`, use `golem_admission_publish_work` with a writable Work store.
It requires a matching live RUNNING agent claim, fresh manifest, correct
Work/session, matching OS boot, and validated 30A runtime binding. It writes an
immutable CAS-backed `admission-link` event in the existing Work ledger. Repeating
the same link is idempotent; conflicting ticket identity fails. Replay validates
the retained binding and CAS dependencies without requiring a past lease to be
live today. This is a link receipt, not permission to bypass execution policy.
One Work retains at most 256 admission links. If publication fails, execution
does not start; the host may explicitly cancel the unstarted reservation or retry
the idempotent publisher after resolving the failure.

Close the Work writer before a long execution callback if the host's ownership
design permits. This API does not change the existing `execution run` writer-lock
contract. `execute` still applies the ordinary policy/lease gates and, when
enrolled, 30B checked dispatch. Recheck those gates at actual launch: publication
and fsync can take time. A nonzero digest alone is not authenticated proof.

`publish` must be idempotent and must never execute work. `execute` returns OK
only after observed termination and durable evidence; nonzero command exit can
still be an observed termination with a failed QA outcome. Transport uncertainty
returns an error and retains the reservation. Admission does not decide QA PASS.

## Recovery

| Durable state at interruption | Reopen result |
| --- | --- |
| Queued root | Still queued, new fence |
| Granted, with or without Work link | Cancelled: this dispatch protocol has no execution intent |
| Starting / running / cancel requested | Reconcile required; retain resources |
| Unstarted root with uncertain child | Reconcile required; retain parent reservation |
| Settling, termination already recorded | Still settling; explicit idempotent release |
| Released / cancelled | Terminal; no redispatch |

Queued/unstarted children cancel on restart. Unknown children remain reserved.
Only the trusted host can settle an uncertain ticket after establishing termination
or non-execution for the exact identity. Reconcile children before their parent.
The caller obtains the fresh token by operation-key lookup; old tokens cannot
settle/release anything. Cancellation of running work is a request, not observed
termination. There is no lease-expiry-based automatic release.

This is at-most-once dispatch per retained ticket, not exactly-once external
effects. A crash just before invoking the callback still requires reconciliation.
Creating a new operation key is not evidence that an older uncertain attempt is
safe to rerun. Conflicting lanes remain occupied until explicitly resolved.

## Storage And Bounds

The separate `GADM0001` ledger has canonical 512-byte little-endian frames,
contiguous sequence, previous SHA-256 digest, and a SHA-256 frame digest.
HWJR v1 opcodes and existing journals are unchanged. Each record is published
without replacement using temporary file, file fsync, link publication and directory
fsync. A partial temporary file is not a committed record. Unknown schemas,
reserved/ignored fields, malformed IDs, invalid transitions and missing records fail
closed. New files are private; existing root permissions are the host's responsibility.

Canonical frame layout (offsets are bytes; integers are unsigned little-endian):

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 8 | ASCII `GADM0001` domain/version |
| 8 | 8 | Sequence, starting at 1 |
| 16 | 32 | Previous frame digest; zero for the first frame |
| 48 | 8 | Opcode: INIT=1, BOOT=2, ENQUEUE=3, GRANT=4, BIND=5, START=6, RUN=7, CANCEL=8, SETTLE=9, RELEASE=10, RESIZE=11 |
| 56 | 8 | Ticket ID; INIT/RESIZE use this field for slot limit; BOOT uses zero |
| 64, 72 | 8 each | Requested CPU/memory; INIT/RESIZE use total limits |
| 80, 88 | 8 each | Foreground boolean (0/1), parent ticket |
| 96, 160, 256 | 64, 96, 96 | Operation key, Work, session; NUL plus zero-filled suffix |
| 352 | 32 | Runtime binding; INIT uses namespace identity |
| 384 | 32 | Receipt digest for BIND/SETTLE |
| 416 | 16 | Owner instance nonce |
| 432 | 8 | Epoch; INIT/RESIZE use foreground bypass limit; ENQUEUE uses zero |
| 440 | 32 | OS boot digest for BOOT and ticket transitions |
| 472 | 8 | Reserved, zero |
| 480 | 32 | SHA-256 of bytes 0 through 479 |

Fields unused by an opcode must be zero. BOOT/transition records do not repeat
request strings/resources. Replay always applies the version-1 transition rules;
a future policy/format change needs an explicit new version, not reinterpretation.

The optional independently retained checkpoint validates an expected prefix
by comparison (it is not a signature). Without an external anchor, whole-tail
deletion or replacement of the entire ledger cannot be detected. Hash chains do
not authenticate a same-user writer. Trusted local filesystem/parent ownership
is required; network filesystem semantics and physical power-loss are not certified.

Any commit I/O failure poisons the current handle. Do not retry blindly: close,
reopen, replay, and lookup the operation key. The event may already exist. Read-only
queries on the poisoned handle are rejected to avoid presenting stale state.

The event cap is 65,536 (32 MiB of frame payload, plus filesystem overhead).
No automatic truncation, compaction, GC or capacity-reset operation is provided.
The host must budget event use and stop intake well before the limit; hitting it
is fail-closed, including recovery/settlement writes. Terminal retention/rollover
requires a future explicit protocol, not deletion of active evidence.

## Research Basis

These are design inputs, not copied implementations or performance guarantees.

| Source and inspected scope | Applied decision / limitation |
| --- | --- |
| [OpenClaw capacity groups, fixed commit](https://github.com/openclaw/openclaw/blob/01457af6876f1c4be61f492d86b0ac7fc596853e/src/process/command-queue.capacity-groups.ts), full module | Shared budget, synchronous arbitration and dependency-cycle hazards; independent C state machine, not the TypeScript queue |
| [Welsh, Culler, Brewer: SEDA, SOSP 2001](https://www.cs.princeton.edu/courses/archive/fall04/cos518/papers/seda.pdf), sections 1-2.2 | Explicit queues and bounded resources; no latency/throughput claim without measurement |
| [Burrows: Chubby, OSDI 2006](https://www.usenix.org/legacy/event/osdi06/tech/full_papers/burrows/burrows_html/), section 2.4 | Fencing generation at protected operations; timeout alone is insufficient |
| [Lamport: Specifying Systems](https://lamport.azurewebsites.net/tla/book-21-07-04.pdf), chapter 8, especially 8.6-8.7 | Separate safety from fairness assumptions; bounded C exploration is not a TLA+ or unbounded liveness proof |
| [Arpaci-Dusseau: OSTEP, Crash Consistency](https://pages.cs.wisc.edu/~remzi/OSTEP/file-journaling.pdf), transaction commit/recovery sections | Distinguish publication, durability uncertainty and replay; SIGKILL/fsync tests do not prove power-loss safety |

## Verification

`ctest --preset release -R 'admission_|mutation_admission' --output-on-failure`
exercises lane limits, FIFO preference, nested handoff, overflow/capacity, allocator
ownership, callback reentry, stale fences, identity rename, retained checkpoints,
wire golden/mutations, dispatch-state crash boundaries, and injected file/directory
fsync, partial-write and EINTR failures. The Work integration suite uses real
document/CAS/agent-session APIs with a synthetic execution callback. It does not
claim a new live Codex/Claude run. The parser also has a libFuzzer target.

## Bounded Execution Companion

The opt-in [worker executor](worker-executor.md) provides the 30D process backend.
Its split-phase launch commits admission intents before spawning; local capacity
is returned only after observed completion and matching durable admission release.
