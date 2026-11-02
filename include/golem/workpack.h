#ifndef GOLEM_WORKPACK_H
#define GOLEM_WORKPACK_H
#include "golem/evidence.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_WORKPACK_MAX_JSON 65536u
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
#ifdef __cplusplus
}
#endif
#endif
