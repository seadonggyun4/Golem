# OutcomeAdjudication (29B)

[한국어](outcome.ko.md) · **English**

Golem does not complete work merely because a tool prints `PASS` or reports zero
errors. Required cases are enrolled first, declared observations are normalized
with fixed rules and evidence links, and completion is verified alongside real
QA. This uses the same Work CAS/journal as the current-agent flow.

## Usage Flow

1. Register a ResearchCase and development stage-selection.
2. Before QA, pin required verification cases with `outcome-enroll`.
3. Run real QA and register QA Markdown.
4. Submit normalized observations with `adjudicate`.
5. Resolve failures, missing cases, or blockers; new adjudications reference the
   previous `record_digest` through `supersedes`.
6. Use the existing `completion finalize` and `completion resume` to determine
   whether the Work is complete.

```sh
golem research outcome enroll "$WORK" policy.json enrollment-1
golem research outcome adjudicate "$WORK" adjudication.json adjudication-1
golem research status "$WORK"
golem research inspect "$WORK" 3
golem research report "$WORK" 3
```

`3` is an example research sequence; use the actual `event.sequence` from the
receipt. Markdown is returned on stdout and is not published automatically. The
same JSON envelope also works through existing `research call` and the C API
`golem_research_call`. Structural validation is `golem research validate
REQUEST.json`; it does not verify evidence or complete work.

## Enrollment

All fields are required. The request envelope is
`{schema_version:1,operation,key,record}`. `operation` is `outcome-enroll`.
Replace the zero digest in the [structural example](../samples/research/outcome-enroll-request.json)
with the actual `record_digest` from the ResearchCase receipt.

| record field | Contract |
| --- | --- |
| schema_version | Integer 1 |
| work_id, case_id, case_digest | Registered ResearchCase in the same Work |
| selection_id | Registered development selection ID |
| gate_id | Gate ID to verify in the real QA receipt |
| adjudication_rule | Only `golem.required-cases.v1`; unknown versions reject |
| required_cases | 1-64 `{id,requirement_id}` entries; no duplicate IDs; requirement is in the selection |

There is one enrollment per case. It is not edited, reduced, or disabled. If a
wrong obligation is enrolled, move to a new Work and correct the design instead
of silently deleting it. Every enrollment is a **Work-wide completion
obligation**. It cannot be bypassed by another selection ID. Use separate Works
for independent pipelines. Document revisions for the same selection ID are
allowed, and existing freshness checks still apply.

For compatibility, old completion rules remain in effect before enrollment. To
use 29B protection, enroll a policy. After enrollment, missing adjudication
blocks completion. Post-hoc enrollment is allowed, but it must not be described
as a pre-registered experiment.

## Adjudication

`operation` is `adjudicate`. The [request template](../samples/research/adjudication-request.json)
contains placeholders; replace them with real receipt and evidence digests.

| record field | Contract |
| --- | --- |
| schema_version, work_id, case_id, case_digest | Integer 1 and existing case reference |
| policy_digest | Enrollment receipt `record_digest` |
| qa_receipt | QA receipt digest issued by the execution engine in the same Work; no noop or arbitrary CAS |
| supersedes | Empty for the first adjudication, then the latest adjudication `record_digest` in the same case |
| raw_status | 1-256 byte description preserving tool-reported raw status; no authority |
| rationale | Normalization rationale, 1-4096 bytes |
| observations | Up to 64 `{id,status,failure_domain,evidence_digest}` entries |
| open_blockers | Up to 32 unique blocker IDs |

Observation IDs must be enrolled required cases. Missing observations are
computed as `NOT_EXECUTED`. Each digest is hash-verified in the same Work CAS.
Store only the minimum necessary report through the evidence API; do not copy
secrets or complete raw logs indiscriminately.

status: `PASS`, `FAIL`, `ERROR`, `SKIPPED`, `NOT_EXECUTED`, `UNKNOWN`.
failure_domain: `NONE`, `PRODUCT`, `HARNESS`, `ENVIRONMENT`, `UNKNOWN`.
PASS allows only NONE. Other statuses do not allow NONE. PRODUCT is allowed only
for FAIL. Cause classification is the observer's declaration; Golem does not
prove causality.

