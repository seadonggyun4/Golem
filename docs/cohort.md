# Comparison Cohorts (29D)

[한국어](cohort.ko.md)

Compare **NON_USE**, **PARTIAL_USE**, and **FULL_USE** without changing the work
completion rules. This is a private measurement registry, not a trial executor,
randomizer, independent reviewer, or causal-effect estimator.

| Assigned arm | Intended intervention |
| --- | --- |
| NON_USE | Agent alone or existing ad hoc workflow; no Golem execution controls |
| PARTIAL_USE | Markdown templates and manually organized evidence; no Golem execution controls |
| FULL_USE | Golem document graph, execution receipts, reentry and completion checks |

Recording control-arm observations in Golem is measurement, not FULL_USE treatment.
Run each task in an isolated workspace/session. Do not give control agents earlier
solutions. Golem does not enforce isolation or independently attest actual exposure.

## Commands

```sh
golem research cohort create WORK cohort.json cohort-key
golem research cohort observe WORK observation.json observation-key
golem research compare WORK study-id
golem research report WORK RESEARCH_SEQUENCE
```

The first two commands wrap schema-1 requests with operations `cohort-create` and
`cohort-observe`; `research call` and `research validate` accept the same envelopes.
`compare` prints deterministic JSON; `report` prints escaped Markdown for any
record. Neither writes projections. Redirect output only to an approved private path.

## Immutable Definition

Shape templates: [create](../samples/research/cohort-request.json) and
[observe](../samples/research/cohort-observe-request.json). Replace zero digests
and IDs with actual CAS/record references before submission; these are parser
examples, not executable study results.

Exact `cohort-create` record fields:

- `schema_version: 1`, `work_id`, `cohort_id`.
- `design`: `MATCHED_BLOCKS` or `OBSERVATIONAL`. Neither asserts randomization.
- `protocol_digest`: predeclared hypothesis, sampling/allocation method, analysis,
  stopping/missing-data rules and isolation plan.
- `task_digest`, `acceptance_digest`, `evaluation_digest`: common task definition,
  acceptance criteria, and evaluator/test interpretation contract across all arms.
- `environment_digest`: planned provider/model version, sampling settings, input
  snapshot, token/cost budget, timebox, operator/session, runner and test-tool versions.
- `members`: 3..48 objects, each exactly `case_id`, `case_digest`, `arm`, `block_id`.

All IDs use the existing ASCII ID contract (1..64 characters). Digests are SHA-256
references to existing Work CAS objects. Artifact contents are user-defined;
Golem verifies bytes, not their scientific adequacy. Pin full JSON/Markdown
contracts, not just filenames. Model/budget changes require a new actual environment
artifact and are reported as deviations, not silently treated as equal conditions.

All three arms must be represented. Every matched block contains exactly one case
per arm. Observational blocks may be unbalanced and may identify time slices;
they must not be presented as randomized comparisons. All members must already
have ResearchCase records in this Work, with matching record digests. No member
may have an attempt plan, decision, outcome enrollment, or other case event yet.
A case belongs to at most one cohort in a Work. The complete roster is committed
atomically, cannot grow/shrink, and cannot be reassigned after observing results.

This enforces **local journal order only**. It cannot prove external execution
had not happened, detect duplicate real-world tasks under new IDs, or prevent
selective publication of entire studies. `external_preregistration_verified=false`.
There is no retrospective cohort mode in v1; use a separate explicitly exploratory
study instead of pretending late assignment was prospective.

## Observations and Revisions

Exact `cohort-observe` fields:

- `schema_version: 1`, `work_id`, `cohort_id`, `cohort_digest`, `case_id`.
- `supersedes`: empty for the first observation, otherwise the latest observation's
  record digest for this cohort member. Stale branches are rejected.
- `status`: `PASS`, `FAIL`, `SKIPPED`, `NOT_DONE`, or `UNKNOWN`.
- `observed_arm`: one of the three arm names. A crossover never changes assignment.
- `environment_digest`: actual conditions, even when different from the plan.
- `evidence_digest`: evaluator output and rationale, including missingness, leakage
  details, protocol deviations and links to supporting artifacts where applicable.
- `leakage`: a JSON boolean declaring known cross-arm information contamination.

PASS means the submitter reports satisfaction of the shared evaluation contract;
FAIL reports a negative result; SKIPPED reports deliberate nonexecution; NOT_DONE
reports incomplete work; UNKNOWN means interpretation is unavailable. Missing
observations are `NOT_RECORDED`, never implicit FAIL or PASS. These meanings are
declarations, **not** 29B adjudications. A PASS cannot satisfy completion obligations.
Common evaluation is a study contract, not independently verified by this module.

Same key plus equal parsed JSON returns the original receipt, even after a newer
revision. A changed payload under that key fails. Observations are append-only.
Revisions can correct status but never erase previously declared leakage, arm
crossover, or environment difference from the comparison's historical flags.

## Replay and Interpretation

`golem.comparison-cohort.v1` keeps every assigned member and groups by original
arm. It exposes latest declared status counts, assigned/observed denominators,
revision counts, historical deviations, member rows, and source record/frame digests.
It does not report success-rate rankings, p-values, causal effects, or independently
verified acceptance. Absence of a deviation declaration is not proof of compliance.
29C metrics exclude cohort records from their measurement population; the global
Work boundary still includes them. 29B completion predicates remain unchanged.

The projection digest hashes compact json-c JSON before adding `projection_digest`;
it is not JCS. The Work head pins the replay prefix. Research events share the
256-record / 64-KiB request bounds. Cohort events use journal schema 2; older engines
reject the unknown operations rather than ignoring them. CAS verification, locks,
permission checks, poisoned-handle recovery and same-key retry follow [research](research.md).
There is no cross-Work join, random allocation or significance test. A selected
member's observations can be included in a [redacted case bundle](bundle.md);
the full cohort roster is not exported by that case-scoped operation.

## Research Basis

- [NIST randomized block designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm):
  motivates explicit blocks and recording nuisance factors rather than treating
  different environments as interchangeable.
- [COS preregistration](https://www.cos.io/initiatives/prereg): motivates a fixed plan
  and transparent amendments; a local sequence is not an external registry attestation.
- [Branson, Randomization Tests to Assess Covariate Balance (2021 preprint)](https://arxiv.org/pdf/1804.08760):
  matching alone does not establish randomized assignment. We preserve descriptive
  output and do not implement or claim the paper's randomization tests.
- [Shadish, Cook and Campbell, Experimental and Quasi-Experimental Designs for
  Generalized Causal Inference (2002), public excerpt](https://iaes.cgiar.org/sites/default/files/pdf/147.pdf):
  reviewed the available opening chapters on causation/validity, not the entire book.
  Selection, attrition, context and alternative explanations constrain causal claims.
