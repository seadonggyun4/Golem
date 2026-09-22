#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/daemon.h"
#include "test.h"
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

typedef struct fixture {
    const char *root;
    golem_daemon *daemon;
    unsigned calls;
    bool error, retry, always;
    golem_stage stages[32];
    char ids[32][96];
} fixture;
static golem_status execute(void *context, golem_runtime *runtime, golem_work_run *run,
    const char *directory, const golem_stage_snapshot *stage, uint64_t deadline, golem_runtime_result *out)
{
    fixture *f = context; (void)directory;
    if (f->calls >= 32 || deadline == 0) return GOLEM_ERR_INVALID_STATE;
    bool worked;
    if (golem_daemon_tick(f->daemon, &worked) != GOLEM_ERR_INVALID_STATE ||
        golem_daemon_close(f->daemon) != GOLEM_ERR_INVALID_STATE) return GOLEM_ERR_INVALID_STATE;
    golem_daemon_job rows[256]; size_t count;
    if (golem_daemon_inspect(f->root, rows, 256, &count) != GOLEM_OK) return GOLEM_ERR_IO;
    bool busy = false;
    for (size_t i = 0; i < count; ++i) if (rows[i].state == GOLEM_DAEMON_BUSY) busy = true;
    if (!busy) return GOLEM_ERR_INVALID_STATE;
    golem_lease_snapshot lease;
    golem_status s = golem_runtime_heartbeat(runtime, UINT64_C(60000000000), &lease);
    if (s != GOLEM_OK) return s;
    strcpy(f->ids[f->calls], golem_work_run_id_borrow(run)); f->stages[f->calls++] = stage->stage;
    if (f->error) return GOLEM_ERR_IO;
    bool fail = f->retry && stage->stage == GOLEM_STAGE_QA && (f->always || stage->attempt == 1);
    *out = (golem_runtime_result){stage->sequence, fail ? GOLEM_STAGE_FAILED : GOLEM_STAGE_PASSED,
        fail ? GOLEM_FAILURE_UX_MISMATCH : GOLEM_FAILURE_NONE, !fail};
    return GOLEM_OK;
}
static int capsule(golem_autonomy mode, golem_work_capsule **out)
{
    golem_graph_spec gs; CHECK(golem_stage_graph_default_spec(&gs) == GOLEM_OK);
    golem_stage_graph *g = NULL; CHECK(golem_stage_graph_create(&gs, &g) == GOLEM_OK);
    const char *scope[] = {"local"}, *acceptance[] = {"test attestation"};
    golem_capsule_spec cs = {.id = "daemon", .goal = "Test durable local scheduling", .scope = {scope, 1}, .acceptance = {acceptance, 1}, .graph = g};
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) cs.permissions[i] = mode;
    CHECK(golem_work_capsule_create(&cs, out) == GOLEM_OK); golem_stage_graph_free(g); return 0;
}
static int start(fixture *f)
{
    golem_daemon_ops ops = {execute}; CHECK(golem_daemon_open(f->root, &ops, f, &f->daemon) == GOLEM_OK); return 0;
}
static int tick(fixture *f, bool expected)
{
    bool worked = !expected; CHECK(golem_daemon_tick(f->daemon, &worked) == GOLEM_OK); CHECK(worked == expected); return 0;
}
static int restart(fixture *f) { CHECK(golem_daemon_close(f->daemon) == GOLEM_OK); f->daemon = NULL; return start(f); }
static int lifecycle(const char *root)
{
    fixture f = {.root = root}; golem_work_capsule *c = NULL; CHECK(capsule(GOLEM_AUTONOMY_AUTO_LOCAL, &c) == 0);
    golem_runtime_options o = {1, 3, 32, UINT64_C(30000000000)}; uint64_t ticket = 99;
    CHECK(golem_daemon_init(root) == GOLEM_OK); CHECK(golem_daemon_init(root) == GOLEM_OK);
    CHECK(golem_daemon_submit(root, "one", c, &o, &ticket) == GOLEM_OK && ticket == 1);
    CHECK(golem_daemon_submit(root, "one", c, &o, &ticket) == GOLEM_ERR_INVALID_ARGUMENT && ticket == 1);
    CHECK(start(&f) == 0);
    golem_daemon *second = NULL; golem_daemon_ops ops = {execute};
    CHECK(golem_daemon_open(root, &ops, &f, &second) == GOLEM_ERR_JOURNAL_BUSY && second == NULL);
    golem_daemon_recovery_report recovery_report = {.jobs = 99};
    CHECK(golem_daemon_recover(root, &recovery_report) == GOLEM_ERR_JOURNAL_BUSY && recovery_report.jobs == 99);
    CHECK(golem_daemon_submit(root, "two", c, &o, &ticket) == GOLEM_OK && ticket == 2);
    golem_daemon_job rows[2]; size_t count = 99;
    CHECK(golem_daemon_inspect(root, rows, 1, &count) == GOLEM_ERR_BUFFER_TOO_SMALL && count == 99);
    CHECK(tick(&f, true) == 0); CHECK(tick(&f, true) == 0);
    CHECK(strcmp(f.ids[0], "one") == 0 && strcmp(f.ids[1], "two") == 0);
    CHECK(restart(&f) == 0);
    for (int i = 0; i < 10; ++i) CHECK(tick(&f, true) == 0);
    CHECK(tick(&f, false) == 0 && f.calls == 12);
    for (size_t i = 0; i < 12; ++i) CHECK(f.stages[i] == (golem_stage)(i / 2));
    CHECK(golem_daemon_inspect(root, rows, 2, &count) == GOLEM_OK && count == 2);
    CHECK(rows[0].state == GOLEM_DAEMON_COMPLETE && rows[1].state == GOLEM_DAEMON_COMPLETE);
    CHECK(restart(&f) == 0); CHECK(tick(&f, false) == 0 && f.calls == 12);
    CHECK(golem_daemon_close(f.daemon) == GOLEM_OK); golem_work_capsule_free(c); return 0;
}
static int retry(const char *root, bool limited)
{
    fixture f = {.root = root, .retry = true, .always = limited}; golem_work_capsule *c = NULL;
    CHECK(capsule(GOLEM_AUTONOMY_AUTO_LOCAL, &c) == 0);
    golem_runtime_options o = {1, 2, 32, UINT64_C(30000000000)}; uint64_t ticket;
    CHECK(golem_daemon_init(root) == GOLEM_OK); CHECK(golem_daemon_submit(root, "retry", c, &o, &ticket) == GOLEM_OK);
    CHECK(start(&f) == 0);
    for (unsigned i = 0; i < 16; ++i) {
        bool worked; CHECK(golem_daemon_tick(f.daemon, &worked) == GOLEM_OK); CHECK(restart(&f) == 0);
        if (!worked) break;
    }
    CHECK(f.stages[5] == GOLEM_STAGE_UX && f.calls == (limited ? 9u : 10u));
    golem_daemon_job job; size_t n; CHECK(golem_daemon_inspect(root, &job, 1, &n) == GOLEM_OK);
    CHECK(job.state == (limited ? GOLEM_DAEMON_ATTENTION : GOLEM_DAEMON_COMPLETE));
    CHECK(golem_daemon_close(f.daemon) == GOLEM_OK); golem_work_capsule_free(c); return 0;
}
static int errors(const char *root, bool denied)
{
    fixture f = {.root = root, .error = !denied}; golem_work_capsule *c = NULL;
    CHECK(capsule(denied ? GOLEM_AUTONOMY_ASK_ALWAYS : GOLEM_AUTONOMY_AUTO_LOCAL, &c) == 0);
    golem_runtime_options o = {1, 3, 32, UINT64_C(30000000000)}; uint64_t ticket;
    CHECK(golem_daemon_init(root) == GOLEM_OK); CHECK(golem_daemon_submit(root, "uncertain", c, &o, &ticket) == GOLEM_OK);
    CHECK(start(&f) == 0); CHECK(tick(&f, true) == 0); CHECK(restart(&f) == 0); f.error = false;
    CHECK(tick(&f, false) == 0 && f.calls == (denied ? 0u : 1u));
    golem_daemon_job job; size_t n; CHECK(golem_daemon_inspect(root, &job, 1, &n) == GOLEM_OK && job.state == GOLEM_DAEMON_ATTENTION);
    CHECK(job.work.status == (denied ? GOLEM_WORK_READY : GOLEM_WORK_RUNNING));
    CHECK(golem_daemon_close(f.daemon) == GOLEM_OK); golem_work_capsule_free(c); return 0;
}
static int corrupt(const char *root)
{
    fixture f = {.root = root}; golem_work_capsule *c = NULL; CHECK(capsule(GOLEM_AUTONOMY_AUTO_LOCAL, &c) == 0);
    golem_runtime_options o = {1, 3, 1, UINT64_C(30000000000)}; uint64_t ticket;
    CHECK(golem_daemon_init(root) == GOLEM_OK);
    CHECK(golem_daemon_submit(root, "corrupt", c, &o, &ticket) == GOLEM_OK);
    CHECK(golem_daemon_submit(root, "limited", c, &o, &ticket) == GOLEM_OK);
    char path[4096]; CHECK(snprintf(path, sizeof(path), "%s/jobs/00000000000000000001/journal.bin", root) > 0);
    int fd = open(path, O_WRONLY); CHECK(fd >= 0); CHECK(write(fd, "bad!", 4) == 4); CHECK(close(fd) == 0);
    CHECK(start(&f) == 0); CHECK(tick(&f, true) == 0 && f.calls == 1); CHECK(restart(&f) == 0);
    CHECK(tick(&f, true) == 0 && f.calls == 1); CHECK(tick(&f, false) == 0);
    golem_daemon_job jobs[2]; size_t n; CHECK(golem_daemon_inspect(root, jobs, 2, &n) == GOLEM_OK && n == 2);
    CHECK(jobs[0].state == GOLEM_DAEMON_ATTENTION && jobs[1].state == GOLEM_DAEMON_ATTENTION);
    CHECK(golem_daemon_close(f.daemon) == GOLEM_OK); golem_work_capsule_free(c); return 0;
}
static golem_status sink(void *context, golem_journal_type type, golem_bytes bytes)
{
    (void)context; (void)type; (void)bytes; return GOLEM_ERR_IO;
}
static golem_status unused_execute(void *context, golem_work_run *run, const golem_stage_snapshot *stage,
    uint64_t deadline, golem_runtime_result *out)
{
    (void)context; (void)run; (void)stage; (void)deadline; (void)out; return GOLEM_ERR_IO;
}
static int recovery(const char *root)
{
    fixture f = {.root = root, .retry = true}; golem_work_capsule *c = NULL;
    CHECK(capsule(GOLEM_AUTONOMY_AUTO_LOCAL, &c) == 0);
    golem_runtime_options o = {1, 3, 32, UINT64_C(30000000000)}; uint64_t ticket;
    CHECK(golem_daemon_init(root) == GOLEM_OK); CHECK(golem_daemon_submit(root, "recover", c, &o, &ticket) == GOLEM_OK);
    CHECK(start(&f) == 0);
    for (int i = 0; i < 6; ++i) CHECK(tick(&f, true) == 0);
    CHECK(golem_daemon_close(f.daemon) == GOLEM_OK);
    char path[4096];
    const char suffix[] = "/jobs/00000000000000000001/journal.bin";
    size_t root_size = strlen(root);
    CHECK(root_size <= sizeof(path) - sizeof(suffix));
    memcpy(path, root, root_size);
    memcpy(path + root_size, suffix, sizeof(suffix));
    golem_journal *journal = NULL; CHECK(golem_journal_open(path, NULL, &journal, NULL) == GOLEM_OK);
    golem_runtime_ops ops = {sink, unused_execute, NULL}; golem_runtime *runtime = NULL;
    o.max_attempts = 2;
    CHECK(golem_runtime_recover(journal, &o, &ops, NULL, NULL, &runtime) == GOLEM_ERR_INVALID_STATE && runtime == NULL);
    o.max_attempts = 3;
    CHECK(golem_runtime_recover(journal, &o, &ops, NULL, NULL, &runtime) == GOLEM_OK);
    golem_runtime_report report; CHECK(golem_runtime_report_get(runtime, &report) == GOLEM_OK);
    CHECK(report.dispatched == 6 && report.reentries == 1 && report.work.status == GOLEM_WORK_READY);
    golem_runtime_free(runtime); runtime = NULL;
    CHECK(golem_journal_close(journal, NULL) == GOLEM_OK);
    CHECK(start(&f) == 0); f.error = true; CHECK(tick(&f, true) == 0);
    CHECK(golem_daemon_close(f.daemon) == GOLEM_OK);
    CHECK(golem_journal_open(path, NULL, &journal, NULL) == GOLEM_OK);
    CHECK(golem_runtime_recover(journal, &o, &ops, NULL, NULL, &runtime) == GOLEM_ERR_INVALID_STATE && runtime == NULL);
    CHECK(golem_journal_close(journal, NULL) == GOLEM_OK);
    golem_work_capsule_free(c); return 0;
}
static int invalid(const char *root)
{
    CHECK(golem_daemon_init(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_daemon_init("relative") == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_daemon_init(root) == GOLEM_OK);
    golem_work_capsule *c = NULL; CHECK(capsule(GOLEM_AUTONOMY_AUTO_LOCAL, &c) == 0);
    CHECK(golem_daemon_recover(root, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_runtime_options o = {1, 3, 32, UINT64_C(30000000000)}; uint64_t ticket = 42;
    CHECK(golem_daemon_submit(root, "../escape", c, &o, &ticket) == GOLEM_ERR_INVALID_ARGUMENT);
    o.timeout_ns = 0; CHECK(golem_daemon_submit(root, "invalid", c, &o, &ticket) == GOLEM_ERR_INVALID_ARGUMENT);
    o.timeout_ns = UINT64_C(3600000000001); CHECK(golem_daemon_submit(root, "invalid", c, &o, &ticket) == GOLEM_ERR_INVALID_ARGUMENT);
    o.timeout_ns = 1; o.max_stage_runs = 1025; CHECK(golem_daemon_submit(root, "invalid", c, &o, &ticket) == GOLEM_ERR_INVALID_ARGUMENT);
    o.max_stage_runs = 32; o.max_attempts = 1025; CHECK(golem_daemon_submit(root, "invalid", c, &o, &ticket) == GOLEM_ERR_INVALID_ARGUMENT);
    o.max_attempts = 3; o.version = 2; CHECK(golem_daemon_submit(root, "invalid", c, &o, &ticket) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(ticket == 42);
    golem_daemon_job row; size_t count = 99; CHECK(golem_daemon_inspect(root, &row, 1, &count) == GOLEM_OK && count == 0);
    CHECK(golem_daemon_inspect(root, NULL, 0, &count) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_daemon_close(NULL) == GOLEM_OK); golem_work_capsule_free(c); return 0;
}
int main(int argc, char **argv)
{
    if (argc != 3) return 1;
    char root[4096]; int n = snprintf(root, sizeof(root), "%s/daemon-XXXXXX", argv[2]); CHECK(n > 0 && (size_t)n < sizeof(root));
    CHECK(mkdtemp(root) != NULL);
    if (strcmp(argv[1], "lifecycle") == 0) return lifecycle(root);
    if (strcmp(argv[1], "retry") == 0) return retry(root, false);
    if (strcmp(argv[1], "limits") == 0) return retry(root, true);
    if (strcmp(argv[1], "uncertain") == 0) return errors(root, false);
    if (strcmp(argv[1], "policy") == 0) return errors(root, true);
    if (strcmp(argv[1], "corruption") == 0) return corrupt(root);
    if (strcmp(argv[1], "recovery") == 0) return recovery(root);
    if (strcmp(argv[1], "invalid") == 0) return invalid(root);
    return 1;
}
