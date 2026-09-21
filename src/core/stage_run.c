#include "internal.h"
golem_status golem_stage_transition_validate(golem_stage_status from, golem_stage_status to)
{
    if (from < GOLEM_STAGE_PENDING || from > GOLEM_STAGE_CANCELLED ||
        to < GOLEM_STAGE_PENDING || to > GOLEM_STAGE_CANCELLED) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (from == GOLEM_STAGE_PENDING &&
        (to == GOLEM_STAGE_RUNNING || to == GOLEM_STAGE_BLOCKED || to == GOLEM_STAGE_CANCELLED)) {
        return GOLEM_OK;
    }
    if (from == GOLEM_STAGE_RUNNING &&
        (to == GOLEM_STAGE_PASSED || to == GOLEM_STAGE_FAILED ||
         to == GOLEM_STAGE_BLOCKED || to == GOLEM_STAGE_CANCELLED)) {
        return GOLEM_OK;
    }
    return GOLEM_ERR_INVALID_STATE;
}
golem_status golem_stage_run_snapshot_get(const golem_stage_run *stage, golem_stage_snapshot *out)
{
    if (stage == NULL || out == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = stage->snapshot;
    return GOLEM_OK;
}
