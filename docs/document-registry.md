# Work and Markdown Registry, Version 1

The base contract below remains valid. [Phase 22](discovery.md) adds metadata
schema 2 for discovery/research/scope assessments; it does not change stored
schema-1 documents or the event frame format.

This is a trusted-local artifact registry, not an agent launcher or semantic
reviewer. Existing agents write Markdown and submit it through the CLI or
`golem/document.h`. Only needed document kinds are registered. No fixed set of
stages is automatically declared complete. All output explicitly reports
`acceptance_verified: false`.

## Commands

```
golem work start NEW_WORK_DIRECTORY SPEC.json
golem document validate METADATA.json BODY.md
golem document submit WORK_DIRECTORY METADATA.json BODY.md IDEMPOTENCY_KEY
golem document inspect WORK_DIRECTORY DOCUMENT_ID REVISION
golem document project WORK_DIRECTORY DOCUMENT_ID REVISION
```

`start` requires a new directory; its parent must exist. The C create API instead
requires an existing empty private directory. Paths must not contain symlink
components or `..`. The user chooses the Work location; no global document path
is imposed. Keep it outside public source, or explicitly Git-ignore it.

Exit codes: 0 successful operation, 1 rejected/failed operation, 2 invalid CLI
usage. A successful submission can have `projection_ready: false`: the immutable
commit succeeded but materializing the convenience Markdown file failed.
Inspect `projection_status`; fix the obstruction and run `document project`.
Do not create another revision just to repair a projection.

`inspect` returns registered metadata, body/manifest/event digests, generation,
revision and projection status. The metadata's producer is a supplied local
attribution, not a cryptographically authenticated agent identity.

## Work Specification

See `samples/documents/work.json`. All keys are required; unknown keys fail:

| Field | Contract |
| --- | --- |
| schema_version, policy_version | Integer 1 |
| work_id | 1-64 ASCII letters, digits, underscores or hyphens |
| request, scope, non_goals | Nontrivial strings |
| permission | AUTO_LOCAL, ASK_ON_EXTERNAL_EFFECT, ASK_ALWAYS or DENY |
| max_revisions | 1-4096, total document registrations in this Work |
| acceptance | 1-256 objects with unique `id` and textual `criterion` |

The specification is immutable. Scope revision is fixed at 1 in this version.
`max_revisions` is a storage/work registration budget, not a token or cost budget.
Existing runtime cost accounting is separate; this registry does not enforce
monetary budgets. Local registration is allowed for AUTO_LOCAL and
ASK_ON_EXTERNAL_EFFECT; ASK_ALWAYS fails pending approval support; DENY blocks.

## Document Metadata

See `samples/documents/planning.json`. Exact JSON bytes are retained, not
reserialized as the original. Duplicate keys (including escaped equivalents),
unknown fields, embedded NULs, invalid UTF-8 and unsupported versions fail closed.

| Field | Contract |
| --- | --- |
| schema_version, template_version, policy_version | Integer 1 |
| work_id | Must match the Work |
| document_id, producer_attempt | ASCII identifiers, 1-64 characters |
| revision | Starts at 1; subsequent revisions are contiguous |
| kind, stage | Pair from the table below |
| parents | Up to 64 unique document references: document_id, revision, digest |
| requirement_ids | Unique IDs from the Work acceptance list |
| scope_revision | Integer 1 |
| source_snapshot | 64 lowercase hexadecimal characters; caller attribution |
| supersedes | Empty for revision 1, otherwise preceding manifest digest |
| expected_generation | Work generation observed before submitting |

The sample's all-zero source snapshot is synthetic. Real integrations must
compute and verify an appropriate source snapshot; the registry checks its
format only. Registration computes `body_digest` itself rather than trusting
a caller-supplied digest. Parent digests identify registered manifests, not body
digests. Work creation is generation 1; every new document commit increments it.

## Markdown Template

MD4C parses Markdown into block/inline events. Version 1 requires one top-level
H1 and each exact, case-sensitive top-level H2 below, once:

`Purpose`, `Scope`, `Parents`, `Evidence`, `Decisions`, `Requirements`, `Work`,
`Validation`, `Risks`, plus the kind-specific section:

| Kind | Stage | Additional H2 |
| --- | --- | --- |
| planning | planning | Acceptance |
| ux | ux | Flows |
| publishing | publishing | Interface |
| development-plan | development | Changes |
| development-result | development | Results |
| qa-plan | qa | Cases |
| qa-result | qa | Results |
| completion | audit | Outcome |
| research | planning | Sources |
| failure | qa | Failure |

