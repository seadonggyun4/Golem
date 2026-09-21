#ifndef GOLEM_LINEAGE_H
#define GOLEM_LINEAGE_H
#include "golem/core.h"
#include "golem/evidence.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_LINEAGE_VERSION 1
#define GOLEM_LINEAGE_MAX_STAGES 1024
#define GOLEM_LINEAGE_MAX_NODES 16384
#define GOLEM_LINEAGE_MAX_EDGES 65536
#define GOLEM_LINEAGE_MAX_RUN_ID 4096

typedef struct golem_lineage golem_lineage;
typedef uint32_t golem_lineage_id; /* 1-based within this graph; zero invalid. */
typedef enum golem_lineage_kind {
    GOLEM_LINEAGE_STAGE_INPUT = 1,
    GOLEM_LINEAGE_CONTEXT_BLOCK = 2,
    GOLEM_LINEAGE_TOOL_RESULT = 3,
    GOLEM_LINEAGE_ARTIFACT = 4,
    GOLEM_LINEAGE_EVIDENCE = 5
} golem_lineage_kind;
typedef struct golem_lineage_limits {
    uint32_t stages, nodes, edges;
} golem_lineage_limits;
typedef struct golem_lineage_stats {
    uint32_t stages, nodes, edges;
    bool has_open_stage;
} golem_lineage_stats;
typedef struct golem_lineage_node {
    golem_lineage_kind kind;
    uint64_t stage_sequence;
    golem_receipt content;
} golem_lineage_node;
typedef struct golem_lineage_stage {
    golem_stage_snapshot execution;
    golem_lineage_id input, last_node;
} golem_lineage_stage;

/* Append-only, single-WorkRun dependency DAG. Serialize mutations per graph.
 * Edges point from a derived node to earlier dependencies. IDs identify uses,
 * not content: equal digests in different roles/attempts remain distinct nodes.
 * Inputs borrow immutable storage for the call; outputs may not alias inputs or
 * graph storage. Failure preserves logical graph and outputs, except diagnostics
 * and required counts on BUFFER_TOO_SMALL. No lifecycle/policy authorization.
 * IDs/attempts must come from a coordinator assigning unique WorkRun IDs.
 * Limits are preallocated: begin/add/seal/query perform no heap allocations.
 * NULL limits = 64 stages, 1024 nodes, 4096 edges. All limits positive, bounded
 * by the MAX macros. run_id length is 1..MAX_RUN_ID, with no embedded NUL.
 * Creates an owned graph with copied ID/allocator; context outlives free.
 * No I/O in model/codec APIs. Matching free accepts NULL. */
golem_status golem_lineage_create(const char *run_id, const golem_lineage_limits *limits,
    const golem_allocator *allocator, golem_lineage **out, golem_diagnostic *diagnostic);
void golem_lineage_free(golem_lineage *graph);
/* Immutable borrowed ID until free. NULL graph returns NULL. */
const char *golem_lineage_run_id_borrow(const golem_lineage *graph);
golem_status golem_lineage_stats_get(const golem_lineage *graph, golem_lineage_stats *out);
golem_status golem_lineage_stage_get(const golem_lineage *graph, uint64_t sequence, golem_lineage_stage *out);
golem_status golem_lineage_node_get(const golem_lineage *graph, golem_lineage_id id, golem_lineage_node *out);

/* Begin captures the matching WorkRun's latest RUNNING attempt, in contiguous
 * sequence order starting at 1. Previous attempt must be sealed. Input receipt
 * becomes the first node. Parents are strictly ascending, unique IDs of EVIDENCE
 * nodes in earlier sealed stages. First attempt has no parents; all later ones
 * require >=1. Explicit selection supports retries/reentry; it does NOT prove
 * a selected predecessor is current/approved under runtime policy. */
golem_status golem_lineage_begin(golem_lineage *graph, const golem_work_run *run,
    const golem_receipt *input, const golem_lineage_id *parents, size_t count,
    golem_lineage_id *out, golem_diagnostic *diagnostic);
/* Non-input node in current open stage; >=1 strictly ascending parent IDs, all
 * in this same stage and already present. Every node thus reaches stage input.
 * Capacity exhaustion is BUFFER_TOO_SMALL, with no mutation or allocations. */
golem_status golem_lineage_add(golem_lineage *graph, golem_lineage_kind kind,
    const golem_receipt *content, const golem_lineage_id *parents, size_t count,
    golem_lineage_id *out, golem_diagnostic *diagnostic);
/* Captures matching terminal Core snapshot; >=1 EVIDENCE node is required.
 * Sealed stages/nodes cannot change, including on failure, cancel or reentry.
 * Does not verify CAS, finish the Core run, or attest acceptance. */
golem_status golem_lineage_seal(golem_lineage *graph, const golem_work_run *run,
    golem_diagnostic *diagnostic);

/* Caller-owned ID arrays; required is the element count. NULL/0 size query.
 * Short buffers untouched; required set on OK/BUFFER_TOO_SMALL only. Results
 * sorted by ascending ID, without duplicates; zero results need no buffer.
 * predecessors(false): direct input evidence; true: all reachable prior evidence
 * through the DAG. O(nodes+edges), bounded stack scratch, no recursion/heap. */
golem_status golem_lineage_parents(const golem_lineage *graph, golem_lineage_id id,
    golem_lineage_id *buffer, size_t capacity, size_t *required);
golem_status golem_lineage_predecessors(const golem_lineage *graph, uint64_t sequence,
    bool transitive, golem_lineage_id *buffer, size_t capacity, size_t *required);

/* Sealed, nonempty graphs only. Canonical little-endian HWLG v1, deterministic
 * for an append history (not canonical across isomorphic node reorderings).
 * Encode writes caller buffer; required byte count on OK/short buffer only.
 * Decode strictly validates bounds, identities, DAG ordering and receipts before
 * publishing an owned graph. No borrowed encoded bytes survive return. Decoded
 * graph capacity equals encoded counts (an immutable checkpoint for inspection).
 * All allocations use allocator (NULL=default); failure preserves *out. */
golem_status golem_lineage_encode(const golem_lineage *graph, void *buffer, size_t capacity,
    size_t *required, golem_diagnostic *diagnostic);
golem_status golem_lineage_decode(golem_bytes bytes, const golem_allocator *allocator,
    golem_lineage **out, golem_diagnostic *diagnostic);
/* Verify every node's content digest and size; verified count only on success.
 * Store verifies targets then persists the graph; load verifies graph key, schema
 * and all targets before returning an owned graph. Neither operation changes Core
 * or journal. Expected graph key/run identity must come from a trusted caller;
 * digest integrity is not provenance or a transaction with mutable external files. */
golem_status golem_lineage_verify(const golem_lineage *graph, golem_evidence_store *store,
    size_t *verified, golem_diagnostic *diagnostic);
golem_status golem_lineage_store(const golem_lineage *graph, golem_evidence_store *store,
    golem_digest *out, golem_diagnostic *diagnostic);
golem_status golem_lineage_load(golem_evidence_store *store, const golem_digest *key,
    const golem_allocator *allocator, golem_lineage **out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
