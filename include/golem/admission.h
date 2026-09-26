#ifndef GOLEM_ADMISSION_H
#define GOLEM_ADMISSION_H
#include "golem/evidence.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_ADMISSION_VERSION 1
#define GOLEM_ADMISSION_MAX_TICKETS 256
#define GOLEM_ADMISSION_MAX_EVENTS 65536
typedef struct golem_admission golem_admission;
typedef struct golem_document_store golem_document_store;
typedef enum golem_admission_state {
    GOLEM_ADMISSION_QUEUED = 1,
    GOLEM_ADMISSION_GRANTED,
    GOLEM_ADMISSION_STARTING,
    GOLEM_ADMISSION_RUNNING,
    GOLEM_ADMISSION_CANCEL_REQUESTED,
    GOLEM_ADMISSION_RECONCILE_REQUIRED,
    GOLEM_ADMISSION_SETTLING,
    GOLEM_ADMISSION_RELEASED,
    GOLEM_ADMISSION_CANCELLED
} golem_admission_state;
typedef struct golem_admission_limits {
    uint64_t slots, cpu_millis, memory_bytes;
    uint64_t foreground_burst; /* 0 = strict FIFO; maximum 32. */
} golem_admission_limits;
typedef struct golem_admission_request {
    char operation[64]; /* Stable idempotency key, not a path. */
    char work[96];
    char session[96];
    golem_digest runtime_binding;
    uint64_t cpu_millis, memory_bytes;
    uint64_t parent; /* 0 = root; otherwise borrow an unstarted root reservation. */
    bool foreground;
} golem_admission_request;
typedef struct golem_admission_token {
    uint64_t ticket, epoch;
    uint8_t instance[16];
    golem_digest boot;
} golem_admission_token;
typedef struct golem_admission_ticket {
    golem_admission_request request;
    golem_admission_token token;
    golem_admission_state state;
    golem_digest binding_receipt, termination_receipt;
} golem_admission_ticket;
typedef struct golem_admission_checkpoint {
    uint64_t records;
    golem_digest head;
} golem_admission_checkpoint;
typedef struct golem_admission_options {
    size_t size;
    uint32_t version;
    bool create;
    golem_admission_limits limits; /* Used only for a new ledger. */
    const golem_allocator *allocator;
    /* Optional retained prefix anchor: rejects deletion/replacement of its prefix. */
    const golem_admission_checkpoint *expected;
} golem_admission_options;

/* Dedicated existing private directory, absolute path, no symlink components.
 * One persistent namespace per repository, shared by all its callers. Never derive
 * the namespace from a workspace path. Rename retains identity; copying creates a
 * second independent authority and is NOT supported. Open holds a lifetime owner
 * flock, replays strictly, and commits a fresh epoch/instance. Uncertain executions
 * retain reservations. No timeout frees them. Legacy daemon paths are not enrolled.
 * Options/requests are borrowed for the call; allocator is copied, context must
 * outlive close. All returned values are caller-owned. Outputs unchanged on error.
 * Serialize calls and close, including callbacks; no callback reentry. No mutation
 * lock is held during callbacks; the single-owner leadership lock remains held.
 * IO failure poisons mutations: close/reopen and query by operation key. */
golem_status golem_admission_open(const char *root, const golem_admission_options *options,
                                  golem_admission **out);
/* Optional caller-owned diagnostic, overwritten on every call. Same ownership
 * and mutation semantics as open. Diagnostic contains a stable operation name
 * and captured errno, never root paths, credentials or boot identity values. */
golem_status golem_admission_open_diagnostic(const char *root,
    const golem_admission_options *options, golem_admission **out,
    golem_diagnostic *diagnostic);
golem_status golem_admission_close(golem_admission *admission);
golem_status golem_admission_identity(golem_admission *admission, golem_digest *namespace_id,
                                      golem_admission_checkpoint *checkpoint);
