#ifndef GOLEM_WORKSPACE_H
#define GOLEM_WORKSPACE_H
#include "golem/document.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_WORKSPACE_PATH_CAPACITY 4096u
typedef enum golem_workspace_operation {
    GOLEM_WORKSPACE_CREATE = 1,
    GOLEM_WORKSPACE_RESUME,
    GOLEM_WORKSPACE_ACTIVATE,
    GOLEM_WORKSPACE_SEAL,
    GOLEM_WORKSPACE_RETAIN,
    GOLEM_WORKSPACE_REMOVE
} golem_workspace_operation;
typedef enum golem_workspace_state {
    GOLEM_WORKSPACE_CREATING = 1,
    GOLEM_WORKSPACE_READY,
    GOLEM_WORKSPACE_ACTIVE,
    GOLEM_WORKSPACE_SEALED,
    GOLEM_WORKSPACE_RETAINED,
    GOLEM_WORKSPACE_REMOVING,
    GOLEM_WORKSPACE_REMOVED,
    GOLEM_WORKSPACE_ATTENTION
} golem_workspace_state;

/* Trusted host configuration, NOT agent-deserialized authority. Existing roots
 * must be canonical absolute directories with no symlink components. The repo
 * must be a main non-bare repository. worktree_root is normally the project's
 * .golem/worktrees; external roots require the SAME explicit host registration.
 * Registration is pinned on first create, including filesystem identities;
 * relocation/replacement is rejected, never implicitly migrated.
 * check must validate policy AND hold exclusive session/global admission for
 * the whole call. SEAL/RETAIN/REMOVE additionally require all workers reaped.
 * It is called again before Git effects. Returning OK is trusted authorization,
 * not an agent claim. Callback must not reenter the store. No default allow.
 * Serialize store calls. Quiescent, privately controlled Git config and roots
 * are required; this is not an OS sandbox against malicious same-user writers. */
typedef struct golem_workspace_host {
    size_t struct_size;
    uint32_t version;
    const char *repository_id;
    const char *repository_root;
    const char *worktree_root;
    golem_status (*check)(void *context, golem_workspace_operation operation,
                         const char *candidate);
    /* Mandatory bounded heartbeat/cancellation check during supervised Git.
     * Non-OK aborts/reaps the child and leaves the intent for explicit recovery. */
    golem_status (*pulse)(void *context);
    void *context;
} golem_workspace_host;
typedef struct golem_workspace_result {
    golem_workspace_state state;
    char path[GOLEM_WORKSPACE_PATH_CAPACITY];
    golem_digest receipt;
} golem_workspace_result;

/* All inputs borrowed for call; result is caller-owned and unchanged on error.
 * Requires an exclusive writable Work store. Candidate is ASCII [A-Za-z0-9_-]
 * (1..64). CREATE requires full lowercase 40/64 hex commit, never a mutable ref.
 * Other operations require base_commit=NULL. RETAIN requires a verified Work CAS
 * evidence digest; other operations require evidence=NULL. No allocation escapes.
 * CREATE copies no dirty input, uses detached HEAD, no hooks, configured filters,
 * submodule init or network fetch. Existing candidates are never adopted.
 * RESUME verifies recorded identity; interrupted create/remove returns ATTENTION
 * without retrying the side effect. ACTIVE resume never grants a new lease.
 * Cleanup is opt-in, non-force, and only for clean candidates still at base HEAD;
 * changed/ignored/untracked content and new commits are retained for review.
 * CAS and receipts are never removed. Failures may leave durable intent and Git
 * metadata: close/reopen and RESUME; never recursively delete leftovers.
 * Workspace receipts form a separate versioned CAS-linked ledger under the Work
 * lock; they do not assert document acceptance or add a completion event. */
golem_status golem_workspace_call(golem_document_store *store,
    const golem_workspace_host *host, golem_workspace_operation operation,
    const char *candidate, const char *base_commit, const golem_digest *evidence,
    golem_workspace_result *out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
