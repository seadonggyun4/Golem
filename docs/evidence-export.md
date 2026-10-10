# Scoped Standalone Evidence Export

`tools/evidence_export.py` implements a separate, opt-in private raw-evidence
format, `golem.evidence-export.v1`. It does not change the structurally redacted
native [CaseStudyBundle](bundle.md), Work permissions, QA or completion authority.
It exports only a caller-selected graph, not a repository, all CAS objects, or a
restorable Work. No network access, remote fetching, execution or restore occurs.

## Boundary and Approval

Supply an explicit catalog of **already authorized, staged** files. Native Work
export permissions must be resolved by the existing native workflow before staging;
this tool does not open a Work or interpret DENY/ASK_ALWAYS. A catalog is not a
substitute for that authorization. It is a private operator declaration, not an
authenticated policy grant. Do not point it at a live Work to bypass that workflow.

Every included object requires `review=PRIVATE_EXPORT_APPROVED`. This confirms an
operator's decision to include those raw bytes, not that a secret scanner or human
reviewer has actually examined them. There is no automatic anonymization or secret
detection. Tokens, personal information, filenames, source paths and signed URLs
may remain inside included bytes. Hashes and graph structure are linkable metadata.
Do not publish a raw export without a separate privacy/release review.

Excluded nodes record only the digest and a controlled reason: SECRET, PRIVACY,
OUT_OF_SCOPE or OPERATOR_EXCLUDED. Their bytes are never opened or copied. The
subgraph behind an unavailable/excluded node is unknown, not silently complete.
Removing a secret child does not remove secret text embedded in an included parent;
exclude that parent too, or create a separately identified reviewed derivative.

## Catalog and Adapters

Catalog keys are exactly `schema=golem.evidence-export-catalog.v1`, `roots` (unique
SHA-256 strings), and `objects` (digest-keyed descriptors). INCLUDE descriptors have
exactly `disposition`, `adapter`, `path`, `review`. Paths are canonical, relative to
the catalog's staging directory. EXCLUDE descriptors have only `disposition` and
`reason`. Unreachable catalog entries are not copied. No filesystem discovery,
prose hash search, URL dereferencing or inferred reference schema is performed.

| Adapter | Reference contract |
| --- | --- |
| links.v1 | Exact JSON `{schema: "golem.evidence-links.v1", references: [...]}`; each reference is `{sha256: DIGEST}` or `{external: LOCATOR}` |
| verification.v1 | Validates the common evidence-verification envelope, expands its subject and all check evidence_refs |
| research-digests.v1 | Explicit schema_version=1 JSON; recursively expands digest, qa_receipt, supersedes and *_digest fields, matching native research bundle field conventions |
| observation-manifest.v1 | Exact agent-observation manifest schema/files; expands each listed file digest |
| opaque.v1 | Explicit terminal byte artifact; no implicit expansion of hashes/paths in content |

Adapters extract typed dependencies, not semantic truth. The research adapter is
not a replacement for native model/acceptance validation. It does not interpret
arbitrary embedded URLs or unknown schema-specific references. `opaque.v1` is a
deliberate leaf declaration, **not** proof that a document contains no dependencies.
Unknown adapters fail closed. Add a versioned adapter and tests for additional
formats; never silently fall back to opaque when a recognized parser fails.

For an existing `agent_io` observation, the bridge validates its bundle and record
pin, then creates a private catalog alongside it, without rewriting the observation:

```sh
python3 tools/evidence_export.py catalog-observation /private/tmp/stage/observation \
  /private/tmp/stage/catalog.json --expect-record RECORD_SHA256 --approve-private-raw
python3 tools/evidence_export.py export /private/tmp/stage/catalog.json \
  /private/tmp/evidence-export --expect-catalog CATALOG_SHA256
python3 tools/evidence_export.py verify /private/tmp/evidence-export \
  --expect-manifest MANIFEST_SHA256
```

Use the returned catalog/manifest digests as exact pins, retained through a trusted
channel. The bridge includes the observation's manifest and all inventoried files,
deduplicated by digest. Payloads are opaque leaves: original observation names and
bytes remain available through its included manifest, but unrelated runtime/CAS
references embedded in a log are not implicitly discovered. Review the catalog
and explicitly exclude sensitive digests before export; its hash then changes.
The bridge requires a sibling catalog, never writes inside the original bundle,
and does not overwrite an existing catalog.

## Graph, Publication and Verification

The exporter traverses the selected roots breadth-first with digest deduplication.
Every included payload must match its declared SHA-256. Missing staged files are
MISSING, unknown digests are UNRESOLVED, approved exclusions are EXCLUDED. A typed
external locator is represented by its hash in metadata and is never fetched;
the original locator remains only in the explicitly approved raw parent. Corruption,
invalid schema and permission errors abort; they are not relabeled as missing.

