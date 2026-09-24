# Research Records (29A)

[한국어](research.ko.md) · **English**

Research records are optional local records where the current agent structures a
Work's case, per-attempt hypotheses, interventions, observations, and next
decisions. They are not automatic research collection and do not capture an
agent's private reasoning. The current scope covers `ResearchCase`,
pre-attempt `AttemptPlan`, `AttemptDecision`, and
[OutcomeAdjudication](outcome.md). [ResearchMetrics](metrics.md) provides read-only
replay projections. [ComparisonCohort](cohort.md) provides fixed assignments and
declared-outcome comparisons. [CaseStudyBundle](bundle.md) provides redacted private
exports. Public release approval and OTel export (29F) are not included.

## Quick Start

Create a new Work with the Golem you built. The example below is synthetic
registration, not product QA.

```sh
mkdir -p .golem/workspace
WORK="$(cd .golem/workspace && pwd -P)/research-example"
build/dev/golem work start "$WORK" samples/documents/work.json
build/dev/golem research case create "$WORK" samples/research/case.json case-first
build/dev/golem research status "$WORK"
build/dev/golem research inspect "$WORK" 1
build/dev/golem research report "$WORK" 1
```

`inspect` returns the original JSON receipt. `report` returns read-only Markdown
on stdout. If you save the Markdown, use a private output path for the Work.
Golem does not publish, redact, or register this Markdown automatically.
`tests/c/research_integration.py` demonstrates the reproducible path from
pre-plan to observation to next attempt.

[`attempt-request.json`](../samples/research/attempt-request.json) is a template
for structural validation and fuzzing. To register it, replace zero-filled
case/input digests with real digests from the same Work and provide real observed
times. Do not turn empty evidence into success.

## Commands and API

| CLI | Role |
| --- | --- |
| `research validate REQUEST.json` | Validate request structure only |
| `research call WORK REQUEST.json` | Register a JSON request |
| `research case create WORK CASE.json KEY` | Build and register a case-create request |
| `research attempt plan WORK PLAN.json KEY` | Register an optional pre-attempt hypothesis |
| `research attempt record WORK ATTEMPT.json KEY` | Register observations and the next decision |
| `research status WORK` | List replayed records |
| `research inspect WORK SEQUENCE` | Return the original immutable receipt |
| `research report WORK SEQUENCE` | Generate escaped Markdown |

The request envelope has exactly `schema_version:1`, `operation`, `key`, and
`record`. `operation` is one of `case-create`, `attempt-plan`,
`attempt-record`, `outcome-enroll`, or `adjudicate`. `KEY` is unique inside the
Work research namespace. The same key with the same parsed JSON always returns
the original receipt. Whitespace and object-key order are irrelevant; array order
is meaningful. Reusing the same key with different content, or reusing the same
case/attempt identity under another key, is rejected.

The C API is in [research.h](../include/golem/research.h). It uses the existing
Work store. JSON inputs are borrowed only for the call. Replies are malloc-owned
and freed with `golem_execution_reply_free`. On failure the caller output is left
unchanged. The store allocator controls the handle, not json-c or reply malloc.
Calls are serialized per handle. `status`, `inspect`, and `report` support
read-only handles.

## ResearchCase v1

All fields are required. See [case.json](../samples/research/case.json).

| Field | Contract |
| --- | --- |
| `schema_version` | Integer 1 |
| `work_id`, `case_id`, `project_id` | ASCII ID, 1-64 bytes; Work ID must match |
| `case_type` | REAL_SERVICE / BENCHMARK_TASK / FAULT_INJECTION / REGRESSION_CANARY |
| `research_questions` | 1-16 `{id, question}` entries; no duplicate IDs |
| `unit_of_analysis` | Unit of analysis, 1-2048 UTF-8 bytes |
| `context` | product/environment/tool/runner/constraints, each 1-2048 bytes |
| `privacy_level` | PRIVATE / REDACTED_EXPORTABLE / PUBLIC_SYNTHETIC |
| `pre_registered_plan_digest` | Empty string if absent; otherwise SHA-256 in the same Work CAS |

Privacy and preregistration are author declarations. They do not prove publishing
permission or an external preregistration timestamp. Use PRIVATE by default. Do
not include raw secrets. A case cannot be silently changed; new questions or a
new design require a new case ID.

## AttemptPlan / AttemptDecision v1

Plan records contain the 11 common fields below. Decision records add 7 fields.

| Common field | Contract |
| --- | --- |
| `schema_version`, `work_id`, `case_id` | v1 and existing Work/case |
| `attempt_id` | Unique ASCII ID inside the case |
| `case_digest` | `record_digest` from the registered case receipt |
| `previous_attempt_digest` | Empty for the first attempt; later the latest Decision digest in the same case |
| `started_at` | Author-observed UTC Unix milliseconds; 0-253402300799999 |
| `actor_kind` | CURRENT_AGENT / HUMAN_OPERATOR / RUNTIME / EXTERNAL_TOOL |
| `hypothesis`, `intervention` | Each 1-4096 bytes; separate hypothesis from planned intervention |
| `input_refs` | 1-32 `{role,digest}` entries; no duplicates |

`role` is DOCUMENT / SOURCE / CONTEXT / TOOL / CONFIG / EVIDENCE. Each digest
must point to material in the Work CAS. A hash of an external file is not enough;
store the minimum approved material with the evidence API, or refer to an
existing receipt/body digest. `role` is a category, not semantic validation. Do
not indiscriminately copy binaries or entire source trees.

