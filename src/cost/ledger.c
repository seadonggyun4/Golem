#include "internal.h"
#include "../core/internal.h"
#include <string.h>

static bool currency_valid(const char c[4])
{
    return c[0] >= 'A' && c[0] <= 'Z' && c[1] >= 'A' && c[1] <= 'Z' &&
        c[2] >= 'A' && c[2] <= 'Z' && c[3] == '\0';
}
static bool text_valid(const char *s)
{
    return s[0] != '\0' && memchr(s, '\0', GOLEM_COST_TEXT_CAPACITY) != NULL;
}
static bool amount_equal(const golem_cost_amount *a, const golem_cost_amount *b)
{
    return a->usage.input_tokens == b->usage.input_tokens &&
        a->usage.cached_input_tokens == b->usage.cached_input_tokens &&
        a->usage.output_tokens == b->usage.output_tokens && a->usage.reasoning_tokens == b->usage.reasoning_tokens &&
        a->usage.tool_calls == b->usage.tool_calls && a->nano_cost == b->nano_cost &&
        a->usage_known == b->usage_known && a->cost_known == b->cost_known;
}
static bool report_equal(const golem_provider_usage *a, const golem_provider_usage *b)
{
    return strcmp(a->provider, b->provider) == 0 && strcmp(a->model, b->model) == 0 &&
        strcmp(a->price_revision, b->price_revision) == 0 && strcmp(a->currency, b->currency) == 0 &&
        amount_equal(&a->actual, &b->actual);
}
static golem_cost_amount known_zero(void)
{
    golem_cost_amount a = {0}; a.usage_known = true; a.cost_known = true; return a;
}
static golem_cost_entry *entry_find(const golem_cost_ledger *l, uint64_t sequence)
{
    if (sequence == 0 || sequence > l->entry_count) return NULL;
    return &l->entries[(size_t)sequence - 1].value;
}
static golem_cost_totals totals_view(const golem_cost_totals *raw)
{
    golem_cost_totals result = *raw;
    if (result.unsettled != 0) {
        result.actual.usage_known = false; result.actual.cost_known = false;
    }
    return result;
}
golem_status golem_cost_ledger_create(const golem_cost_options *o,
    const golem_allocator *a, golem_cost_ledger **out)
{
    if (o == NULL || !currency_valid(o->currency) || o->entry_capacity == 0 || o->report_capacity == 0 ||
        !golem_cost_budget_valid(&o->run_budget)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (o->version != GOLEM_COST_VERSION) return GOLEM_ERR_UNSUPPORTED_VERSION;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i)
        if (!golem_cost_budget_valid(&o->stage_budgets[i])) return GOLEM_ERR_INVALID_ARGUMENT;
    if (o->entry_capacity > SIZE_MAX / sizeof(golem_cost_entry_record) ||
        o->report_capacity > SIZE_MAX / sizeof(golem_cost_report_record)) return GOLEM_ERR_OVERFLOW;
    void *memory;
    golem_status s = golem_allocator_alloc(a, sizeof(golem_cost_ledger), &memory);
    if (s != GOLEM_OK) return s;
    golem_cost_ledger *l = memory;
    *l = (golem_cost_ledger){0}; l->allocator = *a; l->options = *o;
    l->totals.expected = known_zero(); l->totals.actual = known_zero();
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) l->stage_totals[i] = l->totals;
    s = golem_allocator_alloc(a, o->entry_capacity * sizeof(*l->entries), &memory);
    if (s == GOLEM_OK) {
        l->entries = memory;
        s = golem_allocator_alloc(a, o->report_capacity * sizeof(*l->reports), &memory);
        if (s == GOLEM_OK) l->reports = memory;
    }
    if (s != GOLEM_OK) { golem_cost_ledger_free(l); return s; }
    *out = l; return GOLEM_OK;
}
void golem_cost_ledger_free(golem_cost_ledger *l)
{
    if (l == NULL) return;
    (void)golem_allocator_free(&l->allocator, l->entries);
    (void)golem_allocator_free(&l->allocator, l->reports);
    (void)golem_allocator_free(&l->allocator, l);
}
golem_status golem_work_run_cost_enable(golem_work_run *run, const golem_cost_options *o)
{
    if (run == NULL || o == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (run->cost != NULL || run->sequence != 0 || run->status != GOLEM_WORK_READY) return GOLEM_ERR_INVALID_STATE;
    return golem_cost_ledger_create(o, &run->allocator, &run->cost);
}
const golem_cost_ledger *golem_work_run_cost_borrow(const golem_work_run *run)
{
    return run == NULL ? NULL : run->cost;
}
golem_status golem_work_run_cost_plan(golem_work_run *run, uint64_t sequence, const golem_cost_amount *a)
{
    if (run == NULL || !golem_cost_amount_valid(a)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (run->cost == NULL || run->status != GOLEM_WORK_READY) return GOLEM_ERR_INVALID_STATE;
    if (run->sequence == UINT64_MAX || sequence != run->sequence + 1) return GOLEM_ERR_STALE_RESULT;
    run->cost->plan = *a; run->cost->has_plan = true; return GOLEM_OK;
}
golem_status golem_cost_begin(golem_cost_ledger *l, const golem_stage_snapshot *stage,
    const golem_cost_amount *estimate)
{
    if (l == NULL) return GOLEM_OK;
    if (l->entry_count == l->options.entry_capacity) return GOLEM_ERR_COST_CAPACITY;
    if (l->options.report_capacity - l->report_count <= l->unreported) return GOLEM_ERR_COST_CAPACITY;
    golem_cost_entry e = {0}; e.stage = *stage;
    if (estimate != NULL) e.expected = *estimate;
    else if (l->has_plan) e.expected = l->plan;
    golem_cost_totals all = totals_view(&l->totals), scoped = totals_view(&l->stage_totals[stage->stage]);
    golem_cost_amount expected_all, expected_stage;
    golem_status s = golem_cost_amount_add(&all.expected, &e.expected, &expected_all);
    if (s != GOLEM_OK) return s;
    s = golem_cost_amount_add(&scoped.expected, &e.expected, &expected_stage);
    if (s != GOLEM_OK) return s;
    /* Prior actuals must be complete for any enforced dimension; unfinished
     * billing cannot masquerade as zero when admitting the next attempt. */
    s = golem_cost_budget_admit(&l->options.run_budget, &all.actual, &e.expected);
    if (s != GOLEM_OK) return s;
    s = golem_cost_budget_admit(&l->options.stage_budgets[stage->stage], &scoped.actual, &e.expected);
    if (s != GOLEM_OK) return s;
    l->entries[l->entry_count++] = (golem_cost_entry_record){e, SIZE_MAX, SIZE_MAX};
    l->totals.expected = expected_all; l->stage_totals[stage->stage].expected = expected_stage;
    ++l->totals.entries; ++l->totals.unsettled;
    ++l->stage_totals[stage->stage].entries; ++l->stage_totals[stage->stage].unsettled;
    ++l->unreported; l->has_plan = false;
    return GOLEM_OK;
}
void golem_cost_finish(golem_cost_ledger *l, const golem_stage_snapshot *stage)
{
    if (l != NULL) l->entries[(size_t)stage->sequence - 1].value.stage = *stage;
}
golem_status golem_work_run_cost_report(golem_work_run *run, uint64_t sequence,
    const golem_provider_usage *r)
{
    if (run == NULL || r == NULL || !text_valid(r->request_id) || !text_valid(r->provider) ||
        !text_valid(r->model) || !text_valid(r->price_revision) || !currency_valid(r->currency) ||
        !golem_cost_amount_valid(&r->actual)) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_cost_ledger *l = run->cost;
    if (l == NULL) return GOLEM_ERR_INVALID_STATE;
    if (strcmp(r->currency, l->options.currency) != 0) return GOLEM_ERR_IDENTITY_MISMATCH;
    golem_cost_entry *e = entry_find(l, sequence);
    if (e == NULL) return GOLEM_ERR_NOT_FOUND;
    golem_cost_entry_record *record = &l->entries[(size_t)sequence - 1];
    for (size_t i = record->first_report; i != SIZE_MAX; i = l->reports[i].next) {
        if (strcmp(l->reports[i].value.request_id, r->request_id) == 0)
            return report_equal(&l->reports[i].value, r) ? GOLEM_OK : GOLEM_ERR_IDENTITY_MISMATCH;
    }
    if (e->settled) return GOLEM_ERR_INVALID_STATE;
    if (l->report_count == l->options.report_capacity) return GOLEM_ERR_COST_CAPACITY;
    /* Do not let additional calls consume the first-report slot reserved for
     * another admitted attempt. Adapters must bound calls before dispatch. */
    if (e->report_count != 0 && l->options.report_capacity - l->report_count <= l->unreported)
        return GOLEM_ERR_COST_CAPACITY;
    golem_cost_amount base = e->report_count == 0 ? known_zero() : e->actual, sum;
    golem_status s = golem_cost_amount_add(&base, &r->actual, &sum);
    if (s != GOLEM_OK) return s;
    golem_cost_amount all, scoped;
    s = golem_cost_amount_add(&l->totals.actual, &r->actual, &all);
    if (s != GOLEM_OK) return s;
    s = golem_cost_amount_add(&l->stage_totals[e->stage.stage].actual, &r->actual, &scoped);
    if (s != GOLEM_OK) return s;
    size_t index = l->report_count;
    l->reports[l->report_count++] = (golem_cost_report_record){sequence, SIZE_MAX, *r};
    if (record->last_report != SIZE_MAX) l->reports[record->last_report].next = index;
    else { record->first_report = index; --l->unreported; }
    record->last_report = index;
    l->totals.actual = all; l->stage_totals[e->stage.stage].actual = scoped;
    ++l->totals.reports; ++l->stage_totals[e->stage.stage].reports;
    e->actual = sum; ++e->report_count;
    return GOLEM_OK;
}
golem_status golem_work_run_cost_settle(golem_work_run *run, uint64_t sequence)
{
    if (run == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (run->cost == NULL) return GOLEM_ERR_INVALID_STATE;
    golem_cost_entry *e = entry_find(run->cost, sequence);
    if (e == NULL) return GOLEM_ERR_NOT_FOUND;
    if (e->stage.status == GOLEM_STAGE_RUNNING) return GOLEM_ERR_INVALID_STATE;
    if (e->report_count == 0) return GOLEM_ERR_COST_INCOMPLETE;
    if (!e->settled) {
        --run->cost->totals.unsettled; --run->cost->stage_totals[e->stage.stage].unsettled;
        e->settled = true;
    }
    return GOLEM_OK;
}
golem_status golem_cost_ledger_entry_get(const golem_cost_ledger *l,
    uint64_t sequence, golem_cost_entry *out)
{
    if (l == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    const golem_cost_entry *e = entry_find(l, sequence);
    if (e == NULL) return GOLEM_ERR_NOT_FOUND;
    *out = *e; return GOLEM_OK;
}
golem_status golem_cost_ledger_report_get(const golem_cost_ledger *l,
    uint64_t sequence, size_t index, golem_provider_usage *out)
{
    if (l == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    const golem_cost_entry *e = entry_find(l, sequence);
    if (e == NULL || index >= e->report_count) return GOLEM_ERR_NOT_FOUND;
    for (size_t i = l->entries[(size_t)sequence - 1].first_report; i != SIZE_MAX; i = l->reports[i].next) {
        if (index == 0) { *out = l->reports[i].value; return GOLEM_OK; }
        --index;
    }
    return GOLEM_ERR_NOT_FOUND;
}
golem_status golem_cost_ledger_totals_get(const golem_cost_ledger *l, golem_cost_totals *out)
{
    if (l == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    *out = totals_view(&l->totals); return GOLEM_OK;
}
golem_status golem_cost_ledger_options_get(const golem_cost_ledger *l, golem_cost_options *out)
{
    if (l == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    *out = l->options; return GOLEM_OK;
}
golem_status golem_cost_ledger_stage_totals_get(const golem_cost_ledger *l,
    golem_stage stage, golem_cost_totals *out)
{
    if (l == NULL || out == NULL || !golem_core_stage_valid(stage)) return GOLEM_ERR_INVALID_ARGUMENT;
    *out = totals_view(&l->stage_totals[stage]); return GOLEM_OK;
}
