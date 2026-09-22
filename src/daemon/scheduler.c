#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE 1
#endif
#include "internal.h"
#include "../evidence/internal.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

struct golem_daemon {
    char root[GD_PATH]; int leader;
    golem_daemon_ops ops; void *context;
    uint64_t cursor; bool busy, poisoned;
};
typedef struct active_job {
    golem_daemon *daemon; int fd;
    char path[GD_PATH]; golem_journal *journal;
    golem_runtime *runtime;
    uint64_t next_record;
} active_job;
static golem_status now(uint64_t *out)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0 || t.tv_sec < 0 || (uint64_t)t.tv_sec > UINT64_MAX / 1000000000u) return GOLEM_ERR_IO;
    *out = (uint64_t)t.tv_sec * 1000000000u + (uint64_t)t.tv_nsec; return GOLEM_OK;
}
static void put(uint8_t *p, uint64_t v, size_t n) { for (size_t i = 0; i < n; ++i) { p[i] = (uint8_t)v; v >>= 8; } }
static golem_status audit(void *context, const golem_lease_event *e)
{
    active_job *job = context; char name[100], hex[33];
    for (size_t i = 0; i < 16; ++i) (void)snprintf(hex + 2 * i, 3, "%02x", e->lease.token.authority[i]);
    (void)snprintf(name, sizeof(name), "lease-%s-%020" PRIu64, hex, e->sequence);
    uint8_t bytes[64] = "GQLS0001"; memcpy(bytes + 8, e->lease.token.authority, 16);
    put(bytes + 24, e->lease.token.fence, 8); put(bytes + 32, e->observed_ns, 8);
    put(bytes + 40, e->lease.expires_ns, 8); put(bytes + 48, e->sequence, 8); put(bytes + 56, e->type, 4);
    uint32_t crc; (void)golem_journal_crc32((golem_bytes){bytes, 60}, &crc); put(bytes + 60, crc, 4);
    return gd_write(job->fd, name, (golem_bytes){bytes, sizeof(bytes)});
}
static golem_status record(void *context, golem_journal_type type, golem_bytes payload)
{
    active_job *job = context; uint64_t sequence; uint8_t frame[GOLEM_JOURNAL_HEADER_SIZE + GOLEM_JOURNAL_EVENT_SIZE]; size_t size;
    golem_status s = golem_journal_record_encode(type, job->next_record, payload, frame, sizeof(frame), &size, NULL);
    if (s == GOLEM_OK) s = gd_intent_write(job->fd, job->next_record, (golem_bytes){frame, size});
    if (s == GOLEM_OK) s = golem_journal_append(job->journal, type, payload, &sequence, NULL);
    if (s == GOLEM_OK && sequence != job->next_record) s = GOLEM_ERR_REPLAY_MISMATCH;
    if (s == GOLEM_OK) ++job->next_record;
    return s;
}
static golem_status execute(void *context, golem_work_run *run, const golem_stage_snapshot *stage,
    uint64_t deadline, golem_runtime_result *out)
{
    active_job *job = context;
    char name[40]; (void)snprintf(name, sizeof(name), "execution-%020" PRIu64, stage->sequence);
    golem_journal_event event = {.type = GOLEM_JOURNAL_STARTED, .stage = stage->stage,
        .attempt = stage->attempt, .attempt_sequence = stage->sequence, .outcome = GOLEM_STAGE_RUNNING};
    uint8_t bytes[GOLEM_JOURNAL_EVENT_SIZE]; size_t size;
    golem_status s = golem_journal_event_encode(&event, bytes, sizeof(bytes), &size, NULL);
    if (s == GOLEM_OK) s = gd_write(job->fd, name, (golem_bytes){bytes, size});
    if (s != GOLEM_OK) return s;
    return job->daemon->ops.execute(job->daemon->context, job->runtime, run, job->path, stage, deadline, out);
}
golem_status golem_daemon_open(const char *root, const golem_daemon_ops *ops, void *context, golem_daemon **out)
{
    if (ops == NULL || ops->execute == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = gd_root(root); if (fd < 0) return GOLEM_ERR_IO;
    int leader = gd_lock(fd, ".daemon.lock", false, true); (void)close(fd);
    if (leader < 0) return GOLEM_ERR_JOURNAL_BUSY;
    golem_daemon_recovery_report recovery;
    golem_status recovered = GOLEM_ERR_JOURNAL_BUSY;
    /* Keep ownership while a concurrent short submission finishes publication.
     * Never retry acquisition of another daemon's owner lock. */
    for (unsigned attempt = 0; attempt < 100 && recovered == GOLEM_ERR_JOURNAL_BUSY; ++attempt) {
        recovered = gd_recover_queue(root, &recovery);
        if (recovered == GOLEM_ERR_JOURNAL_BUSY) {
            struct timespec delay = {0, 10000000}; (void)nanosleep(&delay, NULL);
        }
    }
    if (recovered != GOLEM_OK) { (void)close(leader); return recovered; }
    golem_daemon *d = calloc(1, sizeof(*d));
    if (d == NULL) { (void)close(leader); return GOLEM_ERR_OUT_OF_MEMORY; }
    strcpy(d->root, root); d->leader = leader; d->ops = *ops; d->context = context; *out = d; return GOLEM_OK;
}
golem_status golem_daemon_tick(golem_daemon *d, bool *worked)
{
    if (d == NULL || worked == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (d->busy || d->poisoned) return GOLEM_ERR_INVALID_STATE;
    d->busy = true;
    golem_daemon_job rows[GOLEM_DAEMON_MAX_JOBS]; size_t count;
    golem_status s = golem_daemon_inspect(d->root, rows, GOLEM_DAEMON_MAX_JOBS, &count);
    if (s == GOLEM_ERR_JOURNAL_BUSY) { *worked = false; d->busy = false; return GOLEM_OK; }
    if (s != GOLEM_OK) { d->busy = false; return s; }
    size_t selected = count;
    for (size_t i = 0; i < count; ++i) if (rows[i].state == GOLEM_DAEMON_READY && rows[i].ticket > d->cursor) { selected = i; break; }
    if (selected == count) for (size_t i = 0; i < count; ++i) if (rows[i].state == GOLEM_DAEMON_READY) { selected = i; break; }
    if (selected == count) { *worked = false; d->busy = false; return GOLEM_OK; }
    active_job job = {.daemon = d, .fd = -1}; golem_runtime_options options;
    golem_lease *lease = NULL; golem_lease_snapshot owned; bool acquired = false;
    s = gd_job_path(d->root, rows[selected].ticket, job.path);
    if (s == GOLEM_OK) s = gd_load(job.path, &rows[selected], &options);
    if (s == GOLEM_OK) { job.fd = golem_evidence_path_open(job.path, true); if (job.fd < 0) s = GOLEM_ERR_IO; }
    char path[GD_PATH];
    if (s == GOLEM_OK) s = gd_path(job.path, "journal.bin", path);
    if (s == GOLEM_OK) s = golem_journal_open(path, NULL, &job.journal, NULL);
    if (s == GOLEM_ERR_JOURNAL_BUSY) {
        if (job.fd >= 0) (void)close(job.fd);
        d->busy = false; *worked = false; return GOLEM_OK;
    }
    golem_runtime_ops runtime_ops = {record, execute, NULL};
    if (s == GOLEM_OK) s = golem_runtime_recover(job.journal, &options, &runtime_ops, &job, NULL, &job.runtime);
    if (s == GOLEM_OK) {
        golem_runtime_report report; s = golem_runtime_report_get(job.runtime, &report);
        if (s == GOLEM_OK) job.next_record = 2 + 2 * report.dispatched + report.reentries;
    }
    golem_lease_ops lease_ops = {audit};
    if (s == GOLEM_OK) s = golem_lease_create(rows[selected].run_id, &lease_ops, &job, NULL, &lease);
    uint64_t time = 0;
    if (s == GOLEM_OK) s = now(&time);
    if (s == GOLEM_OK) { s = golem_lease_acquire(lease, "daemon", time, UINT64_C(60000000000), &owned); acquired = s == GOLEM_OK; }
    if (s == GOLEM_OK) s = golem_runtime_lease_bind(job.runtime, lease, &owned.token);
    if (s == GOLEM_OK) s = golem_runtime_step(job.runtime);
    if (acquired) {
        golem_status released = now(&time);
        if (released == GOLEM_OK) released = golem_lease_release(lease, &owned.token, time);
        if (s == GOLEM_OK) s = released;
    }
    golem_runtime_free(job.runtime); golem_lease_free(lease);
    golem_status closed = golem_journal_close(job.journal, NULL); if (s == GOLEM_OK) s = closed;
    golem_status persisted = GOLEM_OK;
    if (s != GOLEM_OK) {
        const char *message = golem_status_string(s);
        persisted = job.fd < 0 ? GOLEM_ERR_IO : gd_write(job.fd, "attention", (golem_bytes){(const uint8_t *)message, strlen(message)});
    }
    if (job.fd >= 0 && close(job.fd) < 0) persisted = GOLEM_ERR_IO;
    d->cursor = rows[selected].ticket; d->busy = false;
    if (persisted != GOLEM_OK) { d->poisoned = true; return persisted; }
    *worked = true; return GOLEM_OK;
}
golem_status golem_daemon_close(golem_daemon *d)
{
    if (d == NULL) return GOLEM_OK;
    if (d->busy) return GOLEM_ERR_INVALID_STATE;
    golem_status s = close(d->leader) == 0 ? GOLEM_OK : GOLEM_ERR_IO; free(d); return s;
}
