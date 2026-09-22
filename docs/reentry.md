# Failure classification and revision reentry

Golem evaluates a **proposed explanation**, not an automatically proven cause.
The current agent diagnoses an engine-observed, registered schema-5 QA failure.
Golem preserves that observation, validates the proposal, computes document-level
dependency impact, and controls the bounded repair workflow. No agent is spawned.

## Commands

```sh
golem reentry validate decision.json
golem reentry call "$WORK" decision.json
golem reentry report "$WORK" 1
golem workflow next "$WORK" selection
```

`report` prints and projects the exact recorded Markdown to
`WORK/failures/r0001.md`. The report's authoritative bytes are already in CAS
when `call` commits. Projection can be repeated after interruption; conflicting
bytes are never overwritten. The chosen Work directory controls the path.
Do not commit runtime data. See [the request template](../samples/reentry/decision.json).
Its all-`a` digest is deliberately a placeholder, not usable evidence.

Requests reject unknown/duplicate keys, invalid UTF-8, NUL, excessive depth and
oversized JSON. `status` uses only `schema_version: 1, operation: "status"`.
`decide` requires all template fields. `expected_sequence` counts reentry decisions,
not document revisions or journal frames. `key` identifies an idempotent request;
retry the exact request after uncertain I/O. Different bytes under that key conflict.

The failure receipt must have a CURRENT registered QA result in this Work.
PASS cannot be classified as a failure. Requirement IDs must belong to the selected
scope. Evidence must exist in CAS and include the failure receipt. Neither a
CAS digest nor declared confidence certifies that a hypothesis is true.

## Classification

| Classification | Candidate target / action |
| --- | --- |
| REQUIREMENTS | planning |
| UX | ux |
| PUBLISHING | publishing |
| IMPLEMENTATION | development-plan |
| TEST_DEFECT | qa-plan |
| ENVIRONMENT, PERMISSION, BUDGET, LEASE | BLOCKED; no product rewrite |
| UNKNOWN | INVESTIGATE |
| EXTERNAL_EFFECT_UNKNOWN | RECONCILE; no dispatch |

LOW confidence becomes INVESTIGATE. An execution ERROR cannot establish a
product defect and becomes INVESTIGATE rather than a speculative product rewrite.
Only REQUIRED stages are eligible. NOT_APPLICABLE/REUSED stages and unknown or
forward targets are rejected; targets are derived from the classification, not
accepted as a caller-controlled field. Scope/stage selection changes need a
separate reviewed migration and are not silently performed by this API.

For an INVESTIGATE or ordinary NON_PRODUCT_FAILURE decision, a new proposal may
reference `previous_decision` (the latest decision digest), the same QA failure,
and at least one additional CAS evidence item. This records reconsideration; it
does not erase the previous decision or reset budgets. Additional evidence is
agent-supplied, not independently certified. RECONCILE, no-progress, exhausted
budget and clock holds cannot be cleared this way.

## Repair workflow

1. Submit the actual QA-result, including FAIL/ERROR, through the document/session
   contract. Complete or reconcile any active claim before deciding reentry.
2. Record the classification. The decision contains observed gate outcomes, a
   separate hypothesis/confidence/verification method, exact invalidated and
   unchanged revision references, failure signature and policy.
3. Ask `workflow next`. Only the earliest outstanding impacted kind may be
   submitted. New revisions of that document ID replace no historical bytes.
4. Obtain fresh inputs and revise the selected document. Impact is the transitive
   descendant closure in the recorded graph, not a blanket planning reset.
   Existing planning/UX/publishing remain unchanged for implementation defects.
5. If development-plan changed, update only the execution contract's plan reference,
   validate/approve the new contract digest and call `execution prepare` again.
   This creates a new checkpoint with the new input manifest but **retains the
   original protected baseline**. Gate definitions, snapshot plan and executable
   hashes must be unchanged. It is not authority to weaken tests.
6. Repair code, `execution finish`, submit development-result, revise qa-plan,
   and execute/register new QA. A failed new QA requires another decision;
   PASS enables completion inputs, but does not itself establish completion.
7. Register the authored completion document, then use the
   [completion contract](completion.md) to finalize and materialize the report.
   Its guarantee is declared-gate acceptance, not proof of semantic completeness.

