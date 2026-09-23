#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/worker.h"
#include "test.h"
#include <errno.h>
#include <pthread.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static bool fail_thread, lost_child;
static int create_thread(pthread_t *thread, const pthread_attr_t *attr, void *(*entry)(void *),
                         void *context)
{
    return fail_thread ? EAGAIN : pthread_create(thread, attr, entry, context);
}
static golem_status observed(const char *exe, char *const argv[], const char *cwd,
                             char *const env[], golem_bytes input, uint64_t timeout,
                             golem_status (*pulse_fn)(void *), void *context,
                             golem_supervisor_result *result,
                             golem_supervisor_observation *observation)
{
    if (lost_child) {
        *observation = (golem_supervisor_observation){.spawned = true, .reaped = false};
        return GOLEM_ERR_IO;
    }
    return golem_supervisor_run_observed(exe, argv, cwd, env, input, timeout, pulse_fn, context,
                                         result, observation);
}
#define pthread_create create_thread
#define golem_supervisor_run_observed observed
#include "../../src/daemon/worker.c"
#undef pthread_create
#undef golem_supervisor_run_observed

static golem_status publication(void *context, const golem_digest *ns,
                                const golem_admission_ticket *ticket, golem_digest *proof)
{
    (void)ns;
    golem_worker_pool *pool = context;
    if (golem_worker_cancel(pool, 1) != GOLEM_ERR_INVALID_STATE)
        return GOLEM_ERR_INVALID_STATE;
    *proof = ticket->request.runtime_binding;
    return GOLEM_OK;
}
static void *no_memory(void *ctx, size_t bytes)
{
    (void)ctx;
    (void)bytes;
    return NULL;
}
static void no_free(void *ctx, void *ptr)
{
    (void)ctx;
    (void)ptr;
}
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    fail_thread = !strcmp(argv[1], "thread");
    lost_child = !strcmp(argv[1], "reap");
    golem_worker_options o = golem_worker_options_default();
    golem_worker_pool *p = NULL;
    golem_allocator oom = {NULL, no_memory, no_free};
    o.allocator = &oom;
    CHECK(golem_worker_open(&o, &p) == GOLEM_ERR_OUT_OF_MEMORY && p == NULL);
    o.allocator = NULL;
    o.limits.queue_bytes = 1;
    CHECK(golem_worker_open(&o, &p) == GOLEM_OK);
    p->events_enabled = false; /* Simulate unavailable diagnostic stream identity. */
    golem_runtime_event unavailable[1]; golem_runtime_event_page unavailable_page;
    CHECK(golem_worker_events(p, NULL, unavailable, 1, &unavailable_page) == GOLEM_ERR_CRYPTO);
    char *args[] = {"/bin/echo", "safe", NULL}, *env[] = {NULL};
    golem_worker_request r = {.executable = args[0],
                              .cwd = "/",
                              .argv = args,
                              .envp = env,
                              .cpu_units = 1,
                              .memory_bytes = 1,
                              .io_slots = 1,
                              .timeout_ns = 1000000000,
                              .lease_ns = 1000000000,
                              .resource_class = GOLEM_WORKER_QA};
    uint64_t id = 999;
    CHECK(golem_worker_submit(p, &r, &id) == GOLEM_ERR_QUEUE_FULL && id == 999);
    CHECK(golem_worker_close(p) == GOLEM_OK);
    o = golem_worker_options_default();
    CHECK(golem_worker_open(&o, &p) == GOLEM_OK);
    p->clock_known = false; /* Unknown clock must not become a zero duration. */
    r.io_slots = 0;
    CHECK(golem_worker_submit(p, &r, &id) == GOLEM_ERR_INVALID_ARGUMENT);
    r.io_slots = 1;
    r.lease_ns = 0;
    CHECK(golem_worker_submit(p, &r, &id) == GOLEM_ERR_INVALID_ARGUMENT);
    r.lease_ns = 1000000000;
    r.input.size = 16385;
    CHECK(golem_worker_submit(p, &r, &id) == GOLEM_ERR_INVALID_ARGUMENT);
    r.input.size = 0;
    char *many[GOLEM_WORKER_VECTOR_MAX + 2];
    for (unsigned i = 0; i <= GOLEM_WORKER_VECTOR_MAX; ++i)
        many[i] = "x";
    many[GOLEM_WORKER_VECTOR_MAX + 1] = NULL;
    r.argv = many;
    CHECK(golem_worker_submit(p, &r, &id) == GOLEM_ERR_BUFFER_TOO_SMALL);
    r.argv = args;
    char oversized[GOLEM_WORKER_PAYLOAD_MAX];
    memset(oversized, 'x', sizeof(oversized));
    oversized[0] = '/';
    r.executable = oversized;
    CHECK(golem_worker_submit(p, &r, &id) == GOLEM_ERR_BUFFER_TOO_SMALL);
    r.executable = args[0];
    CHECK(id == 999);
    char path[] = "/tmp/golem-worker-fault-XXXXXX", root[4096];
    CHECK(mkdtemp(path) != NULL && realpath(path, root) != NULL);
    golem_admission_options ao = {
        .size = sizeof(ao), .version = 1, .create = true, .limits = {1, 1, 1, 0}};
    golem_admission *a;
    CHECK(golem_admission_open(root, &ao, &a) == GOLEM_OK);
    golem_admission_request ar = {.operation = "one",
                                  .work = "one",
                                  .session = "one",
                                  .cpu_millis = 1,
                                  .memory_bytes = 1,
                                  .foreground = true,
                                  .runtime_binding = {{1}}};
    golem_admission_ticket ticket;
    CHECK(golem_admission_enqueue(a, &ar, &id) == GOLEM_OK);
    CHECK(golem_admission_grant(a, &ticket) == GOLEM_OK);
    CHECK(golem_worker_submit(p, &r, &id) == GOLEM_OK);
    CHECK(golem_worker_start(p, id, a, "one", publication, p) == GOLEM_OK);
    golem_worker_snapshot snapshot;
    for (unsigned i = 0; i < 1000; ++i) {
        CHECK(golem_worker_inspect(p, id, &snapshot) == GOLEM_OK);
        if (snapshot.state == GOLEM_WORKER_FINISHED || snapshot.state == GOLEM_WORKER_ATTENTION)
            break;
        struct timespec delay = {0, 1000000};
        (void)nanosleep(&delay, NULL);
    }
    CHECK(snapshot.status == GOLEM_ERR_IO);
    golem_runtime_event events[64]; golem_runtime_event_page page;
    CHECK(golem_worker_events(p, NULL, events, 64, &page) == GOLEM_OK);
    bool reconcile = false, dispatched = false, preparation_failed = false;
    for (size_t i = 0; i < page.count; ++i) {
        if (events[i].kind != GOLEM_EVENT_INITIALIZED) CHECK(!events[i].elapsed_known);
        reconcile |= events[i].kind == GOLEM_EVENT_RECONCILE;
        dispatched |= events[i].kind == GOLEM_EVENT_DISPATCHED;
        preparation_failed |= events[i].kind == GOLEM_EVENT_PREPARATION_FAILED;
    }
    CHECK(lost_child ? (reconcile && dispatched) : (preparation_failed && !dispatched));
    if (lost_child) {
        CHECK(snapshot.state == GOLEM_WORKER_ATTENTION);
        CHECK(golem_worker_acknowledge(p, id, a, "one") == GOLEM_ERR_INVALID_STATE);
        CHECK(golem_admission_close(a) == GOLEM_OK);
        CHECK(golem_admission_open(root, &ao, &a) == GOLEM_OK);
        CHECK(golem_admission_lookup(a, "one", &ticket) == GOLEM_OK);
        CHECK(ticket.state == GOLEM_ADMISSION_RECONCILE_REQUIRED);
    } else {
        CHECK(snapshot.state == GOLEM_WORKER_FINISHED && !snapshot.observation.spawned);
        CHECK(golem_admission_settle(a, ticket.token, (golem_digest){{2}}) == GOLEM_OK);
        CHECK(golem_admission_release(a, ticket.token) == GOLEM_OK);
        CHECK(golem_worker_acknowledge(p, id, a, "one") == GOLEM_OK);
    }
    CHECK(golem_worker_close(p) == GOLEM_OK);
    CHECK(golem_admission_close(a) == GOLEM_OK);
    return 0;
}
