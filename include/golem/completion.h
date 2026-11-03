#ifndef GOLEM_COMPLETION_H
#define GOLEM_COMPLETION_H
#include "golem/execution.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Inputs are borrowed for the call. On success out owns non-NUL-terminated
 * bytes; release with golem_execution_reply_free. On error out is unchanged.
 * Store locking serializes calls. finalize requires a writable store and
 * records declared acceptance, not proof that all defects are absent.
 * resume is read-only: it never claims a lease or reruns a gate/agent.
 * Close/reopen after I/O uncertainty; retry finalize with the identical key.
 * Work v3 uses request v3 and the separate exact COMPLETION host scope.
 * It requires current QC4 acceptance; legacy finalize is rejected. No automatic
 * retry/repair is authorized for an uncertain v3 result. Historical receipt
 * retrieval is not current completion. See docs/intent-assurance-qc5-implementation.ko.md.
 * See docs/completion.md for legacy schema, limits and trust boundaries. */
golem_status golem_completion_validate(golem_bytes request, golem_diagnostic *diagnostic);
golem_status golem_completion_call(golem_document_store *store, golem_bytes request,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
/* Read immutable report, optionally restore it and referenced document
 * projections. No differing file is replaced. sequence is 1-based.
 * Historical report restoration does not assert current completion. */
golem_status golem_completion_report(golem_document_store *store, uint32_t sequence,
    bool project, golem_execution_reply *out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
