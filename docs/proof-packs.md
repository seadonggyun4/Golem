# Verification proof packs

Proof packs are deterministic, private, derived exports of issued QA receipts.
They do not execute commands, approve completion, establish current workspace
freshness, authenticate an author, or authorize public release.

## Render and check

Create a request with 1 through 8 distinct QA receipt SHA-256 values from one Work:

```json
{
  "schema_version": 1,
  "renderer_version": 1,
  "qa_receipts": ["REPLACE_WITH_ISSUED_QA_RECEIPT_SHA256"],
  "redaction": {
    "schema_version": 1,
    "profile": "MINIMAL",
    "acknowledge_linkability": false
  }
}
```

```sh
golem proof render /absolute/WORK request.json > pack.json
golem proof verify /absolute/WORK request.json pack.json
golem proof integrity pack.json
mkdir -m 700 /absolute/private-exports
golem proof publish pack.json /absolute/private-exports
golem proof verify-dir /absolute/private-exports MANIFEST_SHA256
golem proof integrity pack.json MANIFEST_SHA256
```

`publish` returns the manifest digest. The parent directory must already exist,
be canonical absolute, and have no symlink components. Use a privately controlled
location, outside tracked/public assets. Existing permissions are not changed.
Keep the returned manifest digest independently if replacement detection matters.
The JSON envelope limit is 262144 bytes. The directory scanner is bounded to 1024
entries, including abandoned temporary files; exceeding it fails closed.

## Files and contracts

The pack JSON contains exactly `schema_version` and `files`. Files are UTF-8 strings:

| File | Purpose |
| --- | --- |
| `summary.md` | Per-run outcome; not Work completion |
| `proof.md` | Sanitized facts and evidence-domain caveats |
| `comparison.md` | Descriptive outcomes only; no ranking or eligibility claim |
| `evidence-inventory.json` | Derived facts and optional original CAS references |
| `manifest.json` | Renderer, policy, fixed flags, exact payload names/sizes/digests |
| `COMMIT.json` | Digest of the complete manifest |

Receipt keys are sorted by SHA-256 bytes before assigning ordinal aliases. No
current clock, locale, network, random identifier or build-version string enters
rendered bytes. Timings, when included, come from the receipt. JSON has fixed field
order and LF endings; this is a versioned Golem format, not RFC 8785 or BagIt.
Only fixed text, allowlisted enums, integers and lowercase digests enter Markdown.
Source names, paths, command arguments, case descriptions and log text are omitted.
Renderer v1 has a golden-byte test; a changed rendering contract requires a new
renderer version, not silent replacement of v1 output.

All three Markdown projections share one sanitized facts inventory. The manifest
binds the exact bytes of that inventory and every projection. For reproduction,
retain the request separately from the exported pack and use the original Work.
Distinct receipt sets with identical MINIMAL facts may produce the same pack;
the pack digest identifies projected bytes, not a unique source execution.

## Redaction boundary

The policy parser is shared with [research exports](bundle.md), not duplicated.
`MINIMAL` exposes ordinal runs/gates, outcomes, closed reason classes, exit/signal
and log availability. It omits source digests, identifiers, lengths and timings.
`LINKABLE` requires `acknowledge_linkability: true`; it adds source receipt,
checkpoint, contract, input/snapshot digests, stream observations, retained
receipt/artifact digests and recorded durations. Historical v1 duration is not
available: `duration_availability` is `UNKNOWN` and `duration_ms` is omitted.

Neither profile includes raw or masked stream bytes. `COMPLETE` describes source
log retention, not inclusion in this export. `DISCARDED`, `TRUNCATED` and historical
unknown completeness remain explicit. These are allowlisted projections, not
general secret detection or anonymity guarantees; counts and outcomes can still
reveal information. Review before release. Do not publish the private request by
accident: even MINIMAL requests contain the original receipt identifiers.

Raw observed-stream hashes, retained receipt hashes, retained artifact hashes and
derived file hashes have distinct roles. Different representations normally have
different hashes, but empty/all-masked input can have equal byte hashes. Equality
never merges the roles or upgrades an export to original evidence.

## Verification levels

- `integrity`: fixed schema and flags, complete inventory, exact file bytes,
  manifest and commit consistency. With an independently trusted manifest digest,
  also rejects coordinated package replacement. Does not inspect source facts or
  certify redaction, even if embedded flags claim no raw evidence.
- `verify-dir`: the above, plus all six files must be regular non-symlink files.
  Unexpected entries fail; exact `.pending-<24 lowercase hex>` staging names are
  ignored and never read. Missing commit or payload fails.
- `verify WORK REQUEST PACK`: regenerates the projection from issued receipts
  and CAS dependencies, then compares every file. Missing/corrupt original evidence
  fails. This is source-relative verification, not independent authentication.

A forged pack with recomputed hashes can pass unanchored integrity. It must not
pass source projection verification. Tests cover this distinction. No verification
mode writes the Work, publishes source evidence or changes completion state.

## Publication and recovery

The output directory is `ROOT/<manifest-sha256>/`. Payload files are published
first, then the manifest, then `COMMIT.json`. Each file uses the existing immutable
storage helper: exclusive random staging file, write, file sync and checked close,
no-replace hard link, staging unlink, directory sync. New directories are 0700;
published files are 0400. No rename/replace or mutable `latest` view is used.

Existing destinations are accepted only when their bytes match. A retry can fill
missing components without overwriting another file. Readers must verify all
files; existence of the directory or marker alone is not sufficient. Publication
is a logical commit protocol, not atomic directory visibility or a filesystem
transaction. Concurrent identical publishers are supported; hostile same-user
mutations of the parent/source are outside the model.

Errors leave output arguments unchanged, but may leave complete or orphan files.
In particular, failure after the final link can leave a readable complete pack
whose durability is uncertain. Retry identical publication to resync; never treat
the failed call as durable success. No automatic orphan deletion is performed.
All fsync guarantees depend on the filesystem/device honoring them. Syscall fault
and process-interruption tests are not proof of every physical power-loss case.

Public C APIs and ownership rules are in `include/golem/proof.h`.
