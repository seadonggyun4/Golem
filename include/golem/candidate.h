#ifndef GOLEM_CANDIDATE_H
#define GOLEM_CANDIDATE_H
#include "golem/execution.h"
#include "golem/admission.h"
#include "golem/workspace.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_CANDIDATE_MAX 8u

/* Trusted host bindings, never deserialize these capabilities from agent JSON.
 * Borrowed handles/strings must remain live for the entire serialized call.
 * Provision independent child Work stores and phase-31C workspaces first.
 * Build/temp roots are dedicated, existing canonical directories outside trees.
 * resolve("$target") is used only for target-check; workspace may be NULL there. */
typedef struct golem_candidate_member {
    golem_document_store *work;
    const golem_workspace_host *workspace;
    const char *work_root, *tree_root, *build_root, *temp_root;
    golem_digest environment;
} golem_candidate_member;
typedef struct golem_candidate_host {
    size_t size;
    uint32_t version;
    void *context;
    /* Must validate policy, live agent lease, permissions and request-specific
     * authority. finish additionally attests termination/nonexecution and billing;
     * select requires explicit user choice. Not a default-allow approval hook.
     * Called again before execution/settlement. Must not reenter parent APIs. */
    golem_status (*check)(void *, golem_bytes request);
    golem_status (*resolve)(void *, const char *candidate, golem_candidate_member *);
    /* Nonblocking, at most once: connect an already active agent using admission
     * begin, or a reviewed phase-30 worker using worker_start. The ticket MUST
     * reach RUNNING, with durable Work/session/runtime binding publication.
     * No implicit agent spawn. Host enforces descriptor/shell gates and exact
     * cwd/build/temp, CPU/memory/IO reservation in its shared worker pool.
     * Crash/failure after START_INTENT requires reconciliation, never redispatch. */
    golem_status (*start)(void *, const char *candidate, golem_admission *, const char *operation);
    /* Idempotent nonblocking cancellation request to the connected agent/worker.
     * Required for cancel after START_INTENT. Never implies observed termination. */
    golem_status (*cancel)(void *, const char *candidate);
} golem_candidate_host;

/* Current-agent connector. All bindings/options are trusted caller capabilities,
 * never agent-authored JSON. Borrowed immutable data must outlive the host and
 * every serialized call. No allocation, process spawn or implicit approval.
 * authorize must validate exact-request authority, including user selection and
 * trusted finish termination/billing; request_cancel must notify the real agent.
 * Neither callback may reenter candidate/admission APIs. No OS resource limits:
 * callers requiring physical containment must use a different executor. */
typedef struct golem_candidate_current_binding {
    const char *candidate, *session;
    golem_digest runtime_binding;
    golem_candidate_member member;
} golem_candidate_current_binding;
typedef struct golem_candidate_current_options {
    size_t size;
    uint32_t version;
    const golem_candidate_current_binding *bindings;
    size_t count;
    const golem_candidate_member *target; /* Optional, borrowed read-only target. */
    void *context;
    golem_status (*authorize)(void *, golem_bytes);
    golem_status (*request_cancel)(void *, const char *candidate, const char *session);
} golem_candidate_current_options;
/* Validates configuration and publishes a borrowed host view; output unchanged
 * on failure. start pins the queued Work/session/runtime, verifies the live Work
 * claim through the production publisher and durably enters RUNNING. A failed
 * or interrupted begin is never retried automatically. */
golem_status golem_candidate_current_host(const golem_candidate_current_options *options,
                                          golem_candidate_host *out);

/* Strict bounded v1 manifest. No I/O, side effects or authority; canonical JSON
 * member order is not normalized. Digest pins the validated manifest bytes as
 * parsed/serialized, not a signature. Output unchanged on failure. */
golem_status golem_candidate_validate(golem_bytes manifest, golem_digest *digest,
                                      golem_diagnostic *diagnostic);
/* Freeze the comparison oracle BEFORE candidate dispatch. Requires issued v4/v5
 * checkpoint, one repository, includes executable and protected-file evidence.
 * Only candidate-root prefixes in argv are normalized; no arbitrary rewriting. */
golem_status golem_candidate_gate_digest(golem_document_store *child,
                                         const golem_digest *checkpoint, golem_digest *out,
                                         golem_diagnostic *diagnostic);
/* Borrowed inputs, owned reply freed with golem_execution_reply_free. Parent's
 * lifetime exclusive Work lock serializes mutations. Keep one coordinator handle
 * per parent (no concurrent calls). Errors may leave durable intents; reopen and
 * inspect, never retry start blindly. Read-only status needs no host/admission.
 * Mutations require host capabilities. Comparison needs resolve but never grants
 * completion/merge/push. Resources are cooperative reservations, not an OS sandbox.
 * One attempt per candidate in v1; retries require a NEW budgeted group/candidate. */
golem_status golem_candidate_call(golem_document_store *parent, const golem_candidate_host *host,
                                  golem_admission *admission, golem_bytes request,
                                  golem_execution_reply *out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
