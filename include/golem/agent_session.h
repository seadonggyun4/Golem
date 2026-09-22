#ifndef GOLEM_AGENT_SESSION_H
#define GOLEM_AGENT_SESSION_H
#include "golem/document.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_AGENT_SESSION_VERSION 1u
#define GOLEM_AGENT_MAX_EVENTS 4096u
#define GOLEM_AGENT_MAX_ATTEMPTS 256u
#define GOLEM_AGENT_MAX_TTL_MS 3600000u
#define GOLEM_AGENT_CONTEXT_MAX 33554432u
typedef struct golem_agent_reply { uint8_t *data; size_t size; } golem_agent_reply;
/* Pure request shape/limit validation, not a claim or state precondition check.
 * Borrows bytes; optional caller-owned diagnostic. Does not access filesystem. */
golem_status golem_agent_request_validate(golem_bytes request, golem_diagnostic *diagnostic);
typedef struct golem_agent_clock {
    /* Trusted host clock, NOT agent input. Stable boot identity + monotonic ms.
     * Callback/context borrowed for this call only. NULL selects OS clock.
     * Test clocks must never be exposed to untrusted CLI callers. */
    golem_status (*read)(void *context, uint64_t *milliseconds, golem_digest *boot);
    void *context;
} golem_agent_clock;
/* Versioned JSON protocol; see docs/agent-session.md. Borrows store/request/clock.
 * Serialize calls; store lifetime flock is the cross-process authority. Open a
 * writable store for mutations; query calls also work with read-only handles.
 * Reply is owned, not NUL terminated, free with golem_agent_reply_free. Output
 * unchanged on error; no input/output aliasing. IO may mean committed: close and
 * reopen, retry identical key/bytes. A successful retry returns the old receipt,
 * not renewed permission. Fencing identifiers are NOT authentication credentials.
 * Does not launch agents, sandbox filesystem effects, attest external commands,
 * or declare semantic completion. Local cooperating clients, not distributed HA.
 * Clock rollback/boot change require explicit resume; CLI process exit alone
 * does not reset the durable coordinator. Bounds: 4096 events, 256 attempts.
 */
golem_status golem_agent_session_call(golem_document_store *store, golem_bytes request,
    const golem_agent_clock *clock, golem_agent_reply *out, golem_diagnostic *diagnostic);
void golem_agent_reply_free(golem_agent_reply *reply);
#ifdef __cplusplus
}
#endif
#endif
