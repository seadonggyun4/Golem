# Verification Bundles

Phase 31A extends the existing document-driven execution path, not a second test
runner. A locally issued QA receipt is the identity root. A versioned bundle binds
its Work, attempt, checkpoint, approved contract, executable digests, input
manifest, declared-source snapshot, gate observations and log descriptors.
No supplied replacement outcome, source or attempt is accepted by verification.

## Enrollment and Compatibility

Keep contract v1 for historical behavior: raw stdout/stderr is discarded, only
bounded-buffer digests and counts remain. Completeness of historical logs is
UNKNOWN; inspection never reconstructs missing content or reruns a command.
Historical v1 Markdown bytes are unchanged.

To enroll, review a contract with `schema_version: 2` and this additional field:

```json
"log_retention": {
  "mode": "DISCARD",
  "max_bytes": 0,
  "redactor": "none",
  "require_complete": false
}
```

Explicit bounded capture instead uses:

```json
"log_retention": {
  "mode": "REDACTED_CAPTURE",
  "max_bytes": 16384,
  "redactor": "mask-bytes-v1",
  "require_complete": true
}
```

The whole contract, including retention, is covered by trusted host approval.
Existing prepare/run approval, session, lease, source and protected-test checks
still apply. No JSON `approved` field grants authority. Changes require the
existing reviewed policy/selection lifecycle; do not edit a stored checkpoint.
Requests stay v1; enrolled checkpoint/development/QA receipts use v2, so an old
reader refuses them rather than silently skipping new evidence requirements.

## Retention Semantics

- `DISCARD` remains the default behavior. v2 requires explicit mode selection;
  omitted retention is invalid, not implicit permission to capture.
- `REDACTED_CAPTURE` permits 1..16384 bytes **per stream per gate**. Eight gates
  therefore retain at most 256 KiB of log payload per execution. Only two bounded
  capture buffers are live at once. This deliberately retains the existing 16 KiB
  supervisor/protocol limits instead of silently adopting a proposed 1 MiB cap.
- `mask-bytes-v1` replaces every retained byte with ASCII `*`. It is lossful,
  content-independent and chunk-independent, including split UTF-8 and binary
  input. It preserves length, not readable diagnostic text. It is not a regex
  secret detector. More useful allowlisted redactors need a separately versioned
  contract and security tests; arbitrary user redaction code is not executed.
- RAW and unknown modes/redactors are refused. This version offers no raw-log
  approval escape hatch. Do not describe masked capture as original log storage.
- The sink receives bounded chunks before protocol buffering. The observed digest
  covers every byte delivered to the sink, even the chunk that overflows the
  protocol buffer. Original bytes are not written to a temporary file or CAS.
  Legacy `stdout_digest`/`stdout_size` describe the protocol buffer, not this
  potentially longer observed prefix; v2 log descriptors are authoritative for
  captured-log accounting.

Each descriptor separates observed bytes/digest, retained receipt/size, offset
(zero), cap, redactor, actual pipe EOF and dropped **observed** bytes. `COMPLETE`
means the entire observed stream reached EOF and fits in the retained masked
representation. `TRUNCATED` means partial capture or unknown remainder;
`DISCARDED` means no retained object. `total_bytes_known=false` forbids treating
the observed count as the child's entire output. Child exit alone does not prove
EOF; timeout/cancel/overflow may leave an unknown remainder.

If complete logs are required, incomplete capture produces gate ERROR with
`EVIDENCE_INCOMPLETE` even if case output says PASS. Without that requirement,
retention truncation alone is not a test failure; supervisor overflow still is.
No capture setting weakens exact expected case count/order/identity checks.
Empty, missing, duplicate, reordered, SKIPPED or NOT_DONE cases cannot pass.
v2 preserves PASS/FAIL/ERROR case meanings; exit zero alone never grants PASS.

## Storage and Failure

