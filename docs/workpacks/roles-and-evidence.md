# Roles, verifier proposals and Evidence Package design

All binding/proposal/receipt aggregation in this document is PLANNED, not M1 API.
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

## Semantic verifier proposal v0 (future separate schema)

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
64 KiB. These limits require review before M6 implementation.

CAS / manifest / native receipt = authority under their original local trust contracts.
Markdown and future HTML = derived projection. JSON export must identify which fields
are native records and which are derived statements. Offline verification checks
closed schema, inventory bounds, complete objects, byte counts/digests and referenced
receipt structure; absent signatures it does not prove authorship. Timestamps do not
prove trusted order. Tampering/truncation/missing object/unknown schema must fail
integrity verification. Re-rendered Markdown may differ without altering authoritative
bytes; Markdown must never be accepted instead of a receipt. Historical success does
not establish current source/target applicability. M1 has no exporter or verifier.
