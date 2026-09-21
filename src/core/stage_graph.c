#include "internal.h"

bool golem_core_stage_valid(golem_stage stage)
{
    return stage >= GOLEM_STAGE_PLANNING && stage < GOLEM_STAGE_COUNT;
}
bool golem_core_failure_valid(golem_failure failure)
{
    return failure > GOLEM_FAILURE_NONE && failure < GOLEM_FAILURE_COUNT;
}
bool golem_core_failure_blocks(golem_failure failure)
{
    return failure == GOLEM_FAILURE_POLICY_DENIED ||
           failure == GOLEM_FAILURE_STALE_LEASE ||
           failure == GOLEM_FAILURE_BUDGET_EXHAUSTED;
}
size_t golem_core_graph_index(const golem_stage_graph *graph, golem_stage stage)
{
    for (size_t i = 0; i < graph->spec.count; ++i) {
        if (graph->spec.order[i] == stage) {
            return i;
        }
    }
    return graph->spec.count;
}
const char *golem_stage_name(golem_stage stage)
{
    static const char *const names[] = {
        "planning", "ux", "publishing", "development", "qa", "audit"
    };
    return golem_core_stage_valid(stage) ? names[stage] : "unknown";
}
golem_status golem_stage_graph_default_spec(golem_graph_spec *out)
{
    if (out == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    golem_graph_spec spec = {0};
    spec.count = GOLEM_STAGE_COUNT;
    for (size_t i = 0; i < spec.count; ++i) {
        spec.order[i] = (golem_stage)i;
    }
    for (size_t i = 0; i < GOLEM_FAILURE_COUNT; ++i) {
        spec.reentry[i] = GOLEM_STAGE_NONE;
    }
    spec.reentry[GOLEM_FAILURE_PLANNING_GAP] = GOLEM_STAGE_PLANNING;
    spec.reentry[GOLEM_FAILURE_UX_MISMATCH] = GOLEM_STAGE_UX;
    spec.reentry[GOLEM_FAILURE_PUBLISHING_GAP] = GOLEM_STAGE_PUBLISHING;
    spec.reentry[GOLEM_FAILURE_IMPLEMENTATION_DEFECT] = GOLEM_STAGE_DEVELOPMENT;
    spec.reentry[GOLEM_FAILURE_QA_FLAKE] = GOLEM_STAGE_QA;
    spec.reentry[GOLEM_FAILURE_AUDIT_GAP] = GOLEM_STAGE_PLANNING;
    *out = spec;
    return GOLEM_OK;
}
static golem_status graph_create(const golem_graph_spec *spec,
    const golem_allocator *allocator, golem_stage_graph **out)
{
    if (spec == NULL || out == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (spec->count == 0 || spec->count > GOLEM_STAGE_COUNT) {
        return GOLEM_ERR_INVALID_GRAPH;
    }
    bool seen[GOLEM_STAGE_COUNT] = {false};
    for (size_t i = 0; i < spec->count; ++i) {
        golem_stage stage = spec->order[i];
        if (!golem_core_stage_valid(stage) || seen[stage]) {
            return GOLEM_ERR_INVALID_GRAPH;
        }
        seen[stage] = true;
    }
    for (size_t i = 0; i < GOLEM_FAILURE_COUNT; ++i) {
        if (!golem_core_stage_valid(spec->reentry[i]) && spec->reentry[i] != GOLEM_STAGE_NONE) {
            return GOLEM_ERR_INVALID_GRAPH;
        }
    }
    void *memory;
    golem_status status = golem_allocator_alloc(allocator, sizeof(golem_stage_graph), &memory);
    if (status != GOLEM_OK) {
        return status;
    }
    golem_stage_graph *graph = memory;
    graph->allocator = allocator == NULL ? golem_allocator_default() : *allocator;
    graph->spec = *spec;
    *out = graph;
    return GOLEM_OK;
}
golem_status golem_stage_graph_create_with_allocator(const golem_graph_spec *spec,
    const golem_allocator *allocator, golem_stage_graph **out, golem_diagnostic *diagnostic)
{
    golem_status status = golem_allocator_validate(allocator);
    if (status == GOLEM_OK) {
        status = graph_create(spec, allocator, out);
    }
    return golem_core_report(diagnostic, status, "stage graph creation failed");
}
golem_status golem_stage_graph_create(const golem_graph_spec *spec, golem_stage_graph **out)
{
    return golem_stage_graph_create_with_allocator(spec, NULL, out, NULL);
}
void golem_stage_graph_free(golem_stage_graph *graph)
{
    if (graph != NULL) {
        (void)golem_allocator_free(&graph->allocator, graph);
    }
}
golem_status golem_stage_graph_spec_get(const golem_stage_graph *graph, golem_graph_spec *out)
{
    if (graph == NULL || out == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = graph->spec;
    return GOLEM_OK;
}
golem_status golem_stage_graph_next(const golem_stage_graph *graph, golem_stage from, golem_stage *out)
{
    if (graph == NULL || out == NULL || !golem_core_stage_valid(from)) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    size_t index = golem_core_graph_index(graph, from);
    if (index == graph->spec.count) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = index + 1 == graph->spec.count ? GOLEM_STAGE_NONE : graph->spec.order[index + 1];
    return GOLEM_OK;
}
golem_status golem_stage_graph_validate_transition(const golem_stage_graph *graph, golem_stage from, golem_stage to)
{
    golem_stage next;
    golem_status status = golem_stage_graph_next(graph, from, &next);
    if (status != GOLEM_OK) {
        return status;
    }
    return next == to ? GOLEM_OK : GOLEM_ERR_INVALID_STATE;
}
golem_status golem_stage_graph_reentry(const golem_stage_graph *graph, golem_stage from, golem_failure failure, golem_stage *out)
{
    if (graph == NULL || out == NULL || !golem_core_stage_valid(from) || !golem_core_failure_valid(failure)) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    size_t current = golem_core_graph_index(graph, from);
    if (current == graph->spec.count) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (golem_core_failure_blocks(failure)) {
        return GOLEM_ERR_POLICY_DENIED;
    }
    golem_stage target = failure == GOLEM_FAILURE_TIMEOUT ? from : graph->spec.reentry[failure];
    size_t index = golem_core_graph_index(graph, target);
    if (index == graph->spec.count || index > current) {
        return GOLEM_ERR_NO_REENTRY;
    }
    *out = target;
    return GOLEM_OK;
}
