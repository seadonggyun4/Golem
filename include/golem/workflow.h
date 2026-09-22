#ifndef GOLEM_WORKFLOW_H
#define GOLEM_WORKFLOW_H
#include "golem/document.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_WORKFLOW_VERSION 1u
#define GOLEM_WORKFLOW_CONTEXT_MAX 16777216u
typedef enum golem_document_freshness {
    GOLEM_DOCUMENT_CURRENT = 0,
    GOLEM_DOCUMENT_STALE = 1,
    GOLEM_DOCUMENT_SUPERSEDED = 2
} golem_document_freshness;
typedef struct golem_dependency_node {
    const char *work_id, *document_id;
    uint32_t revision;
    golem_digest manifest_digest;
    const size_t *parents; /* indices in the supplied node array */
    size_t parent_count;
} golem_dependency_node;
/* Pure bounded DAG evaluation, independent of insertion order, filesystem and
 * scheduler. One Work per graph. Rejects cycles, duplicate revisions/edges,
 * cross-Work nodes and out-of-range parents. Latest revision is inferred, never
 * trusted from the caller. O(V log V + E) plus <=64 duplicate-edge checks/node.
 * Borrows inputs for call; outputs caller-owned, unchanged on failure. allocator
 * controls temporary graph storage. At most 4096 nodes/16384 edges. No recursion.
 * CURRENT means dependency-fresh, NOT content approval or execution authority. */
golem_status golem_document_graph_evaluate(const golem_dependency_node *nodes, size_t count,
    const golem_allocator *allocator, golem_document_freshness *states,
    size_t capacity, golem_diagnostic *diagnostic);
/* Store queries below borrow the handle, hold its existing lifetime lock, and
 * never mutate the registry. Serialize calls. Raw JSON UTF-8, no trailing NUL.
 * NULL/0 queries required size; short buffers untouched. required is set only on
 * OK/BUFFER_TOO_SMALL. Outputs/inputs must not alias. Internal allocations use
 * store allocator where practical; JSON dependency owns its allocations.
 * Proposals/manifests are not claims, leases, QA PASS or completion receipts. */
golem_status golem_workflow_select(golem_document_store *store, const char *scope_id,
    uint32_t revision, const char *mode, void *buffer, size_t capacity,
    size_t *required, golem_diagnostic *diagnostic);
golem_status golem_workflow_inputs(golem_document_store *store, const char *selection_id,
    const char *target_kind, const golem_digest *source_snapshot, uint64_t byte_budget,
    void *buffer, size_t capacity, size_t *required, golem_diagnostic *diagnostic);
golem_status golem_workflow_trace(golem_document_store *store, const char *document_id,
    uint32_t revision, void *buffer, size_t capacity, size_t *required,
    golem_diagnostic *diagnostic);
golem_status golem_workflow_next(golem_document_store *store, const char *selection_id,
    void *buffer, size_t capacity, size_t *required, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
