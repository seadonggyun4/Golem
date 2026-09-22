# Conditional Markdown Workflow

Phase 23 adds stage selection, exact upstream references and transitive freshness
to the immutable [document registry](document-registry.md). It does not launch
another agent. The current agent authors Markdown, registers it, requests the
next inputs, and performs the work. Registration is not semantic acceptance.

## CLI

The following are query commands; their JSON output must be explicitly registered
using `golem document submit` with Markdown and metadata to change the Work.
`WORK` is the registry directory, not a source checkout.

```sh
golem workflow select WORK scope 1 development
golem workflow inputs WORK selection planning SOURCE_SHA256 1048576
golem workflow trace WORK planning 1
golem workflow next WORK selection
```

`select` accepts `development` or `documents`. It requires a current Phase 22
scope whose assessment is ready. Selection returns six ordered decisions:
planning, ux, publishing, development, qa, audit. Planning, development, QA and
completion verification cannot be skipped. UX/publishing are required when any
selected finding requires them; otherwise the proposal supplies an explicit
NOT_APPLICABLE reason. An agent may conservatively require additional stages.
Omissions contrary to the selected scope are rejected at registration.

## Registration Contracts

Metadata schema 3 extends the registry's base fields with `selection`, uses kind
`stage-selection`, stage `planning`, and requires a `## Stages` Markdown section.
Its scope reference must also be a metadata parent. Each decision contains
`stage`, `status`, `reason`, `evidence` (the exact scope reference), and `reuse`.
The full selection returned by `select` is the starting payload, not a receipt.

Metadata schema 4 extends the base fields with `input_manifest`. Request the
manifest for the target kind, copy its `direct` array into metadata `parents`,
and use the manifest generation as `expected_generation`. Include exact
`golem-doc:ID:REVISION:MANIFEST_DIGEST` parent links in the Markdown. Use the
existing kind-specific sections documented in the registry guide. Carry all
selected requirement IDs downstream. Submit the authored body and metadata
together. Submission re-computes the manifest under the registry lock; changing
only the generation on an old manifest cannot make it valid.

Schema 1/2 documents remain readable. Legacy stage documents do not count as
managed handoffs simply because their kind matches. Explicit reviewed reuse is
the narrow exception for UX and publishing.

## Dependency Rules

Every managed document directly references its stage selection. Additional
direct dependencies are:

| Target kind | Required direct inputs |
| --- | --- |
| planning | selected scope |
| ux | planning |
| publishing | planning, applicable ux |
| development-plan | planning, applicable ux and publishing |
| development-result | planning, development-plan |
| qa-plan | planning, development-plan, development-result |
| qa-result | planning, development-plan, development-result, qa-plan |
| completion | planning, development-plan, development-result, qa-plan, qa-result |

In `documents` mode, development-result is forbidden and omitted from subsequent
dependencies. QA still needs its own documents; no implementation/test success
is fabricated. The manifest includes the entire transitive closure, not just
this table's direct edges. Each entry binds revision, manifest digest, Markdown
body digest and byte length. Work, selection, source snapshot, schema, template
and policy identities are bound as well.

The context budget counts Markdown bytes, not tokens; maximum is 16 MiB.
Metadata/manifest JSON has a separate 256 KiB limit. A closure that does not fit
fails; required inputs are never silently truncated. These are bounded APIs,
not an unbounded context compressor.

## Freshness and Recovery

`CURRENT` means the revision is latest and all its ancestors are current.
`SUPERSEDED` means a later revision of the same document exists. `STALE` means
at least one ancestor is superseded or stale. Whole-revision digest invalidation
is conservative: even an editorial revision can require downstream review.
No modification-time heuristic or semantic equivalence guess is used.

The pure C graph API in `golem/workflow.h` uses iterative topological evaluation,
rejecting cycles, duplicate revisions/edges and cross-Work dependencies. Limits
are 4096 revisions, 16384 edges and 64 parents per revision. Queries rebuild the
graph from immutable registry records; no mutable freshness cache must survive a
restart. Historical trace preserves the original references.

Registration and handoff reject stale parents, unavailable/corrupt CAS objects,
and modified existing Markdown projections. Missing projections may be repaired
from CAS by the registry; they are not independent authority. Concurrent commits
within the same Work invalidate the manifest generation conservatively. Another
Work cannot invalidate this Work's generation. An idempotent resubmission returns
the original receipt, which may now be stale; query freshness before reuse.

`source_snapshot` is a caller-supplied, validated digest, not a live filesystem
scan. The agent must capture changes and register updated scope/selection when
the work's source basis changes. This phase does not prove repository cleanliness.
Scope/template/policy version fields currently remain at version 1.

## Reviewed Reuse

Only UX and publishing can use `REUSED`. Add the reused document as a selection
parent and set `reuse` to `{ "document": REF, "review_digest": SHA256 }`.
Store the following JSON as CAS evidence first:

```json
{
  "schema_version": 1,
  "work_id": "example-work",
  "document": {"document_id": "ux", "revision": 1, "digest": "MANIFEST_SHA256"},
  "scope": {"document_id": "scope", "revision": 1, "digest": "MANIFEST_SHA256"},
  "source_snapshot": "SOURCE_SHA256",
  "policy_version": 1,
  "template_version": 1,
  "decision": "REUSE",
  "reason": "Explain applicability to the selected scope."
}
```

Replace digest placeholders with real digests. This is an immutable review
record, not a signature or reviewer authentication. The document must be current
and match the snapshot; stale ancestors cannot be waived by attaching a review.
Register a revised document against current parents instead. QA PASS is never
copied by this reuse mechanism.
Revising a selection cannot reuse a document that transitively depends on that
selection's previous revision: the new revision would invalidate its own inputs.
Such submissions are rejected before publication.

## Next Action Is Not Authority

`next` returns document/reentry actions or VERIFY_COMPLETION. Two current managed
documents of the same required kind are ambiguous and cause rejection. Artifact
presence alone keeps `acceptance_verified` false. With a persisted receipt,
[completion verification](completion.md) can return DONE, RECOVER_REPORT, or
REVALIDATE_COMPLETION. Only current DONE sets `acceptance_verified` true, within
the declared-gate assurance contract. `execution_authorized` remains false;
claims, leases and existing policy checks still govern execution/registration.

## Design References

- [Build Systems a la Carte (ICFP 2018)](https://simon.peytonjones.org/assets/pdfs/build-systems-original.pdf):
  dependency tracking and rebuilding are separate from execution scheduling.
- [Software Engineering at Google, chapter 18](https://abseil.io/resources/swe-book/html/ch18.html):
  explicit artifact dependencies and reproducible inputs.
- [W3C PROV Constraints](https://www.w3.org/TR/prov-constraints/):
  provenance identity and validity constraints. This implementation's document DAG
  is deliberately narrower than the general PROV model.
- [MetaGPT (ICLR 2024)](https://arxiv.org/html/2308.00352v7): structured handoffs
  motivate explicit artifacts, not importing a multi-agent execution framework.

These are design inspirations, not evidence that document freshness establishes
semantic correctness or that Golem reproduces the papers' evaluation results.