Masked bytes and their binary receipts use existing atomic no-replace CAS writes,
file/directory synchronization and hash/size verification. New directories are
0700 and objects 0400. Gate observations refer to those receipts. The QA result is
written to CAS, then its deterministic bundle, then its issued-receipt marker.
Consumers reverify retained objects and the persisted v2 bundle through `ex_load`,
including QA document submission and completion paths. Missing or corrupt
evidence cannot silently become a valid receipt.

An actual command may finish before evidence publication fails. The durable
`.started` attempt remains; absent `.done` prevents automatic reexecution. If
`.done` already exists and the store is readable, retrying the identical attempt
can finish metadata publication from original observations without running the
command. This is not a general corrupted-store repair facility. CAS orphans are
not completion receipts and are never automatically deleted. No TTL, pruning or
GC is introduced; retention here controls capture, not time-based expiry.

## Inspection

```sh
golem execution bundle inspect "$WORK" "$QA_RECEIPT_SHA256"
golem execution bundle verify "$WORK" bundle.json
```

Inspection returns deterministic bundle JSON. A caller can save that output in a
private location. Verification compares a supplied bundle with its locally issued
source and checks dependencies; extra fields and substituted references fail.
Both commands open the Work read-only, execute no subprocess, and do not capture
historical logs. Success verifies integrity, **not QA PASS, source freshness,
authenticity, semantic acceptance or public-release permission**. A faithfully
recorded FAIL bundle is valid evidence. Use the existing execution `verify` and
completion gates for freshness and acceptance, respectively.

QA Markdown for v2 includes the bundle digest and per-stream availability;
it never embeds raw log text. Bundles retain internal IDs, digests and timing:
they are private review material, not automatically redacted public exports.
Digests/lengths may permit linking or guessing low-entropy inputs. Keep the Work
private and use the separate reviewed research export boundary for sharing.

## API and Limits

`golem_execution_bundle_inspect` borrows a store and receipt digest and returns an
owned `golem_execution_reply`, released with `golem_execution_reply_free`.
`golem_execution_bundle_verify` borrows bytes for the call. Outputs are unchanged
on failure. Existing store locking and caller synchronization apply. Golem capture
buffers use the store allocator; OpenSSL and json-c own their internal memory.

The additive `golem_supervisor_run_streamed` has size/version-checked callback
options and a separate capture summary; existing public struct layouts remain
unchanged. Callback chunks are borrowed only during the call, sequential per
invocation, and must be processed promptly. Callback errors abort/reap. These are
cooperative local process observations, not a sandbox or signed remote identity.

Times are host monotonic milliseconds, not UTC or comparable across boots.
Source coverage remains declared, non-atomic files. Candidate inventory and
worktree isolation belong to later phases; this bundle does not claim them.

## Design References

- Torres-Arias et al., [in-toto, USENIX Security 2019](https://www.usenix.org/system/files/sec19-torres-arias.pdf),
  sections 2 and 3: distinguish step inputs, outputs and execution byproducts;
  bind evidence across steps. Golem adopts this separation, not the paper's signed
  supply-chain guarantees: local CAS hashes are not signatures.
- [SLSA v1.2 Verification Summary Attestation](https://slsa.dev/spec/v1.2/verification_summary):
  bind verification to policy and input evidence. This native bundle is not a VSA
  and claims no SLSA level or standards conformance.
- Beyer et al., [Site Reliability Engineering, chapter 17](https://sre.google/sre-book/testing-reliability/),
  O'Reilly, 2016: use layered testing and failure scenarios to establish bounded
  confidence. A successful declared test set is not universal correctness.
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html),
  data exclusion, protection and verification sections: minimize sensitive data,
  treat external log content as untrusted, bound resources and test logging
  failures. Raw discard plus conservative opt-in masking implements this boundary.

These sources informed design decisions; their relevant sections were reviewed,
not every chapter or every cited work. No external project source was copied.
## Derived proof packs

For immutable multi-file Markdown exports, redaction and source-relative verification,
see [Verification proof packs](proof-packs.md). These exports do not replace QA receipts.
