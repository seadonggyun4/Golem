# Experimental manifest v0

Gate A contract; implementation status is tracked in [development plan](development-plan.md).
Use JSON only. YAML examples in discussion are explanatory, never accepted input.
The schema identifier is `golem.workpack.v0`; it is independent of pack version and
Golem library version. No compatibility with a future v1 is implied.

## Closed manifest

All listed fields are required, additional properties are rejected at every object.
M1 deliberately has a single object with string/string-array fields; later structured
role/binding/proposal formats require separately versioned schemas.

| Field | Type / bound / semantics |
| --- | --- |
| schema | exact `golem.workpack.v0` |
| id | ASCII lowercase dotted identifier, 1–128 bytes, segment starts letter; subsequent lowercase/digit/hyphen; no empty segments |
| version | three decimal components 0–65535, no leading zeroes, no prerelease/build tags |
| status | exact `experimental` |
| core_min, core_max | same version grammar; inclusive interval, min ≤ max; compatibility is declaration, not verified runtime availability |
| publisher | ASCII identifier, ≤128 bytes, self-declaration, not signature |
| provenance | lowercase 64-character SHA-256 declaration, not authenticated origin |
| intent, negative_intent | 1–16 unique strings each, UTF-8, 1–256 bytes each |
| roles | 1–16 unique ASCII identifiers |
| capabilities | 1–32 unique ASCII identifiers; symbolic requirements, not executable tool names/grants |
| prohibited_effects | 1–32 unique ASCII identifiers; no automatic enforcement claim |
| inputs, evidence | 1–32 unique ASCII identifiers each |
| completion | exact `READY_FOR_RELEASE`; declaration only |
| freshness | exact `EXACT_SOURCE_AND_CURRENT_EVIDENCE` |
| recovery | exact `STOP_ON_UNKNOWN` |

Total input 65536 bytes maximum, parser nesting limit 16 (schema permits only root and
arrays), no duplicate decoded keys, embedded NUL, trailing values, NaN, malformed UTF-8,
control characters (U+0000–001F and U+007F) or empty/space-only display strings.
Identifiers reject Unicode entirely, preventing confusable authority names. Display
metadata preserves UTF-8 exact bytes, never normalizes identities and is untrusted.
Canonical-equivalent Unicode display strings may differ: Unicode normalization and
cross-language matching are NOT implemented. Initial arrays reject exact duplicates.
Unknown extension/command/path/provider fields fail, not silently execute.

## Identity and serialization

M1 identity digest = SHA-256 of the exact successfully validated input bytes, using
`golem_digest_bytes`. Whitespace, object member order, escapes and newline differences
produce different digests. This is intentionally NOT JCS, a semantic digest, publisher
identity or signature. The sample's compact sorted-key UTF-8 JSON plus one newline is
the repository fixture convention, not a mandatory canonical encoding. Tests must
show both stable identical-byte digests and distinct reformatted-byte digests.
A future canonical serializer must use a new explicit identity algorithm/version;
it cannot silently replace existing exact-byte references.

A bound Work must eventually pin `(schema, id, version, exact_digest, core_contract)`;
M1 only validates bytes and returns digest, does not bind. No `latest`, version ranges
or unpinned aliases are authority references. Catalog duplicate `(id,version)` with
different digests is an ambiguity error; equal digest is a duplicate discovery entry,
not additional authority. Deprecated packs stay available for historical replay;
new enrollment may be denied by owner policy. Old bytes are never overwritten.

M1 accepts caller-owned memory, no filesystem path and no auxiliary objects. Thus it
cannot follow symlinks/traverse paths/download schemas. M2 file loading must walk a
fixed owner-selected root with no-follow checks on every component, reject symlink,
non-regular file, parent traversal and growth beyond 65536, and verify read identity
before returning. No such filesystem security claim is made for M1 callers.

## Public M1 API and report

Planned additive `golem_workpack_validate(golem_bytes, golem_digest*, golem_diagnostic*)`:
borrowed bounded input, required digest output unchanged on any failure, optional
caller-owned diagnostic containing only static error codes, no input text. No Work
handle, lock, file access, network, scripts, dynamic imports, callbacks or grants.
Reuse common strict parser and existing SHA-256. Return existing `golem_status` codes:
INVALID_ARGUMENT (missing output), PARSE (JSON/shape/field/bound violation),
UNSUPPORTED_VERSION (recognized schema key with other string), OUT_OF_MEMORY, CRYPTO.
Successful result is structural validation only. Detailed static diagnostic tags:
`PACK_JSON`, `PACK_SCHEMA`, `PACK_FIELDS`, `PACK_ID`, `PACK_VERSION`, `PACK_TEXT`,
`PACK_LIST`, `PACK_DECLARATION`. No semantic authorization report is emitted in M1.

Future report JSON (NOT implemented):
`{schema:"golem.workpack.validation.v1", structurally_valid:true,
exact_digest:"…", authorized:false, bound:false, work_done:false, blockers:[]}`.
No unknown property becomes authorized because the structural validator succeeded.