| Decision-only field | Contract |
| --- | --- |
| `ended_at` | At or after started_at, within the same millisecond range |
| `observations` | Up to 32 `{digest,summary,counts}` entries; no duplicate digests |
| `classification` | One taxonomy value below |
| `next_action` | One action value below; not an execution command |
| `decision_rule` | Versioned ASCII ID for the rule the author used |
| `confidence` | LOW / MEDIUM / HIGH; not a calibrated statistical probability |
| `plan_digest` | Pre-attempt Plan `record_digest` or empty string |

Observation summaries are 1-2048 bytes. Counts contain up to 16 `{name,value}`
entries. Names are unique ASCII IDs; values are integers from 0 to INT64_MAX.
These numbers are submitted observations, not metrics Golem derives or verifies
from raw results.

classification: PRODUCT_PASS_OBSERVED, PRODUCT_FAILURE_OBSERVED,
TEST_HARNESS_LIMITATION, ENVIRONMENT_LIMITATION, UNCERTAIN_EXTERNAL_EFFECT,
STALE_EVIDENCE_REJECTED, FALSE_COMPLETION_PREVENTED,
DUPLICATE_EXECUTION_PREVENTED, INSUFFICIENT_EVIDENCE, OPERATOR_ABORTED.

next_action: CONTINUE, REVISE_DOCUMENT, RERUN_ALLOWED, RECONCILE, BLOCKED,
STOP_NOT_DONE, FINALIZE_CANDIDATE.

Empty observations are allowed only for INSUFFICIENT_EVIDENCE or
OPERATOR_ABORTED. UNCERTAIN_EXTERNAL_EFFECT allows only RECONCILE, BLOCKED, or
STOP_NOT_DONE. FINALIZE_CANDIDATE is allowed only with PRODUCT_PASS_OBSERVED,
but it **does not grant DONE**. Semantic adjudication and completion blocking are
handled by the [29B contract](outcome.md).

If a pre-attempt Plan exists, all common Decision fields must match that Plan.
Omitting the Plan digest to alter an earlier hypothesis after the fact is
rejected. A Decision without a prior Plan is a retrospective record. Golem checks
journal ordering for the Plan, but it does not prove the Plan was written before
real external action; wall clock time is not authoritative. A prior Decision
reference in the same case must be current at registration time. Split parallel
investigations into separate cases. Do not mutate old Plans; record a new
attempt ID.

## Storage, Replay, Recovery

`src/research/model.c` performs bounded schema validation, `store.c` handles
CAS/journal registration and replay, and `report.c` generates derived Markdown.
There is no separate database or server dependency.

Research uses the existing Work lifetime flock, no-replace atomic event publish,
and hash chain. A research event is a CAS object with
`schema_version/type/sequence/request`, and the Work journal references its
digest. `sequence` is the research ordinal. Document generation does not change.
29A records do not invalidate existing document CAS conditions, sessions, or
completion. 29B enrollment and adjudication do not change document generation,
but they can require completion revalidation.

Every Work open revalidates schema, IDs, attempt links, Plan matches, and all CAS
references. Missing, modified, or unknown events fail closed. Existing Works open
unchanged; a Work containing research events is rejected by older engines that do
not understand the event. Registration and compact requests are each limited to
64 KiB. Each Work may contain up to 256 research events. A Plan consumes one
event. Limit changes require separate compatibility review.

CAS objects written before journal publish and then interrupted are uncommitted
orphans and are not counted. If a response is lost or memory fails after publish,
the event may already be committed; close and reopen the handle, then retry with
the **same key**. Do not rerun with a new key or edit state directly. As with the
existing store, deletion of the final suffix cannot be detected without an
external checkpoint. The hash chain does not prove trusted authorship or the
truth of observations.

## Research Basis

Runeson and Host's [case study guidelines](https://doi.org/10.1007/s10664-008-9102-8)
emphasize traceable evidence from research questions through observations and
interpretation. Golem applies that idea by separating questions, units of
analysis, and evidence references; the paper does not validate Golem.

Public descriptions and tables of contents for
[Case Study Research in Software Engineering](https://onlinelibrary.wiley.com/doi/book/10.1002/9781118181034)
separate research design, data collection, analysis, and reporting. This
documentation does not claim to have read the full paid text. The case/attempt/
report boundaries are Golem design decisions informed by that structure.

[PROV-DM](https://www.w3.org/TR/prov-dm/) informs the separation of evidence,
attempts, and actors. This implementation is not PROV serialization or
conformance. A [study of case-study reporting limitations](https://arxiv.org/abs/2402.08411)
emphasizes context, classification, and generalization limits; one REAL_SERVICE
success must not be presented as universal performance improvement.

## Replay Lookup Bounds

Research keys and case identities have separate, store-local open-addressed
indexes. Each has twice the maximum event capacity, stores only event ordinals,
and compares full strings on collisions. They allocate no memory during adoption
and are rebuilt only from validated journal events. They are not persisted cache
authority: referenced CAS evidence, sequence, duplicate identity and schema checks
still run on replay. Idempotent retry still compares the complete parsed request.
Worst-case collisions remain bounded by the table size; constant-time adversarial
lookup is not promised. Capacity and colliding-key CLI tests close/reopen the Work
on every operation, including conflicting retry rejection.

[MIT 6.006 hashing notes](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/bd220fb629aefdf30f416b5abf45d38d_MIT6_006S20_r04.pdf)
inform the collision/load-factor reasoning. CLRS, *Introduction to Algorithms*,
4th edition, chapter 11 is a textbook reference; only the publisher's description
and contents were checked, not the full paid chapter. The index is a Golem design,
not a performance guarantee taken from either reference.
