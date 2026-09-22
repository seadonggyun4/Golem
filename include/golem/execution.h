#ifndef GOLEM_EXECUTION_H
#define GOLEM_EXECUTION_H
#include "golem/document.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct golem_execution_reply { uint8_t *data; size_t size; } golem_execution_reply;
/* Local cooperative, synchronous document-driven verification. JSON v1 commands:
 * prepare, finish, run, verify. See docs/execution.md for bounded schemas.
 * Inputs borrowed for the call. Reply owns malloc storage (not NUL terminated);
 * free with reply_free. Output unchanged on failure. Serial calls per store.
 * prepare requires the trusted host's approval digest returned by validate:
 * SHA256 of json-c compact JSON, retaining parsed member order (not JCS).
 * NULL denies approval. Do not approve unchecked/untrusted agent requests.
 * run also requires that approval; approval is NOT read from request JSON.
 * Commands run arbitrary trusted project code, NOT a sandbox. No inherited env.
 * Never auto-retry run after an uncertain outcome; persistent attempt markers
 * prevent duplicate dispatch. A failed gate is a successful API result containing
 * FAIL/ERROR, never semantic product acceptance. No provider/agent is spawned. */
golem_status golem_execution_contract_validate(golem_bytes contract, golem_digest *digest,
    golem_diagnostic *diagnostic);
golem_status golem_execution_call(golem_document_store *store, golem_bytes request,
    const golem_digest *approved_contract, golem_execution_reply *out, golem_diagnostic *diagnostic);
/* Render exact schema-5 result Markdown from its immutable execution receipt.
 * Does not execute commands or attest current filesystem state. */
golem_status golem_execution_render(golem_document_store *store, golem_bytes metadata,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
void golem_execution_reply_free(golem_execution_reply *reply);
#ifdef __cplusplus
}
#endif
#endif
