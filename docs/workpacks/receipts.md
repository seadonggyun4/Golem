# M6: private evidence packages

`receipt manifest`, `receipt export` and `receipt verify` are native C APIs and thin
local CLI commands. They support the existing **native-documents-v1** binding only.
They do not add MCP routes, client permissions, a new Work event or migration.
The [owner-selected design](m6-export-design.md) is implementation authorization,
not permission to export an existing project.

```text
current bound Work + exact document references
  → manifest: native validation, document closure, exact inventory + approval digest
  → owner reviews inventory, disclosure and private destination
  → export: recheck source and exact digest → new immutable package
  → verify: independently retained manifest digest + package → integrity observation
```

## Request and commands

A request is a strict JSON object, at most 64 KiB. Replace these placeholders with
current native references; a prepared request is not approval:

```json
{
  "schema": "golem.workpack.receipt-request.v0",
  "expected_generation": 9,
  "binding_receipt": "<64 lowercase hex characters>",
  "documents": [
    {"document_id": "selection", "revision": 1, "digest": "<native document event SHA-256>"}
  ]
}
```

Select 1–64 distinct exact current references in the bound role's native document
closure. The native generation is the current document count plus one, as in M4;
the manifest separately pins the current Work chain head. The bound selection and
native parents of all selected documents are included. Unknown/stale/unbound
references fail. Review the expanded inventory before authorizing disclosure.

```sh
golem receipt manifest /private/work /private/request.json /private/exports --format json
# Review the returned inventory and approval_digest; do not approve by script default.
golem receipt export /private/work /private/request.json /private/exports --format json --approve-export EXACT_REVIEWED_DIGEST
golem receipt verify /private/exports/MANIFEST_SHA256 --expect-manifest INDEPENDENTLY_RETAINED_MANIFEST_SHA256
```

`--format markdown` adds `summary.md`; JSON remains the integrity root. The CLI uses
0 for success, 1 for native/read/write/output failure, 2 for usage errors. It emits
full JSON, with no automatic output-cache publication. Existing explicitly configured
command/API recording may still append its own audit. The APIs are
`golem_workpack_receipt_manifest`, `golem_workpack_receipt_export` and
`golem_workpack_receipt_verify`; all preserve caller output on failure. A failed CLI
stdout write after publication is an uncertain response, not permission to repeat export.

## Included objects and bounds

| Item | Treatment |
| --- | --- |
| Work specification, exact Pack, bound native role contract | Existing native validators and exact hashes |
| Historical binding event | Existing binding request parser; exact header/scope/reference checks, not authenticated approval offline |
| Selected documents | Native event, original metadata and body; validate each pair and exact parent references |
| Role/completion history | Nullable digests in a labelled `HISTORICAL_REFERENCES_ONLY_NOT_EXPORTED` observation; referenced records/dependencies are not copied or evaluated |
| Markdown | Fixed renderer version 1; counts and Pack digest only; exact derived bytes checked |

The closed `golem.workpack.receipt-manifest.v0` has `schema`, `renderer_version`,
`format`, `work` (identity/generation/head), `pack` (id/version/digest),
`binding_receipt`, `refs` (work_spec/role_contract/observation), `documents`,
`inventory`, `scope`, `current_applicability`, `limitations`, `missing_objects`,
`signature`, and `projection`. Each inventory row has digest/size/type/media_type.
Each document has document_id/revision/event/metadata/body. Types are closed to
work-spec, pack, binding, role-contract, history-observation, document-event,
document-metadata, document-body. The body media type is text/markdown; all others
are application/json. Unknown fields/types/schemas/versions are rejected.

Manifest ≤64 KiB, at most 256 unique objects and 83 expanded documents, total object
payload ≤16 MiB. Native limits remain: Pack ≤64 KiB, structured objects ≤256 KiB,
document body ≤1 MiB. Summary ≤768 bytes; commit marker ≤1 KiB; directory entries
≤1024. Shared identical same-type objects are deduplicated. A digest reused for a
different type fails. Limits fail closed; no truncation or partial success.
`missing_objects:[]` means the selected inventory is complete, **not all Work evidence**.

Raw selected metadata/bodies can contain sensitive or untrusted material. No secret
sanitizer, external fetch, log scan, credential read or arbitrary CAS/path export is
provided. Native source references inside metadata remain data; they are not followed.
M5 agent proposals, external tool results and general QA/session evidence are not
implicitly included. Supporting another type requires its own reviewed contract.

## Approval, storage and failures

The separate export digest hashes `golem.workpack.private-export-approval.v0`, the
exact manifest digest and canonical output parent path/device/inode. The manifest
pins source identity/head/generation, binding, exact inventory and chosen format.
M4 binding/ execution approvals cannot substitute. This is trusted local-caller
attestation, not authentication of a human or permission for public/network release.

The parent must already exist, be owned by the effective user with no group/other
permissions, and be neither the Work nor its ancestor/descendant. Canonical absolute
paths and no-follow native directory checks are required. Parent identity replacement,
source drift or changed format invalidates the digest. Work is opened read-only under
its existing lock; export creates no Work/CAS/journal/approval record.

Export takes nonblocking locks and exclusively creates a 0700 child named by the
manifest digest. It reuses native immutable no-replace publication and fsync: payloads,
optional summary, manifest.json, then COMMIT.json. Files are 0400. An existing child
is always rejected, even if complete. Partial directories and uncertain results remain;
there is no retry, rollback, resume, repair or cleanup. Read-only verify may inspect a
retained package without repeating publication. An error after COMMIT can coexist
with a verifiable package and must not be presented as a confirmed export response.

Verify uses bounded no-follow regular single-link reads, recomputed hashes, native
schemas and cross-object references. Extra files fail; only exact native
`.pending-<24 lowercase hex>` names are ignored and never read or interpreted as
committed evidence. Missing marker/object, links, truncation, unknown schema/type,
wrong references, oversized objects and tampered projection fail. Advisory locks and
hashes do not defend against a hostile same-OS-user process with arbitrary write access.

## What verification means

Success reports `integrity:VERIFIED`, `origin:UNAUTHENTICATED`,
`current_applicability:NOT_EVALUATED`, `semantic_truth_verified:false`,
`completion_verified:false`, `authorized:false`. `signature` must be null. Supply an
independently retained expected manifest hash; a package and its attacker-replaced
hash can be internally consistent without being authentic. The partial historical
binding header is not a replay of the whole native event chain. Source/target
freshness, truthful evidence, independent review, QA PASS and current DONE require
their original live native contracts. No import/restore/execute path is provided.

Regression fixtures cover approval/format/parent drift, unchanged Work, native locks,
missing/truncated/linked/extra files, schema/type/reference/size/count bounds,
unsigned recomputed packages, projection tampering, and failures before payload and
after commit publication. See the [execution record](development-plan.md) for run
results and explicit NOT_RUN scopes.
