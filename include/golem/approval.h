#ifndef GOLEM_APPROVAL_H
#define GOLEM_APPROVAL_H
#include "golem/agent_session.h"
#include "golem/execution.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_APPROVAL_MAX_JSON 16384u
#define GOLEM_APPROVAL_MAX_EVENTS 256u
#define GOLEM_APPROVAL_MAX_PENDING 32u
#define GOLEM_APPROVAL_MAX_TTL_MS 3600000u
/* Trusted host boundary; never construct from agent JSON. Both callbacks are
 * synchronous, borrowed, must return promptly, and must not reenter the store.
 * decide reads a decision already collected over a separate host channel. Never
 * wait for human input holding a Work handle. Missing decision returns an error.
 * The host must authenticate its operator and protect this channel from agents.
 * recheck checks current policy epoch, issuer authorization and revocation at
 * consumption/dispatch. Stored receipts alone cannot grant live authority. */
typedef struct golem_approval_host {
    size_t struct_size;
    uint32_t version;
    golem_status (*decide)(void *context, const golem_digest *action, const char *operation,
                           golem_digest *issuer, uint64_t *policy_epoch);
    golem_status (*recheck)(void *context, const golem_digest *action, const golem_digest *issuer,
                            uint64_t policy_epoch);
    void *context;
} golem_approval_host;
/* Pure strict request validator. No permissions or effects. */
golem_status golem_approval_request_validate(golem_bytes request);
/* Read-only execution scope construction from prepare/finish/run requests.
 * Pins Work policy, request, command contract, source snapshot, document inputs,
 * runtime generation and current session fence. Reply contains action + digest.
 * Does not approve or execute. See docs/approvals.md. */
golem_status golem_approval_describe(golem_document_store *store, golem_bytes execution_request,
                                     golem_execution_reply *out, golem_diagnostic *diagnostic);
/* request/status/approve/deny/revoke/expire. Mutations need writable store.
 * Same key+request is idempotent; returns historical receipt, never renews TTL.
 * Approval request TTL begins at request creation. Boot change or clock rollback
 * invalidates live authority. Supplied clock is trusted host/test input only.
 * Inputs borrowed, output owned by reply_free, unchanged on error. */
golem_status golem_approval_call(golem_document_store *store, golem_bytes request,
                                 const golem_approval_host *host, const golem_agent_clock *clock,
                                 golem_execution_reply *out, golem_diagnostic *diagnostic);
/* Recompute exact scope, recheck host/fence, commit one-use consume intent, then
 * perform the existing execution operation. DENY remains absolute. ASK_ALWAYS
 * is satisfied only for this operation. Existing shell approval is still needed.
 * A consumed receipt is never dispatched again. Crash/error leaves UNCERTAIN;
 * status/recover reads the recorded result without dispatch or renewed authority.
 * No raw approval tokens, secrets or remote signatures are accepted in JSON. */
golem_status
golem_execution_call_receipted(golem_document_store *store, golem_bytes execution_request,
                               const golem_digest *request_receipt, const golem_approval_host *host,
                               const golem_execution_approval *execution_approval,
                               golem_execution_reply *out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
