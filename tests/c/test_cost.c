#include "golem/cost.h"
#include "golem/policy.h"
#include "test.h"
#include <string.h>

static golem_cost_options options(void)
{
    golem_cost_options o = {0}; o.version = GOLEM_COST_VERSION;
    memcpy(o.currency, "USD", 4); o.entry_capacity = 32; o.report_capacity = 64; return o;
}
static golem_cost_amount amount(uint64_t cost)
{
    golem_cost_amount a = {{10, 2, 3, 4, 1}, cost, true, true}; return a;
}
static golem_provider_usage provider(uint64_t cost)
{
    golem_provider_usage r = {0};
    strcpy(r.request_id, "call-1"); strcpy(r.provider, "provider-a"); strcpy(r.model, "model-a");
    strcpy(r.price_revision, "fixture-v1"); strcpy(r.currency, "USD"); r.actual = amount(cost); return r;
}
static int make_run(golem_autonomy mode, const golem_allocator *allocator, golem_work_run **out)
{
    golem_graph_spec gs; golem_stage_graph *g = NULL; golem_work_capsule *c = NULL;
    CHECK(golem_stage_graph_default_spec(&gs) == GOLEM_OK);
    CHECK(golem_stage_graph_create(&gs, &g) == GOLEM_OK);
    const char *scope[] = {"cost"}, *accept[] = {"accounted"};
    golem_capsule_spec spec = {0}; spec.id = "cost-capsule"; spec.goal = "record every attempt";
    spec.scope = (golem_string_list){scope, 1}; spec.acceptance = (golem_string_list){accept, 1}; spec.graph = g;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) spec.permissions[i] = mode;
    CHECK(golem_work_capsule_create(&spec, &c) == GOLEM_OK);
    CHECK(golem_work_run_create_with_allocator("cost-run", c, 3, allocator, out, NULL) == GOLEM_OK);
    golem_work_capsule_free(c); golem_stage_graph_free(g); return 0;
}
static int arithmetic(void)
{
    golem_token_usage u = {1, 2, 3, 4, 5}, sum = {0};
    golem_cost_rates r = {{10, 20, 30, 40, 50}}; uint64_t cost = 999;
    CHECK(golem_cost_calculate(&u, &r, &cost) == GOLEM_OK && cost == 550);
    CHECK(golem_token_usage_add(&u, &u, &sum) == GOLEM_OK && sum.reasoning_tokens == 8 && sum.tool_calls == 10);
    for (size_t i = 0; i < 5; ++i) {
        golem_token_usage huge = {0}, one = {1, 1, 1, 1, 1};
        if (i == 0) huge.input_tokens = UINT64_MAX;
        if (i == 1) huge.cached_input_tokens = UINT64_MAX;
        if (i == 2) huge.output_tokens = UINT64_MAX;
        if (i == 3) huge.reasoning_tokens = UINT64_MAX;
        if (i == 4) huge.tool_calls = UINT64_MAX;
        sum = u;
        CHECK(golem_token_usage_add(&huge, &one, &sum) == GOLEM_ERR_OVERFLOW && sum.input_tokens == 1);
        cost = 999;
        CHECK(golem_cost_calculate(&huge, &r, &cost) == GOLEM_ERR_OVERFLOW && cost == 999);
    }
    u = (golem_token_usage){UINT64_MAX, 1, 0, 0, 0}; r.nano_per_unit = (golem_token_usage){1, 1, 0, 0, 0};
    CHECK(golem_cost_calculate(&u, &r, &cost) == GOLEM_ERR_OVERFLOW);
    r.nano_per_unit.cached_input_tokens = 0;
    CHECK(golem_cost_calculate(&u, &r, &cost) == GOLEM_OK && cost == UINT64_MAX);
    CHECK(golem_cost_calculate(NULL, &r, &cost) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_token_usage_add(&u, NULL, &sum) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
static int lifecycle(void)
{
    golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &run) == 0);
    golem_cost_options o = options(); CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
    const golem_cost_ledger *l = golem_work_run_cost_borrow(run);
    o.currency[0] = 'X'; golem_cost_options copy;
    CHECK(golem_cost_ledger_options_get(l, &copy) == GOLEM_OK && strcmp(copy.currency, "USD") == 0);
    for (uint64_t sequence = 1; sequence <= 6; ++sequence) {
        golem_cost_amount estimate = amount(100);
        CHECK(golem_work_run_cost_plan(run, sequence, &estimate) == GOLEM_OK);
        golem_stage_snapshot stage;
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
        CHECK(stage.sequence == sequence && stage.stage == (golem_stage)(sequence - 1));
        golem_cost_entry e;
        CHECK(golem_cost_ledger_entry_get(l, sequence, &e) == GOLEM_OK);
        CHECK(e.stage.sequence == sequence && e.expected.nano_cost == 100 && !e.actual.cost_known && !e.settled);
        golem_provider_usage r = provider(80);
        CHECK(golem_work_run_cost_report(run, sequence, &r) == GOLEM_OK);
        CHECK(golem_work_run_cost_settle(run, sequence) == GOLEM_ERR_INVALID_STATE);
        CHECK(golem_work_run_finish(run, sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
        CHECK(golem_work_run_cost_settle(run, sequence) == GOLEM_OK);
        CHECK(golem_work_run_cost_settle(run, sequence) == GOLEM_OK);
    }
    golem_cost_totals t;
    CHECK(golem_cost_ledger_totals_get(l, &t) == GOLEM_OK);
    CHECK(t.entries == 6 && t.reports == 6 && t.unsettled == 0 && t.actual.cost_known);
    CHECK(t.expected.nano_cost == 600 && t.actual.nano_cost == 480 && t.actual.usage.input_tokens == 60);
    golem_cost_entry e; CHECK(golem_cost_ledger_entry_get(l, 1, &e) == GOLEM_OK && e.stage.status == GOLEM_STAGE_PASSED);
    golem_work_run_free(run); CHECK(e.actual.nano_cost == 80); return 0;
}
static int retry(void)
{
    golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &run) == 0);
    golem_cost_options o = options(); CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
    golem_stage_snapshot s;
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    CHECK(golem_work_run_finish(run, 1, GOLEM_STAGE_FAILED, GOLEM_FAILURE_TIMEOUT, false) == GOLEM_OK);
    CHECK(golem_work_run_reenter(run) == GOLEM_OK);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK && s.sequence == 2 && s.attempt == 2);
    CHECK(golem_work_run_cancel(run) == GOLEM_OK);
    golem_provider_usage r = provider(5);
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
    CHECK(golem_work_run_cost_report(run, 2, &r) == GOLEM_OK);
    CHECK(golem_work_run_cost_settle(run, 1) == GOLEM_OK);
    CHECK(golem_work_run_cost_settle(run, 2) == GOLEM_OK);
    golem_cost_entry e;
    const golem_cost_ledger *l = golem_work_run_cost_borrow(run);
    CHECK(golem_cost_ledger_entry_get(l, 1, &e) == GOLEM_OK && e.stage.status == GOLEM_STAGE_FAILED && e.stage.attempt == 1);
    CHECK(golem_cost_ledger_entry_get(l, 2, &e) == GOLEM_OK && e.stage.status == GOLEM_STAGE_CANCELLED && e.stage.attempt == 2);
    golem_cost_totals t; CHECK(golem_cost_ledger_totals_get(l, &t) == GOLEM_OK);
    CHECK(t.entries == 2 && t.actual.nano_cost == 10 && t.actual.cost_known && !t.expected.cost_known);
    CHECK(golem_cost_ledger_stage_totals_get(l, GOLEM_STAGE_PLANNING, &t) == GOLEM_OK);
    CHECK(t.entries == 2 && t.actual.nano_cost == 10 && t.unsettled == 0);
    CHECK(golem_cost_ledger_stage_totals_get(l, GOLEM_STAGE_UX, &t) == GOLEM_OK && t.entries == 0);
    golem_work_run_free(run); return 0;
}
static int budget(void)
{
    golem_cost_amount a = amount(1);
    for (unsigned i = 0; i < 6; ++i) {
        golem_budget b = {0}; b.enabled = 1u << i;
        CHECK(golem_budget_check(&b, &a) == GOLEM_ERR_BUDGET_EXHAUSTED);
        b.limits = a.usage; b.nano_cost_limit = a.nano_cost;
        CHECK(golem_budget_check(&b, &a) == GOLEM_OK);
        golem_cost_amount unknown = {0};
        CHECK(golem_budget_check(&b, &unknown) == GOLEM_ERR_COST_INCOMPLETE);
        b.enabled = 0; CHECK(golem_budget_check(&b, &unknown) == GOLEM_OK);
    }
    for (int scoped = 0; scoped <= 1; ++scoped) {
        golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &run) == 0);
        golem_cost_options o = options(); golem_budget b = {0};
        b.enabled = GOLEM_BUDGET_COST; b.nano_cost_limit = 100;
        if (scoped) o.stage_budgets[0] = b; else o.run_budget = b;
        CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
        golem_stage_permission_request request; golem_policy_decision decision = {0}; decision.version = 999;
        golem_stage_snapshot s = {0}; s.sequence = 999;
        CHECK(golem_work_run_permission_request(run, GOLEM_EFFECT_LOCAL, &request, NULL) == GOLEM_OK);
        CHECK(golem_work_run_begin_authorized(run, &request, &s, &decision, NULL) == GOLEM_ERR_COST_INCOMPLETE);
        CHECK(s.sequence == 999 && decision.version == 999);
        a = amount(101); CHECK(golem_work_run_cost_plan(run, 1, &a) == GOLEM_OK);
        CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_ERR_BUDGET_EXHAUSTED);
        a = amount(100); CHECK(golem_work_run_cost_plan(run, 1, &a) == GOLEM_OK);
        CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK && s.sequence == 1);
        CHECK(golem_work_run_finish(run, 1, GOLEM_STAGE_FAILED, GOLEM_FAILURE_TIMEOUT, false) == GOLEM_OK);
        CHECK(golem_work_run_reenter(run) == GOLEM_OK);
        a = amount(0); CHECK(golem_work_run_cost_plan(run, 2, &a) == GOLEM_OK);
        CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_ERR_COST_INCOMPLETE);
        golem_provider_usage r = provider(101);
        CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
        CHECK(golem_work_run_cost_settle(run, 1) == GOLEM_OK);
        CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_ERR_BUDGET_EXHAUSTED);
        golem_cost_totals t; CHECK(golem_cost_ledger_totals_get(golem_work_run_cost_borrow(run), &t) == GOLEM_OK);
        CHECK(t.entries == 1 && t.actual.nano_cost == 101);
        golem_work_run_free(run);
    }
    golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_DENY, NULL, &run) == 0);
    golem_cost_options o = options(); CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
    golem_stage_snapshot s; CHECK(golem_work_run_begin(run, false, true, &s) == GOLEM_ERR_POLICY_DENIED);
    golem_cost_totals t; CHECK(golem_cost_ledger_totals_get(golem_work_run_cost_borrow(run), &t) == GOLEM_OK && t.entries == 0);
    golem_work_run_free(run); return 0;
}
static int reports(void)
{
    golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &run) == 0);
    golem_cost_options o = options(); CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
    golem_stage_snapshot s; CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    golem_provider_usage r = provider(40), copy;
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
    r.actual.nano_cost++;
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_ERR_IDENTITY_MISMATCH);
    strcpy(r.request_id, "fallback"); strcpy(r.provider, "local"); r.actual = amount(0);
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
    const golem_cost_ledger *l = golem_work_run_cost_borrow(run);
    CHECK(golem_cost_ledger_report_get(l, 1, 1, &copy) == GOLEM_OK && strcmp(copy.provider, "local") == 0);
    strcpy(r.request_id, "unknown"); r.actual = (golem_cost_amount){0};
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
    CHECK(golem_work_run_cancel(run) == GOLEM_OK);
    CHECK(golem_work_run_cost_settle(run, 1) == GOLEM_OK);
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
    strcpy(r.request_id, "late"); CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_ERR_INVALID_STATE);
    golem_cost_totals t; CHECK(golem_cost_ledger_totals_get(l, &t) == GOLEM_OK);
    CHECK(t.reports == 3 && t.actual.nano_cost == 40 && !t.actual.cost_known && !t.actual.usage_known);
    golem_work_run_free(run);
    /* Aggregate overflow must reject atomically, even across different calls. */
    CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &run) == 0);
    CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    r = provider(UINT64_MAX); CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
    strcpy(r.request_id, "overflow"); r.actual.nano_cost = 1;
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_ERR_OVERFLOW);
    CHECK(golem_cost_ledger_totals_get(golem_work_run_cost_borrow(run), &t) == GOLEM_OK && t.reports == 1);
    golem_work_run_free(run); return 0;
}
static int capacity(void)
{
    for (int entries = 0; entries <= 1; ++entries) {
        golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &run) == 0);
        golem_cost_options o = options(); if (entries) o.entry_capacity = 1; else o.report_capacity = 1;
        CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
        golem_stage_snapshot s;
        CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
        CHECK(golem_work_run_finish(run, 1, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
        CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_ERR_COST_CAPACITY && s.sequence == 1);
        golem_provider_usage r = provider(0);
        CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
        CHECK(golem_work_run_cost_settle(run, 1) == GOLEM_OK);
        CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_ERR_COST_CAPACITY);
        golem_work_run_free(run);
    }
    /* Extra reports cannot steal another attempt's reserved first slot. */
    golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &run) == 0);
    golem_cost_options o = options(); o.report_capacity = 2;
    CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
    golem_stage_snapshot s;
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    CHECK(golem_work_run_finish(run, 1, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    golem_provider_usage r = provider(1);
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
    strcpy(r.request_id, "extra");
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_ERR_COST_CAPACITY);
    CHECK(golem_work_run_cost_report(run, 2, &r) == GOLEM_OK);
    CHECK(golem_work_run_cost_report(run, 2, &r) == GOLEM_OK);
    golem_work_run_free(run); return 0;
}
static int aggregate(void)
{
    golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &run) == 0);
    golem_cost_options o = options(); CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
    golem_stage_snapshot s;
    for (uint64_t i = 1; i <= 3; ++i) {
        CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
        CHECK(golem_work_run_finish(run, i, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    }
    /* Interleaved, late provider data: partial and settled totals differ. */
    golem_provider_usage r = provider(10);
    CHECK(golem_work_run_cost_report(run, 2, &r) == GOLEM_OK);
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
    strcpy(r.request_id, "second"); r.actual.nano_cost = 20;
    CHECK(golem_work_run_cost_report(run, 2, &r) == GOLEM_OK);
    CHECK(golem_work_run_cost_settle(run, 2) == GOLEM_OK);
    const golem_cost_ledger *l = golem_work_run_cost_borrow(run);
    golem_cost_totals t;
    CHECK(golem_cost_ledger_totals_get(l, &t) == GOLEM_OK && t.actual.nano_cost == 40 && !t.actual.cost_known && t.unsettled == 2);
    CHECK(golem_cost_ledger_stage_totals_get(l, GOLEM_STAGE_UX, &t) == GOLEM_OK && t.actual.cost_known && t.actual.nano_cost == 30);
    golem_provider_usage read;
    CHECK(golem_cost_ledger_report_get(l, 2, 1, &read) == GOLEM_OK && read.actual.nano_cost == 20);
    CHECK(golem_work_run_cost_settle(run, 1) == GOLEM_OK);
    r.actual = (golem_cost_amount){0}; r.actual.cost_known = true; r.actual.usage_known = true;
    CHECK(golem_work_run_cost_report(run, 3, &r) == GOLEM_OK);
    CHECK(golem_work_run_cost_settle(run, 3) == GOLEM_OK);
    CHECK(golem_cost_ledger_totals_get(l, &t) == GOLEM_OK && t.actual.cost_known && t.actual.nano_cost == 40 && t.unsettled == 0);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    r.actual = amount(UINT64_MAX - 40);
    CHECK(golem_work_run_cost_report(run, 4, &r) == GOLEM_OK);
    strcpy(r.request_id, "global-overflow"); r.actual = amount(1);
    CHECK(golem_work_run_cost_report(run, 4, &r) == GOLEM_ERR_OVERFLOW);
    CHECK(golem_cost_ledger_totals_get(l, &t) == GOLEM_OK && t.actual.nano_cost == UINT64_MAX && t.reports == 5);
    CHECK(golem_work_run_finish(run, 4, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    CHECK(golem_work_run_cost_settle(run, 4) == GOLEM_OK);
    /* Estimates and actuals are independent totals without a money budget. */
    golem_cost_amount estimate = amount(UINT64_MAX);
    CHECK(golem_work_run_cost_plan(run, 5, &estimate) == GOLEM_OK);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    CHECK(golem_work_run_finish(run, 5, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    estimate = amount(1);
    CHECK(golem_work_run_cost_plan(run, 6, &estimate) == GOLEM_OK);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_ERR_OVERFLOW && s.sequence == 5);
    CHECK(golem_cost_ledger_totals_get(l, &t) == GOLEM_OK && t.entries == 5 && t.expected.nano_cost == UINT64_MAX);
    golem_work_run_free(run); return 0;
}
typedef struct tracker { size_t calls, fail_at, live; } tracker;
static void *allocate(void *context, size_t size)
{
    tracker *t = context; if (++t->calls == t->fail_at) return NULL;
    void *p = malloc(size); if (p != NULL) ++t->live; return p;
}
static void deallocate(void *context, void *p) { tracker *t = context; --t->live; free(p); }
static int ownership(void)
{
    for (size_t fail = 1; fail <= 3; ++fail) {
        tracker t = {0}; golem_allocator a = {&t, allocate, deallocate};
        golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, &a, &run) == 0);
        size_t baseline = t.live; t.fail_at = t.calls + fail; golem_cost_options o = options();
        CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(t.live == baseline && golem_work_run_cost_borrow(run) == NULL);
        t.fail_at = 0; CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
        size_t calls = t.calls; t.fail_at = calls + 1;
        golem_stage_snapshot s; CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
        golem_provider_usage r = provider(1);
        CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_OK);
        CHECK(golem_work_run_cancel(run) == GOLEM_OK);
        CHECK(golem_work_run_cost_settle(run, 1) == GOLEM_OK && t.calls == calls);
        golem_work_run_free(run); CHECK(t.live == 0);
    }
    return 0;
}
static int invalid(void)
{
    golem_work_run *run = NULL; CHECK(make_run(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &run) == 0);
    golem_cost_options o = options(); o.version = 0;
    CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_ERR_UNSUPPORTED_VERSION);
    o = options(); o.entry_capacity = SIZE_MAX;
    CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_ERR_OVERFLOW);
    o = options(); o.stage_budgets[5].enabled = 128;
    CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_ERR_INVALID_ARGUMENT);
    o = options(); o.currency[3] = 'X';
    CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_ERR_INVALID_ARGUMENT);
    o = options(); CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_OK);
    CHECK(golem_work_run_cost_enable(run, &o) == GOLEM_ERR_INVALID_STATE);
    golem_cost_amount a = amount(1); CHECK(golem_work_run_cost_plan(run, 2, &a) == GOLEM_ERR_STALE_RESULT);
    a.cost_known = false; CHECK(golem_work_run_cost_plan(run, 1, &a) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_stage_snapshot s; CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    golem_provider_usage r = provider(1); memset(r.provider, 'x', sizeof(r.provider));
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_ERR_INVALID_ARGUMENT);
    r = provider(1); strcpy(r.currency, "EUR");
    CHECK(golem_work_run_cost_report(run, 1, &r) == GOLEM_ERR_IDENTITY_MISMATCH);
    r = provider(1); CHECK(golem_work_run_cost_report(run, 2, &r) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_work_run_cancel(run) == GOLEM_OK);
    CHECK(golem_work_run_cost_settle(run, 1) == GOLEM_ERR_COST_INCOMPLETE);
    golem_cost_entry e = {0}; e.stage.sequence = 999;
    CHECK(golem_cost_ledger_entry_get(golem_work_run_cost_borrow(run), 0, &e) == GOLEM_ERR_NOT_FOUND && e.stage.sequence == 999);
    CHECK(golem_work_run_cost_borrow(NULL) == NULL);
    CHECK(golem_cost_ledger_totals_get(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_cost_enable(NULL, &o) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_cost_report(NULL, 1, &r) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_cost_settle(NULL, 1) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_cost_ledger_report_get(golem_work_run_cost_borrow(run), 1, 0, &r) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_cost_ledger_entry_get(NULL, 1, &e) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_cost_ledger_options_get(NULL, &o) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_cost_plan(NULL, 1, &a) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_budget_check(NULL, &a) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_cost_totals totals;
    CHECK(golem_cost_ledger_stage_totals_get(golem_work_run_cost_borrow(run), GOLEM_STAGE_NONE, &totals) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_work_run_free(run); return 0;
}
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    const struct { const char *name; int (*run)(void); } cases[] = {
        {"arithmetic", arithmetic}, {"lifecycle", lifecycle}, {"retry", retry}, {"budget", budget},
        {"reports", reports}, {"capacity", capacity}, {"aggregate", aggregate}, {"ownership", ownership}, {"invalid", invalid}
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i)
        if (strcmp(argv[1], cases[i].name) == 0) return cases[i].run();
    return EXIT_FAILURE;
}
