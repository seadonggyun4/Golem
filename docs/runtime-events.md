# Runtime diagnostics

`golem/runtime_event.h` provides copied, read-only diagnostic pages. It does not
grant execution permission, release a lease, complete a Work, or replace evidence.
It observes the opt-in admission/worker APIs, not every legacy daemon path or
external agent process.

An optional [read-only SSE bridge](event-stream.md) and shared
`golem/event_reader.h` view build on these APIs. Subscription state and HTTP
dependencies stay outside the runtime writer.

## Two sources

| Source | Producer | Identity/lifetime | Time |
| --- | --- | --- | --- |
| Admission journal | After successful durable commit, or verified replay | First record digest + sequence + record digest; survives restart | Unavailable in the original journal |
| Worker observation | Coordinator control calls and terminal collection | Random pool identity + local sequence; ends with pool | Optional monotonic nanoseconds since pool creation |

`running_committed` records dispatch intent, not actual child execution.
`dispatched` means a supervisor thread was created, not executable success.
`finished` may include failure or proven non-execution. `reconcile` means child
termination could not be confirmed. `recovery` records a new admission epoch,
not recovery success for every job. `settlement_recorded` records a host receipt,
not independent verification of it. Cancellation is a request, not termination.

Worker terminal observations are harvested on inspect, events, start, cancel and
acknowledge calls. Time is coordinator observation time, not exact child exit time.
Compare elapsed values only within one pool. Unknown time/status remains explicitly
unknown; no Unix timestamps, fake zero durations or distributed trace IDs are inferred.

## Bounded readers

- `golem_worker_events`: worker memory ring.
- `golem_admission_events`: current admission handle's derived ring.
- `golem_runtime_events_snapshot`: read-only verification/replay of an existing
  absolute private admission directory. No lock creation, boot event or mutation.
- `golem_runtime_events_export`: JSONL, OTLP Logs JSON or PROV-JSON through the
  research/observability layer; no network, evidence or filesystem writes.

Rings retain 256 records; pages hold at most 64. Each reader owns its cursor.
There is no subscription registry, callback or per-event allocation. Writers
never wait for readers. Calls must obey the owner's serialization rules: this is
not an MPMC queue or a real-time guarantee. Synchronous export/file I/O performed
by the host can still delay its own coordinator; keep that work out of execution.

Cursor text: `1:<stream-sha256>:<sequence>:<record-anchor-sha256>`. Worker anchors
are zero because they are not journal records. Future, cross-stream, malformed
and mismatched retained anchors fail. Overwritten anchors return `STALE_RESULT`
with bounds and `missed`, without records. Explicitly resume with a null cursor
only after acknowledging the gap. An evicted anchor can require resynchronization
even when no successor was missed. `dropped` counts retention eviction, not
deletion from the source journal. Diagnostics never release reservations.

Random-identity failure disables worker diagnostics, not execution. Missing clock
data remains unavailable. Sequence exhaustion freezes the ring instead of reusing IDs.

## CLI

Use an absolute admission directory, not a document Work store:

```sh
golem events /absolute/private/admission --jsonl
golem events /absolute/private/admission --jsonl --after 'CURSOR_FROM_NEXT'
golem events /absolute/private/admission --otlp
golem events /absolute/private/admission --prov
```

JSONL starts with page metadata (`oldest`, `newest`, `dropped`, `missed`, `count`,
`next`), followed by at most 64 records. Resume with `next`; an empty page has
`count: 0`. Stale cursors exit nonzero with a gap report on stderr, not silent
skipping. Corrupt journals fail before stdout. Output errors cannot mutate state.

This is a snapshot command, not SSE, a network service or `--follow`. Disk snapshots
replay the complete journal: O(journal length), bounded retained output. Use the
live C API for frequent polling. Concurrent appends belong to a later snapshot;
retry scans invalidated by concurrent filesystem changes. After failed fsync,
readable bytes alone do not prove durability; existing reconciliation still applies.

## Disclosure and derived exports

Only fixed enums, numeric subject/epoch, cursor hashes, known status and optional
local elapsed time are exported. No argv, cwd, environment, prompt, raw stdout or
stderr, arbitrary messages or Work/session names. IDs/hashes/timing remain private
linkable metadata; review before sharing. Serialization does not authenticate
caller-constructed records.

OTLP exports log bodies without invented Unix timestamps or spans. PROV describes
derivation from journal record digests. Transient observations do not pretend to
have a CAS/journal source. Projection identifiers use the SHA-256 digest of the
exact versioned diagnostic JSON bytes; journal source identifiers use the record
digest. Overlapping pages share identical entities, while different diagnostic
content receives different identifiers. This is byte identity, not semantic JSON
canonicalization or proof of authenticity. All formats mark `DERIVED_ONLY`. This extends the Phase 29F
observability layer but is not a Phase 29E case-study bundle and does not enroll
diagnostics as QA evidence. Existing case-bundle redaction policies remain intact.

## References and limits

- [SEDA, Welsh et al., SOSP 2001](https://www.cs.princeton.edu/courses/archive/fall04/cos518/papers/seda.pdf): finite queues and isolation inform bounded diagnostic retention.
- [The Site Reliability Workbook, Monitoring](https://sre.google/workbook/monitoring/): distinguish useful observations, retrieval cost and monitoring complexity.
- [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/): unknown time and observation/occurrence distinction.
- [W3C PROV-DM, derivation](https://www.w3.org/TR/prov-dm/#component2): derived diagnostics are not their original evidence or authentication.

Tests cover retention gaps, independent cursors, unavailable clocks, failed commits,
restart identity, worker termination failures, privacy allowlists, no-write CLI
snapshots and cursor mutation. They do not establish production latency, distributed
tracing fidelity or a performance improvement.
