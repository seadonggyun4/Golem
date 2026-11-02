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
#ifdef __cplusplus
}
#endif
#endif
