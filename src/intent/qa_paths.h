#ifndef GOLEM_INTENT_QA_PATHS_H
#define GOLEM_INTENT_QA_PATHS_H
#include "review.h"
/* Pure QC2 model inspection. No publication, grant, result or completion.
 * Unsupported typed referents remain explicit blockers, never trusted labels. */
typedef struct gi_qa_paths_inputs {
    gi_review_inputs baseline;
    golem_bytes applicability, obligations, mapping, execution_contract;
} gi_qa_paths_inputs;
typedef struct gi_qa_paths_result {
    golem_digest applicability, obligations, mapping, execution_contract;
    size_t requirements, rows, obligations_count, native_obligations, semantic_obligations;
    size_t undecided, unsupported_references;
    bool structurally_complete, execution_authorized, qa_accepted;
} gi_qa_paths_result;
/* Failure leaves output unchanged. GOLEM_OK means structure only; unsupported
 * reference count must be zero before any future gate can consider acceptance.
 * This structure-only API leaves referents unresolved; gi_qa_paths_resolve
 * performs typed byte and current host-evidence resolution. */
golem_status gi_qa_paths_inspect(const gi_qa_paths_inputs *, gi_qa_paths_result *, golem_diagnostic *);
#endif
