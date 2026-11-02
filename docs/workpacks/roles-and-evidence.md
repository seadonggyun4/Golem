# Roles, verifier proposals and Evidence Package design

M4 implements [native document binding](binding.md); M5 implements the bounded
[untrusted proposal parser and native role evaluation](proposals.md). General role
mapping remains PLANNED. M6 implements only the [native document receipt scope](receipts.md);
the broader aggregation below is historical design. M5 does not authenticate
principals or evaluate semantic truth.
Existing [role contracts](../role-contracts.md), [completion](../completion.md),
[evidence export](../evidence-export.md) and [proof packs](../proof-packs.md) remain canonical.

## Role/capability contract

Role means permission plus input/output contract, not persona or a model label.

| Role | Input/output | Additional gate |
| --- | --- | --- |
| proposer | Exact source → proposed change and intended acceptance | No self-granted effects |
| executor | Approved exact action → native execution receipt | Existing D4/native owner gate |
| deterministic verifier | Pinned input/config → reproducible check receipt | Check result is not completion |
| semantic verifier | Exact artifacts/contract → findings proposal | Cannot emit authoritative PASS |
| approver | Reviewed evidence → owner decision | Must be independent where policy requires |
| publisher | Approved release input → observed release outcome | Separate export/network/host authority |
| recovery operator | Uncertain state → explicit recovery decision | Never automatic redispatch |

The reference `data_validator` is a custom role mapped to deterministic verification,
not a built-in execution entitlement. Custom names declare requirements only until
owner-reviewed mapping to existing native contracts is implemented. Separation of
duties uses independently established principals; client/model labels are insufficient.
Unknown identity and self-approval block. Claims/handoffs must retain current owner,
lease, generation, source, input and role-contract digest. Duplicate workers, stale
role submissions, foreign owners and interrupted execution cannot acquire authority
through pack selection. Revisions invalidate dependent evidence transitively through
the native graph. No pack scheduler or concurrency manager is introduced.

Capabilities are closed symbolic references. A resolver must check each pack ceiling
against owner policy, current Work state, role and runtime availability. Missing tool,
prohibited effect, unsupported mapping, stale generation or policy conflict = blocked.
M1 only validates names; it does NOT implement intersection or enforce effect policy.

## Semantic verifier proposal design (historical; implemented limits in proposals.md)

A bounded typed proposal needs: schema; proposal ID; Work/generation; pack digest;
inspected artifact `{digest,size}` references; verifier principal and model/provider
self-declarations; prompt/contract digest; findings `{id,severity,summary,evidence_refs}`;
confidence category (not calibrated probability); limitations; recommendation;
unresolved questions. Proposed limits: 64 KiB, 32 findings, 32 artifact refs, 2048
UTF-8 bytes per narrative field. Reject unknown keys, path/executable/provider secrets,
foreign artifact references and stale parent hashes. Do not store raw model reasoning,
API keys, hidden prompts or unnecessary dataset values. Minimum provenance is exact
artifact, contract, tool/model declaration and caller-established role identity.

Model/provider fields do not authenticate the worker. Accepting a proposal artifact
proves neither its findings nor evidence truth. Failed verifiers stay failed; disagreement
between multiple verifiers is preserved and escalated to explicit owner decision,
never averaged into native PASS. Deterministic checks retain separate receipts.
Metadata and findings may contain prompt/tool-output injection: render as quoted data,
never dispatch instructions from it. Publication and external providers need separate
capabilities; no automatic provider/API-key setup is part of this design.

```
proposal artifact accepted ≠ finding proven true ≠ QA PASS
≠ owner approval ≠ native completion
```

## Evidence Package / portable receipt (future)

A package is a bounded projection of native authoritative records, not a second ledger.
Proposed manifest fields: schema/renderer version, Work identity and generation,
exact pack reference, source snapshot, role submission refs, tool inventory, Evidence
inventory `(digest,size,media_type)`, owner decision refs, native completion receipt
ref, unresolved blockers, declared timestamps, missing-object list. No arbitrary
filesystem paths or automatic retrieval. Proposed total 16 MiB/256 objects; manifest
64 KiB. M6 selected these bounds; its narrower implemented schema is in [receipts.md](receipts.md).

