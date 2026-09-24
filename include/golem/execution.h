#ifndef GOLEM_EXECUTION_H
#define GOLEM_EXECUTION_H
#include "golem/document.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct golem_execution_reply { uint8_t *data; size_t size; } golem_execution_reply;
/* Local cooperative, synchronous document-driven verification. JSON v1 commands:
 * prepare, finish, run, verify. See docs/execution.md for bounded schemas.
 * Execution contract v5 / snapshot plan v3 uses verified CAS inventory references;
 * v1-v4 retain their historical inline formats. See docs/change-inventory.md.
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
/* Trusted host input, never deserialize this structure from agent JSON.
 * Version 1 requires exact struct_size. All pointers are borrowed for the call.
 * shell_contract is a SECOND approval of the complete v3 contract, after review
 * of the whole script and its effects. NULL denies shell execution. This is not
 * a signature, a sandbox, or a separate-principal authentication mechanism.
 * The legacy call cannot authorize shell scripts. Outputs unchanged on failure. */
typedef struct golem_execution_approval {
    size_t struct_size;
    uint32_t version;
    const golem_digest *contract;
    const golem_digest *shell_contract;
} golem_execution_approval;
golem_status golem_execution_call_authorized(golem_document_store *store, golem_bytes request,
    const golem_execution_approval *approval, golem_execution_reply *out,
    golem_diagnostic *diagnostic);
/* Render exact schema-5 result Markdown from its immutable execution receipt.
 * Does not execute commands or attest current filesystem state. */
golem_status golem_execution_render(golem_document_store *store, golem_bytes metadata,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
void golem_execution_reply_free(golem_execution_reply *reply);
/* Read-only versioned verification bundle derived from a locally issued QA
 * receipt. Checks CAS dependencies, not current source freshness or acceptance.
 * Does not run commands or create files. inspect returns owned JSON via the
 * existing reply/free pair; outputs unchanged on failure. verify rejects any
 * change or unknown field relative to the deterministic source-bound bundle.
 * No signing/authenticity claim; caller controls and trusts the local store.
 * v1 historical logs remain unavailable, never retroactively captured. */
golem_status golem_execution_bundle_inspect(golem_document_store *store,
    const golem_digest *qa_receipt, golem_execution_reply *out, golem_diagnostic *diagnostic);
golem_status golem_execution_bundle_verify(golem_document_store *store,
    golem_bytes bundle, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
