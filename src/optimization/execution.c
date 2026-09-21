#include "internal.h"
#include "../core/internal.h"
#include <string.h>

static golem_status report(golem_diagnostic *d, golem_status status)
{
    if (d != NULL) (void)golem_diagnostic_set(d, status, GOLEM_DIAGNOSTIC_NO_OFFSET, NULL);
    return status;
}
golem_status golem_work_run_begin_optimized(golem_work_run *run,
    const golem_optimization_context *context, const golem_optimization_proposal *proposal,
    const golem_optimization_approval *approval, golem_stage_snapshot *stage,
    golem_optimization_decision *decision, golem_diagnostic *diagnostic)
{
    if (run == NULL || approval == NULL || stage == NULL ||
        approval->authorization < GOLEM_AUTHORIZATION_NONE || approval->authorization > GOLEM_AUTHORIZATION_REJECTED)
        return report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT);
    golem_optimization_decision selected;
    golem_status status = golem_work_run_optimization_evaluate(run, context, proposal, &selected);
    if (status != GOLEM_OK) return report(diagnostic, status);
    if (selected.verdict == GOLEM_OPTIMIZATION_REJECT) {
        if (decision != NULL) *decision = selected;
        return report(diagnostic, GOLEM_ERR_OPTIMIZATION_REJECTED);
    }
    if (approval->authorization == GOLEM_AUTHORIZATION_GRANTED &&
        (memchr(approval->route_id, '\0', sizeof(approval->route_id)) == NULL || strcmp(approval->route_id, selected.route_id) != 0))
        return report(diagnostic, GOLEM_ERR_IDENTITY_MISMATCH);
    golem_stage_permission_request request = {run->id, context->stage, context->sequence, context->attempt,
        selected.effect, approval->authorization};
    status = golem_core_begin_authorized(run, &request, &selected.expected, stage, NULL, diagnostic);
    if (status == GOLEM_OK) {
        run->latest.optimized_binding = true;
        strcpy(run->latest.admitted_route, selected.route_id);
        run->latest.admitted_context = context->context_digest;
        run->latest.admitted_predecessor = context->predecessor_digest;
    }
    if (status == GOLEM_OK && selected.selected_kind == GOLEM_OPTIMIZATION_FALLBACK)
        ++run->optimization->fallbacks[context->stage];
    if (decision != NULL && (status == GOLEM_OK || status == GOLEM_ERR_APPROVAL_REQUIRED || status == GOLEM_ERR_POLICY_DENIED))
        *decision = selected;
    return status;
}
