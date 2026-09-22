#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include "../evidence/internal.h"
#include "../adapter_protocol/internal.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <openssl/rand.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <unistd.h>

static void put(uint8_t *p, uint64_t value, size_t n) { for (size_t i = 0; i < n; ++i) { p[i] = (uint8_t)value; value >>= 8; } }
static uint64_t get(const uint8_t *p, size_t n) { uint64_t v = 0; for (size_t i = n; i > 0; --i) v = (v << 8) | p[i - 1]; return v; }
static bool options_valid(const golem_runtime_options *o)
{
    return o != NULL && o->version == 1 && o->max_attempts > 0 && o->max_attempts <= 1024 &&
        o->max_stage_runs > 0 && o->max_stage_runs <= 1024 && o->timeout_ns > 0 && o->timeout_ns <= UINT64_C(3600000000000);
}
golem_status golem_daemon_init(const char *root)
{
    int valid = gd_root(root); if (valid >= 0) { (void)close(valid); return GOLEM_OK; }
    if (root == NULL || root[0] != '/' || strlen(root) > GD_PATH - 180) return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = golem_evidence_path_open(root, true); if (fd < 0) return GOLEM_ERR_IO;
    int lock = gd_lock(fd, ".queue.lock", true, true); golem_status s = lock < 0 ? GOLEM_ERR_JOURNAL_BUSY : GOLEM_OK;
    struct stat st;
    if (s == GOLEM_OK && fstatat(fd, "format", &st, AT_SYMLINK_NOFOLLOW) == 0) s = GOLEM_ERR_INVALID_STATE;
    if (s == GOLEM_OK && mkdirat(fd, "jobs", 0700) < 0 && errno != EEXIST) s = GOLEM_ERR_IO;
    int jobs = -1, leader = -1;
    if (s == GOLEM_OK) { jobs = openat(fd, "jobs", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC); if (jobs < 0) s = GOLEM_ERR_IO; }
    if (s == GOLEM_OK) { leader = gd_lock(fd, ".daemon.lock", true, true); if (leader < 0) s = GOLEM_ERR_JOURNAL_BUSY; }
    if (s == GOLEM_OK) s = gd_write(fd, "format", (golem_bytes){(const uint8_t *)"GolemQueue1\n", 12});
    if (jobs >= 0) (void)close(jobs);
    if (leader >= 0) (void)close(leader);
    if (lock >= 0) (void)close(lock);
    (void)close(fd); return s;
}
golem_status gd_load(const char *path, golem_daemon_job *job, golem_runtime_options *options)
{
    char file[GD_PATH]; gd_blob meta = {0}, journal = {0}, context = {0}, attention = {0};
    int journal_lock = -1;
    golem_work_run *run = NULL; golem_status s = gd_path(path, "options.bin", file);
    if (s == GOLEM_OK) s = gd_read(file, 32, &meta);
    uint32_t crc = 0;
    if (s == GOLEM_OK && meta.size == 32) (void)golem_journal_crc32((golem_bytes){meta.data, 28}, &crc);
    if (s == GOLEM_OK && (meta.size != 32 || memcmp(meta.data, "GQOP0001", 8) != 0 || get(meta.data + 28, 4) != crc)) s = GOLEM_ERR_PARSE;
    if (s == GOLEM_OK) {
        *options = (golem_runtime_options){1, (uint32_t)get(meta.data + 8, 4), get(meta.data + 12, 8), get(meta.data + 20, 8)};
        if (!options_valid(options)) s = GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (s == GOLEM_OK) s = gd_path(path, "journal.bin", file);
    if (s == GOLEM_OK) {
        journal_lock = golem_evidence_path_open(file, false);
        if (journal_lock < 0) s = GOLEM_ERR_IO;
        else if (flock(journal_lock, LOCK_SH | LOCK_NB) < 0) s = GOLEM_ERR_JOURNAL_BUSY;
    }
    if (s == GOLEM_OK) s = gd_read(file, GD_LIMIT, &journal);
    if (s == GOLEM_OK) s = gd_intents_check(path, (golem_bytes){journal.data, journal.size});
    if (s == GOLEM_OK) s = golem_journal_replay((golem_bytes){journal.data, journal.size}, NULL, &run, NULL);
    if (s == GOLEM_OK) {
        const char *id = golem_work_run_id_borrow(run);
        if (!golem_adapter_id_valid(id)) s = GOLEM_ERR_IDENTITY_MISMATCH;
        else memcpy(job->run_id, id, strlen(id) + 1);
    }
    if (s == GOLEM_OK) {
        gd_blob identity = {0}; s = gd_path(path, "id", file);
        if (s == GOLEM_OK) s = gd_read(file, 95, &identity);
        if (s == GOLEM_OK && (identity.size != strlen(job->run_id) || memcmp(identity.data, job->run_id, identity.size) != 0)) s = GOLEM_ERR_IDENTITY_MISMATCH;
        free(identity.data);
    }
    if (s == GOLEM_OK) s = gd_path(path, "context.bin", file);
    if (s == GOLEM_OK) s = gd_read(file, GOLEM_JOURNAL_MAX_PAYLOAD, &context);
    if (s == GOLEM_OK) {
        golem_journal_record first; size_t consumed;
        s = golem_journal_record_decode((golem_bytes){journal.data, journal.size}, &first, &consumed, NULL);
        if (s == GOLEM_OK && (first.type != GOLEM_JOURNAL_CREATED || first.payload.size != context.size ||
            memcmp(first.payload.data, context.data, context.size) != 0)) s = GOLEM_ERR_REPLAY_MISMATCH;
    }
    if (s == GOLEM_OK) {
        (void)golem_work_run_snapshot_get(run, &job->work);
        job->state = job->work.status == GOLEM_WORK_SUCCEEDED || job->work.status == GOLEM_WORK_CANCELLED ? GOLEM_DAEMON_COMPLETE :
            job->work.status == GOLEM_WORK_READY || job->work.status == GOLEM_WORK_FAILED ? GOLEM_DAEMON_READY : GOLEM_DAEMON_ATTENTION;
        job->reason = job->state == GOLEM_DAEMON_ATTENTION ? GOLEM_ERR_INCOMPLETE_WORK : GOLEM_OK;
        s = gd_path(path, "attention", file);
        if (s == GOLEM_OK) {
            golem_status a = gd_read(file, 128, &attention);
            if (a != GOLEM_ERR_NOT_FOUND) { job->state = GOLEM_DAEMON_ATTENTION; job->reason = a == GOLEM_OK ? GOLEM_ERR_INCOMPLETE_WORK : a; }
        }
    }
    if (s != GOLEM_OK) { job->state = s == GOLEM_ERR_JOURNAL_BUSY ? GOLEM_DAEMON_BUSY : GOLEM_DAEMON_ATTENTION; job->reason = s; }
    if (journal_lock >= 0) (void)close(journal_lock);
    golem_work_run_free(run); free(meta.data); free(journal.data); free(context.data); free(attention.data); return s;
}
golem_status golem_daemon_inspect(const char *root, golem_daemon_job *jobs, size_t capacity, size_t *count)
{
    if (jobs == NULL || count == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = gd_root(root); if (fd < 0) return GOLEM_ERR_IO;
    int lock = gd_lock(fd, ".queue.lock", false, false);
    uint64_t tickets[GOLEM_DAEMON_MAX_JOBS]; size_t n = 0;
    golem_status s = lock < 0 ? GOLEM_ERR_JOURNAL_BUSY : gd_list(fd, tickets, &n);
    if (s == GOLEM_OK && capacity < n) s = GOLEM_ERR_BUFFER_TOO_SMALL;
    golem_daemon_job *rows = NULL;
    if (s == GOLEM_OK && n > 0) { rows = calloc(n, sizeof(*rows)); if (rows == NULL) s = GOLEM_ERR_OUT_OF_MEMORY; }
    for (size_t i = 0; s == GOLEM_OK && i < n; ++i) {
        char path[GD_PATH]; s = gd_job_path(root, tickets[i], path); rows[i].ticket = tickets[i];
        golem_runtime_options options;
        if (s == GOLEM_OK) (void)gd_load(path, &rows[i], &options);
    }
    if (s == GOLEM_OK) { if (n > 0) memcpy(jobs, rows, n * sizeof(*rows)); *count = n; }
    free(rows); if (lock >= 0) (void)close(lock); (void)close(fd); return s;
}
golem_status golem_daemon_submit(const char *root, const char *id, const golem_work_capsule *capsule,
    const golem_runtime_options *options, uint64_t *ticket)
{
    if (!golem_adapter_id_valid(id) || capsule == NULL || !options_valid(options) || ticket == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = gd_root(root); if (fd < 0) return GOLEM_ERR_IO;
    int lock = gd_lock(fd, ".queue.lock", false, true), jobs = -1, pending = -1;
    uint64_t tickets[GOLEM_DAEMON_MAX_JOBS]; size_t n = 0;
    golem_status s = lock < 0 ? GOLEM_ERR_JOURNAL_BUSY : gd_list(fd, tickets, &n);
    if (s == GOLEM_OK && (n == GOLEM_DAEMON_MAX_JOBS || (n > 0 && tickets[n - 1] == UINT64_MAX))) s = GOLEM_ERR_OVERFLOW;
    for (size_t i = 0; s == GOLEM_OK && i < n; ++i) {
        char path[GD_PATH], file[GD_PATH]; gd_blob identity = {0};
        s = gd_job_path(root, tickets[i], path);
        if (s == GOLEM_OK) s = gd_path(path, "id", file);
        if (s == GOLEM_OK) s = gd_read(file, 95, &identity);
        if (s == GOLEM_OK && identity.size == strlen(id) && memcmp(identity.data, id, identity.size) == 0) s = GOLEM_ERR_INVALID_ARGUMENT;
        free(identity.data);
    }
    uint64_t next = n == 0 ? 1 : tickets[n - 1] + 1;
    uint8_t random[8]; char temp[40] = ".pending-", final[32];
    if (s == GOLEM_OK && RAND_bytes(random, sizeof(random)) != 1) s = GOLEM_ERR_CRYPTO;
    if (s == GOLEM_OK) for (size_t i = 0; i < sizeof(random); ++i) (void)snprintf(temp + 9 + i * 2, 3, "%02x", random[i]);
    (void)snprintf(final, sizeof(final), "%020" PRIu64, next);
    if (s == GOLEM_OK) { jobs = openat(fd, "jobs", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC); if (jobs < 0) s = GOLEM_ERR_IO; }
    if (s == GOLEM_OK && mkdirat(jobs, temp, 0700) < 0) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK) { pending = openat(jobs, temp, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC); if (pending < 0) s = GOLEM_ERR_IO; }
    size_t size = 0, frame_size = 0; void *payload = NULL, *frame = NULL;
    if (s == GOLEM_OK) {
        s = golem_journal_created_encode(id, capsule, options->max_attempts, NULL, 0, &size, NULL);
        if (s == GOLEM_ERR_BUFFER_TOO_SMALL) { payload = malloc(size); s = payload == NULL ? GOLEM_ERR_OUT_OF_MEMORY : GOLEM_OK; }
    }
    if (s == GOLEM_OK) s = golem_journal_created_encode(id, capsule, options->max_attempts, payload, size, &size, NULL);
    if (s == GOLEM_OK) s = gd_write(pending, "context.bin", (golem_bytes){payload, size});
    if (s == GOLEM_OK) {
        s = golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){payload, size}, NULL, 0, &frame_size, NULL);
        if (s == GOLEM_ERR_BUFFER_TOO_SMALL) { frame = malloc(frame_size); s = frame == NULL ? GOLEM_ERR_OUT_OF_MEMORY : GOLEM_OK; }
    }
    if (s == GOLEM_OK) s = golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){payload, size}, frame, frame_size, &frame_size, NULL);
    if (s == GOLEM_OK) s = gd_write(pending, "journal.bin", (golem_bytes){frame, frame_size});
    uint8_t meta[32] = "GQOP0001"; uint32_t crc;
    put(meta + 8, options->max_attempts, 4); put(meta + 12, options->max_stage_runs, 8); put(meta + 20, options->timeout_ns, 8);
    (void)golem_journal_crc32((golem_bytes){meta, 28}, &crc); put(meta + 28, crc, 4);
    if (s == GOLEM_OK) s = gd_write(pending, "options.bin", (golem_bytes){meta, sizeof(meta)});
    if (s == GOLEM_OK) s = gd_write(pending, "id", (golem_bytes){(const uint8_t *)id, strlen(id)});
    if (s == GOLEM_OK) s = gd_intent_write(pending, 1, (golem_bytes){frame, frame_size});
    uint8_t recovery[40] = "GRCV0001"; golem_digest meta_digest;
    if (s == GOLEM_OK) s = golem_digest_bytes((golem_bytes){meta, sizeof(meta)}, &meta_digest);
    if (s == GOLEM_OK) { memcpy(recovery + 8, &meta_digest, 32); s = gd_write(pending, "recovery.meta", (golem_bytes){recovery, sizeof(recovery)}); }
    if (s == GOLEM_OK && (renameat(jobs, temp, jobs, final) < 0 || fsync(jobs) < 0)) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK) *ticket = next;
    free(frame); free(payload);
    if (pending >= 0) (void)close(pending);
    if (jobs >= 0) (void)close(jobs);
    if (lock >= 0) (void)close(lock);
    (void)close(fd); return s;
}
