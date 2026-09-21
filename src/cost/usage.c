#include "internal.h"

static void fields(const golem_token_usage *u, uint64_t v[5])
{
    v[0] = u->input_tokens; v[1] = u->cached_input_tokens; v[2] = u->output_tokens;
    v[3] = u->reasoning_tokens; v[4] = u->tool_calls;
}
golem_status golem_token_usage_add(const golem_token_usage *a,
    const golem_token_usage *b, golem_token_usage *out)
{
    if (a == NULL || b == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    uint64_t x[5], y[5]; fields(a, x); fields(b, y);
    for (size_t i = 0; i < 5; ++i) {
        if (y[i] > UINT64_MAX - x[i]) return GOLEM_ERR_OVERFLOW;
        x[i] += y[i];
    }
    *out = (golem_token_usage){x[0], x[1], x[2], x[3], x[4]};
    return GOLEM_OK;
}
golem_status golem_cost_calculate(const golem_token_usage *usage,
    const golem_cost_rates *rates, uint64_t *nano_cost)
{
    if (usage == NULL || rates == NULL || nano_cost == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    uint64_t u[5], r[5], sum = 0; fields(usage, u); fields(&rates->nano_per_unit, r);
    for (size_t i = 0; i < 5; ++i) {
        if (r[i] != 0 && u[i] > (UINT64_MAX - sum) / r[i]) return GOLEM_ERR_OVERFLOW;
        sum += u[i] * r[i];
    }
    *nano_cost = sum; return GOLEM_OK;
}
bool golem_cost_amount_valid(const golem_cost_amount *a)
{
    if (a == NULL || (!a->cost_known && a->nano_cost != 0)) return false;
    uint64_t u[5]; fields(&a->usage, u);
    for (size_t i = 0; i < 5; ++i) if (!a->usage_known && u[i] != 0) return false;
    return true;
}
golem_status golem_cost_amount_add(const golem_cost_amount *a,
    const golem_cost_amount *b, golem_cost_amount *out)
{
    golem_cost_amount sum = {0};
    golem_status status = golem_token_usage_add(&a->usage, &b->usage, &sum.usage);
    if (status != GOLEM_OK) return status;
    if (b->nano_cost > UINT64_MAX - a->nano_cost) return GOLEM_ERR_OVERFLOW;
    sum.nano_cost = a->nano_cost + b->nano_cost;
    sum.usage_known = a->usage_known && b->usage_known;
    sum.cost_known = a->cost_known && b->cost_known;
    *out = sum; return GOLEM_OK;
}
