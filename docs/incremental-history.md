# Incremental live Work history

`golem work history WORK REQUEST.json` now accepts **schema 2** for append-tolerant
polling of both existing document and agent event streams. Schema 1's pinned,
combined-offset snapshot pagination is unchanged. No background watcher, network
subscription, new database, provider call, or Work mutation is introduced.

## Protocol

Start a complete read with an explicit null cursor:

```json
{"schema_version":2,"work_id":"example-work","limit":64,"cursor":null}
```

Use `golem --output-mode full work history WORK REQUEST.json` for a machine
consumer. The reply includes events, mode, fallback reason, current stream heads
and totals, `has_more`, and a versioned `cursor`. Supply that exact cursor in the
next request. No manual arithmetic or interpretation of an opaque offset is needed.

The cursor binds Work ID, the first document-frame hash (content-lineage anchor),
and independently the last consumed sequence/frame hash in each stream. Zero
positions have zero hashes. Only verified prefixes may advance. Separate positions
avoid losing agent events when new document events move the boundary of the old
combined stream. The anchor is not a secret or physical-store UUID: byte-identical
clones share lineage. The observation wrapper additionally binds the Work path.

`limit` is **per stream**, in 1..256; a page has at most twice that many events.
Each stream gets a quota, so a growing document stream cannot starve agent history.
Ordering is per-stream sequence, not global chronological or causal order. Each
page uses the existing shared Work lock, and may observe appends since the prior
page. It is not a frozen multi-page snapshot; use schema 1 when that is required.

| Result | Consumer action |
| --- | --- |
| FULL / BASELINE_REQUIRED | Begin a new full traversal from zero |
| FULL / CURSOR_INVALID | Invalid/unknown cursor contract; discard the old derived baseline and begin a full traversal |
| FULL / PREFIX_MISMATCH | Cursor is ahead, from another lineage/Work, or has a different prefix; reset the derived baseline |
| DELTA with events | Consume new events, then persist the returned cursor |
| DELTA with no events | No new events at the observed heads; this is not a current lease, QA or health assertion |
| Error/nonzero exit | Preserve the old cursor and evidence; inspect the error, never treat it as an empty delta |

FULL describes a **reset page**, not necessarily all history in one response.
Continue while `has_more` is true. The next page may say DELTA because its cursor
is now valid. A false `has_more` means caught up to that page's observed heads,
not that future events cannot arrive. Reusing an old valid cursor deliberately
replays the same prefix of changes; consumers must be idempotent using stream,
sequence and event digest. Persist cursor and consumed state together, only after
successful processing. There is no exactly-once delivery or server-side consumer
acknowledgement claim, and no automatic execution of event contents.

Malformed outer requests, unknown request versions and wrong requested Work IDs
remain errors. An untrusted cursor is only a reading hint: it grants no permission.
Missing/corrupt CURRENT frames or CAS are errors even with a bad cursor. Full
fallback never skips or repairs corruption. Historical event details remain
available through their payload/frame digests and original CAS.

## Recorded polling

The existing observation runner supports a one-shot polling command:

```sh
python3 tools/agent_io.py observe-history --cwd /path/to/repository \
  --cli /path/to/golem --work /private/path/work --work-id example-work \
  --limit 64 --output /private/path/page-001
python3 tools/agent_io.py observe-history --cwd /path/to/repository \
  --cli /path/to/golem --work /private/path/work --work-id example-work \
  --since /private/path/page-001 --revision PREVIOUS_OBSERVATION_REVISION \
  --limit 64 --output /private/path/page-002
```

Use the previous view's `revision`, not its raw stdout hash. The wrapper verifies
the previous manifest, record hash, compatible query/CLI/Work scope and successful
capture before extracting the native cursor. Missing pins, corruption, failed
captures or unknown page schemas cause an explicitly recorded full reset request.
The engine independently validates its cursor against live prefixes. No caller
baseline file is overwritten and no effects are retried. `baseline.json` records
the fallback decision; original streams, process result and source/binary identity
remain in the normal execution evidence bundle. Raw pages can be inspected with
the existing `raw --step history` command. Cursor advancement remains caller-owned.
The observation view's outer `mode` describes that view; the native page's
FULL/DELTA and `has_more` are in the history step's observed fields. Do not use the
outer view mode to decide whether to reset a live-history consumer.

This differs from the existing offline `view --since --revision`: that command
compares completed command observations. It does not query a live Work. Live
history does not require an unchanged source checkout: its scope is the Work log,
not code freshness or execution readiness. Source identity is still recorded.

## Limits and extension boundary

The **output** is incremental, but source open/replay and integrity verification
remain O(total history), with additional projection passes. There is no claim of
O(delta) disk access, lower latency or token savings. Reusing the existing verified
projector preserves all existing event kinds and attribution rather than building
a second reducer. Trusted indexed checkpoints would need their own crash, rollback
and invalidation proof before enabling prefix-skipping optimizations.

The streams cover the existing Work document and agent journals, including linked
event references. They do not inline every separate runtime log, nor project live
lease expiry without events. Request current status/next before effects. Arbitrary
filesystem writers are outside the cooperating-store lock contract. Byte budgets
and native history bounds remain; a failed page never publishes a new cursor.

## Research rationale

Inspected on 2026-10-02. These are scoped design inferences, not performance results
or a claim that Golem implements a distributed stream-processing framework.

| Primary reference and read scope | Application and limits |
| --- | --- |
| McSherry, Murray, Isaacs, Isard, [Differential Dataflow, CIDR 2013](https://www.microsoft.com/en-us/research/wp-content/uploads/2013/01/differentialdataflow.pdf), abstract, introduction, motivation and section 3/3.1 | Separate versions and changes; distinguish incremental output from incremental computation. Independent stream positions are not a Naiad timestamp lattice implementation; no reported speedup is transferred. |
| PostgreSQL 18, [Logical Decoding Concepts](https://www.postgresql.org/docs/18/logicaldecoding-explanation.html), sections 47.2.1-2 and 47.2.5 | Replay can redeliver; consumers must persist progress safely. A consistent snapshot/change boundary must be explicit. Golem uses verified local prefixes, not PostgreSQL slots, WAL retention or distributed replication guarantees. |
| Abiteboul, Hull, Vianu, *Foundations of Databases* (1995), [chapter 11 introduction and decomposition/lossless-join discussion](https://webdam.di.ens.fr/Alice/pdfs/Chapter-11.pdf) | Preserve data and dependencies when changing representation. Tests compare paged events with full history and retain original event identities. Only the relevant portions were inspected; chapter 22 retrieval failed and is not cited as read. |
| W3C, [PROV-DM](https://www.w3.org/TR/prov-dm/), entity/derivation and bundle concepts | Distinguish raw journal identity, observation-bundle identity and derived views. Hashes do not authenticate authors or establish execution authority. |

Regressions cover empty polls, simultaneous stream growth, append during paging,
per-stream quotas, duplicate-free reconstruction, explicit baseline reset, current
corruption rejection, schema-1 compatibility and recorded hash-pinned polling.
No semantic agent-performance evaluation or Linux revalidation is implied.
