/* Test-only compilation of the production coordinator with syscall boundaries
 * redirected to crash injectors. No environment hooks enter the shipped binary. */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "../../src/daemon/internal.h"
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
static const char *point;
static golem_status crash_intent(int dir, uint64_t sequence, golem_bytes frame);
static golem_status crash_write(int dir, const char *name, golem_bytes bytes);
static golem_status crash_append(golem_journal *journal, golem_journal_type type,
    golem_bytes bytes, uint64_t *sequence, golem_diagnostic *diagnostic);
#define gd_intent_write crash_intent
#define gd_write crash_write
#define golem_journal_append crash_append
#define golem_daemon_open crash_daemon_open
#define golem_daemon_tick crash_daemon_tick
#define golem_daemon_close crash_daemon_close
#include "../../src/daemon/scheduler.c"
#undef gd_intent_write
#undef gd_write
#undef golem_journal_append
#undef golem_daemon_open
#undef golem_daemon_tick
#undef golem_daemon_close

static void crash(const char *at) { if (strcmp(point, at) == 0) { (void)kill(getpid(), SIGKILL); _Exit(90); } }
static golem_status crash_intent(int dir, uint64_t sequence, golem_bytes frame)
{
    golem_journal_record record; size_t consumed;
    golem_status s = golem_journal_record_decode(frame, &record, &consumed, NULL);
    if (s == GOLEM_OK && record.type == GOLEM_JOURNAL_STARTED) crash("before-start");
    if (s == GOLEM_OK) s = gd_intent_write(dir, sequence, frame);
    if (s == GOLEM_OK && record.type == GOLEM_JOURNAL_STARTED) crash("start-intent");
    if (s == GOLEM_OK && record.type == GOLEM_JOURNAL_FINISHED) crash("finish-intent");
    return s;
}
static golem_status crash_write(int dir, const char *name, golem_bytes bytes)
{
    golem_status s = gd_write(dir, name, bytes);
    if (s == GOLEM_OK && strncmp(name, "execution-", 10) == 0) crash("claim");
    return s;
}
static golem_status crash_append(golem_journal *journal, golem_journal_type type,
    golem_bytes bytes, uint64_t *sequence, golem_diagnostic *diagnostic)
{
    golem_status s = golem_journal_append(journal, type, bytes, sequence, diagnostic);
    if (s == GOLEM_OK && type == GOLEM_JOURNAL_STARTED) crash("started");
    if (s == GOLEM_OK && type == GOLEM_JOURNAL_FINISHED) crash("finished");
    return s;
}
static golem_status worker(void *context, golem_runtime *runtime, golem_work_run *run,
    const char *directory, const golem_stage_snapshot *stage, uint64_t deadline, golem_runtime_result *out)
{
    (void)runtime; (void)run; (void)directory; (void)deadline;
    int fd = open(context, O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC, 0600);
    if (fd < 0) return GOLEM_ERR_IO;
    char line[64]; int n = snprintf(line, sizeof(line), "%" PRIu64 "\n", stage->sequence);
    bool ok = n > 0 && write(fd, line, (size_t)n) == n && fsync(fd) == 0;
    if (close(fd) < 0) ok = false;
    if (!ok) return GOLEM_ERR_IO;
    crash("execute");
    *out = (golem_runtime_result){stage->sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true};
    return GOLEM_OK;
}
int main(int argc, char **argv)
{
    if (argc != 4) return 2;
    point = argv[2]; golem_daemon_ops ops = {worker}; golem_daemon *d = NULL;
    golem_status s = crash_daemon_open(argv[1], &ops, argv[3], &d);
    for (size_t i = 0; s == GOLEM_OK && i < 128; ++i) {
        bool worked; s = crash_daemon_tick(d, &worked); if (s != GOLEM_OK || !worked) break;
    }
    golem_status closed = crash_daemon_close(d);
    return s == GOLEM_OK && closed == GOLEM_OK ? 0 : 1;
}
