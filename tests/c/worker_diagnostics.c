#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "golem/worker.h"
#include "test.h"
#include <errno.h>
#include <pthread.h>
#include <string.h>
#include <time.h>

static bool clock_failure, bad_clock, join_failure;
static int test_clock(clockid_t id, struct timespec *t)
{
    if (clock_failure) { errno = EPERM; return -1; }
    if (bad_clock) { *t = (struct timespec){1, -1}; return 0; }
    return clock_gettime(id, t);
}
static int test_join(pthread_t thread, void **result)
{
    if (join_failure) { errno = ENOSPC; return EDEADLK; }
    return pthread_join(thread, result);
}
static golem_status test_supervisor(const char *exe, char *const argv[], const char *cwd,
    char *const env[], golem_bytes input, uint64_t timeout, golem_status (*pulse_fn)(void *),
    void *context, golem_supervisor_result *result, golem_supervisor_observation *observation)
{
    (void)exe; (void)argv; (void)cwd; (void)env; (void)input; (void)timeout;
    (void)pulse_fn; (void)context; (void)result; (void)observation;
    return golem_system_error_note(GOLEM_ERR_IO, "worker.fixture", "read", EIO);
}
#define clock_gettime test_clock
#define pthread_join test_join
#define golem_supervisor_run_observed test_supervisor
#include "../../src/daemon/worker.c"
#undef clock_gettime
#undef pthread_join
#undef golem_supervisor_run_observed

int main(int argc, char **argv)
{
    CHECK(argc == 2);
    clock_failure = !strcmp(argv[1], "clock");
    bad_clock = !strcmp(argv[1], "clock-value");
    if (clock_failure || bad_clock) {
        golem_system_error_scope scope;
        CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
        uint64_t value = 123;
        errno = EBUSY;
        CHECK(now_ns(&value) == GOLEM_ERR_IO && value == 123);
        CHECK(golem_system_error_end(&scope) == GOLEM_OK);
        CHECK(scope.count == 1 && scope.entries[0].error_number == (clock_failure ? EPERM : 0));
        return 0;
    }
    golem_worker_options options = golem_worker_options_default();
    golem_worker_pool *pool = NULL;
    CHECK(golem_worker_open(&options, &pool) == GOLEM_OK);
    char *args[] = {"/not-executed", NULL}, *env[] = {NULL};
    golem_worker_request request = {.executable = args[0], .cwd = "/", .argv = args,
        .envp = env, .cpu_units = 1, .memory_bytes = 1, .io_slots = 1,
        .timeout_ns = UINT64_C(60000000000), .lease_ns = UINT64_C(60000000000),
        .resource_class = GOLEM_WORKER_QA};
    uint64_t id;
    CHECK(golem_worker_submit(pool, &request, &id) == GOLEM_OK);
    golem_system_error_scope scope = {.omitted = 123};
    CHECK(golem_worker_diagnostics(pool, id, &scope) == GOLEM_ERR_INVALID_STATE && scope.omitted == 123);
    golem_status recorded = GOLEM_ERR_PARSE;
    CHECK(golem_worker_recording_status(pool, id, &recorded) == GOLEM_ERR_INVALID_STATE);
    CHECK(recorded == GOLEM_ERR_PARSE);
    worker_job *job = &pool->jobs[id - 1];
    if (!strcmp(argv[1], "cancelled")) {
        CHECK(golem_worker_cancel(pool, id) == GOLEM_OK);
        CHECK(golem_worker_diagnostics(pool, id, &scope) == GOLEM_OK && scope.count == 0);
    } else {
        uint64_t now;
        CHECK(now_ns(&now) == GOLEM_OK);
        atomic_store(&job->deadline, now + UINT64_C(60000000000));
        job->state = GOLEM_WORKER_RUNNING;
        CHECK(gr_context_capture(&job->recording_context) == GOLEM_OK);
        CHECK(pthread_create(&job->thread, NULL, execute, job) == 0);
        job->threaded = true;
        CHECK(pthread_join(job->thread, NULL) == 0);
        job->threaded = false;
        CHECK(golem_worker_diagnostics(pool, id, &scope) == GOLEM_OK);
        CHECK(scope.parent == NULL && scope.count == 1);
        CHECK(!strcmp(scope.entries[0].component, "worker.fixture"));
        CHECK(scope.entries[0].error_number == EIO);
        CHECK(golem_worker_recording_status(pool, id, &recorded) == GOLEM_OK && recorded == GOLEM_OK);
        CHECK(job->status == GOLEM_ERR_IO);
        if (!strcmp(argv[1], "join")) {
            /* Only the mock sees this already-joined ID. No second real join. */
            job->threaded = join_failure = true;
            CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
            CHECK(golem_worker_close(pool) == GOLEM_ERR_IO);
            CHECK(golem_system_error_end(&scope) == GOLEM_OK);
            CHECK(scope.count == 1 && scope.entries[0].error_number == EDEADLK);
            CHECK(!strcmp(scope.entries[0].operation, "pthread_join"));
            job->threaded = join_failure = false;
        }
    }
    CHECK(golem_worker_close(pool) == GOLEM_OK);
    return 0;
}
