#ifndef GOLEM_REENTRY_H
#define GOLEM_REENTRY_H
#include "golem/execution.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Borrowed JSON input; owned non-NUL-terminated reply, released with
 * golem_execution_reply_free. Output unchanged on failure. Calls are serialized
 * by the document store lock. No process, provider, or implicit retry is started.
 * decide appends a durable policy-bounded proposal evaluation; status is read-only.
 * A decision is not permission to execute or proof of a causal explanation.
 * See docs/reentry.md. Close/reopen after uncertain I/O; retry the same key. */
golem_status golem_reentry_validate(golem_bytes request, golem_diagnostic *diagnostic);
golem_status golem_reentry_call(golem_document_store *store, golem_bytes request,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
/* Regenerate/project the recorded failure Markdown. sequence is 1-based.
 * project requires a writable store; it never replaces differing bytes. */
golem_status golem_reentry_report(golem_document_store *store, uint32_t sequence,
    bool project, golem_execution_reply *out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
