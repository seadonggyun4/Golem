#include "internal.h"
#include "golem/policy.h"
#include "../cost/internal.h"
golem_status golem_core_ownership_check(const golem_work_run *run)
{
    return run->ownership_check == NULL ? GOLEM_OK : run->ownership_check(run->ownership_context);
}
static golem_status run_create(const char *id, const golem_work_capsule *capsule,
    uint32_t max_attempts, const golem_allocator *allocator, golem_work_run **out)
{
    if (id == NULL || id[0] == '\0' || capsule == NULL || out == NULL || max_attempts == 0) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    void *memory;
    golem_status status = golem_allocator_alloc(allocator, sizeof(golem_work_run), &memory);
    if (status != GOLEM_OK) {
        return status;
    }
    golem_work_run *run = memory;
    *run = (golem_work_run){0};
    run->allocator = allocator == NULL ? golem_allocator_default() : *allocator;
    run->id = golem_core_string_clone(id, &run->allocator);
    if (run->id == NULL) {
        golem_work_run_free(run);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    status = golem_work_capsule_create_with_allocator(&capsule->spec, &run->allocator, &run->capsule, NULL);
    if (status != GOLEM_OK) {
        golem_work_run_free(run);
        return status;
    }
    run->max_attempts = max_attempts;
    run->status = GOLEM_WORK_READY;
    *out = run;
    return GOLEM_OK;
}
golem_status golem_work_run_create_with_allocator(const char *id, const golem_work_capsule *capsule,
    uint32_t max_attempts, const golem_allocator *allocator, golem_work_run **out,
    golem_diagnostic *diagnostic)
{
    golem_status status = golem_allocator_validate(allocator);
    if (status == GOLEM_OK) {
        status = run_create(id, capsule, max_attempts, allocator, out);
    }
    return golem_core_report(diagnostic, status, "work run creation failed");
}
golem_status golem_work_run_create(const char *id, const golem_work_capsule *capsule,
    uint32_t max_attempts, golem_work_run **out)
{
    return golem_work_run_create_with_allocator(id, capsule, max_attempts, NULL, out, NULL);
}
void golem_work_run_free(golem_work_run *run)
{
    if (run != NULL) {
        golem_cost_ledger_free(run->cost);
        (void)golem_allocator_free(&run->allocator, run->optimization);
        golem_work_capsule_free(run->capsule);
        (void)golem_allocator_free(&run->allocator, run->id);
        (void)golem_allocator_free(&run->allocator, run);
    }
}
const char *golem_work_run_id_borrow(const golem_work_run *run)
{
    return run == NULL ? NULL : run->id;
}
golem_status golem_work_run_snapshot_get(const golem_work_run *run, golem_work_snapshot *out)
{
    if (run == NULL || out == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    size_t count = run->capsule->graph.spec.count;
    golem_work_snapshot snapshot = {run->status, GOLEM_STAGE_NONE, 0, count};
    if (run->position < count) {
        snapshot.current_stage = run->capsule->graph.spec.order[run->position];
    }
    for (size_t i = 0; i < count; ++i) {
        snapshot.passed_count += run->passed[i] ? 1u : 0u;
    }
    *out = snapshot;
    return GOLEM_OK;
}
golem_status golem_work_run_attempts_get(const golem_work_run *run, golem_stage stage, uint32_t *out)
{
    if (run == NULL || out == NULL || !golem_core_stage_valid(stage) ||
        golem_core_graph_index(&run->capsule->graph, stage) == run->capsule->graph.spec.count) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = run->attempts[stage];
    return GOLEM_OK;
}
const golem_stage_run *golem_work_run_stage_borrow(const golem_work_run *run)
{
    return run == NULL || run->sequence == 0 ? NULL : &run->latest;
}
golem_status golem_work_run_begin(golem_work_run *run, bool external_effect, bool authorized, golem_stage_snapshot *out)
{
    if (out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_stage_permission_request request;
    golem_status status = golem_work_run_permission_request(run,
        external_effect ? GOLEM_EFFECT_EXTERNAL : GOLEM_EFFECT_LOCAL, &request, NULL);
    if (status != GOLEM_OK) return status;
    request.authorization = authorized ? GOLEM_AUTHORIZATION_GRANTED : GOLEM_AUTHORIZATION_NONE;
    status = golem_work_run_begin_authorized(run, &request, out, NULL, NULL);
    return status == GOLEM_ERR_APPROVAL_REQUIRED ? GOLEM_ERR_POLICY_DENIED : status;
}
golem_status golem_work_run_finish(golem_work_run *run, uint64_t sequence, golem_stage_status outcome, golem_failure failure, bool requirements_met)
{
    if (run == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (run->status != GOLEM_WORK_RUNNING) {
        return GOLEM_ERR_INVALID_STATE;
    }
    golem_status ownership = golem_core_ownership_check(run);
    if (ownership != GOLEM_OK) return ownership;
    if (sequence != run->sequence) {
        return GOLEM_ERR_STALE_RESULT;
    }
    if ((outcome != GOLEM_STAGE_PASSED && outcome != GOLEM_STAGE_FAILED) ||
        (outcome == GOLEM_STAGE_PASSED && failure != GOLEM_FAILURE_NONE) ||
        (outcome == GOLEM_STAGE_FAILED && (!golem_core_failure_valid(failure) || requirements_met))) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (outcome == GOLEM_STAGE_PASSED && !requirements_met) {
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    golem_stage_status next = golem_core_failure_blocks(failure) ? GOLEM_STAGE_BLOCKED : outcome;
    golem_status status = golem_stage_transition_validate(run->latest.snapshot.status, next);
    if (status != GOLEM_OK) {
        return status;
    }
    run->latest.snapshot.status = next;
    run->latest.snapshot.failure = failure;
    golem_cost_finish(run->cost, &run->latest.snapshot);
    if (next == GOLEM_STAGE_PASSED) {
        run->passed[run->position] = true;
        ++run->position;
        run->status = run->position == run->capsule->graph.spec.count ? GOLEM_WORK_SUCCEEDED : GOLEM_WORK_READY;
    } else {
        run->status = next == GOLEM_STAGE_BLOCKED ? GOLEM_WORK_BLOCKED : GOLEM_WORK_FAILED;
    }
    return GOLEM_OK;
}
golem_status golem_work_run_cancel(golem_work_run *run)
{
    if (run == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    golem_status ownership = golem_core_ownership_check(run);
    if (ownership != GOLEM_OK) return ownership;
    if (run->status == GOLEM_WORK_SUCCEEDED || run->status == GOLEM_WORK_CANCELLED) {
        return GOLEM_ERR_INVALID_STATE;
    }
    if (run->status == GOLEM_WORK_RUNNING) {
        run->latest.snapshot.status = GOLEM_STAGE_CANCELLED;
        golem_cost_finish(run->cost, &run->latest.snapshot);
    }
    run->status = GOLEM_WORK_CANCELLED;
    return GOLEM_OK;
}
