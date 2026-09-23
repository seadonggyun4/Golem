#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/worker.h"
#include "golem/runtime_event.h"
#include "test.h"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static void nap(void)
{
    struct timespec t = {0, 1000000};
    (void)nanosleep(&t, NULL);
}
static golem_status publish(void *context, const golem_digest *ns,
                            const golem_admission_ticket *ticket, golem_digest *proof)
{
    (void)context;
    (void)ns;
    *proof = ticket->request.runtime_binding;
    return GOLEM_OK;
}
static int finish(golem_worker_pool *p, uint64_t id, golem_admission *a, const char *op,
                  golem_worker_snapshot *out)
{
    for (unsigned i = 0; i < 10000; ++i) {
        CHECK(golem_worker_inspect(p, id, out) == GOLEM_OK);
        if (out->state == GOLEM_WORKER_FINISHED)
            break;
        nap();
    }
    CHECK(out->state == GOLEM_WORKER_FINISHED);
    golem_runtime_event events[64]; golem_runtime_event_page page;
    CHECK(golem_worker_events(p, NULL, events, 64, &page) == GOLEM_OK);
    bool dispatched = false, finished = false;
    for (size_t i = 0; i < page.count; ++i) {
        if (events[i].subject != id) continue;
        dispatched |= events[i].kind == GOLEM_EVENT_DISPATCHED;
        finished |= events[i].kind == GOLEM_EVENT_FINISHED && events[i].status_known && events[i].status == out->status;
    }
    CHECK(dispatched && finished);
    CHECK(golem_worker_acknowledge(p, id, a, op) == GOLEM_ERR_INVALID_STATE);
    golem_admission_ticket t;
    CHECK(golem_admission_lookup(a, op, &t) == GOLEM_OK);
    CHECK(golem_admission_settle(a, t.token, (golem_digest){{2}}) == GOLEM_OK);
    CHECK(golem_admission_release(a, t.token) == GOLEM_OK);
    CHECK(golem_worker_acknowledge(p, id, a, op) == GOLEM_OK);
    CHECK(golem_worker_acknowledge(p, id, a, op) == GOLEM_OK);
    return 0;
}
static int enroll(golem_admission *a, const char *op, bool foreground)
{
    golem_admission_request r = {
        .cpu_millis = 1, .memory_bytes = 1, .foreground = foreground, .runtime_binding = {{1}}};
    (void)snprintf(r.operation, sizeof(r.operation), "%s", op);
    (void)snprintf(r.work, sizeof(r.work), "%s", op);
    (void)snprintf(r.session, sizeof(r.session), "%s", op);
    uint64_t id;
    golem_admission_ticket t;
    CHECK(golem_admission_enqueue(a, &r, &id) == GOLEM_OK);
    CHECK(golem_admission_grant(a, &t) == GOLEM_OK);
    return 0;
}
static int child(int argc, char **argv)
{
    const char *mode = argv[2];
    if (!strcmp(mode, "orphan")) {
        if (argc != 5)
            return 2;
        int fd = open(argv[3], O_CREAT | O_WRONLY | O_EXCL, 0600);
        if (fd < 0)
            return 3;
        (void)close(fd);
        for (unsigned i = 0; i < 500; ++i)
            nap();
        fd = open(argv[4], O_CREAT | O_WRONLY | O_EXCL, 0600);
        if (fd < 0)
            return 4;
        (void)close(fd);
        return 0;
    }
    if (!strcmp(mode, "hang"))
        for (;;)
            pause();
    if (!strcmp(mode, "signal")) {
        raise(SIGTERM);
        return 1;
    }
    if (!strcmp(mode, "exit"))
        return 17;
    if (!strcmp(mode, "overflow")) {
        char data[4096] = {0};
        for (unsigned i = 0; i < 32; ++i)
            if (write(1, data, sizeof(data)) < 0)
                return 1;
        return 0;
    }
    if (!strcmp(mode, "overlap")) {
        if (argc != 5)
            return 2;
        int fd = open(argv[3], O_CREAT | O_WRONLY | O_EXCL, 0600);
        if (fd < 0)
            return 3;
        (void)close(fd);
        for (unsigned i = 0; i < 5000; ++i) {
            if (access(argv[4], F_OK) == 0)
                return 0;
            nap();
        }
        return 4;
    }
    char data[1024];
    ssize_t n;
    while ((n = read(0, data, sizeof(data))) > 0)
        if (write(1, data, (size_t)n) != n)
            return 1;
    return n < 0;
}
int main(int argc, char **argv)
{
    if (argc >= 3 && !strcmp(argv[1], "--child"))
        return child(argc, argv);
    CHECK(argc == 2);
    char executable[4096];
    CHECK(realpath(argv[0], executable) != NULL);
    char root[] = "/tmp/golem-worker-XXXXXX";
    CHECK(mkdtemp(root) != NULL);
    char canonical[4096];
    CHECK(realpath(root, canonical) != NULL);
    golem_admission_options ao = {.size = sizeof(ao),
                                  .version = 1,
                                  .create = true,
                                  .limits = {32, UINT64_MAX, UINT64_MAX, 0}};
    golem_admission *a;
    CHECK(golem_admission_open(canonical, &ao, &a) == GOLEM_OK);
    golem_worker_options o = golem_worker_options_default();
    o.limits.worker_slots = 2;
    o.limits.io_slots = 2;
    golem_worker_pool *p;
    CHECK(golem_worker_open(&o, &p) == GOLEM_OK);
    char *env[] = {NULL};
    char *args[] = {executable, "--child", "echo", NULL, NULL, NULL};
    golem_worker_request r = {.executable = executable,
                              .cwd = "/",
                              .argv = args,
                              .envp = env,
                              .cpu_units = 1,
                              .memory_bytes = 1,
                              .io_slots = 1,
                              .timeout_ns = UINT64_C(6000000000),
                              .lease_ns = UINT64_C(6000000000),
                              .resource_class = GOLEM_WORKER_QA};
    uint64_t id;
    golem_worker_snapshot snapshot;
    const char *mode = argv[1];
    if (!strcmp(mode, "recovery")) {
        CHECK(golem_worker_close(p) == GOLEM_OK);
        CHECK(golem_admission_close(a) == GOLEM_OK);
        char started[4096], finished[4096];
        (void)snprintf(started, sizeof(started), "%s/.started", root);
        (void)snprintf(finished, sizeof(finished), "%s/.finished", root);
        args[2] = "orphan";
        args[3] = started;
        args[4] = finished;
        pid_t owner = fork();
        CHECK(owner >= 0);
        if (!owner) {
            if (golem_admission_open(canonical, &ao, &a) != GOLEM_OK ||
                golem_worker_open(&o, &p) != GOLEM_OK || enroll(a, "one", true) ||
                golem_worker_submit(p, &r, &id) != GOLEM_OK ||
                golem_worker_start(p, id, a, "one", publish, NULL) != GOLEM_OK)
                _exit(10);
            for (;;)
                pause();
        }
        for (unsigned i = 0; i < 5000 && access(started, F_OK); ++i)
            nap();
        CHECK(access(started, F_OK) == 0);
        CHECK(kill(owner, SIGKILL) == 0);
        int status;
        CHECK(waitpid(owner, &status, 0) == owner && WIFSIGNALED(status));
        CHECK(golem_admission_open(canonical, &ao, &a) == GOLEM_OK);
        golem_admission_ticket ticket;
        CHECK(golem_admission_lookup(a, "one", &ticket) == GOLEM_OK);
        CHECK(ticket.state == GOLEM_ADMISSION_RECONCILE_REQUIRED);
        CHECK(golem_worker_open(&o, &p) == GOLEM_OK);
        CHECK(golem_worker_submit(p, &r, &id) == GOLEM_OK);
        CHECK(golem_worker_start(p, id, a, "one", publish, NULL) == GOLEM_ERR_REQUIREMENTS_UNMET);
        CHECK(golem_worker_cancel(p, id) == GOLEM_OK);
        CHECK(golem_worker_acknowledge(p, id, NULL, NULL) == GOLEM_OK);
        for (unsigned i = 0; i < 5000 && access(finished, F_OK); ++i)
            nap();
        CHECK(access(finished, F_OK) == 0);
        /* A marker is not a termination receipt; keep durable reconciliation. */
        CHECK(golem_admission_lookup(a, "one", &ticket) == GOLEM_OK);
        CHECK(ticket.state == GOLEM_ADMISSION_RECONCILE_REQUIRED);
    } else if (!strcmp(mode, "limits")) {
        o.limits.worker_slots = 1;
        o.limits.foreground_slots = 1;
        golem_worker_pool *unchanged = p;
        CHECK(golem_worker_open(&o, &unchanged) == GOLEM_ERR_INVALID_ARGUMENT && unchanged == p);
        r.cpu_units = UINT64_MAX;
        CHECK(golem_worker_submit(p, &r, &id) == GOLEM_ERR_BUDGET_EXHAUSTED);
        r.cpu_units = 1;
        r.memory_bytes = UINT64_MAX;
        CHECK(golem_worker_submit(p, &r, &id) == GOLEM_ERR_BUDGET_EXHAUSTED);
        r.memory_bytes = 1;
        for (unsigned i = 0; i < GOLEM_WORKER_MAX_JOBS; ++i) {
            CHECK(golem_worker_submit(p, &r, &id) == GOLEM_OK);
            CHECK(golem_worker_cancel(p, id) == GOLEM_OK);
            CHECK(golem_worker_acknowledge(p, id, NULL, NULL) == GOLEM_OK);
        }
        CHECK(golem_worker_submit(p, &r, &id) == GOLEM_ERR_QUEUE_FULL);
    } else if (!strcmp(mode, "overlap")) {
        char one[4096], two[4096];
        (void)snprintf(one, sizeof(one), "%s/one", root);
        (void)snprintf(two, sizeof(two), "%s/two", root);
        args[2] = "overlap";
        args[3] = one;
        args[4] = two;
        CHECK(enroll(a, "one", true) == 0);
        CHECK(golem_worker_submit(p, &r, &id) == GOLEM_OK);
        CHECK(golem_worker_start(p, id, a, "one", publish, NULL) == GOLEM_OK);
        uint64_t second;
        args[3] = two;
        args[4] = one;
        CHECK(enroll(a, "two", true) == 0);
        CHECK(golem_worker_submit(p, &r, &second) == GOLEM_OK);
        CHECK(golem_worker_start(p, second, a, "two", publish, NULL) == GOLEM_OK);
        CHECK(finish(p, id, a, "one", &snapshot) == 0);
        CHECK(snapshot.status == GOLEM_OK);
        CHECK(finish(p, second, a, "two", &snapshot) == 0);
        CHECK(snapshot.status == GOLEM_OK);
        CHECK(unlink(one) == 0 && unlink(two) == 0);
    } else if (!strcmp(mode, "reserve")) {
        CHECK(golem_worker_close(p) == GOLEM_OK);
        o.limits.foreground_slots = 1;
        CHECK(golem_worker_open(&o, &p) == GOLEM_OK);
        args[2] = "hang";
        r.resource_class = GOLEM_WORKER_BACKGROUND;
        CHECK(enroll(a, "one", false) == 0);
        CHECK(golem_worker_submit(p, &r, &id) == GOLEM_OK);
        CHECK(golem_worker_start(p, id, a, "one", publish, NULL) == GOLEM_OK);
        uint64_t second;
        CHECK(enroll(a, "two", false) == 0);
        CHECK(golem_worker_submit(p, &r, &second) == GOLEM_OK);
        CHECK(golem_worker_start(p, second, a, "two", publish, NULL) == GOLEM_ERR_LEASE_BUSY);
        CHECK(golem_worker_cancel(p, id) == GOLEM_OK);
        CHECK(golem_worker_start(p, second, a, "two", publish, NULL) == GOLEM_ERR_LEASE_BUSY);
        CHECK(finish(p, id, a, "one", &snapshot) == 0);
        CHECK(golem_worker_start(p, second, a, "two", publish, NULL) == GOLEM_OK);
        CHECK(golem_worker_cancel(p, second) == GOLEM_OK);
        CHECK(finish(p, second, a, "two", &snapshot) == 0);
    } else {
        args[2] = (char *)mode;
        if (!strcmp(mode, "cancel") || !strcmp(mode, "lease") || !strcmp(mode, "timeout"))
            args[2] = "hang";
        if (!strcmp(mode, "lease"))
            r.lease_ns = 50000000;
        if (!strcmp(mode, "timeout"))
            r.timeout_ns = 50000000;
        if (!strcmp(mode, "missing"))
            r.executable = "/golem-no-such-executable";
        if (!strcmp(mode, "echo"))
            r.input = (golem_bytes){(const uint8_t *)"echo", 4};
        CHECK(enroll(a, "one", true) == 0);
        CHECK(golem_worker_submit(p, &r, &id) == GOLEM_OK);
        CHECK(golem_worker_start(p, id, a, "one", publish, NULL) == GOLEM_OK);
        CHECK(golem_worker_start(p, id, a, "one", publish, NULL) == GOLEM_ERR_INVALID_STATE);
        if (!strcmp(mode, "cancel")) {
            for (unsigned i = 0; i < 100; ++i) {
                CHECK(golem_worker_inspect(p, id, &snapshot) == GOLEM_OK);
                CHECK(golem_worker_heartbeat(p, id, r.lease_ns) == GOLEM_OK);
                nap();
            }
            CHECK(golem_worker_close(p) == GOLEM_ERR_INVALID_STATE);
            CHECK(golem_worker_cancel(p, id) == GOLEM_OK);
            CHECK(golem_worker_heartbeat(p, id, r.lease_ns) == GOLEM_ERR_STALE_LEASE);
        }
        CHECK(finish(p, id, a, "one", &snapshot) == 0);
        if (!strcmp(mode, "echo"))
            CHECK(snapshot.status == GOLEM_OK && snapshot.result.output_size == 4);
        if (!strcmp(mode, "exit"))
            CHECK(snapshot.result.exit_code == 17 && snapshot.status == GOLEM_ERR_INCOMPLETE_WORK);
        if (!strcmp(mode, "signal"))
            CHECK(snapshot.result.signal_number == SIGTERM);
        if (!strcmp(mode, "overflow"))
            CHECK(snapshot.status == GOLEM_ERR_OVERFLOW);
        if (!strcmp(mode, "lease"))
            CHECK(snapshot.lease_expired && snapshot.status == GOLEM_ERR_STALE_LEASE);
        if (!strcmp(mode, "timeout"))
            CHECK(snapshot.result.timed_out);
        if (!strcmp(mode, "missing"))
            CHECK(!snapshot.observation.spawned && snapshot.status == GOLEM_ERR_IO);
        else
            CHECK(snapshot.observation.reaped || !snapshot.observation.spawned);
    }
    CHECK(golem_worker_close(p) == GOLEM_OK);
    CHECK(golem_admission_close(a) == GOLEM_OK);
    CHECK(waitpid(-1, NULL, WNOHANG) == -1 && errno == ECHILD);
    return 0;
}
