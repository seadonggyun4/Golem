#include "../optimization/internal.h"

bool golem_optimization_fallback_valid(const golem_fallback_policy *p)
{
    return p != NULL && (p->triggers & ~(uint32_t)GOLEM_FALLBACK_ON_ALL) == 0;
}
golem_status golem_fallback_check(const golem_fallback_policy *p,
    golem_fallback_trigger trigger, uint32_t used, golem_effect effect, bool *out)
{
    if (!golem_optimization_fallback_valid(p) || out == NULL ||
        trigger < GOLEM_FALLBACK_NONE || trigger > GOLEM_FALLBACK_QUALITY_FAILURE ||
        effect < GOLEM_EFFECT_UNKNOWN || effect > GOLEM_EFFECT_EXTERNAL)
        return GOLEM_ERR_INVALID_ARGUMENT;
    bool allowed = false;
    if (trigger >= GOLEM_FALLBACK_UNAVAILABLE && trigger <= GOLEM_FALLBACK_BUDGET_PRESSURE &&
        used < p->max_per_stage && effect != GOLEM_EFFECT_UNKNOWN &&
        (!p->local_only || effect == GOLEM_EFFECT_LOCAL))
        allowed = (p->triggers & (1u << ((unsigned)trigger - 1))) != 0;
    *out = allowed; return GOLEM_OK;
}