The bundle has exactly `manifest.json` and `data/`, with immutable payload bytes
named by SHA-256. Metadata contains no staging paths. Directories/files are created
0700/0600, without overwrite. Payloads are fsynced before publishing the final
fsynced manifest. Interruptions before manifest publication leave a private,
incomplete directory for inspection. Failure during final fsync may leave complete
bytes without confirmed durability; rerun verification rather than infer success
from file existence. Output must be outside staging. File reads use descriptor-
relative O_NOFOLLOW traversal, reject parent escapes, symlinks and special files.
This is a controlled private POSIX workflow, not protection against a hostile same-
user process concurrently replacing output directories. No power-loss durability
guarantee beyond the filesystem's fsync contract is claimed.

The standalone verifier needs only the bundle and this versioned tool/runtime,
not the original project/catalog. It verifies payload hashes, exact file inventory,
strict metadata, selected-root reachability, limits and completeness. Crucially it
**re-extracts every included node's typed references** and compares them with the
manifest, so dropping a reference and recomputing the manifest hash is insufficient.
Extra payloads/directories, unreported edges and unreachable nodes are rejected.

Integrity and completeness are separate:

- `integrity=MATCH` means the retained bytes/graph match this manifest. An unsigned
  manifest does not prove producer identity or the historical truth of missing/
  exclusion declarations. An independent trusted manifest pin detects replacement.
- `completeness=COMPLETE_DECLARED_SCOPE` means every reachable **declared typed**
  reference was included. It never means all possible evidence/Work dependencies,
  software environments, causal explanations or external latest versions are known.
- `completeness=INCOMPLETE` preserves missing, unresolved, excluded and external
  references. Such a bundle remains independently inspectable, but is not a closed
  raw-evidence set. No subtree below an unavailable node is claimed to be explored.
- `content_truth=NOT_ESTABLISHED`, `authenticity=NOT_VERIFIED`,
  `remote_latest_verified=false`, `acceptance_authorized=false` always remain.

CLI exit 0: operation succeeded and declared scope is complete (or catalog created).
Exit 2: valid, explicitly incomplete bundle. Exit 1: invalid/unsafe/failed operation.
Errors preserve controlled diagnostic codes/type/errno without printing raw paths,
locators or content. API errors are available to a trusted local caller.

Bounds are fail-closed: 1,024 nodes/catalog entries, 8,192 edges, graph/JSON depth
64, 8 MiB per payload, 64 MiB total retained payload, 2 MiB catalog/manifest.
The implementation buffers a bounded graph, not an unbounded whole-store scan.
Adapter selection and graph traversal are separate from filesystem publication.

## Research Basis

Reviewed on 2026-10-10; these are design applications, not claims of conformance:

- Kunze et al., [RFC 8493](https://www.rfc-editor.org/rfc/rfc8493), sections 3 and 5:
  distinguish payload availability from checksum validation; test path escapes.
  This format is **not BagIt** and makes no BagIt-valid claim for incomplete graphs.
- Quinlan and Dorward, [Venti: a new approach to archival storage](https://www.usenix.org/legacy/events/fast02/quinlan/quinlan.pdf),
  FAST 2002, abstract/introduction: content-addressed immutable blocks permit
  deduplication. Here SHA-256 identifies bytes; no network archive is implemented.
- Soiland-Reyes et al., [Packaging research artefacts with RO-Crate](https://www.researchobject.org/2021-packaging-research-artefacts-with-ro-crate/manuscript.html),
  Data Science (2022), sections 2 and 2.3: represent contained and externally linked
  artifacts separately with explicit relations. This format is not JSON-LD/RO-Crate.
- Digital Preservation Coalition, *Digital Preservation Handbook*, second edition,
  [Fixity and checksums](https://www.dpconline.org/handbook/technical-solutions-and-tools/fixity-and-checksums):
  establish and recheck retained-byte fixity. No automated repair/archive service.
- Venkataramanan and Shriram, *Data Privacy: Principles and Practice*, CRC Press
  (2017), [publisher preview](https://api.pageplace.de/preview/DT0400.9781498721059_A28393879/preview-9781498721059_A28393879.pdf),
  introduction pp. 1-3 and front matter only: useful shared data can contain sensitive
  information. This motivates explicit private review and exclusions, not a claim
  that hashing or omission anonymizes a graph. The full book was not consulted.

Tests include a real recorded subprocess exported and verified after deletion of
its observation and Git source, transitive research/common-contract references,
deduplication, missing/excluded/external edges, cycle-safe traversal, tampering,
inventory/path attacks, bounded failure and interrupted publication. They do not
establish actual secret detection, authenticated authorship, remote freshness,
native Work restoration or universal semantic closure.
