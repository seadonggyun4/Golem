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
#ifdef __cplusplus
}
#endif
#endif
