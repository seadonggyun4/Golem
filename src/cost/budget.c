#include "internal.h"
bool golem_cost_budget_valid(const golem_budget *b)
{
    return b != NULL && (b->enabled & ~(uint32_t)GOLEM_BUDGET_ALL) == 0;
}
static golem_cost_amount masked(const golem_cost_amount *a, uint32_t enabled)
{
    golem_cost_amount m = *a;
    if ((enabled & GOLEM_BUDGET_INPUT) == 0) m.usage.input_tokens = 0;
    if ((enabled & GOLEM_BUDGET_CACHED_INPUT) == 0) m.usage.cached_input_tokens = 0;
    if ((enabled & GOLEM_BUDGET_OUTPUT) == 0) m.usage.output_tokens = 0;
    if ((enabled & GOLEM_BUDGET_REASONING) == 0) m.usage.reasoning_tokens = 0;
    if ((enabled & GOLEM_BUDGET_TOOLS) == 0) m.usage.tool_calls = 0;
    if ((enabled & GOLEM_BUDGET_COST) == 0) m.nano_cost = 0;
    return m;
}
golem_status golem_cost_budget_admit(const golem_budget *b,
    const golem_cost_amount *prior, const golem_cost_amount *planned)
{
    if (b->enabled == 0) return GOLEM_OK;
    /* Only constrained dimensions participate in actual + next estimate. */
    golem_cost_amount a = masked(prior, b->enabled), p = masked(planned, b->enabled), sum;
    golem_status s = golem_cost_amount_add(&a, &p, &sum);
    return s == GOLEM_OK ? golem_budget_check(b, &sum) : s;
}
golem_status golem_budget_check(const golem_budget *b, const golem_cost_amount *a)
{
    if (!golem_cost_budget_valid(b) || a == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (((b->enabled & 31u) != 0 && !a->usage_known) ||
        ((b->enabled & GOLEM_BUDGET_COST) != 0 && !a->cost_known)) return GOLEM_ERR_COST_INCOMPLETE;
    uint64_t values[] = {a->usage.input_tokens, a->usage.cached_input_tokens, a->usage.output_tokens,
        a->usage.reasoning_tokens, a->usage.tool_calls, a->nano_cost};
    uint64_t limits[] = {b->limits.input_tokens, b->limits.cached_input_tokens, b->limits.output_tokens,
        b->limits.reasoning_tokens, b->limits.tool_calls, b->nano_cost_limit};
    for (size_t i = 0; i < 6; ++i)
        if ((b->enabled & (1u << i)) != 0 && values[i] > limits[i]) return GOLEM_ERR_BUDGET_EXHAUSTED;
    return GOLEM_OK;
}
