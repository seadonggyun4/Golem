#include "internal.h"
#include "descriptor_internal.h"
#include "../core/internal.h"
#include <string.h>

golem_status golem_adapter_create(const golem_adapter_ops *ops, void *context,
    const golem_allocator *allocator, golem_adapter **out)
{
    if (ops == NULL || ops->probe == NULL || ops->run_stage == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status status = golem_allocator_validate(allocator);
    if (status != GOLEM_OK) return status;
    void *memory;
    status = golem_allocator_alloc(allocator, sizeof(golem_adapter), &memory);
    if (status != GOLEM_OK) return status;
    golem_adapter *a = memory;
    *a = (golem_adapter){*ops, context, allocator == NULL ? golem_allocator_default() : *allocator};
    *out = a; return GOLEM_OK;
}
void golem_adapter_free(golem_adapter *a)
{
    if (a != NULL) (void)golem_allocator_free(&a->allocator, a);
}
golem_status golem_adapter_probe(const golem_adapter *a, golem_adapter_capability *out, golem_diagnostic *d)
{
    if (a == NULL || out == NULL) return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    golem_adapter_capability c = {0};
    golem_status s = a->ops.probe(a->context, &c, d);
    if (s == GOLEM_OK) s = golem_adapter_capability_valid(&c);
    if (s == GOLEM_OK) *out = c;
    return golem_adapter_report(d, s);
}
static golem_status dispatch(golem_adapter *a, golem_work_run *run,
    const golem_adapter_request *r, golem_evidence_store *store, const golem_harness_guard *guard,
    golem_adapter_result *out, golem_diagnostic *d)
{
    if (a == NULL || run == NULL || store == NULL || out == NULL) return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    golem_status s = golem_adapter_request_valid(r);
    if (s != GOLEM_OK) return golem_adapter_report(d, s);
    if (run->status != GOLEM_WORK_RUNNING || run->latest.adapter_dispatched)
        return golem_adapter_report(d, GOLEM_ERR_INVALID_STATE);
    s = golem_core_ownership_check(run);
    if (s != GOLEM_OK) return golem_adapter_report(d, s);
    if (strcmp(run->id, r->run_id) != 0) return golem_adapter_report(d, GOLEM_ERR_IDENTITY_MISMATCH);
    if (r->stage != run->latest.snapshot.stage || r->sequence != run->sequence || r->attempt != run->latest.snapshot.attempt)
        return golem_adapter_report(d, GOLEM_ERR_STALE_RESULT);
    if (run->latest.optimized_binding &&
        (strcmp(run->latest.admitted_route, r->adapter_id) != 0 ||
         memcmp(&run->latest.admitted_context, &r->context.digest, sizeof(r->context.digest)) != 0 ||
         memcmp(&run->latest.admitted_predecessor, &r->predecessor, sizeof(r->predecessor)) != 0))
        return golem_adapter_report(d, GOLEM_ERR_IDENTITY_MISMATCH);
    golem_adapter_capability c;
    s = golem_adapter_probe(a, &c, d);
    if (s != GOLEM_OK) return s;
    if (strcmp(c.adapter_id, r->adapter_id) != 0) return golem_adapter_report(d, GOLEM_ERR_IDENTITY_MISMATCH);
    if ((c.stages & (1u << r->stage)) == 0 ||
        (c.effect == GOLEM_EFFECT_EXTERNAL && run->latest.admitted_effect != GOLEM_EFFECT_EXTERNAL))
        return golem_adapter_report(d, GOLEM_ERR_POLICY_DENIED);
    s = golem_adapter_inputs_verify(r, store);
    if (s != GOLEM_OK) return golem_adapter_report(d, s);
    if (guard != NULL) {
        s = golem_harness_guard_check(guard, r, &c, store);
        if (s != GOLEM_OK) return golem_adapter_report(d, s);
    }
    s = golem_core_ownership_check(run);
    if (s != GOLEM_OK) return golem_adapter_report(d, s);
    /* Callback may have effects even when its result is lost/invalid. */
    run->latest.adapter_dispatched = true;
    golem_adapter_result result = {0};
    s = a->ops.run_stage(a->context, r, store, &result, d);
    golem_status ownership = golem_core_ownership_check(run);
    if (ownership != GOLEM_OK) return golem_adapter_report(d, ownership);
    if (s == GOLEM_OK) s = golem_adapter_result_validate(r, &result);
    if (s == GOLEM_OK && c.simulation != result.simulation) s = GOLEM_ERR_IDENTITY_MISMATCH;
    uint64_t size;
    if (s == GOLEM_OK) s = golem_evidence_verify(store, &result.evidence.digest, &size, d);
    if (s == GOLEM_OK && size != result.evidence.size) s = GOLEM_ERR_SIZE_MISMATCH;
    if (s == GOLEM_OK && guard != NULL) s = golem_harness_guard_check(guard, r, &c, store);
    if (s == GOLEM_OK) s = golem_core_ownership_check(run);
    if (s == GOLEM_OK) *out = result;
    return golem_adapter_report(d, s);
}
golem_status golem_adapter_dispatch(golem_adapter *a, golem_work_run *run,
    const golem_adapter_request *r, golem_evidence_store *store, golem_adapter_result *out, golem_diagnostic *d)
{
    return dispatch(a, run, r, store, NULL, out, d);
}
golem_status golem_adapter_dispatch_checked(golem_adapter *a, golem_work_run *run,
    const golem_adapter_request *r, golem_evidence_store *store, const golem_harness_guard *guard,
    golem_adapter_result *out, golem_diagnostic *d)
{
    if (!guard) return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    return dispatch(a, run, r, store, guard, out, d);
}
