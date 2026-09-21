#include "golem/lease.h"
#include "golem/runtime.h"
#include "test.h"
#include <string.h>

typedef struct fixture {
    golem_lease *lease;
    golem_lease_snapshot owned;
    golem_runtime *runtime;
    golem_lease_event events[64]; size_t events_count;
    uint64_t now, calls, records;
    unsigned mode;
    bool audit_failure;
    uint8_t journal[32768]; size_t journal_size;
} fixture;
static golem_status audit(void *context, const golem_lease_event *event)
{
    fixture *f = context;
    if (f->audit_failure) return GOLEM_ERR_IO;
    if (f->events_count >= 64) return GOLEM_ERR_OVERFLOW;
    f->events[f->events_count++] = *event;
    return GOLEM_OK;
}
static int authority(fixture *f, const char *resource)
{
    golem_lease_ops ops = {audit};
    CHECK(golem_lease_create(resource, &ops, f, NULL, &f->lease) == GOLEM_OK);
    CHECK(golem_lease_acquire(f->lease, "worker-A", 0, 10, &f->owned) == GOLEM_OK);
    return 0;
}
static int lifecycle(void)
{
    fixture f = {0}; CHECK(authority(&f, "work") == 0);
    CHECK(f.owned.token.fence == 1 && f.owned.expires_ns == 10);
    golem_lease_snapshot next = {0};
    CHECK(golem_lease_acquire(f.lease, "worker-A", 1, 10, &next) == GOLEM_ERR_LEASE_BUSY);
    CHECK(next.token.fence == 0);
    CHECK(golem_lease_acquire(f.lease, "worker-B", 1, 10, &next) == GOLEM_ERR_LEASE_BUSY);
    CHECK(golem_lease_validate(f.lease, &f.owned.token, 9) == GOLEM_OK);
    CHECK(golem_lease_heartbeat(f.lease, &f.owned.token, 9, 10, &next) == GOLEM_OK);
    CHECK(next.token.fence == 1 && next.expires_ns == 19);
    CHECK(golem_lease_validate(f.lease, &f.owned.token, 10) == GOLEM_OK);
    CHECK(golem_lease_heartbeat(f.lease, &f.owned.token, 10, 1, &next) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_lease_validate(f.lease, &f.owned.token, 19) == GOLEM_ERR_STALE_LEASE);
    CHECK(golem_lease_heartbeat(f.lease, &f.owned.token, 19, 10, &next) == GOLEM_ERR_STALE_LEASE);
    CHECK(golem_lease_validate(f.lease, &f.owned.token, 18) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_lease_acquire(f.lease, "worker-B", 19, 10, &next) == GOLEM_OK);
    CHECK(next.token.fence == 2);
    CHECK(golem_lease_release(f.lease, &f.owned.token, 19) == GOLEM_ERR_STALE_LEASE);
    CHECK(golem_lease_heartbeat(f.lease, &f.owned.token, 19, 100, &f.owned) == GOLEM_ERR_STALE_LEASE);
    CHECK(golem_lease_validate(f.lease, &next.token, 20) == GOLEM_OK);
    CHECK(golem_lease_release(f.lease, &next.token, 20) == GOLEM_OK);
    CHECK(golem_lease_validate(f.lease, &next.token, 20) == GOLEM_ERR_STALE_LEASE);
    CHECK(golem_lease_acquire(f.lease, "worker-B", 20, 10, &next) == GOLEM_OK && next.token.fence == 3);
    CHECK(f.events_count == 5);
    for (size_t i = 0; i < f.events_count; ++i) CHECK(f.events[i].sequence == i + 1);
    CHECK(f.events[1].type == GOLEM_LEASE_HEARTBEAT && f.events[3].type == GOLEM_LEASE_RELEASED);
    golem_lease_free(f.lease); return 0;
}
static int identity(void)
{
    fixture a = {0}, b = {0}; CHECK(authority(&a, "work") == 0); CHECK(authority(&b, "work") == 0);
    CHECK(golem_lease_validate(b.lease, &a.owned.token, 0) == GOLEM_ERR_STALE_LEASE);
    golem_lease_token forged = b.owned.token; ++forged.fence;
    CHECK(golem_lease_validate(b.lease, &forged, 0) == GOLEM_ERR_STALE_LEASE);
    forged = b.owned.token; forged.version = 2;
    CHECK(golem_lease_validate(b.lease, &forged, 0) == GOLEM_ERR_STALE_LEASE);
    golem_lease_free(a.lease); golem_lease_free(b.lease); return 0;
}
static int invalid(void)
{
    fixture f = {0}; CHECK(authority(&f, "work") == 0);
    golem_lease_snapshot out = {0};
    CHECK(golem_lease_acquire(f.lease, "worker", 10, 0, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_lease_acquire(f.lease, "worker", UINT64_MAX, 1, &out) == GOLEM_ERR_OVERFLOW);
    CHECK(out.token.fence == 0);
    CHECK(golem_lease_acquire(f.lease, "worker", 10, 1, &out) == GOLEM_ERR_INVALID_STATE);
    golem_lease_free(f.lease);
    f = (fixture){0}; CHECK(authority(&f, "work") == 0); f.audit_failure = true;
    CHECK(golem_lease_heartbeat(f.lease, &f.owned.token, 1, 20, &out) == GOLEM_ERR_IO);
    CHECK(golem_lease_validate(f.lease, &f.owned.token, 1) == GOLEM_ERR_STALE_LEASE);
    CHECK(golem_lease_acquire(f.lease, "worker", 50, 10, &out) == GOLEM_ERR_STALE_LEASE);
    CHECK(f.events_count == 1); golem_lease_free(f.lease);
    CHECK(golem_lease_validate(NULL, NULL, 0) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_lease_resource_borrow(NULL) == NULL); golem_lease_free(NULL);
    return 0;
}
static golem_status now(void *context, uint64_t *out) { *out = ((fixture *)context)->now; return GOLEM_OK; }
static golem_status record(void *context, golem_journal_type type, golem_bytes payload)
{
    fixture *f = context; size_t n;
    golem_status s = golem_journal_record_encode(type, f->records + 1, payload,
        f->journal + f->journal_size, sizeof(f->journal) - f->journal_size, &n, NULL);
    if (s == GOLEM_OK) { f->journal_size += n; ++f->records; }
    if (f->mode == 3 && type == GOLEM_JOURNAL_STARTED) f->now = 10;
    return s;
}
static golem_status execute(void *context, golem_work_run *run, const golem_stage_snapshot *stage,
    uint64_t deadline, golem_runtime_result *out)
{
    fixture *f = context; (void)deadline; ++f->calls;
    if (f->mode == 1 || f->mode == 2 || f->mode == 5) f->now = 10;
    if (f->mode == 2) {
        golem_lease_snapshot takeover;
        golem_status s = golem_lease_acquire(f->lease, "worker-B", f->now, 100, &takeover);
        if (s != GOLEM_OK) return s;
    }
    if (f->mode == 4) {
        f->now += 5;
        golem_lease_snapshot updated;
        golem_status s = golem_runtime_heartbeat(f->runtime, 20, &updated);
        if (s != GOLEM_OK) return s;
    }
    if (f->mode == 5) {
        if (golem_work_run_finish(run, stage->sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) != GOLEM_ERR_STALE_LEASE)
            return GOLEM_ERR_INVALID_STATE;
        /* Even an executor ignoring a failed checkpoint cannot publish success. */
        if (golem_runtime_checkpoint(f->runtime) != GOLEM_ERR_STALE_LEASE) return GOLEM_ERR_INVALID_STATE;
    }
    *out = (golem_runtime_result){stage->sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true};
    if (f->mode == 6 && stage->stage == GOLEM_STAGE_QA)
        *out = (golem_runtime_result){stage->sequence, GOLEM_STAGE_FAILED, GOLEM_FAILURE_QA_FLAKE, false};
    return GOLEM_OK;
}
static int runtime_setup(fixture *f)
{
    CHECK(authority(f, "leased-run") == 0);
    golem_graph_spec gs; CHECK(golem_stage_graph_default_spec(&gs) == GOLEM_OK);
    golem_stage_graph *graph = NULL; CHECK(golem_stage_graph_create(&gs, &graph) == GOLEM_OK);
    const char *text[] = {"local"}; golem_capsule_spec spec = {.id = "lease", .goal = "Test ownership",
        .scope = {text, 1}, .acceptance = {text, 1}, .graph = graph};
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) spec.permissions[i] = GOLEM_AUTONOMY_AUTO_LOCAL;
    golem_work_capsule *c = NULL; CHECK(golem_work_capsule_create(&spec, &c) == GOLEM_OK);
    golem_runtime_options options = {1, 3, 32, 0}; golem_runtime_ops ops = {record, execute, now};
    CHECK(golem_runtime_create("leased-run", c, &options, &ops, f, NULL, &f->runtime) == GOLEM_OK);
    fixture wrong = {0}; CHECK(authority(&wrong, "other-run") == 0);
    CHECK(golem_runtime_lease_bind(f->runtime, wrong.lease, &wrong.owned.token) == GOLEM_ERR_IDENTITY_MISMATCH);
    CHECK(golem_runtime_lease_bind(f->runtime, f->lease, &wrong.owned.token) == GOLEM_ERR_STALE_LEASE);
    golem_lease_free(wrong.lease);
    CHECK(golem_runtime_lease_bind(f->runtime, f->lease, &f->owned.token) == GOLEM_OK);
    CHECK(golem_runtime_lease_bind(f->runtime, f->lease, &f->owned.token) == GOLEM_ERR_INVALID_STATE);
    golem_work_capsule_free(c); golem_stage_graph_free(graph); return 0;
}
static int runtime(void)
{
    for (unsigned mode = 0; mode < 6; ++mode) {
        fixture f = {.mode = mode}; CHECK(runtime_setup(&f) == 0);
        if (mode == 0) f.now = 10;
        golem_status expected = mode == 4 ? GOLEM_OK : GOLEM_ERR_STALE_LEASE;
        CHECK(golem_runtime_drive(f.runtime) == expected);
        CHECK(f.calls == (mode == 4 ? 6u : mode == 0 || mode == 3 ? 0u : 1u));
        golem_runtime_report report; CHECK(golem_runtime_report_get(f.runtime, &report) == GOLEM_OK);
        CHECK(report.stopped);
        CHECK(report.work.status == (mode == 4 ? GOLEM_WORK_SUCCEEDED : mode == 0 ? GOLEM_WORK_READY : GOLEM_WORK_RUNNING));
        uint64_t calls = f.calls, records = f.records;
        CHECK(golem_runtime_drive(f.runtime) == expected && calls == f.calls && records == f.records);
        if (mode != 0) {
            golem_work_run *replayed = NULL;
            CHECK(golem_journal_replay((golem_bytes){f.journal, f.journal_size}, NULL, &replayed, NULL) == GOLEM_OK);
            golem_work_snapshot work; CHECK(golem_work_run_snapshot_get(replayed, &work) == GOLEM_OK);
            CHECK(work.status == report.work.status); golem_work_run_free(replayed);
        }
        if (mode == 4) CHECK(f.events_count == 7);
        golem_runtime_free(f.runtime); golem_lease_free(f.lease);
    }
    fixture f = {0}; CHECK(runtime_setup(&f) == 0);
    CHECK(golem_runtime_step(f.runtime) == GOLEM_OK); f.now = 10;
    CHECK(golem_runtime_cancel(f.runtime) == GOLEM_ERR_STALE_LEASE && f.calls == 1);
    golem_runtime_free(f.runtime); golem_lease_free(f.lease);
    f = (fixture){0}; CHECK(runtime_setup(&f) == 0); f.now = 10;
    golem_lease_snapshot updated;
    CHECK(golem_runtime_heartbeat(f.runtime, 100, &updated) == GOLEM_ERR_STALE_LEASE);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_STALE_LEASE && f.calls == 0);
    golem_runtime_free(f.runtime); golem_lease_free(f.lease);
    f = (fixture){.mode = 6}; CHECK(runtime_setup(&f) == 0);
    for (int i = 0; i < 5; ++i) CHECK(golem_runtime_step(f.runtime) == GOLEM_OK);
    f.now = 10;
    CHECK(golem_runtime_step(f.runtime) == GOLEM_ERR_STALE_LEASE && f.calls == 5);
    golem_runtime_report report; CHECK(golem_runtime_report_get(f.runtime, &report) == GOLEM_OK);
    CHECK(report.reentries == 0 && report.work.status == GOLEM_WORK_FAILED);
    golem_runtime_free(f.runtime); golem_lease_free(f.lease);
    f = (fixture){0}; CHECK(runtime_setup(&f) == 0);
    CHECK(golem_lease_release(f.lease, &f.owned.token, 0) == GOLEM_OK);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_STALE_LEASE && f.calls == 0);
    golem_runtime_free(f.runtime); golem_lease_free(f.lease);
    f = (fixture){0}; CHECK(runtime_setup(&f) == 0); f.now = 5;
    CHECK(golem_runtime_checkpoint(f.runtime) == GOLEM_OK); f.now = 4;
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_INVALID_STATE && f.calls == 0);
    golem_runtime_free(f.runtime); golem_lease_free(f.lease);
    f = (fixture){0}; CHECK(runtime_setup(&f) == 0); f.audit_failure = true;
    CHECK(golem_runtime_heartbeat(f.runtime, 20, &updated) == GOLEM_ERR_IO);
    CHECK(golem_runtime_drive(f.runtime) == GOLEM_ERR_IO && f.calls == 0);
    golem_runtime_free(f.runtime); golem_lease_free(f.lease); return 0;
}
typedef struct allocation { size_t live; bool fail; } allocation;
static void *allocate(void *context, size_t size)
{
    allocation *a = context;
    if (a->fail) return NULL;
    void *memory = malloc(size); if (memory != NULL) ++a->live; return memory;
}
static void deallocate(void *context, void *memory) { --((allocation *)context)->live; free(memory); }
static int ownership(void)
{
    allocation a = {.fail = true}; golem_allocator allocator = {&a, allocate, deallocate};
    fixture f = {0}; golem_lease_ops ops = {audit}; char resource[] = "copied";
    CHECK(golem_lease_create(resource, &ops, &f, &allocator, &f.lease) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(f.lease == NULL && a.live == 0);
    a.fail = false;
    CHECK(golem_lease_create(resource, &ops, &f, &allocator, &f.lease) == GOLEM_OK);
    resource[0] = 'X'; ops.record = NULL; allocator.allocate = NULL;
    CHECK(strcmp(golem_lease_resource_borrow(f.lease), "copied") == 0);
    CHECK(golem_lease_acquire(f.lease, "worker", 0, 10, &f.owned) == GOLEM_OK);
    golem_lease_free(f.lease); CHECK(a.live == 0); return 0;
}
int main(int argc, char **argv)
{
    if (argc != 2) return 1;
    if (strcmp(argv[1], "lifecycle") == 0) return lifecycle();
    if (strcmp(argv[1], "identity") == 0) return identity();
    if (strcmp(argv[1], "invalid") == 0) return invalid();
    if (strcmp(argv[1], "runtime") == 0) return runtime();
    if (strcmp(argv[1], "ownership") == 0) return ownership();
    return 1;
}