## Derived Rules

| Derived field | Meaning |
| --- | --- |
| normalized_status | Priority FAIL > ERROR > UNKNOWN > NOT_EXECUTED > SKIPPED > PASS |
| required_case_complete | Every required case has an executed PASS or FAIL result; this is not success |
| completion_eligible | All required cases PASS, full QA and selected gate PASS, and no blockers |
| work_outcome | PASS if eligible, otherwise NOT_DONE; it does not grant Work DONE |
| *_count | Computed from observations; callers cannot submit totals or eligibility |

Product, harness, and environment counts are the number of non-pass cases that
declare that domain. Environment ERROR is not counted as a product bug. SKIPPED
is not passing even when fail_count and error_count are zero. If all observations
PASS but native QA FAILs, completion is impossible.

## Completion, Recovery, Compatibility

- The latest adjudication QA digest must exactly match the QA receipt for the
  completion target.
- Outcome adjudication does not replace document/source freshness, real gate/case
  PASS, permissions, session checks, or unsubmitted execution checks.
- Completion receipts pin policy/adjudication digests and show them in completion
  Markdown.
- If a blocker or new adjudication appears after completion, current state is
  REVALIDATE_COMPLETION.
- Retrying the same key for an old receipt is historical RECORDED, not a new DONE
  claim.
- After blocker resolution, a new adjudication key can complete the same document
  generation again.
- Adding ordinary 29A logs does not invalidate completion.
- Outcome events use journal schema 2. Replay recomputes assessment from inputs
  and evidence, rejecting stored eligible tampering, invalid supersedes, and
  missing or modified CAS.
- Previous schema-1 records and completion without enrollment keep their
  byte-level assessment contract. Older engines fail closed when they cannot
  interpret outcome events.

## Trust Boundary

The v1 `source_kind` is `DECLARED_OBSERVATIONS`. Golem does not universally parse
external result formats or ask AI to judge report prose. The author is
responsible for mapping observations to evidence. The engine verifies that a real
QA receipt exists and that gate results match, but it does not independently
review whether the attached evidence proves every claim. `independent_review` is
false. Do not use this as safety certification, proof of zero defects, or proof
that tool output is true.

It follows the existing journal's local trust model. Whole-store rewrite defense
or final-suffix deletion detection without signatures or external checkpoints is
a separate problem. Read-only outcome projections are documented in
[ResearchMetrics (29C)](metrics.md). Comparison cohorts and public export
(29D-29F) are not added here.

## Basis and Design Interpretation

- Barr et al. (2015), [The Oracle Problem in Software Testing: A Survey](https://discovery.ucl.ac.uk/id/eprint/1471263/),
  separates automating test execution from automating the judgment of correctness.
  Golem uses this to separate execution success, observations, semantic
  adjudication, and completion, and to avoid guessing that unverified cases PASS.
  The v1 declared-normalization model does not solve the general oracle problem.
- Smith and Lin (2024), [Using Assurance Cases to Guide Verification and Validation of Research Software](https://arxiv.org/html/2411.03291v1),
  separates claims, evidence, requirement/design/test traceability, operating
  assumptions, and review. Golem applies that structure to required cases,
  evidence, and derived assessment. It does not implement independent review.
- Jeff Tian, [Software Quality Engineering: Testing, Quality Assurance, and Quantifiable Improvement](https://onlinelibrary.wiley.com/doi/book/10.1002/0471722324):
  public descriptions and contents distinguish prevention, verification, and
  measurement beyond testing. This documentation does not claim to have read the
  full paid text. Golem's separate execution/product/harness/environment fields
  are a design choice informed by that distinction.
- [W3C PROV-CONSTRAINTS](https://www.w3.org/TR/prov-constraints/) informs
  identity, ordering, and consistency checks for immutable enrollment and the
  supersedes chain. This is not PROV conformance, nor a claim that provenance
  proves truth.

Rules and status priority are Golem's conservative product contract, not a
standard quoted from those sources. Reproducible validation uses the real C QA
fixture in `tests/c/outcome_integration.py`.
