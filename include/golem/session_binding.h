#ifndef GOLEM_SESSION_BINDING_H
#define GOLEM_SESSION_BINDING_H
#include "golem/agent_session.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_SESSION_BINDING_MAX_BYTES 32768u
#define GOLEM_NATIVE_THREAD_MAX_BYTES 1024u
#define GOLEM_HISTORY_PAGE_MAX 256u
/* Trusted synchronous host callback, not a JSON option. It must verify the
 * association represented by candidate, including its descriptor and native
 * thread digest. No reentry or store mutation. The returned identity is recorded
 * provenance, NOT authentication or an independent-review authorization. */
typedef struct golem_session_binding_host {
    golem_status (*observe)(void *context, golem_bytes candidate, golem_digest *identity);
    void *context;
} golem_session_binding_host;
/* Borrowed inputs, owned reply freed with golem_agent_reply_free; unchanged on
 * failure. Strict JSON, bounded allocation, no pointers retained. Serialize on
 * the Work store. attach requires a writable handle and current sequence/token;
 * inspect is read-only. Native IDs are hashed, never filenames or persisted raw.
 * Duplicate attach returns a historical receipt, not a refreshed fence/lease.
 * New binding epochs revoke old tokens; no agent is spawned or authenticated. */
golem_status golem_session_binding_request_validate(golem_bytes request);
golem_status golem_session_binding_call(golem_document_store *store, golem_bytes request,
                                        const golem_agent_clock *clock,
                                        const golem_session_binding_host *host,
                                        golem_agent_reply *out, golem_diagnostic *diagnostic);
/* Read-only, paged source-event projection, not a second authoritative database.
 * Request pins both stream heads on subsequent pages; changed heads are stale.
 * Missing/corrupt prefixes return errors, never a successful empty history.
 * Ordering is stream/sequence, NOT cross-stream chronology. */
golem_status golem_work_history(golem_document_store *store, golem_bytes request,
                                golem_agent_reply *out, golem_diagnostic *diagnostic);
/* Future approval hosts must check this fence immediately before consuming a
 * capability. Pure read of current durable state + trusted clock; grants nothing.
 * Borrowed request: {binding_id,token}; success means live/current, not approved. */
golem_status golem_session_fence_check(golem_document_store *store, golem_bytes request,
                                       const golem_agent_clock *clock,
                                       golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
