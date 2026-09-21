#include "golem/runtime.h"
#include "test.h"
#include <string.h>

typedef struct fixture {
    golem_runtime *runtime;
    uint8_t journal[32768]; size_t size;
    uint64_t records, calls, now, increment;
    golem_stage visited[64];
    golem_failure failure;
    bool always, invalid, stale, reentrant;
    uint64_t fail_record, fail_execute, fail_clock;
    uint64_t clocks;
} fixture;
static golem_status record(void *context, golem_journal_type type, golem_bytes payload)
{
    fixture *f = context;
    if (f->records + 1 == f->fail_record) return GOLEM_ERR_IO;
    size_t required;
    golem_status s = golem_journal_record_encode(type, f->records + 1, payload,
        f->journal + f->size, sizeof(f->journal) - f->size, &required, NULL);
    if (s == GOLEM_OK) { f->size += required; ++f->records; }
    return s;
}
static golem_status execute(void *context, golem_work_run *run,
    const golem_stage_snapshot *stage, uint64_t deadline, golem_runtime_result *out)
{
    fixture *f = context; (void)run; (void)deadline;
    if (f->calls >= 64) return GOLEM_ERR_OVERFLOW;
    f->visited[f->calls++] = stage->stage;
    if (f->reentrant && (golem_runtime_step(f->runtime) != GOLEM_ERR_INVALID_STATE ||
        golem_runtime_drive(f->runtime) != GOLEM_ERR_INVALID_STATE ||
        golem_runtime_cancel(f->runtime) != GOLEM_ERR_INVALID_STATE)) return GOLEM_ERR_INVALID_STATE;
    if (f->calls == f->fail_execute) return GOLEM_ERR_IO;
    bool fail = stage->stage == GOLEM_STAGE_QA && f->failure != GOLEM_FAILURE_NONE && (f->always || stage->attempt == 1);
    *out = (golem_runtime_result){stage->sequence + (f->stale ? 1 : 0),
        fail ? GOLEM_STAGE_FAILED : GOLEM_STAGE_PASSED,
        fail ? f->failure : GOLEM_FAILURE_NONE, !fail && !f->invalid};
    return GOLEM_OK;
}
static golem_status now(void *context, uint64_t *out)
{
    fixture *f = context;
    if (++f->clocks == f->fail_clock) return GOLEM_ERR_IO;
    *out = f->now; f->now += f->increment; return GOLEM_OK;
}
static int capsule(golem_autonomy mode, const golem_graph_spec *spec, golem_work_capsule **out)
{
    golem_graph_spec gs; CHECK(golem_stage_graph_default_spec(&gs) == GOLEM_OK);
    golem_stage_graph *graph = NULL; CHECK(golem_stage_graph_create(spec == NULL ? &gs : spec, &graph) == GOLEM_OK);
    const char *scope[] = {"local"}, *acceptance[] = {"verified test result"};
    golem_capsule_spec cs = {.id = "runtime", .goal = "Exercise local runtime", .scope = {scope, 1}, .acceptance = {acceptance, 1}, .graph = graph};
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) cs.permissions[i] = mode;
    CHECK(golem_work_capsule_create(&cs, out) == GOLEM_OK); golem_stage_graph_free(graph); return 0;
}
static int setup(fixture *f, golem_autonomy mode, const golem_graph_spec *gs, uint32_t attempts, uint64_t max, uint64_t timeout)
{
    golem_work_capsule *c = NULL; CHECK(capsule(mode, gs, &c) == 0);
    golem_runtime_options options = {GOLEM_RUNTIME_VERSION, attempts, max, timeout};
    golem_runtime_ops ops = {record, execute, now};
    CHECK(golem_runtime_create("local-run", c, &options, &ops, f, NULL, &f->runtime) == GOLEM_OK);
    golem_work_capsule_free(c); return 0;
}
static int replay(fixture *f, golem_work_status expected)
{
    golem_work_run *run = NULL;
    CHECK(golem_journal_replay((golem_bytes){f->journal, f->size}, NULL, &run, NULL) == GOLEM_OK);
    golem_work_snapshot s; CHECK(golem_work_run_snapshot_get(run, &s) == GOLEM_OK);
    CHECK(s.status == expected); golem_work_run_free(run); return 0;
}
static int matrix(void)
{
    const golem_failure failures[] = {GOLEM_FAILURE_PLANNING_GAP, GOLEM_FAILURE_UX_MISMATCH,
        GOLEM_FAILURE_PUBLISHING_GAP, GOLEM_FAILURE_IMPLEMENTATION_DEFECT, GOLEM_FAILURE_QA_FLAKE,
        GOLEM_FAILURE_AUDIT_GAP, GOLEM_FAILURE_TIMEOUT};
    const golem_stage targets[] = {GOLEM_STAGE_PLANNING, GOLEM_STAGE_UX, GOLEM_STAGE_PUBLISHING,
        GOLEM_STAGE_DEVELOPMENT, GOLEM_STAGE_QA, GOLEM_STAGE_PLANNING, GOLEM_STAGE_QA};
    for (size_t i = 0; i < sizeof(failures) / sizeof(failures[0]); ++i) {
        fixture f = {.failure = failures[i], .reentrant = true};
        CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 3, 32, 0) == 0);
        CHECK(golem_runtime_drive(f.runtime) == GOLEM_OK);
        CHECK(f.visited[5] == targets[i]);
        CHECK(f.calls == 5 + (uint64_t)(GOLEM_STAGE_COUNT - targets[i]));
        golem_runtime_report report; CHECK(golem_runtime_report_get(f.runtime, &report) == GOLEM_OK);
        CHECK(report.stopped && report.reentries == 1 && report.work.status == GOLEM_WORK_SUCCEEDED);
        CHECK(replay(&f, GOLEM_WORK_SUCCEEDED) == 0);
        uint64_t calls = f.calls; CHECK(golem_runtime_drive(f.runtime) == GOLEM_OK && calls == f.calls);
        golem_runtime_free(f.runtime);
    }
    return 0;
}
static int limits(void)
{
    for (int kind = 0; kind < 2; ++kind) {
        fixture f = {.failure = GOLEM_FAILURE_QA_FLAKE, .always = true};
        CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 2, kind == 0 ? 32 : 3, 0) == 0);
        CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_ATTEMPT_LIMIT);
        CHECK(f.calls == (kind == 0 ? 6u : 3u));
        CHECK(golem_runtime_step(f.runtime) == GOLEM_ERR_ATTEMPT_LIMIT);
        CHECK(replay(&f, kind == 0 ? GOLEM_WORK_FAILED : GOLEM_WORK_READY) == 0);
        golem_runtime_free(f.runtime);
    }
    return 0;
}
static int policy(void)
{
    for (int mode = GOLEM_AUTONOMY_DENY; mode <= GOLEM_AUTONOMY_ASK_ALWAYS; ++mode) {
        fixture f = {0}; CHECK(setup(&f, (golem_autonomy)mode, NULL, 2, 16, 0) == 0);
        golem_status expected = mode == GOLEM_AUTONOMY_DENY ? GOLEM_ERR_POLICY_DENIED :
            mode == GOLEM_AUTONOMY_ASK_ALWAYS ? GOLEM_ERR_APPROVAL_REQUIRED : GOLEM_OK;
        CHECK(golem_runtime_drive(f.runtime) == expected);
        CHECK(f.calls == (expected == GOLEM_OK ? 6u : 0u));
        golem_runtime_free(f.runtime);
    }
    for (int failure = GOLEM_FAILURE_POLICY_DENIED; failure <= GOLEM_FAILURE_BUDGET_EXHAUSTED; ++failure) {
        fixture f = {.failure = (golem_failure)failure}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 3, 32, 0) == 0);
        CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_POLICY_DENIED);
        CHECK(f.calls == 5); CHECK(replay(&f, GOLEM_WORK_BLOCKED) == 0); golem_runtime_free(f.runtime);
    }
    return 0;
}
static int timeout(void)
{
    fixture f = {.now = 100, .increment = 10}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 2, 16, 10) == 0);
    CHECK(golem_runtime_step(f.runtime) == GOLEM_OK);
    golem_stage_snapshot stage; CHECK(golem_stage_run_snapshot_get(golem_work_run_stage_borrow(golem_runtime_run_borrow(f.runtime)), &stage) == GOLEM_OK);
    CHECK(stage.failure == GOLEM_FAILURE_TIMEOUT);
    f.increment = 0;
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_OK);
    CHECK(f.visited[0] == GOLEM_STAGE_PLANNING && f.visited[1] == GOLEM_STAGE_PLANNING);
    CHECK(replay(&f, GOLEM_WORK_SUCCEEDED) == 0); golem_runtime_free(f.runtime);
    f = (fixture){.now = UINT64_MAX}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 2, 16, 10) == 0);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_OVERFLOW && f.calls == 0); golem_runtime_free(f.runtime);
    f = (fixture){.now = 100}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 2, 16, 10) == 0);
    CHECK(golem_runtime_step(f.runtime) == GOLEM_OK); f.now = 99;
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_INVALID_STATE && f.calls == 1); golem_runtime_free(f.runtime);
    f = (fixture){.fail_clock = 2}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 2, 16, 10) == 0);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_IO); CHECK(replay(&f, GOLEM_WORK_RUNNING) == 0); golem_runtime_free(f.runtime);
    f = (fixture){.increment = 100, .fail_execute = 1}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 2, 16, 10) == 0);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_IO && f.calls == 1);
    CHECK(replay(&f, GOLEM_WORK_RUNNING) == 0); golem_runtime_free(f.runtime);
    f = (fixture){.failure = GOLEM_FAILURE_STALE_LEASE}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 2, 16, 10) == 0);
    for (int i = 0; i < 4; ++i) CHECK(golem_runtime_step(f.runtime) == GOLEM_OK);
    f.increment = 100;
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_POLICY_DENIED && f.calls == 5);
    CHECK(replay(&f, GOLEM_WORK_BLOCKED) == 0); golem_runtime_free(f.runtime);
    return 0;
}
static int failures(void)
{
    for (unsigned i = 0; i < 6; ++i) {
        fixture f = {0};
        if (i < 3) f.fail_record = i + 1;
        if (i == 3) f.fail_execute = 1;
        if (i == 4) f.invalid = true;
        if (i == 5) f.stale = true;
        CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 3, 32, 0) == 0);
        golem_status expected = i < 4 ? GOLEM_ERR_IO : i == 4 ? GOLEM_ERR_INVALID_ARGUMENT : GOLEM_ERR_STALE_RESULT;
        CHECK(golem_runtime_drive(f.runtime) == expected);
        uint64_t calls = f.calls, records = f.records;
        CHECK(golem_runtime_drive(f.runtime) == expected && f.calls == calls && f.records == records);
        CHECK(golem_runtime_cancel(f.runtime) == GOLEM_ERR_INVALID_STATE);
        if (i != 0) CHECK(replay(&f, i == 1 ? GOLEM_WORK_READY : GOLEM_WORK_RUNNING) == 0);
        golem_runtime_free(f.runtime);
    }
    fixture f = {.failure = GOLEM_FAILURE_QA_FLAKE, .fail_record = 12};
    CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 3, 32, 0) == 0);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_IO && f.calls == 5);
    CHECK(replay(&f, GOLEM_WORK_FAILED) == 0); golem_runtime_free(f.runtime); return 0;
}
static int overrides(void)
{
    golem_graph_spec gs; CHECK(golem_stage_graph_default_spec(&gs) == GOLEM_OK);
    gs.count = 2; gs.order[0] = GOLEM_STAGE_DEVELOPMENT; gs.order[1] = GOLEM_STAGE_QA;
    fixture f = {.failure = GOLEM_FAILURE_UX_MISMATCH}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, &gs, 3, 32, 0) == 0);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_NO_REENTRY && f.calls == 2); golem_runtime_free(f.runtime);
    gs.reentry[GOLEM_FAILURE_UX_MISMATCH] = GOLEM_STAGE_DEVELOPMENT;
    f = (fixture){.failure = GOLEM_FAILURE_UX_MISMATCH}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, &gs, 3, 32, 0) == 0);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_OK && f.calls == 4);
    CHECK(replay(&f, GOLEM_WORK_SUCCEEDED) == 0); golem_runtime_free(f.runtime);
    f = (fixture){.failure = GOLEM_FAILURE_UNKNOWN}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 3, 32, 0) == 0);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_NO_REENTRY); golem_runtime_free(f.runtime); return 0;
}
static int cancel(void)
{
    for (int steps = 0; steps < 2; ++steps) {
        fixture f = {0}; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 3, 32, 0) == 0);
        if (steps) CHECK(golem_runtime_step(f.runtime) == GOLEM_OK);
        CHECK(golem_runtime_cancel(f.runtime) == GOLEM_OK);
        CHECK(golem_runtime_cancel(f.runtime) == GOLEM_OK);
        CHECK(golem_runtime_drive(f.runtime) == GOLEM_OK && f.calls == (uint64_t)steps);
        CHECK(replay(&f, GOLEM_WORK_CANCELLED) == 0); golem_runtime_free(f.runtime);
    }
    CHECK(golem_runtime_step(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_runtime_drive(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_runtime_cancel(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_runtime_report_get(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_runtime_run_borrow(NULL) == NULL); golem_runtime_free(NULL); return 0;
}
typedef struct allocations { size_t calls, fail, live; } allocations;
static void *allocate(void *context, size_t size)
{
    allocations *a = context; if (++a->calls == a->fail) return NULL;
    void *p = malloc(size); if (p != NULL) ++a->live; return p;
}
static void deallocate(void *context, void *p) { allocations *a = context; --a->live; free(p); }
static int ownership(void)
{
    golem_work_capsule *c = NULL; CHECK(capsule(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &c) == 0);
    fixture invalid = {0}; golem_runtime *output = NULL;
    golem_runtime_options bad = {2, 2, 16, 0}; golem_runtime_ops callbacks = {record, execute, now};
    CHECK(golem_runtime_create("invalid", c, &bad, &callbacks, &invalid, NULL, &output) == GOLEM_ERR_UNSUPPORTED_VERSION);
    bad.version = 1; bad.max_stage_runs = 0;
    CHECK(golem_runtime_create("invalid", c, &bad, &callbacks, &invalid, NULL, &output) == GOLEM_ERR_INVALID_ARGUMENT);
    bad.max_stage_runs = 16; callbacks.record = NULL;
    CHECK(golem_runtime_create("invalid", c, &bad, &callbacks, &invalid, NULL, &output) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(output == NULL && invalid.records == 0);
    bool succeeded = false;
    for (size_t fail = 1; fail < 100; ++fail) {
        allocations a = {.fail = fail}; golem_allocator allocator = {&a, allocate, deallocate};
        fixture f = {0}; golem_runtime *r = NULL;
        golem_runtime_options options = {1, 2, 16, 0}; golem_runtime_ops ops = {record, execute, now};
        golem_status s = golem_runtime_create("owned", c, &options, &ops, &f, &allocator, &r);
        if (s == GOLEM_OK) {
            options.max_stage_runs = 0; ops.execute = NULL;
            CHECK(golem_runtime_drive(r) == GOLEM_OK); golem_runtime_free(r); succeeded = true;
        } else CHECK(s == GOLEM_ERR_OUT_OF_MEMORY && r == NULL && f.records == 0);
        CHECK(a.live == 0); if (succeeded) break;
    }
    CHECK(succeeded); golem_work_capsule_free(c); return 0;
}
int main(int argc, char **argv)
{
    const struct { const char *name; int (*run)(void); } cases[] = {
        {"matrix", matrix}, {"limits", limits}, {"policy", policy}, {"timeout", timeout},
        {"failures", failures}, {"overrides", overrides}, {"cancel", cancel}, {"ownership", ownership}};
    if (argc != 2) return 1;
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) if (strcmp(argv[1], cases[i].name) == 0) return cases[i].run();
    return 1;
}
