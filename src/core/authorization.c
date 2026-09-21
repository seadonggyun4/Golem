#include "internal.h"
#include "golem/policy.h"
#include "../cost/internal.h"
#include <string.h>

static golem_status report(golem_diagnostic *d, golem_status status, const char *message)
{
    if (d != NULL) (void)golem_diagnostic_set(d, status, GOLEM_DIAGNOSTIC_NO_OFFSET, message);
    return status;
}
golem_status golem_work_run_permission_request(const golem_work_run *run, golem_effect effect,
    golem_stage_permission_request *out, golem_diagnostic *d)
{
    if (run == NULL || out == NULL || effect < GOLEM_EFFECT_UNKNOWN || effect > GOLEM_EFFECT_EXTERNAL)
        return report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (run->status != GOLEM_WORK_READY) return report(d, GOLEM_ERR_INVALID_STATE, NULL);
    golem_stage stage = run->capsule->graph.spec.order[run->position];
    if (run->sequence == UINT64_MAX || run->attempts[stage] >= run->max_attempts)
        return report(d, GOLEM_ERR_ATTEMPT_LIMIT, NULL);
    *out = (golem_stage_permission_request){run->id, stage, run->sequence + 1, run->attempts[stage] + 1,
        effect, GOLEM_AUTHORIZATION_NONE};
    return report(d, GOLEM_OK, NULL);
}
golem_status golem_core_begin_authorized(golem_work_run *run,
    const golem_stage_permission_request *r, const golem_cost_amount *estimate, golem_stage_snapshot *out,
    golem_policy_decision *decision, golem_diagnostic *d)
{
    if (run == NULL || r == NULL || out == NULL || r->run_id == NULL ||
        r->stage < GOLEM_STAGE_PLANNING || r->stage >= GOLEM_STAGE_COUNT || r->sequence == 0 || r->attempt == 0 ||
        r->authorization < GOLEM_AUTHORIZATION_NONE || r->authorization > GOLEM_AUTHORIZATION_REJECTED)
        return report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (strcmp(run->id, r->run_id) != 0) return report(d, GOLEM_ERR_IDENTITY_MISMATCH, NULL);
    golem_stage_permission_request expected;
    golem_status status = golem_work_run_permission_request(run, r->effect, &expected, d);
    if (status != GOLEM_OK) return status;
    if (r->stage != expected.stage || r->sequence != expected.sequence || r->attempt != expected.attempt)
        return report(d, GOLEM_ERR_STALE_RESULT, "permission request does not match next attempt");
    golem_policy_request request = {r->stage, r->effect, r->authorization};
    golem_policy_decision evaluated;
    status = golem_autonomy_evaluate(run->capsule->spec.permissions[r->stage], &request, &evaluated);
    if (status != GOLEM_OK) return report(d, status, NULL);
    if (evaluated.verdict != GOLEM_POLICY_ALLOW) {
        if (decision != NULL) *decision = evaluated;
        status = evaluated.verdict == GOLEM_POLICY_ASK ? GOLEM_ERR_APPROVAL_REQUIRED : GOLEM_ERR_POLICY_DENIED;
        return report(d, status, golem_policy_reason_name(evaluated.reason));
    }
    golem_stage_snapshot started = {r->stage, GOLEM_STAGE_RUNNING, GOLEM_FAILURE_NONE,
        expected.attempt, expected.sequence};
    status = golem_core_ownership_check(run);
    if (status != GOLEM_OK) return report(d, status, NULL);
    status = golem_cost_begin(run->cost, &started, estimate);
    if (status != GOLEM_OK) return report(d, status, NULL);
    if (decision != NULL) *decision = evaluated;
    /* Only this gate advances the identity/counters. Policy outcomes above are
     * observational; ASK/DENY do not create a failed or blocked StageRun. */
    run->sequence = expected.sequence;
    run->attempts[r->stage] = expected.attempt;
    run->latest.snapshot = started;
    run->latest.admitted_effect = r->effect;
    run->latest.adapter_dispatched = false;
    run->latest.optimized_binding = false;
    run->status = GOLEM_WORK_RUNNING;
    *out = run->latest.snapshot;
    return report(d, GOLEM_OK, NULL);
}
golem_status golem_work_run_begin_authorized(golem_work_run *run,
    const golem_stage_permission_request *r, golem_stage_snapshot *out,
    golem_policy_decision *decision, golem_diagnostic *d)
{
    return golem_core_begin_authorized(run, r, NULL, out, decision, d);
}
