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
 * Ordering is stream/sequence, NOT cross-stream chronology.
 * Schema 2 supports append-tolerant polling with independently hash-pinned
 * per-stream cursors; see docs/incremental-history.md. Invalid baselines return
 * an explicit FULL reset page, not an empty delta. Corrupt current sources fail.
 * limit is PER STREAM (1..256). Output is incremental; source replay is not.
 * Persist a returned cursor only after consuming its page; reads grant nothing. */
golem_status golem_work_history(golem_document_store *store, golem_bytes request,
                                golem_agent_reply *out, golem_diagnostic *diagnostic);
/* Read-only consolidated assessment/status/journal projection under the store
 * lock. Request: schema_version=1, work_id, byte_budget (1..32 MiB), and
 * document_head/agent_head (both empty or both expected SHA256 values).
 * Assessments are interned by JSON-C compact bytes, not semantic equivalence.
 * Original CAS/journals remain authoritative. No persistence or approval.
 * Clock-derived lease status is an observation, never a future lease guarantee.
 * Same owned-reply/unchanged-on-error contract as session calls. The byte budget
 * bounds serialized output, not total allocator usage. Unknown versions fail. */
golem_status golem_work_record(golem_document_store *store, golem_bytes request,
                               const golem_agent_clock *clock, golem_agent_reply *out,
                               golem_diagnostic *diagnostic);
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
