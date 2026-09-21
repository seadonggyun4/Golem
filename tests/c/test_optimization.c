#include "golem/optimization.h"
#include "test.h"
#include <string.h>

static golem_cost_amount amount(uint64_t nano, uint64_t tokens)
{
    golem_cost_amount a = {{tokens, 0, 0, 0, 0}, nano, true, true}; return a;
}
static golem_cost_options costs(void)
{
    golem_cost_options o = {0}; o.version = GOLEM_COST_VERSION;
    strcpy(o.currency, "USD"); o.entry_capacity = 8; o.report_capacity = 16; return o;
}
static golem_optimization_policy policy(void)
{
    golem_optimization_policy p = {0}; p.version = GOLEM_OPTIMIZATION_VERSION;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) p.allowed[i] = GOLEM_OPTIMIZE_ALL;
    p.minimum_savings_nano = 1;
    p.fallback = (golem_fallback_policy){GOLEM_FALLBACK_ON_ALL, 2, false}; return p;
}
static int make_run(golem_stage stage, golem_autonomy mode, const golem_allocator *a,
    const golem_cost_options *co, const golem_optimization_policy *op, golem_work_run **out)
{
    golem_graph_spec gs = {0}; gs.count = 1; gs.order[0] = stage;
    for (size_t i = 0; i < GOLEM_FAILURE_COUNT; ++i) gs.reentry[i] = GOLEM_STAGE_NONE;
    golem_stage_graph *g = NULL; golem_work_capsule *c = NULL;
    CHECK(golem_stage_graph_create(&gs, &g) == GOLEM_OK);
    const char *scope[] = {"test"}, *acceptance[] = {"verified outcome"};
    golem_capsule_spec s = {0}; s.id = "optimization-capsule"; s.goal = "safe optional advisor";
    s.scope = (golem_string_list){scope, 1}; s.acceptance = (golem_string_list){acceptance, 1}; s.graph = g;
    s.permissions[stage] = mode;
    CHECK(golem_work_capsule_create(&s, &c) == GOLEM_OK);
    CHECK(golem_work_run_create_with_allocator("optimizer-run", c, 5, a, out, NULL) == GOLEM_OK);
    golem_work_capsule_free(c); golem_stage_graph_free(g);
    if (co != NULL) CHECK(golem_work_run_cost_enable(*out, co) == GOLEM_OK);
    if (op != NULL) CHECK(golem_work_run_optimization_enable(*out, op) == GOLEM_OK);
    return 0;
}
static int context(golem_work_run *run, golem_optimization_context *out)
{
    golem_stage_permission_request r;
    CHECK(golem_work_run_permission_request(run, GOLEM_EFFECT_LOCAL, &r, NULL) == GOLEM_OK);
    golem_optimization_context c = {0};
    c.run_id = r.run_id; c.stage = r.stage; c.sequence = r.sequence; c.attempt = r.attempt;
    strcpy(c.currency, "USD"); c.context_digest.bytes[0] = 1; c.predecessor_digest.bytes[0] = 2; c.requirements_digest.bytes[0] = 3;
    strcpy(c.baseline.id, "baseline"); c.baseline.effect = GOLEM_EFFECT_LOCAL;
    c.baseline.estimate = amount(100, 10); c.baseline.requirements_digest = c.requirements_digest; c.baseline.verified = true;
    c.candidate = c.baseline; strcpy(c.candidate.id, "candidate"); c.candidate.estimate = amount(60, 6);
    c.overhead = amount(5, 1); c.advisor_effect = GOLEM_EFFECT_LOCAL; c.baseline_available = true;
    c.cache_verified = true; c.cache = (golem_cache_model){20, 10, 4, 10};
    *out = c; return 0;
}
static golem_optimization_proposal proposal(const golem_optimization_context *c, golem_optimization_kind kind)
{
    golem_optimization_proposal p = {0}; p.version = GOLEM_OPTIMIZATION_VERSION;
    p.run_id = c->run_id; p.stage = c->stage; p.sequence = c->sequence; p.attempt = c->attempt;
    p.context_digest = c->context_digest; p.predecessor_digest = c->predecessor_digest;
    p.requirements_digest = c->requirements_digest; p.kind = kind; strcpy(p.route_id, c->candidate.id); return p;
}
static int cache(void)
{
    golem_cache_model m = {30, 10, 4, 5}; golem_cache_result r;
    CHECK(golem_cache_break_even(&m, &r) == GOLEM_OK);
    CHECK(r.break_even_reads == 6 && r.uncached_nano == 50 && r.cached_nano == 50 && !r.profitable);
    m.expected_reads = 6;
    CHECK(golem_cache_break_even(&m, &r) == GOLEM_OK && r.savings_nano == 6 && r.profitable);
    m.expected_reads = 0; CHECK(golem_cache_break_even(&m, &r) == GOLEM_OK && !r.profitable && r.cached_nano == 30);
    m.cached_read_nano = 10; CHECK(golem_cache_break_even(&m, &r) == GOLEM_OK && r.break_even_reads == 0);
    m.cached_read_nano = 11; CHECK(golem_cache_break_even(&m, &r) == GOLEM_OK && r.break_even_reads == 0);
    m = (golem_cache_model){0, 1, 0, 1};
    CHECK(golem_cache_break_even(&m, &r) == GOLEM_OK && r.break_even_reads == 1 && r.profitable);
    m = (golem_cache_model){UINT64_MAX, 1, 0, 0};
    CHECK(golem_cache_break_even(&m, &r) == GOLEM_OK && r.break_even_reads == 0);
    r.savings_nano = 999; m = (golem_cache_model){0, UINT64_MAX, 0, 2};
    CHECK(golem_cache_break_even(&m, &r) == GOLEM_ERR_OVERFLOW && r.savings_nano == 999);
    m = (golem_cache_model){UINT64_MAX, 0, 1, 1};
    CHECK(golem_cache_break_even(&m, &r) == GOLEM_ERR_OVERFLOW && r.savings_nano == 999);
    CHECK(golem_cache_break_even(NULL, &r) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_cache_break_even(&m, NULL) == GOLEM_ERR_INVALID_ARGUMENT); return 0;
}
static int selection(void)
{
    golem_work_run *run = NULL; golem_cost_options co = costs(); golem_optimization_policy op = policy();
    CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &co, &op, &run) == 0);
    golem_optimization_context c; CHECK(context(run, &c) == 0);
    golem_optimization_proposal p = proposal(&c, GOLEM_OPTIMIZATION_ROUTE);
    golem_optimization_decision d;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK);
    CHECK(d.verdict == GOLEM_OPTIMIZATION_APPLY && d.expected.nano_cost == 65 && d.expected.usage.input_tokens == 7 && d.savings_nano == 35);
    golem_cost_totals t;
    CHECK(golem_cost_ledger_totals_get(golem_work_run_cost_borrow(run), &t) == GOLEM_OK && t.entries == 0);
    c.candidate.verified = false;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK && d.reason == GOLEM_OPTIMIZATION_QUALITY_UNVERIFIED);
    c.candidate.verified = true; c.candidate.requirements_digest.bytes[0] ^= 1;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK && d.verdict == GOLEM_OPTIMIZATION_REJECT);
    c.candidate.requirements_digest = c.requirements_digest; p.kind = GOLEM_OPTIMIZATION_CACHE;
    c.cache_verified = false;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK && d.reason == GOLEM_OPTIMIZATION_CACHE_UNVERIFIED);
    c.cache_verified = true; c.cache.setup_nano++;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_ERR_IDENTITY_MISMATCH);
    c.cache.setup_nano--;
    golem_optimization_approval a = {0}; golem_stage_snapshot s;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_OK);
    CHECK(d.selected_kind == GOLEM_OPTIMIZATION_CACHE);
    CHECK(golem_work_run_finish(run, s.sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, false) == GOLEM_ERR_REQUIREMENTS_UNMET);
    CHECK(golem_work_run_finish(run, s.sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    golem_cost_entry entry;
    CHECK(golem_cost_ledger_entry_get(golem_work_run_cost_borrow(run), 1, &entry) == GOLEM_OK && entry.expected.nano_cost == 65);
    CHECK(!entry.actual.cost_known && !entry.settled);
    golem_work_run_free(run); return 0;
}
static int noop(void)
{
    golem_cost_options co = costs(); golem_optimization_policy op = policy(); op.minimum_savings_nano = 10;
    golem_work_run *run = NULL; CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &co, &op, &run) == 0);
    golem_optimization_context c; CHECK(context(run, &c) == 0);
    golem_optimization_proposal p = proposal(&c, GOLEM_OPTIMIZATION_ROUTE); golem_optimization_decision d;
    for (uint64_t cost = 90; cost <= 101; ++cost) {
        c.candidate.estimate.nano_cost = cost;
        CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK);
        CHECK(d.verdict == GOLEM_OPTIMIZATION_KEEP_BASELINE && d.reason == GOLEM_OPTIMIZATION_NO_SAVINGS);
        CHECK(strcmp(d.route_id, "baseline") == 0 && d.expected.nano_cost == 105 && d.savings_nano == 0);
    }
    c.candidate.estimate.nano_cost = 85;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK && d.savings_nano == 10);
    CHECK(golem_work_run_optimization_evaluate(run, &c, NULL, &d) == GOLEM_OK && d.reason == GOLEM_OPTIMIZATION_NO_PROPOSAL);
    p.kind = GOLEM_OPTIMIZATION_NOOP;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK && d.reason == GOLEM_OPTIMIZATION_EXPLICIT_NOOP);
    c.baseline_available = false;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK && d.reason == GOLEM_OPTIMIZATION_BASELINE_UNAVAILABLE);
    golem_work_run_free(run);
    CHECK(golem_optimization_policy_init(&op) == GOLEM_OK);
    CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &co, &op, &run) == 0);
    CHECK(context(run, &c) == 0); p = proposal(&c, GOLEM_OPTIMIZATION_ROUTE);
    op.allowed[0] = GOLEM_OPTIMIZE_ALL;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK && d.reason == GOLEM_OPTIMIZATION_DISABLED);
    CHECK(golem_work_run_optimization_policy_get(run, &op) == GOLEM_OK && op.allowed[0] == 0);
    golem_work_run_free(run); return 0;
}
static int gates(void)
{
    for (int mode = 0; mode <= GOLEM_AUTONOMY_ASK_ALWAYS; ++mode)
    for (int stage = 0; stage < GOLEM_STAGE_COUNT; ++stage)
    for (int effect = 0; effect <= GOLEM_EFFECT_EXTERNAL; ++effect)
    for (int grant = 0; grant <= GOLEM_AUTHORIZATION_REJECTED; ++grant)
    for (int kind = GOLEM_OPTIMIZATION_NOOP; kind <= GOLEM_OPTIMIZATION_FALLBACK; ++kind) {
        golem_cost_options co = costs(); golem_optimization_policy op = policy(); golem_work_run *run = NULL;
        CHECK(make_run((golem_stage)stage, (golem_autonomy)mode, NULL, &co, &op, &run) == 0);
        golem_optimization_context c; CHECK(context(run, &c) == 0);
        c.baseline.effect = (golem_effect)effect; c.candidate.effect = (golem_effect)effect;
        if (kind == GOLEM_OPTIMIZATION_FALLBACK) c.fallback_trigger = GOLEM_FALLBACK_BUDGET_PRESSURE;
        golem_optimization_proposal p = proposal(&c, (golem_optimization_kind)kind);
        golem_optimization_approval a = {0}; a.authorization = (golem_authorization)grant;
        strcpy(a.route_id, kind == GOLEM_OPTIMIZATION_NOOP ? "baseline" : "candidate");
        golem_stage_snapshot s = {0}; s.sequence = 999; golem_optimization_decision d; golem_diagnostic diag;
        golem_status expected;
        if (kind == GOLEM_OPTIMIZATION_FALLBACK && effect == GOLEM_EFFECT_UNKNOWN)
            expected = GOLEM_ERR_OPTIMIZATION_REJECTED;
        else if (mode == GOLEM_AUTONOMY_DENY || effect == GOLEM_EFFECT_UNKNOWN || grant == GOLEM_AUTHORIZATION_REJECTED)
            expected = GOLEM_ERR_POLICY_DENIED;
        else if (grant == GOLEM_AUTHORIZATION_NONE && (mode == GOLEM_AUTONOMY_ASK_ALWAYS || effect == GOLEM_EFFECT_EXTERNAL))
            expected = GOLEM_ERR_APPROVAL_REQUIRED;
        else expected = GOLEM_OK;
        CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, &diag) == expected && diag.status == expected);
        golem_cost_totals t; CHECK(golem_cost_ledger_totals_get(golem_work_run_cost_borrow(run), &t) == GOLEM_OK);
        uint32_t attempts; CHECK(golem_work_run_attempts_get(run, (golem_stage)stage, &attempts) == GOLEM_OK);
        CHECK(t.entries == (expected == GOLEM_OK ? 1u : 0u) && attempts == t.entries);
        CHECK(s.sequence == (expected == GOLEM_OK ? 1u : 999u));
        golem_work_run_free(run);
    }
    return 0;
}
static int scope(void)
{
    golem_work_run *run = NULL; golem_cost_options co = costs(); golem_optimization_policy op = policy();
    CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &co, &op, &run) == 0);
    golem_optimization_context c; CHECK(context(run, &c) == 0);
    golem_optimization_proposal p = proposal(&c, GOLEM_OPTIMIZATION_ROUTE);
    golem_optimization_decision d = {0}; d.savings_nano = 999;
    for (int i = 0; i < 8; ++i) {
        golem_optimization_proposal bad = p;
        if (i == 0) bad.run_id = "other";
        if (i == 1) bad.stage = GOLEM_STAGE_AUDIT;
        if (i == 2) ++bad.sequence;
        if (i == 3) ++bad.attempt;
        if (i == 4) bad.context_digest.bytes[0]++;
        if (i == 5) bad.predecessor_digest.bytes[0]++;
        if (i == 6) bad.requirements_digest.bytes[0]++;
        if (i == 7) strcpy(bad.route_id, "unresolved-adapter");
        CHECK(golem_work_run_optimization_evaluate(run, &c, &bad, &d) ==
            (i == 0 || i == 7 ? GOLEM_ERR_IDENTITY_MISMATCH : GOLEM_ERR_STALE_RESULT));
        CHECK(d.savings_nano == 999);
    }
    golem_optimization_approval a = {0}; a.authorization = GOLEM_AUTHORIZATION_GRANTED; strcpy(a.route_id, "baseline");
    golem_stage_snapshot s = {0}; s.sequence = 999;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_IDENTITY_MISMATCH);
    CHECK(s.sequence == 999 && d.savings_nano == 999);
    a.authorization = GOLEM_AUTHORIZATION_NONE;
    c.candidate.effect = GOLEM_EFFECT_EXTERNAL;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_APPROVAL_REQUIRED);
    c.candidate.effect = GOLEM_EFFECT_LOCAL; c.advisor_effect = GOLEM_EFFECT_EXTERNAL;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_APPROVAL_REQUIRED);
    c.advisor_effect = GOLEM_EFFECT_LOCAL; c.baseline.effect = GOLEM_EFFECT_EXTERNAL;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_APPROVAL_REQUIRED);
    a.authorization = GOLEM_AUTHORIZATION_GRANTED; strcpy(a.route_id, "candidate");
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_OK);
    CHECK(golem_work_run_finish(run, 1, GOLEM_STAGE_FAILED, GOLEM_FAILURE_TIMEOUT, false) == GOLEM_OK);
    CHECK(golem_work_run_reenter(run) == GOLEM_OK);
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_STALE_RESULT);
    CHECK(context(run, &c) == 0);
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_ERR_STALE_RESULT);
    golem_work_run_free(run); return 0;
}
static int fallback(void)
{
    golem_fallback_policy fp = {GOLEM_FALLBACK_ON_ALL, 2, true}; bool allowed;
    for (int trigger = 0; trigger <= GOLEM_FALLBACK_QUALITY_FAILURE; ++trigger) {
        CHECK(golem_fallback_check(&fp, (golem_fallback_trigger)trigger, 0, GOLEM_EFFECT_LOCAL, &allowed) == GOLEM_OK);
        CHECK(allowed == (trigger >= GOLEM_FALLBACK_UNAVAILABLE && trigger <= GOLEM_FALLBACK_BUDGET_PRESSURE));
        CHECK(golem_fallback_check(&fp, (golem_fallback_trigger)trigger, 2, GOLEM_EFFECT_LOCAL, &allowed) == GOLEM_OK && !allowed);
        CHECK(golem_fallback_check(&fp, (golem_fallback_trigger)trigger, 0, GOLEM_EFFECT_EXTERNAL, &allowed) == GOLEM_OK && !allowed);
    }
    golem_cost_options co = costs(); golem_optimization_policy op = policy(); op.fallback.max_per_stage = 1;
    golem_work_run *run = NULL;
    CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_ASK_ALWAYS, NULL, &co, &op, &run) == 0);
    golem_optimization_context c; CHECK(context(run, &c) == 0); c.baseline_available = false;
    c.fallback_trigger = GOLEM_FALLBACK_UNAVAILABLE;
    golem_optimization_proposal p = proposal(&c, GOLEM_OPTIMIZATION_FALLBACK);
    golem_optimization_approval a = {0}; golem_stage_snapshot s; golem_optimization_decision d;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_APPROVAL_REQUIRED);
    p.kind = GOLEM_OPTIMIZATION_ROUTE;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_OPTIMIZATION_REJECTED);
    p.kind = GOLEM_OPTIMIZATION_FALLBACK; c.fallback_trigger = GOLEM_FALLBACK_POLICY_DENIED;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_OPTIMIZATION_REJECTED);
    c.fallback_trigger = GOLEM_FALLBACK_UNAVAILABLE;
    a.authorization = GOLEM_AUTHORIZATION_GRANTED; strcpy(a.route_id, "candidate");
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_OK);
    CHECK(golem_work_run_finish(run, 1, GOLEM_STAGE_FAILED, GOLEM_FAILURE_TIMEOUT, false) == GOLEM_OK);
    CHECK(golem_work_run_reenter(run) == GOLEM_OK);
    CHECK(context(run, &c) == 0); c.fallback_trigger = GOLEM_FALLBACK_TIMEOUT;
    p = proposal(&c, GOLEM_OPTIMIZATION_FALLBACK);
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_OPTIMIZATION_REJECTED);
    CHECK(d.reason == GOLEM_OPTIMIZATION_FALLBACK_FORBIDDEN);
    golem_work_run_free(run); return 0;
}
static int atomic(void)
{
    golem_work_run *run = NULL; golem_cost_options co = costs(); golem_optimization_policy op = policy();
    co.run_budget.enabled = GOLEM_BUDGET_COST; co.run_budget.nano_cost_limit = 64;
    CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &co, &op, &run) == 0);
    golem_cost_amount prior = amount(10, 1);
    CHECK(golem_work_run_cost_plan(run, 1, &prior) == GOLEM_OK);
    golem_optimization_context c; CHECK(context(run, &c) == 0);
    golem_optimization_proposal p = proposal(&c, GOLEM_OPTIMIZATION_ROUTE);
    golem_optimization_approval a = {0}; golem_stage_snapshot s = {0}; s.sequence = 999;
    golem_optimization_decision d = {0}; d.savings_nano = 999;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_BUDGET_EXHAUSTED);
    CHECK(s.sequence == 999 && d.savings_nano == 999);
    c.overhead.nano_cost = UINT64_MAX;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_OVERFLOW);
    CHECK(s.sequence == 999 && d.savings_nano == 999);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    golem_cost_entry e;
    CHECK(golem_cost_ledger_entry_get(golem_work_run_cost_borrow(run), 1, &e) == GOLEM_OK && e.expected.nano_cost == 10);
    golem_work_run_free(run);
    /* Budget rejection cannot spend the single allowed fallback transition. */
    op.fallback.max_per_stage = 1;
    CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &co, &op, &run) == 0);
    CHECK(context(run, &c) == 0); c.fallback_trigger = GOLEM_FALLBACK_BUDGET_PRESSURE;
    p = proposal(&c, GOLEM_OPTIMIZATION_FALLBACK);
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_BUDGET_EXHAUSTED);
    c.candidate.estimate.nano_cost = 59;
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_OK);
    CHECK(d.expected.nano_cost == 64);
    golem_work_run_free(run);
    /* A NOOP does not erase advisor overhead to fit a budget. */
    co = costs(); co.run_budget.enabled = GOLEM_BUDGET_COST; co.run_budget.nano_cost_limit = 100;
    CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &co, &op, &run) == 0);
    CHECK(context(run, &c) == 0); p = proposal(&c, GOLEM_OPTIMIZATION_NOOP);
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_ERR_BUDGET_EXHAUSTED);
    golem_work_run_free(run); return 0;
}
typedef struct tracker { bool fail; size_t calls, live; } tracker;
static void *allocate(void *context, size_t size)
{
    tracker *t = context; ++t->calls; if (t->fail) return NULL;
    void *p = malloc(size); if (p != NULL) ++t->live; return p;
}
static void deallocate(void *context, void *p) { tracker *t = context; --t->live; free(p); }
static int ownership(void)
{
    tracker t = {0}; golem_allocator allocator = {&t, allocate, deallocate};
    golem_cost_options co = costs(); golem_optimization_policy op = policy(); golem_work_run *run = NULL;
    CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, &allocator, &co, NULL, &run) == 0);
    size_t live = t.live; t.fail = true;
    CHECK(golem_work_run_optimization_enable(run, &op) == GOLEM_ERR_OUT_OF_MEMORY && t.live == live);
    golem_optimization_policy copy;
    CHECK(golem_work_run_optimization_policy_get(run, &copy) == GOLEM_ERR_INVALID_STATE);
    t.fail = false; CHECK(golem_work_run_optimization_enable(run, &op) == GOLEM_OK);
    op.allowed[0] = 0; CHECK(golem_work_run_optimization_policy_get(run, &copy) == GOLEM_OK && copy.allowed[0] == GOLEM_OPTIMIZE_ALL);
    size_t calls = t.calls; t.fail = true; allocator.allocate = NULL;
    golem_optimization_context c; CHECK(context(run, &c) == 0); golem_optimization_proposal p = proposal(&c, GOLEM_OPTIMIZATION_ROUTE);
    golem_optimization_decision d; golem_optimization_approval a = {0}; golem_stage_snapshot s;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_OK);
    CHECK(golem_work_run_begin_optimized(run, &c, &p, &a, &s, &d, NULL) == GOLEM_OK && t.calls == calls);
    golem_work_run_free(run); CHECK(t.live == 0 && d.expected.nano_cost == 65); return 0;
}
static int failure_barrier(void)
{
    for (int enabled = 0; enabled <= 1; ++enabled)
    for (int trigger = GOLEM_FALLBACK_POLICY_DENIED; trigger <= GOLEM_FALLBACK_QUALITY_FAILURE; ++trigger)
    for (int kind = -1; kind <= GOLEM_OPTIMIZATION_FALLBACK; ++kind)
    for (int granted = 0; granted <= 1; ++granted) {
        golem_cost_options co = costs(); golem_optimization_policy op = policy();
        if (!enabled) op.allowed[GOLEM_STAGE_PLANNING] = 0;
        golem_work_run *run = NULL;
        CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &co, &op, &run) == 0);
        golem_optimization_context c; CHECK(context(run, &c) == 0);
        c.fallback_trigger = (golem_fallback_trigger)trigger;
        golem_optimization_proposal p = proposal(&c,
            kind < 0 ? GOLEM_OPTIMIZATION_NOOP : (golem_optimization_kind)kind);
        const golem_optimization_proposal *input = kind < 0 ? NULL : &p;
        golem_optimization_decision d;
        CHECK(golem_work_run_optimization_evaluate(run, &c, input, &d) == GOLEM_OK);
        CHECK(d.verdict == GOLEM_OPTIMIZATION_REJECT && d.reason == GOLEM_OPTIMIZATION_FALLBACK_FORBIDDEN);
        golem_optimization_approval a = {0};
        a.authorization = granted ? GOLEM_AUTHORIZATION_GRANTED : GOLEM_AUTHORIZATION_NONE;
        strcpy(a.route_id, !enabled || kind <= GOLEM_OPTIMIZATION_NOOP ? "baseline" : "candidate");
        golem_stage_snapshot s = {0}; s.sequence = 999; golem_diagnostic diagnostic;
        CHECK(golem_work_run_begin_optimized(run, &c, input, &a, &s, &d, &diagnostic) == GOLEM_ERR_OPTIMIZATION_REJECTED);
        CHECK(s.sequence == 999 && diagnostic.status == GOLEM_ERR_OPTIMIZATION_REJECTED);
        golem_cost_totals totals; golem_work_snapshot work; uint32_t attempts;
        CHECK(golem_cost_ledger_totals_get(golem_work_run_cost_borrow(run), &totals) == GOLEM_OK && totals.entries == 0);
        CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK && work.status == GOLEM_WORK_READY);
        CHECK(golem_work_run_attempts_get(run, GOLEM_STAGE_PLANNING, &attempts) == GOLEM_OK && attempts == 0);
        golem_work_run_free(run);
    }
    return 0;
}
static int invalid(void)
{
    golem_optimization_policy op = policy(); golem_cost_options co = costs(); golem_work_run *run = NULL;
    CHECK(make_run(GOLEM_STAGE_PLANNING, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, NULL, NULL, &run) == 0);
    CHECK(golem_work_run_optimization_enable(run, &op) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_work_run_cost_enable(run, &co) == GOLEM_OK);
    op.version = 0; CHECK(golem_work_run_optimization_enable(run, &op) == GOLEM_ERR_UNSUPPORTED_VERSION);
    op = policy(); op.allowed[0] = 8; CHECK(golem_work_run_optimization_enable(run, &op) == GOLEM_ERR_INVALID_ARGUMENT);
    op = policy(); op.fallback.triggers = 16; CHECK(golem_work_run_optimization_enable(run, &op) == GOLEM_ERR_INVALID_ARGUMENT);
    op = policy(); CHECK(golem_work_run_optimization_enable(run, &op) == GOLEM_OK);
    CHECK(golem_work_run_optimization_enable(run, &op) == GOLEM_ERR_INVALID_STATE);
    golem_optimization_context c; CHECK(context(run, &c) == 0); golem_optimization_proposal p = proposal(&c, GOLEM_OPTIMIZATION_ROUTE);
    golem_optimization_decision d = {0}; d.savings_nano = 999;
    p.version = 0; CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_ERR_UNSUPPORTED_VERSION);
    p.version = GOLEM_OPTIMIZATION_VERSION; p.kind = (golem_optimization_kind)99;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_ERR_INVALID_ARGUMENT);
    p.kind = GOLEM_OPTIMIZATION_ROUTE; memset(p.route_id, 'x', sizeof(p.route_id));
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_ERR_INVALID_ARGUMENT);
    p = proposal(&c, GOLEM_OPTIMIZATION_ROUTE); c.overhead.cost_known = false; c.overhead.nano_cost = 0;
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, &d) == GOLEM_ERR_COST_INCOMPLETE);
    CHECK(d.savings_nano == 999);
    CHECK(golem_optimization_policy_init(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_optimization_evaluate(NULL, &c, &p, &d) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_optimization_evaluate(run, NULL, &p, &d) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_optimization_evaluate(run, &c, &p, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_begin_optimized(run, &c, &p, NULL, NULL, &d, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_optimization_policy_get(NULL, &op) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_work_run_free(run); return 0;
}
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    const struct { const char *name; int (*run)(void); } cases[] = {
        {"cache", cache}, {"selection", selection}, {"noop", noop}, {"gates", gates}, {"scope", scope},
        {"fallback", fallback}, {"atomic", atomic}, {"ownership", ownership}, {"invalid", invalid},
        {"failure_barrier", failure_barrier}
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i)
        if (strcmp(argv[1], cases[i].name) == 0) return cases[i].run();
    return EXIT_FAILURE;
}
