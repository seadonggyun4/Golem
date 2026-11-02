# M6 export contract decision — owner selected

Owner selected proposal SHA-256 `24cfd1e66949a7daa937af843ec7bf468e83ad5e3748793057b18aa9691c817f`.
Implementation and isolated fixtures are authorized. No production export, approval issuance, policy change
or client update is authorized by this document. Existing M4 binding and M5 identity
limitations remain. No Work journal event or migration is added.

## Selected scope

Native APIs and thin local CLI provide receipt manifest, explicit private export,
and offline verification. Existing native-documents-v1 Works only. No general QA,
external-tool, session-owner or independent-identity mapping is invented.

The request chooses exact current document references within the bound native role
closure, never arbitrary filesystem paths, arbitrary CAS digests or recursive scans.
The export includes the bound Pack, binding reference, enrolled native role contract,
selected document metadata/body pairs and separately labelled native observations.
Historical role/completion references, when available and supported by the existing
native parser, remain historical; absent/unsupported facts remain null/NOT_EVALUATED.
No log/credential/provider material is automatically followed or included. M5 model
proposals are not automatically imported. A future adapter needs a new reviewed type.

Allowlisted types: Work Pack manifest v0; native Work specification accepted by the
existing native validator; native-document metadata/body pairs accepted by the
existing document validator; enrolled role contract accepted by the native role
validator; the already replay-verified binding event as a historical source record;
separately labelled native read observations. Opaque records cannot be used to claim
independently verified reducer history. Unknown media/type/schema combinations fail.
Exact type and object references are closed in the implemented manifest schema.

## Limits and trust

- Manifest <=64 KiB, at most 256 inventoried objects, total payload <=16 MiB.
- Reuse stricter native per-object limits (Pack 64 KiB, native document body 1 MiB,
  native structured records 256 KiB). No hidden relaxation of native limits.
- Inventory includes exact SHA-256, byte size, fixed media/type and typed references.
- Exact Work/binding/Pack/role/source references are cross-checked. No substring hash
  discovery, network fetch, automatic repair or fallback from recognized to opaque.
- Manifest JSON is the integrity root; Markdown is a derived projection and is never
  accepted as a native receipt or approval. No untrusted prose is rendered as command.
- Verification checks complete object inventory, bytes, supported structural schemas
  and cross-object references. It does not prove truthful evidence, author identity,
  independent review, current Work freshness, QA PASS, completion or release authority.
- An independently retained expected manifest digest is required for anchored verify.
  Even a fully recomputed package with its new digest is still unsigned/untrusted as
  to origin. Hash equality is not source authentication.

## Explicit disclosure/publication gate

Manifest inspection is read-only under the existing native Work lock and policy.
Private export requires a separate exact `--approve-export` digest over the native
export plan, current source identity/head, selected inventory, format and canonical
absolute output parent. Existing execution/binding approvals and M2 drafts cannot
substitute. This is trusted local-caller attestation, not authenticated human identity.
It grants neither network/public release nor permission to export a different Work.

Use existing native no-follow path/directory handling, bounded CAS reads, immutable
no-replace publication and fsync primitives. Output is a new content-addressed child
of an already existing private parent, outside the source Work. Never alter parent
permissions, replace conflicting bytes or use source Work/CAS as output. The manifest
and commit marker follow payload publication. A missing object never becomes a
successful complete export; partial directories and uncertain publication are retained.
No automatic cleanup, replay, redispatch, reconciliation or rollback. Re-query/read-only
verification is separate from repeating export. No original Work files are written.

## Verification and preservation

Only isolated synthetic Works and private temporary export directories are used in
this task. Tests cover malformed/oversized/unknown schema, truncated/missing/corrupt
objects, incorrect size/digest/type/ref, source/selection drift, forged/unsigned
origin, Markdown substitution, path/link/output-source overlap, unchanged Work,
publication interruption and output invariance. Reuse native parsers/reducers/locks;
no Python implementation of runtime decisions or publication.

Codex/Claude plugins, TopSolar policies, native approvals, Work/evidence and
COMMIT_UNKNOWN are preserved. No real client/Work export, external call or new
production approval is performed. Source changes, fixtures and docs are committed
and pushed to the existing workpack-contract-m1 branch only after validation.
