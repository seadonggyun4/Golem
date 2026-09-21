#include "internal.h"
#include "../core/internal.h"
#include "../cost/internal.h"
#include <string.h>

static bool text_valid(const char *s)
{
    return s[0] != '\0' && memchr(s, '\0', GOLEM_COST_TEXT_CAPACITY) != NULL;
}
static bool effect_valid(golem_effect e)
{
    return e >= GOLEM_EFFECT_UNKNOWN && e <= GOLEM_EFFECT_EXTERNAL;
}
static bool digest_equal(const golem_digest *a, const golem_digest *b)
{
    return memcmp(a->bytes, b->bytes, GOLEM_DIGEST_SIZE) == 0;
}
static bool digest_present(const golem_digest *a)
{
    static const golem_digest zero = {{0}};
    return !digest_equal(a, &zero);
}
static golem_status policy_valid(const golem_optimization_policy *p)
{
    if (p == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (p->version != GOLEM_OPTIMIZATION_VERSION) return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (!golem_optimization_fallback_valid(&p->fallback)) return GOLEM_ERR_INVALID_ARGUMENT;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i)
        if ((p->allowed[i] & ~(uint32_t)GOLEM_OPTIMIZE_ALL) != 0) return GOLEM_ERR_INVALID_ARGUMENT;
    return GOLEM_OK;
}
golem_status golem_optimization_policy_init(golem_optimization_policy *out)
{
    if (out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    *out = (golem_optimization_policy){0}; out->version = GOLEM_OPTIMIZATION_VERSION;
    return GOLEM_OK;
}
golem_status golem_work_run_optimization_enable(golem_work_run *run, const golem_optimization_policy *p)
{
    if (run == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status status = policy_valid(p);
    if (status != GOLEM_OK) return status;
    if (run->status != GOLEM_WORK_READY || run->sequence != 0 || run->cost == NULL || run->optimization != NULL)
        return GOLEM_ERR_INVALID_STATE;
    void *memory;
    status = golem_allocator_alloc(&run->allocator, sizeof(golem_optimizer_state), &memory);
    if (status != GOLEM_OK) return status;
    golem_optimizer_state *state = memory;
    *state = (golem_optimizer_state){0}; state->policy = *p;
    run->optimization = state; return GOLEM_OK;
}
golem_status golem_work_run_optimization_policy_get(const golem_work_run *run, golem_optimization_policy *out)
{
    if (run == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (run->optimization == NULL) return GOLEM_ERR_INVALID_STATE;
    *out = run->optimization->policy; return GOLEM_OK;
}
static golem_status route_valid(const golem_optimization_route *r)
{
    if (!text_valid(r->id) || !effect_valid(r->effect) || !golem_cost_amount_valid(&r->estimate))
        return GOLEM_ERR_INVALID_ARGUMENT;
    return r->estimate.cost_known && r->estimate.usage_known ? GOLEM_OK : GOLEM_ERR_COST_INCOMPLETE;
}
static golem_status bindings(const golem_work_run *run, const golem_optimization_context *c,
    const golem_optimization_proposal *p)
{
    if (c->run_id == NULL || !effect_valid(c->advisor_effect) ||
        !digest_present(&c->context_digest) || !digest_present(&c->requirements_digest) ||
        !golem_cost_amount_valid(&c->overhead) ||
        c->fallback_trigger < GOLEM_FALLBACK_NONE || c->fallback_trigger > GOLEM_FALLBACK_QUALITY_FAILURE)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (strcmp(run->id, c->run_id) != 0 || memcmp(run->cost->options.currency, c->currency, 4) != 0)
        return GOLEM_ERR_IDENTITY_MISMATCH;
    golem_stage_permission_request next;
    golem_status status = golem_work_run_permission_request(run, c->baseline.effect, &next, NULL);
    if (status != GOLEM_OK) return status;
    if (next.stage != c->stage || next.sequence != c->sequence || next.attempt != c->attempt)
        return GOLEM_ERR_STALE_RESULT;
    if (!c->overhead.cost_known || !c->overhead.usage_known) return GOLEM_ERR_COST_INCOMPLETE;
    status = route_valid(&c->baseline);
    if (status != GOLEM_OK || p == NULL) return status;
    if (p->version != GOLEM_OPTIMIZATION_VERSION) return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (p->run_id == NULL || p->kind < GOLEM_OPTIMIZATION_NOOP || p->kind > GOLEM_OPTIMIZATION_FALLBACK ||
        (p->kind != GOLEM_OPTIMIZATION_NOOP && !text_valid(p->route_id))) return GOLEM_ERR_INVALID_ARGUMENT;
    if (strcmp(c->run_id, p->run_id) != 0) return GOLEM_ERR_IDENTITY_MISMATCH;
    if (c->stage != p->stage || c->sequence != p->sequence || c->attempt != p->attempt ||
        !digest_equal(&c->context_digest, &p->context_digest) ||
        !digest_equal(&c->predecessor_digest, &p->predecessor_digest) ||
        !digest_equal(&c->requirements_digest, &p->requirements_digest)) return GOLEM_ERR_STALE_RESULT;
    return GOLEM_OK;
}
static golem_effect effect_union(golem_effect a, golem_effect b)
{
    if (a == GOLEM_EFFECT_UNKNOWN || b == GOLEM_EFFECT_UNKNOWN) return GOLEM_EFFECT_UNKNOWN;
    return a == GOLEM_EFFECT_EXTERNAL || b == GOLEM_EFFECT_EXTERNAL ? GOLEM_EFFECT_EXTERNAL : GOLEM_EFFECT_LOCAL;
}
static golem_status reject(golem_optimization_reason reason, golem_optimization_decision *out)
{
    golem_optimization_decision d = {0}; d.verdict = GOLEM_OPTIMIZATION_REJECT; d.reason = reason;
    *out = d; return GOLEM_OK;
}
static golem_status choose(const golem_optimization_context *c, const golem_optimization_route *r,
    golem_optimization_kind kind, golem_optimization_verdict verdict, golem_optimization_reason reason,
    golem_optimization_decision *out)
{
    golem_optimization_decision d = {0}; d.verdict = verdict; d.reason = reason; d.selected_kind = kind;
    memcpy(d.route_id, r->id, strlen(r->id) + 1);
    d.effect = effect_union(effect_union(c->baseline.effect, r->effect), c->advisor_effect);
    golem_status status = golem_cost_amount_add(&r->estimate, &c->overhead, &d.expected);
    if (status != GOLEM_OK) return status;
    if (verdict == GOLEM_OPTIMIZATION_APPLY && c->baseline.estimate.nano_cost > d.expected.nano_cost)
        d.savings_nano = c->baseline.estimate.nano_cost - d.expected.nano_cost;
    *out = d; return GOLEM_OK;
}
static golem_status baseline(const golem_optimization_context *c, golem_optimization_reason reason,
    golem_optimization_decision *out)
{
    if (!c->baseline_available) return reject(GOLEM_OPTIMIZATION_BASELINE_UNAVAILABLE, out);
    return choose(c, &c->baseline, GOLEM_OPTIMIZATION_NOOP, GOLEM_OPTIMIZATION_KEEP_BASELINE, reason, out);
}
golem_status golem_work_run_optimization_evaluate(const golem_work_run *run,
    const golem_optimization_context *c, const golem_optimization_proposal *p, golem_optimization_decision *out)
{
    if (run == NULL || c == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (run->optimization == NULL || run->cost == NULL) return GOLEM_ERR_INVALID_STATE;
    golem_status status = bindings(run, c, p);
    if (status != GOLEM_OK) return status;
    /* These host-observed failures require resolution outside optimization.
     * Even an absent/disabled advisor or NOOP must not resume the baseline. */
    if (c->fallback_trigger == GOLEM_FALLBACK_POLICY_DENIED ||
        c->fallback_trigger == GOLEM_FALLBACK_QUALITY_FAILURE)
        return reject(GOLEM_OPTIMIZATION_FALLBACK_FORBIDDEN, out);
    if (!c->baseline.verified || !digest_equal(&c->requirements_digest, &c->baseline.requirements_digest))
        return reject(GOLEM_OPTIMIZATION_QUALITY_UNVERIFIED, out);
    if (p == NULL) return baseline(c, GOLEM_OPTIMIZATION_NO_PROPOSAL, out);
    if (p->kind == GOLEM_OPTIMIZATION_NOOP) return baseline(c, GOLEM_OPTIMIZATION_EXPLICIT_NOOP, out);
    const golem_optimization_policy *policy = &run->optimization->policy;
    if ((policy->allowed[c->stage] & (1u << ((unsigned)p->kind - 1))) == 0)
        return baseline(c, GOLEM_OPTIMIZATION_DISABLED, out);
    status = route_valid(&c->candidate);
    if (status != GOLEM_OK) return status;
    if (strcmp(c->candidate.id, p->route_id) != 0 || strcmp(c->candidate.id, c->baseline.id) == 0)
        return GOLEM_ERR_IDENTITY_MISMATCH;
    if (!c->candidate.verified || !digest_equal(&c->requirements_digest, &c->candidate.requirements_digest))
        return reject(GOLEM_OPTIMIZATION_QUALITY_UNVERIFIED, out);
    if (p->kind == GOLEM_OPTIMIZATION_CACHE) {
        if (!c->cache_verified) return reject(GOLEM_OPTIMIZATION_CACHE_UNVERIFIED, out);
        golem_cache_result cache;
        status = golem_cache_break_even(&c->cache, &cache);
        if (status != GOLEM_OK) return status;
        if (cache.uncached_nano != c->baseline.estimate.nano_cost || cache.cached_nano != c->candidate.estimate.nano_cost)
            return GOLEM_ERR_IDENTITY_MISMATCH;
    }
    if (p->kind == GOLEM_OPTIMIZATION_FALLBACK) {
        bool allowed;
        status = golem_fallback_check(&policy->fallback, c->fallback_trigger,
            run->optimization->fallbacks[c->stage], c->candidate.effect, &allowed);
        if (status != GOLEM_OK) return status;
        if (!allowed) return reject(GOLEM_OPTIMIZATION_FALLBACK_FORBIDDEN, out);
    } else if (!c->baseline_available || c->fallback_trigger != GOLEM_FALLBACK_NONE) {
        /* Availability recovery must not evade fallback-specific controls by
         * relabelling the operation ROUTE or CACHE. */
        return reject(GOLEM_OPTIMIZATION_FALLBACK_FORBIDDEN, out);
    }
    golem_optimization_decision d;
    status = choose(c, &c->candidate, p->kind, GOLEM_OPTIMIZATION_APPLY, GOLEM_OPTIMIZATION_ACCEPTED, &d);
    if (status != GOLEM_OK) return status;
    if (d.expected.nano_cost >= c->baseline.estimate.nano_cost || d.savings_nano < policy->minimum_savings_nano)
        return baseline(c, GOLEM_OPTIMIZATION_NO_SAVINGS, out);
    *out = d; return GOLEM_OK;
}