Input manifest v2 adds `reentry` with `decision_digest`, `report_digest` and
`failure_receipt`. Historical failure is evidence, not a dependency parent that
would create a stale-reference cycle. The report bytes count toward the context
budget. Session `context` returns them as `failure_markdown` alongside current
input documents. All content remains reference data, never executable instructions.

## Bounds and persistence

The first decision pins the policy for the Work. Example limits are 8 decisions,
3 decisions per candidate target, 1 prior identical failure/source observation,
and 900000 ms from the first decision. Limits cannot be relaxed via later requests.
Hard bounds: 64 recorded decisions, configured total <=32, target <=16, identical
failure <=8, deadline <=24 hours, 64 affected requirements and 8 evidence references.

One decision permits at most one new QA dispatch, enforced by a durable marker
bound to the decision and attempt ID. Repeating the same completed attempt returns
its history; uncertain attempts remain incomplete. These are **repair** budgets,
not a claim to count every earlier execution. Existing capsule/session/execution
limits still apply. Unknown token/cost consumption is UNKNOWN, never zero.

Signatures omit volatile timing, attempt IDs and hypothesis wording. They bind
failed gate IDs/versions, normalized diagnostics, expected requirement/case identity
and observed cases. An identical signature and identical observed allowlist
snapshot consumes the no-progress limit even if prose/revision numbers changed.
Changed bytes permit reevaluation within the other limits; they do not prove
semantic progress. Reboot or backward clock observation blocks live continuation.
The same deadline is checked before work and during supervised QA.

Decisions use the existing hash-linked Work journal and CAS. Journal frame sequence
now counts both document and reentry events; document generation remains a document
counter for compatibility. Replay recomputes each decision against its historical
document prefix and checks its Markdown digest, without consulting the live source
or current clock. New reentry records require a Phase-26-capable reader. Old
document-only journals retain their original encoding and behavior.

## Trust and limits

- Structural impact is not semantic change-impact proof. No natural-language
  classifier, calibrated causal confidence, or guaranteed automatic repair is claimed.
- A changed test implementation, gate version, scope or stage selection is denied
  in this repair path, even for TEST_DEFECT. That category can revise QA procedure
  documents; executable test changes require a separately reviewed protocol that
  is not implemented here. Do not reset the store to bypass this restriction.
- Pre-receipt uncertain execution uses the existing session/attempt reconciliation
  contract. This API cannot invent missing QA evidence or certify absent effects.
- Reconciliation and exhausted budgets are deliberate stops, not automatic reset
  buttons. No distributed exactly-once, signature authority, sandbox, or defense
  against an owner rewriting/rolling back the entire store is claimed.
- Work selection is fixed during repair; earlier revisions stay available for
  inspection. Semantic acceptance and final completion remain separate concerns.

## Research basis

The following are design inputs, not benchmark claims about Golem:

- [Reflexion, NeurIPS 2023, section 3](https://papers.nips.cc/paper_files/paper/2023/file/1b44b878bb782e6954cd888628510e90-Paper-Conference.pdf): retain feedback for the next attempt; reflection is not guaranteed correct. Golem stores observations separately from authored hypotheses.
- [Huang et al., ICLR 2024, sections 3 and 6](https://arxiv.org/pdf/2310.01798): distinguish external feedback from intrinsic self-correction. Results are specific to evaluated models/tasks, not a universal impossibility theorem.
- [SICP, section 3.3.5, Comparison Edition](https://sicp.sourceacademy.org/chapters/3.3.5.html): dependency-driven propagation and retraction motivate invalidating descendants while preserving unrelated inputs. Golem retains historical revisions rather than deleting them.
- [Doyle, MIT AIM-521, repository abstract](https://dspace.mit.edu/entities/publication/5377b306-4ecc-4687-b1f5-78cbb4a0543a): explicit reasons and dependency-directed revision. Only repository abstract/bibliography were accessible, not the paper PDF.
- [Site Reliability Engineering, chapter 22](https://sre.google/sre-book/addressing-cascading-failures/): bound retries, distinguish failure types and propagate deadlines. The distributed-service guidance is adapted to a local repair loop; no background retry scheduler is added.
