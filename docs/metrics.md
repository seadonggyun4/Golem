# Research Metrics (29C)

Cohort records (29D) are excluded from this measurement population; they still
advance the global replay boundary. Use [cohort comparison](cohort.md) for those records.

**English** | [한국어](metrics.ko.md)

Read-only, versioned projections of a fully replayed Work journal. Golem counts
records and derives measures from validated 29A/29B contracts, not from arbitrary
numbers supplied in an agent's observations. Metrics never grant completion.

## Use

```sh
golem research metrics "$WORK"
golem research metrics "$WORK" --case parser-case
golem research metrics "$WORK" --case parser-case --format markdown
```

JSON is the default. Markdown goes to stdout without writing a report, CAS object
or journal event. Use private storage for saved projections. No redaction or
publication permission is implied, even though authored narratives are omitted.
An unknown case is an error, not an empty successful sample. Duplicate/unknown
flags, empty IDs and unsupported formats are rejected.

C callers use `golem_research_metrics` or `golem_research_metrics_report` from
[research.h](../include/golem/research.h). `case_id=NULL` selects all cases.
The store and filter are borrowed; serialize calls on the handle. A read-only
handle is sufficient. Successful replies own malloc storage, released with
`golem_execution_reply_free`; output is unchanged on failure. The handle denotes
its replayed prefix, not later files or live source state.

## Populations and Rules

The rule is `golem.research-metrics.v1`. Changing metric meaning requires a new
rule version. A Work is not a ResearchCase: one Work can contain many cases.

| Group | Definition |
| --- | --- |
| `counts` | Selected unique committed research records, cases, plans, decisions and adjudication revisions |
| `linked_plan_attempt_count` | Decisions referencing their validated prior plan |
| `retrospective_attempt_count` | Decisions without a linked prior plan |
| `unobserved_plan_count` | Recorded plans without a matching decision; not automatically failures |
| `declared_*_counts` | Classification, actor and next-action labels on AttemptDecision records; not independently proven facts |
| `latest_*_case_count` | Only the latest adjudication per selected case; revisions are not extra successful cases |
| `ineligible_adjudication_revision_count` | Recorded adjudication revisions with computed eligibility false |
| `pass_but_ineligible_revision_count` | Normalized PASS but computed eligibility false; not a count of attempted completion refusals |
| `required_case_coverage` | Sum of required verification obligations and latest assessment counts; case-local obligations, not globally unique tests |
| `adjudication_recovery` | Case-local not-eligible episodes and their recorded transitions to eligible |
| `declared_attempt_duration` | Count, sum, minimum and maximum of declared `ended_at-started_at` intervals in milliseconds |
| `work_history` | Whole-Work completion/reentry record counts, regardless of case filter; historical, not live status |

An enrolled case without adjudication contributes to
`latest_unassessed_enrollment_count` and `unassessed_required_case_count`.
It is not silently dropped, classified as PASS, or counted as an observed recovery
episode. Unenrolled cases remain visible. Latest coverage includes SKIPPED,
NOT_EXECUTED and UNKNOWN separately. Failure-domain counts retain the 29B
declared-input limitations. Histogram keys not present have zero matching
**recorded declarations**, not necessarily zero real-world events.

Overlapping declared intervals are not de-overlapped: their sum is not Work
elapsed time, paid time, agent productivity or trusted operational latency.
Empty samples have `min_ms=null` and `max_ms=null`. Arbitrary observation `counts`
are never summed, averaged or used as denominators.

## Recovery Denominator

A first ineligible assessment starts an episode. Further ineligible revisions
continue it. The next eligible revision in the same case closes it once. A later
ineligible revision starts another episode. Initial PASS creates no episode.

Example: `SKIPPED → SKIPPED → PASS → PASS → FAIL` gives two episodes, one recovered
and one open. The exact descriptive fraction is exposed as `rate_numerator=1`,
`rate_denominator=2`, `rate_defined=true`. A zero denominator means undefined.
Open episodes remain in the denominator and are separately visible.

