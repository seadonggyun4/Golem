#include "internal.h"
golem_status golem_work_run_reenter(golem_work_run *run)
{
    if (run == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (run->status != GOLEM_WORK_FAILED) {
        return GOLEM_ERR_INVALID_STATE;
    }
    golem_status ownership = golem_core_ownership_check(run);
    if (ownership != GOLEM_OK) return ownership;
    golem_stage target;
    golem_status status = golem_stage_graph_reentry(&run->capsule->graph,
        run->latest.snapshot.stage, run->latest.snapshot.failure, &target);
    if (status != GOLEM_OK) {
        return status;
    }
    size_t index = golem_core_graph_index(&run->capsule->graph, target);
    /* Recovery must be able to rerun the entire invalidated suffix. */
    for (size_t i = index; i < run->capsule->graph.spec.count; ++i) {
        golem_stage stage = run->capsule->graph.spec.order[i];
        if (run->attempts[stage] >= run->max_attempts) {
            return GOLEM_ERR_ATTEMPT_LIMIT;
        }
    }
    /* Invalidate completion, not attempt history. */
    for (size_t i = index; i < run->capsule->graph.spec.count; ++i) {
        run->passed[i] = false;
    }
    run->position = index;
    run->status = GOLEM_WORK_READY;
    return GOLEM_OK;
}