golem_status golem_admission_enqueue(golem_admission *admission,
                                     const golem_admission_request *request, uint64_t *ticket);
golem_status golem_admission_lookup(golem_admission *admission, const char *operation,
                                    golem_admission_ticket *out);
/* Atomic all-or-nothing grant. NOT_FOUND means empty/no eligible request.
 * Once the oldest root has consumed its bounded bypass allowance, newer roots
 * cannot pass it even when it is blocked: capacity drains, preventing starvation.
 * Nested requests use ONLY the parent budget, depth one, one child at a time. */
golem_status golem_admission_grant(golem_admission *admission, golem_admission_ticket *out);
/* Explicit durable limit update; shrinking does not revoke existing reservations. */
golem_status golem_admission_resize(golem_admission *admission, golem_admission_limits limits);
golem_status golem_admission_cancel(golem_admission *admission, golem_admission_token token);
/* Binding publication must be durable before publish returns OK, and bind the
 * namespace + token + Work/session/runtime_binding. It must be idempotent. This is
 * a trusted host contract, not verification of arbitrary agent-supplied digests.
 * execute is called only after durable STARTING and RUNNING intents, at most once
 * per ticket. It must observe termination and persist evidence before returning OK.
 * Non-OK leaves the reservation for reconciliation, never automatic redispatch.
 * This synchronous bridge does not implement a worker pool or grant shell rights.
 * execute must still enforce policy/lease and any enrolled 30B checked dispatch
 * at actual launch; the admission ticket never replaces those gates. */
typedef struct golem_admission_dispatch_ops {
    golem_status (*publish)(void *context, const golem_digest *namespace_id,
                            const golem_admission_ticket *ticket, golem_digest *receipt);
    golem_status (*execute)(void *context, const golem_admission_ticket *ticket,
                            golem_digest *termination_receipt);
} golem_admission_dispatch_ops;
golem_status golem_admission_dispatch(golem_admission *admission, golem_admission_token token,
                                      const golem_admission_dispatch_ops *ops, void *context);
/* Split-phase bridge for an external bounded executor. Commits publication,
 * STARTING and RUNNING without executing. Returns the canonical running ticket.
 * Never repeat execution after this succeeds: a launch error must be settled as
 * proven non-execution; a crash requires reconciliation. Same publisher contract
 * and policy obligations as dispatch. Output unchanged on failure. */
golem_status golem_admission_begin(golem_admission *admission, golem_admission_token token,
    golem_status (*publish)(void *, const golem_digest *, const golem_admission_ticket *,
                           golem_digest *), void *context, golem_admission_ticket *out);
/* Production Work-ledger publisher for use inside a host publish callback.
 * Requires a writable Work store, matching live RUNNING agent claim, fresh input
 * manifest and 30A runtime binding. Commits a CAS-backed admission-link event to
 * the Work ledger, idempotently. Does not grant authority or execute the agent.
 * The host must pass the ticket received from dispatch, not agent-authored data.
 * Store is borrowed for this call; receipt is caller-owned, unchanged on failure.
 * Close the Work writer before long-running execute callbacks when appropriate. */
golem_status golem_admission_publish_work(golem_document_store *store,
                                          const golem_digest *namespace_id,
                                          const golem_admission_ticket *ticket,
                                          golem_digest *receipt);
/* Trusted host reconciliation only: proof must attest observed termination or
 * proven non-execution for this exact token. An arbitrary digest is not authority.
 * Reconcile required tickets have a NEW epoch; stale acknowledgments are rejected.
 * Settling is durable before release, and duplicate same-proof settle/release is
 * idempotent. Parent settlement/release is denied while children remain live. */
golem_status golem_admission_settle(golem_admission *admission, golem_admission_token token,
                                    golem_digest termination_receipt);
golem_status golem_admission_release(golem_admission *admission, golem_admission_token token);

#ifdef __cplusplus
}
#endif
#endif