Bodies may use Korean or other valid UTF-8; headings are fixed English template
identifiers. Version 1 rejects raw HTML, nested/deeper headings, empty sections
and placeholder-only sections. Code blocks alone do not satisfy explanatory
prose requirements. The minimum prose heuristic is structural, not evidence of
correctness or writing quality. Mention every requirement ID as a token under
Requirements. Explain the absence of parents instead of leaving that section
empty. For each declared parent include exactly one matching link under Parents:

```markdown
[Planning](golem-doc:planning:1:REPLACE_WITH_MANIFEST_SHA256)
```

Only latest registered direct parent revisions are accepted at submission.
Self-references, duplicate parents and mismatched/missing links fail. Later
parent changes do not rewrite historical children. Transitive invalidation,
selected CURRENT revisions and development authorization belong to later
workflow gates, not this registry.

## Revision and Transaction Rules

To revise a document, keep its ID and kind, increment revision, set supersedes
to the previous manifest digest, update expected_generation, and use a new
idempotency key. Refresh parent metadata and Markdown links together. Never edit
an already registered file to represent a revision.

A lifetime filesystem lock serializes writable handles. Validation, permission,
generation, revision, parent and budget checks precede committing. Body and raw
metadata enter CAS first, then the commit manifest, then an immutable frame.
Publishing the frame uses a same-directory temporary file, fsync and no-replace
link, followed by directory fsync. Projection happens after this commit point.

Retry with the same key and identical metadata/body bytes to obtain the original
receipt, even after later commits. Equivalent but differently formatted JSON is
not an identical request. Reusing a key with changed bytes fails. An uncertain
I/O commit poisons the writable handle: close and reopen/replay before retrying.
Crash-created unreferenced CAS objects are harmless; no automatic garbage
collection is implemented. Incomplete initialization is not silently adopted.

## Storage and Replay

```
WORK_DIRECTORY/
  objects/sha256/...             # existing evidence CAS layout
  events/00000001.evt            # Work creation
  events/00000002.evt            # document commit
  documents/planning/r0001.md    # byte-exact Markdown projection
```

Frames are 80 bytes: magic `GWDOC001` (8), little-endian sequence (8), previous
frame SHA-256 (32), payload CAS SHA-256 (32). Payload schema version is 1.
Document payloads bind raw metadata, body and idempotency key. This is a separate
versioned document stream, not an incompatible change to the existing execution
journal; `document inspect` opens/replays it. `golem replay` remains the execution
bundle command. No automatic legacy-data migration is performed.

Opening verifies the full committed chain, CAS bytes, schemas, Markdown and
historical transition preconditions. Gaps, malformed frames and corrupt bytes
fail; unpublished `.pending-*` files are ignored. Missing projections can be
recreated. Differing files or symlinks are never overwritten, including on repair.

This detects internal corruption, not every deletion: removing an entire valid
tail cannot be distinguished from an older registry without an external durable
checkpoint. Hashes are not signatures. A hostile same-user writer can rewrite
the whole store; private root permissions and backups remain required. Network
filesystems with weaker locking/durability semantics are outside the guarantee.

## C Ownership and Limits

Public declarations document ownership in `include/golem/document.h`. Inputs are
borrowed for the call; stores own copied state until close. Caller allocators
cover store/entry allocations, not dependencies' internal allocations. Serialize
calls on a handle. Read-only handles cannot submit/project.

Body and metadata read APIs return exact bytes with no trailing NUL. NULL/0 queries
size; short buffers remain unchanged. Output results stay unchanged on errors
except explicitly documented diagnostics/required-size outputs. The caller must
keep the allocator context alive until close.

Bounds: Markdown 1 MiB, JSON 256 KiB, 4096 revisions, 64 parents per document,
16384 parent edges per Work. Parser nesting is bounded. Admission bounds keep
full replay and in-memory indexes finite; this is not an unbounded database.

## Design Basis and Boundaries

Structured role artifacts and explicit handoffs draw on
[MetaGPT](https://arxiv.org/html/2308.00352v7); immutable entities and producer
activity attribution follow the distinction in
[W3C PROV-DM](https://www.w3.org/TR/prov-dm/). Parsing uses
[MD4C](https://github.com/mity/md4c), with versioned Golem restrictions rather than
claiming every CommonMark document is a valid Golem artifact.

Executable acceptance must remain separate from document formatting, consistent
with [Specification by Example](https://www.manning.com/books/specification-by-example).
These are design influences, not claims of formal conformance or reproduced
research results. Agent session authentication, verified leases, transitive
freshness, actual QA gates, automated reentry and completion certification are
not provided by this Phase 21 contract.
