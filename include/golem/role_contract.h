#ifndef GOLEM_ROLE_CONTRACT_H
#define GOLEM_ROLE_CONTRACT_H
#include "golem/execution.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_ROLE_MAX_JSON 65536u
#define GOLEM_ROLE_MAX_RULES 64u
#define GOLEM_ROLE_MAX_EVENTS 64u
/* Borrowed inputs, serialized by the Work store lock. Owned replies use
 * golem_execution_reply_free; outputs are unchanged on failure. Enrollment is
 * immutable per Work, bound to a selection ID across revisions, and requires
 * the reviewed engine-serialized contract digest. Other selections cannot bypass it.
 * Approval is trusted local caller attestation, not identity authentication.
 * evaluate/status are read-only; assess/enroll require a writable store.
 * Roles grant no execution permissions. Unknown independent identities block.
 * I/O uncertainty requires reopen; retry the identical key, never rerun work.
 * JSON schemas, bounds and historical/live semantics: docs/role-contracts.md. */
golem_status golem_role_validate(golem_bytes contract, golem_digest *digest,
                                 golem_diagnostic *diagnostic);
/* Pure request validation; does not authorize or open a Work. */
golem_status golem_role_request_validate(golem_bytes request, golem_diagnostic *diagnostic);
golem_status golem_role_template(const char *name, golem_execution_reply *out);
golem_status golem_role_call(golem_document_store *store, golem_bytes request,
                             const golem_digest *approved_contract, golem_execution_reply *out,
                             golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
