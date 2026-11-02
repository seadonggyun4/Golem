#ifndef GOLEM_WORKPACK_H
#define GOLEM_WORKPACK_H
#include "golem/execution.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_WORKPACK_MAX_JSON 65536u
#define GOLEM_WORKPACK_CATALOG_MAX_JSON 1048576u
#define GOLEM_WORKPACK_CATALOG_MAX_ENTRIES 256u
#define GOLEM_WORKPACK_CATALOG_REPORT_MAX 2097152u
#define GOLEM_WORKPACK_SCHEMA "golem.workpack.v0"
/* Experimental pure manifest validator. Borrowed immutable bytes, required
 * caller-owned digest, optional diagnostic; outputs must not alias input or each
 * other. Digest unchanged on failure. Digest covers EXACT input bytes, not a
 * canonical/semantic JSON representation. No file/Work access, grants, binding,
 * execution, compatibility/availability assertion or completion evaluation.
 * Closed schema and limits: docs/workpacks/schema.md. */
golem_status golem_workpack_validate(golem_bytes input, golem_digest *digest,
                                      golem_diagnostic *diagnostic);
/* Bounded local snapshot. Relative paths are anchored at the process cwd;
 * absolute paths at /. All components use native no-follow traversal. No '..',
 * symlinks, non-regular files or hardlinks. No directory scan or Work access.
 * buffer must have MAX_JSON bytes. Outputs unchanged on failure. No NUL added.
 * Path <=4095 bytes. Concurrent change is rejected, not automatically retried. */
golem_status golem_workpack_read(const char *path, uint8_t *buffer, size_t capacity,
                                size_t *size, golem_diagnostic *diagnostic);
/* Validated metadata serialized as JSON (not original bytes/canonical identity).
 * required includes trailing NUL, set on success/BUFFER_TOO_SMALL only.
 * buffer unchanged on failure. NULL buffer with zero capacity is a size query.
 * All outputs must be distinct from each other and input. */
golem_status golem_workpack_inspect(golem_bytes input, char *buffer, size_t capacity,
                                   size_t *required, golem_diagnostic *diagnostic);
/* Inclusive numeric declaration comparison only, never runtime availability.
 * Core version is length-delimited strict x.y.z (<=17 bytes, components<=65535).
 * compatible unchanged on failure. */
golem_status golem_workpack_compatibility(golem_bytes input, golem_string_view core_version,
                                         bool *compatible, golem_diagnostic *diagnostic);
/* Explicit local catalog discovery. NULL/zero query lists all validated entries;
 * otherwise strict UTF-8 query <=256 bytes. No grants, binding or Work access.
 * Every relative manifest is read and exact digest/metadata checked, including
 * excluded results. No scan/network/cache. Duplicate ID/version is an error.
 * JSON report is deterministic; ties never choose a winner. required includes NUL
 * and changes only on OK/BUFFER_TOO_SMALL; buffer unchanged on error. A size query
 * performs filesystem reads; a later call is a fresh observation, not a snapshot
 * handle. Output/input must not alias. See docs/workpacks/delivery.md. */
golem_status golem_workpack_catalog(const char *path, golem_string_view query,
                                   char *buffer, size_t capacity, size_t *required,
                                   golem_diagnostic *diagnostic);
/* M4 opt-in native documents binding. Requests <=128 KiB, exact bytes, no
 * output aliasing. resolve/explain need a read-only store; bind requires native
 * writable lock, policy/CAS and a separately reviewed domain-specific digest.
 * No grants, role enrollment, execution or release. Unsupported mappings block.
 * Replies owned by caller via golem_execution_reply_free; unchanged on error.
 * Same raw request/key plus approved digest returns historical receipt only.
 * Publication I/O poisons writer; never automatically retry. See M4 design. */
golem_status golem_workpack_resolve(golem_document_store *store, golem_bytes request,
                                   golem_execution_reply *out, golem_diagnostic *diagnostic);
golem_status golem_workpack_bind(golem_document_store *store, golem_bytes request,
                                const golem_digest *approved_binding,
                                golem_execution_reply *out, golem_diagnostic *diagnostic);
golem_status golem_workpack_explain(golem_document_store *store,
                                   golem_execution_reply *out, golem_diagnostic *diagnostic);
/* M5 untrusted proposals: pure closed-schema validation <=64 KiB. Exact digest
 * unchanged on failure. No identity authentication or authority from claims. */
#define GOLEM_WORKPACK_PROPOSAL_MAX_JSON 65536u
#define GOLEM_WORKPACK_MAX_PROPOSALS 8u
golem_status golem_workpack_proposal_validate(golem_bytes input, golem_digest *digest,
                                             golem_diagnostic *diagnostic);
/* Read-only native-documents-v1 binding/role assessment plus 1..8 proposals.
 * Shared native Work lock; current generation, exact binding/contract and native
 * document closure/CAS required. Self-declared principals never authenticate.
 * Duplicate proposal/principal declarations fail. Failed/unknown claims retained;
 * disagreement never resolves to PASS. No stored assessment, approval or completion.
 * Existing explicitly configured native recording may write its own audit.
 * Reply <=256 KiB, unchanged on error; free via golem_execution_reply_free. */
golem_status golem_workpack_assess(golem_document_store *store, const golem_bytes *proposals,
                                  size_t count, golem_execution_reply *out,
                                  golem_diagnostic *diagnostic);
/* M6 private native document receipt package. Request <=64 KiB; closed typed
 * inventory <=256 objects /16 MiB, manifest <=64 KiB. Work remains read-only.
 * Plan pins the current native source, exact inventory/format and canonical
 * private output parent identity. Separate export approval is local caller
 * attestation, never identity authentication, execution or release permission.
 * Export creates a NEW immutable child; an existing/partial child is rejected.
 * Any failure may leave partial or durable-but-unconfirmed files; preserve them,
 * never automatically retry/repair. Output arguments stay unchanged on error.
 * Verify requires an independently retained manifest digest; it proves bounded
 * structural integrity only, never source truth, current QA/completion or origin.
 * Replies use golem_execution_reply_free. See docs/workpacks/receipts.md. */
golem_status golem_workpack_receipt_manifest(golem_document_store *store, golem_bytes request,
    const char *parent, const char *format, golem_execution_reply *out, golem_diagnostic *diagnostic);
golem_status golem_workpack_receipt_export(golem_document_store *store, golem_bytes request,
    const char *parent, const char *format, const golem_digest *approved_export,
    golem_digest *manifest, golem_diagnostic *diagnostic);
golem_status golem_workpack_receipt_verify(const char *directory, const golem_digest *expected_manifest,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
/* M7 bounded Truthound 3.3.1 capture adapter; no file/tool/Work operations.
 * Exact source/config/Pack pins are caller attestations, not authenticated origin.
 * <=256KiB capture, three <=64KiB responses. Unknown/truncated/failed observations
 * never authorize release or native completion. Replies freed by existing API. */
golem_status golem_workpack_reference_observe(golem_bytes input, const golem_digest *source,
    const golem_digest *config, const golem_digest *pack, golem_execution_reply *out,
    golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
