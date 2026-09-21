#ifndef GOLEM_CORE_INTERNAL_H
#define GOLEM_CORE_INTERNAL_H
#include "golem/core.h"
#include "golem/cost.h"
#include "golem/policy.h"
#include "golem/evidence.h"
struct golem_stage_graph {
    golem_graph_spec spec;
    golem_allocator allocator;
};
struct golem_work_capsule {
    golem_allocator allocator;
    golem_capsule_spec spec;
    struct golem_stage_graph graph;
    char *id;
    char *goal;
    char **lists[4];
};
struct golem_stage_run {
    golem_stage_snapshot snapshot;
    golem_effect admitted_effect;
    bool adapter_dispatched;
    bool optimized_binding;
    char admitted_route[GOLEM_COST_TEXT_CAPACITY];
    golem_digest admitted_context, admitted_predecessor;
};
struct golem_work_run {
    golem_status (*ownership_check)(void *context);
    void *ownership_context;
    golem_allocator allocator;
    golem_cost_ledger *cost;
    struct golem_optimizer_state *optimization;
    char *id;
    golem_work_capsule *capsule;
    golem_work_status status;
    size_t position;
    bool passed[GOLEM_STAGE_COUNT];
    uint32_t attempts[GOLEM_STAGE_COUNT];
    uint32_t max_attempts;
    uint64_t sequence;
    struct golem_stage_run latest;
};
bool golem_core_stage_valid(golem_stage stage);
golem_status golem_core_ownership_check(const golem_work_run *run);
golem_status golem_core_begin_authorized(golem_work_run *run,
    const golem_stage_permission_request *request, const golem_cost_amount *estimate,
    golem_stage_snapshot *out, golem_policy_decision *decision, golem_diagnostic *diagnostic);
bool golem_core_failure_valid(golem_failure failure);
bool golem_core_failure_blocks(golem_failure failure);
size_t golem_core_graph_index(const golem_stage_graph *graph, golem_stage stage);
char *golem_core_string_clone(const char *source, const golem_allocator *allocator);
golem_status golem_core_report(golem_diagnostic *diagnostic,
    golem_status status, const char *message);
#endif