CAS / manifest / native receipt = authority under their original local trust contracts.
Markdown and future HTML = derived projection. JSON export must identify which fields
are native records and which are derived statements. Offline verification checks
closed schema, inventory bounds, complete objects, byte counts/digests and referenced
receipt structure; absent signatures it does not prove authorship. Timestamps do not
prove trusted order. Tampering/truncation/missing object/unknown schema must fail
integrity verification. Re-rendered Markdown may differ without altering authoritative
bytes; Markdown must never be accepted instead of a receipt. Historical success does
not establish current source/target applicability. M1 has no exporter or verifier.

## Planned wire examples and failure rules

These are historical design examples, not schemas accepted by M1 or exact M5 input.
For the implemented M5 fields (including binding receipt and declared verifier status),
use [the current proposal contract](proposals.md) and its sample. All digest/identity placeholders
must be replaced by exact native references before M4–M6 can accept them. New identity
formats and persisted events require the later design gate; a string cannot authenticate
a principal.

```json
{
  "schema": "golem.workpack.verifier-proposal.v0",
  "proposal_id": "review-01",
  "work": {"identity": "<native Work identity>", "generation": 1},
  "pack_digest": "<exact manifest SHA-256>",
  "artifacts": [{"digest": "<source SHA-256>", "size": 123}],
  "verifier": {"principal_ref": "<owner-reviewed role mapping>", "model_declared": "external", "provider_declared": "external"},
  "contract_digest": "<review contract SHA-256>",
  "findings": [{"id": "finding-01", "severity": "BLOCKING", "summary": "PII finding needs owner review", "evidence_refs": ["<evidence SHA-256>"]}],
  "confidence": "UNCERTAIN",
  "limitations": ["Sampled PII results are not exhaustive"],
  "recommendation": "NEEDS_OWNER_REVIEW",
  "unresolved_questions": ["Is the detected data permitted for this release?"]
}
```

Proposed enums: severity `INFO|WARNING|BLOCKING`, confidence `UNCERTAIN|LIMITED|SUPPORTED`,
recommendation `NEEDS_OWNER_REVIEW|REJECT_PROPOSAL|NO_BLOCKING_FINDING_OBSERVED`.
None maps to QA PASS. At most 32 limitations/questions and 32 evidence refs per finding;
all refs must resolve inside the inspected snapshot's allowed evidence set. Duplicate
finding IDs, unresolved/foreign refs and generation changes fail validation. Proposals
from failed or unavailable verifiers are retained as failed observations, not fabricated
successful empty findings. No raw chain-of-thought field is permitted.

```json
{
  "schema": "golem.workpack.receipt-manifest.v0",
  "work": {"identity": "<native Work identity>", "generation": 1},
  "pack": {"id": "io.styxis.golem.dataset-release-gate", "version": "0.1.0", "digest": "<exact SHA-256>"},
  "source_snapshot": "<source SHA-256>",
  "role_submissions": [],
  "tool_inventory": [],
  "evidence_inventory": [{"digest": "<object SHA-256>", "size": 123, "media_type": "application/json"}],
  "owner_decisions": [],
  "native_completion_receipt": null,
  "unresolved_blockers": ["NATIVE_COMPLETION_NOT_OBSERVED"],
  "declared_timestamps": [],
  "missing_objects": [],
  "signature": null,
  "current_applicability": "NOT_EVALUATED"
}
```

This example deliberately represents incomplete evidence. Empty decisions and null
completion never become success. JSON export is byte-bounded and preserves these
unknowns; Markdown/HTML render them without changing authority. The implemented M6 allowlists and cross-object checks are documented in
[receipts.md](receipts.md); this broad example is not accepted input.
