#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE 1
#endif
#include "internal.h"
#include "../evidence/internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

#define GD_MAX_RECORDS 4096u
golem_status gd_intent_write(int dir, uint64_t sequence, golem_bytes frame)
{
    if (sequence == 0 || sequence > GD_MAX_RECORDS) return GOLEM_ERR_OVERFLOW;
    char name[40]; (void)snprintf(name, sizeof(name), "intent-%020" PRIu64, sequence);
    return gd_write(dir, name, frame);
}
static int compare(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b; return x < y ? -1 : x > y;
}
static golem_status intent_list(const char *path, uint64_t *sequences, size_t *count)
{
    int fd = golem_evidence_path_open(path, true); if (fd < 0) return GOLEM_ERR_IO;
    DIR *dir = fdopendir(fd); if (dir == NULL) { (void)close(fd); return GOLEM_ERR_IO; }
    golem_status s = GOLEM_OK; size_t n = 0; struct dirent *entry; errno = 0;
    while ((entry = readdir(dir)) != NULL) {
        if (strncmp(entry->d_name, "intent-", 7) != 0) continue;
        if (strlen(entry->d_name) != 27 || n == GD_MAX_RECORDS) { s = GOLEM_ERR_CORRUPT_JOURNAL; break; }
        uint64_t sequence = 0;
        for (size_t i = 7; i < 27; ++i) {
            unsigned digit = (unsigned)(entry->d_name[i] - '0');
            if (digit > 9 || sequence > (UINT64_MAX - digit) / 10) { s = GOLEM_ERR_CORRUPT_JOURNAL; break; }
            sequence = sequence * 10 + digit;
        }
        if (s != GOLEM_OK) break;
        sequences[n++] = sequence;
    }
    if (errno != 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
    if (closedir(dir) < 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK) {
        qsort(sequences, n, sizeof(*sequences), compare);
        for (size_t i = 0; i < n; ++i) if (sequences[i] != i + 1) return GOLEM_ERR_CORRUPT_JOURNAL;
        if (n == 0) return GOLEM_ERR_UNSUPPORTED_VERSION;
        *count = n;
    }
    return s;
}
static golem_status read_named(const char *path, const char *name, size_t limit, gd_blob *out)
{
    char file[GD_PATH]; golem_status s = gd_path(path, name, file);
    return s == GOLEM_OK ? gd_read(file, limit, out) : s;
}
/* Build and semantically validate the complete authoritative event transcript.
 * Nothing is changed until all frames, identity, context and option binding pass. */
static golem_status transcript(const char *path, gd_blob *out)
{
    gd_blob marker = {0}, options = {0}, identity = {0}, context = {0}, joined = {0};
    uint64_t sequences[GD_MAX_RECORDS]; size_t count = 0, capacity = 0;
    golem_status s = read_named(path, "recovery.meta", 40, &marker);
    if (s == GOLEM_ERR_NOT_FOUND) s = GOLEM_ERR_UNSUPPORTED_VERSION;
    if (s == GOLEM_OK && (marker.size != 40 || memcmp(marker.data, "GRCV0001", 8) != 0)) s = GOLEM_ERR_UNSUPPORTED_VERSION;
    if (s == GOLEM_OK) s = read_named(path, "options.bin", 32, &options);
    golem_digest digest;
    if (s == GOLEM_OK) s = golem_digest_bytes((golem_bytes){options.data, options.size}, &digest);
    if (s == GOLEM_OK && (options.size != 32 || memcmp(marker.data + 8, &digest, 32) != 0)) s = GOLEM_ERR_DIGEST_MISMATCH;
    if (s == GOLEM_OK) s = read_named(path, "id", 95, &identity);
    if (s == GOLEM_OK && (identity.size == 0 || memchr(identity.data, 0, identity.size) != NULL)) s = GOLEM_ERR_IDENTITY_MISMATCH;
    if (s == GOLEM_OK) s = read_named(path, "context.bin", GOLEM_JOURNAL_MAX_PAYLOAD, &context);
    if (s == GOLEM_OK) s = intent_list(path, sequences, &count);
    for (size_t i = 0; s == GOLEM_OK && i < count; ++i) {
        char name[40]; (void)snprintf(name, sizeof(name), "intent-%020" PRIu64, sequences[i]);
        gd_blob frame = {0}; s = read_named(path, name, GOLEM_JOURNAL_MAX_PAYLOAD + GOLEM_JOURNAL_HEADER_SIZE, &frame);
        golem_journal_record record; size_t consumed;
        if (s == GOLEM_OK) s = golem_journal_record_decode((golem_bytes){frame.data, frame.size}, &record, &consumed, NULL);
        if (s == GOLEM_OK && (consumed != frame.size || record.sequence != sequences[i])) s = GOLEM_ERR_CORRUPT_JOURNAL;
        if (s == GOLEM_OK && i == 0 && (record.type != GOLEM_JOURNAL_CREATED || record.payload.size != context.size ||
            memcmp(record.payload.data, context.data, context.size) != 0)) s = GOLEM_ERR_REPLAY_MISMATCH;
        if (s == GOLEM_OK && frame.size > GD_LIMIT - joined.size) s = GOLEM_ERR_OVERFLOW;
        if (s == GOLEM_OK && joined.size + frame.size > capacity) {
            size_t grown = capacity == 0 ? 4096 : capacity;
            while (grown < joined.size + frame.size) grown = grown > GD_LIMIT / 2 ? GD_LIMIT : grown * 2;
            void *allocation = realloc(joined.data, grown);
            if (allocation == NULL) s = GOLEM_ERR_OUT_OF_MEMORY;
            else { joined.data = allocation; capacity = grown; }
        }
        if (s == GOLEM_OK) { memcpy(joined.data + joined.size, frame.data, frame.size); joined.size += frame.size; }
        free(frame.data);
    }
    golem_replay *replay = NULL; golem_work_run *run = NULL;
    golem_replay_options replay_options = {.expected_run_id = (const char *)identity.data};
    if (s == GOLEM_OK) s = golem_replay_create(&replay_options, NULL, &replay, NULL);
    if (s == GOLEM_OK) s = golem_replay_feed(replay, (golem_bytes){joined.data, joined.size}, NULL);
    if (s == GOLEM_OK) s = golem_replay_finish(replay, &run, NULL, NULL);
    golem_work_run_free(run); golem_replay_free(replay);
    free(marker.data); free(options.data); free(identity.data); free(context.data);
    if (s == GOLEM_OK) *out = joined; else free(joined.data);
    return s;
}
golem_status gd_intents_check(const char *path, golem_bytes journal)
{
    gd_blob expected = {0}; golem_status s = transcript(path, &expected);
    if (s == GOLEM_OK && (journal.size != expected.size || memcmp(journal.data, expected.data, journal.size) != 0)) s = GOLEM_ERR_REPLAY_MISMATCH;
    free(expected.data); return s;
}
static golem_status repair(const char *path, bool *changed, bool *fatal)
{
    *fatal = false;
    int dir = golem_evidence_path_open(path, true); if (dir < 0) return GOLEM_ERR_IO;
    int fd = openat(dir, "journal.bin", O_RDWR | O_APPEND | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    (void)close(dir); if (fd < 0) return GOLEM_ERR_IO;
    golem_status s = GOLEM_OK; struct stat st; gd_blob expected = {0};
    if (fstat(fd, &st) < 0 || !S_ISREG(st.st_mode) || st.st_size < 0 || (uintmax_t)st.st_size > GD_LIMIT) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK && flock(fd, LOCK_EX | LOCK_NB) < 0) s = GOLEM_ERR_JOURNAL_BUSY;
    if (s == GOLEM_OK && (fstat(fd, &st) < 0 || st.st_size < 0 || (uintmax_t)st.st_size > GD_LIMIT)) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK) s = transcript(path, &expected);
    size_t size = s == GOLEM_OK ? (size_t)st.st_size : 0;
    if (s == GOLEM_OK && size > expected.size) s = GOLEM_ERR_REPLAY_MISMATCH;
    uint8_t bytes[8192]; size_t offset = 0;
    while (s == GOLEM_OK && offset < size) {
        size_t n = size - offset < sizeof(bytes) ? size - offset : sizeof(bytes);
        ssize_t got = pread(fd, bytes, n, (off_t)offset);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0) { s = GOLEM_ERR_IO; break; }
        if (memcmp(bytes, expected.data + offset, (size_t)got) != 0) { s = GOLEM_ERR_REPLAY_MISMATCH; break; }
        offset += (size_t)got;
    }
    /* A verified byte prefix can be completed solely by append, never truncate.
     * Another crash simply leaves a longer prefix for the next recovery. */
    while (s == GOLEM_OK && offset < expected.size) {
        ssize_t n = write(fd, expected.data + offset, expected.size - offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { s = GOLEM_ERR_IO; *fatal = true; break; }
        offset += (size_t)n;
    }
    bool repaired = s == GOLEM_OK && size != expected.size;
    if (s == GOLEM_OK && fsync(fd) < 0) { s = GOLEM_ERR_IO; *fatal = true; }
    if (close(fd) < 0 && s == GOLEM_OK) { s = GOLEM_ERR_IO; *fatal = true; }
    free(expected.data); if (s == GOLEM_OK) *changed = repaired; return s;
}
golem_status gd_recover_queue(const char *root, golem_daemon_recovery_report *out)
{
    int fd = gd_root(root); if (fd < 0) return GOLEM_ERR_IO;
    int lock = gd_lock(fd, ".queue.lock", false, false);
    uint64_t tickets[GOLEM_DAEMON_MAX_JOBS]; size_t count = 0;
    golem_status s = lock < 0 ? GOLEM_ERR_JOURNAL_BUSY : gd_list(fd, tickets, &count);
    golem_daemon_recovery_report report = {0};
    for (size_t i = 0; s == GOLEM_OK && i < count; ++i) {
        char path[GD_PATH]; s = gd_job_path(root, tickets[i], path); if (s != GOLEM_OK) break;
        bool changed = false, fatal = false; golem_status recovered = repair(path, &changed, &fatal); ++report.jobs;
        if (recovered == GOLEM_ERR_JOURNAL_BUSY) { ++report.busy; continue; }
        if (fatal || recovered == GOLEM_ERR_OUT_OF_MEMORY) { s = recovered; break; }
        if (recovered != GOLEM_OK) { ++report.attention; continue; }
        if (changed) ++report.repaired;
        golem_daemon_job job = {0}; golem_runtime_options options;
        (void)gd_load(path, &job, &options);
        if (job.state == GOLEM_DAEMON_READY) ++report.ready;
        else if (job.state == GOLEM_DAEMON_COMPLETE) ++report.complete;
        else if (job.state == GOLEM_DAEMON_BUSY) ++report.busy;
        else ++report.attention;
    }
    if (lock >= 0) (void)close(lock);
    (void)close(fd); if (s == GOLEM_OK) *out = report; return s;
}
golem_status golem_daemon_recover(const char *root, golem_daemon_recovery_report *out)
{
    if (out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = gd_root(root); if (fd < 0) return GOLEM_ERR_IO;
    int owner = gd_lock(fd, ".daemon.lock", false, true); (void)close(fd);
    if (owner < 0) return GOLEM_ERR_JOURNAL_BUSY;
    golem_daemon_recovery_report report;
    golem_status s = gd_recover_queue(root, &report);
    if (close(owner) < 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK) *out = report;
    return s;
}