This is not a runtime crash-recovery success rate, proof of a product fix,
independent trials, or a causal estimate of Golem's benefit. Cases are never paired
across identities. No statistical confidence interval or cross-project ranking is
invented from these observations.

## Unavailable Is Not Zero

`unavailable` entries contain `value:null` and a reason:

- Actual false-completion/stale-evidence/duplicate-execution prevention counts:
  rejected calls and same-key retries do not form a complete durable fact stream.
- Actual uncertain-effect reconciliation and manual intervention counts:
  declarations do not prove the corresponding actions happened.
- Time to failure/classification/completion: no matched trusted clock contract.
- Cloud/local costs and unknown-cost population: no research-linked cost contract.
- A weighted evidence-completeness score: the proposed composite is not validated.
  Inspect the explicit coverage components instead.
- Current task completion: not evaluated by historical metrics.

Use the actual completion/resume workflow for current acceptance. A past completion
record remains historical evidence after code changes or new blockers. Metrics
always return `acceptance_verified=false` and `execution_authorized=false`.

## Replay and Provenance

`boundary` pins the complete Work journal head, event counts and document
generation. `source_records` lists selected research ordinals, record digests and
frame digests. Case filters do not change the global replay boundary. Nonresearch
events can therefore change the projection digest without changing research counts.

`projection_digest` is SHA-256 of the compact json-c JSON payload **before** that
field is appended, in emitted member order. It is not a signature, RFC 8785/JCS,
or a new CAS receipt. The same head, rule, filter and retained evidence produce
the same JSON/Markdown bytes. There is no generation time, live clock, source
probe, provider call, cache update or external write in the reducer.

Opening a Work validates its existing journal and CAS first. Missing, corrupt or
semantically forged events fail closed. Uncommitted pending files and CAS orphans
do not become observations. Metrics cannot detect deletion of an entire valid
journal suffix without an external checkpoint; the existing trust model remains.
No historical-prefix CLI, cohort comparison, public bundle or OTel export is added.

## Implementation and Verification

`src/research/metrics.c` owns the bounded reducer and JSON projection;
`metrics_report.c` renders that same model. No new database, event type or on-disk
schema migration is needed. The existing 256-record bound applies; per-case scans
are bounded by that population. JSON stays within 256 KiB and Markdown within
1 MiB, including the maximum 256-case fixture.

Tests cover zero denominators, maximum population/duration, case filtering,
idempotency, corruption, read-only fingerprints, narrative exclusion, recovery
episodes, latest-revision selection and historical completion versus live source.
See `tests/c/metrics_integration.py` and `tests/c/outcome_metrics_integration.py`.

## Research Basis

- Fenton and Bieman, *Software Metrics*, third edition:
  [public publisher preview](https://api.pageplace.de/preview/DT0400.9781439838235_A38252996/preview-9781439838235_A38252996.pdf).
  We examined the available measurement-theory discussion and contents, not the
  complete book. Entities, attributes and valid numeric mappings inform explicit
  populations and the refusal to invent a quality score.
- [Teaching Software Metrology](https://arxiv.org/html/2406.14494v1): its distinction
  between consistent measurement and measuring the intended construct informs
  the separation of reproducible counts from effectiveness claims.
- Runeson and Höst, [case-study research guidelines](https://doi.org/10.1007/s10664-008-9102-8):
  context and validity boundaries motivate keeping cases distinct and avoiding
  generalization from one Work.
- Fowler, [Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html):
  rebuilding state from recorded events and isolating external interactions
  inform the side-effect-free projection. This is an architectural reference,
  not a peer-reviewed evaluation of Golem.

These are design inputs, not evidence that Golem improves outcomes. The exact
episode rules and JSON contract are Golem product decisions, not quoted standards.
