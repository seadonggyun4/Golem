#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#define _FILE_OFFSET_BITS 64
#include "internal.h"
#include "golem/replay.h"
#include <errno.h>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>

_Static_assert(sizeof(off_t) >= 8, "journal backend requires 64-bit file offsets");

struct golem_journal {
    golem_allocator allocator;
    int fd;
    size_t length;
    uint64_t next_sequence;
    bool poisoned;
    golem_digest chain_head;
};

golem_status golem_journal_checkpoint_get(const golem_journal *j, golem_journal_checkpoint *out)
{
    if (j == NULL || out == NULL)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->poisoned)
        return GOLEM_ERR_INVALID_STATE;
    *out = (golem_journal_checkpoint){j->next_sequence == 0 ? UINT64_MAX : j->next_sequence - 1,
                                      j->length, j->chain_head};
    return GOLEM_OK;
}

static golem_status read_at(int fd, uint8_t *buffer, size_t size, size_t offset)
{
    while (size != 0) {
        ssize_t amount = pread(fd, buffer, size, (off_t)offset);
        if (amount < 0 && errno == EINTR)
            continue;
        if (amount < 0)
            return GOLEM_ERR_IO;
        if (amount == 0)
            return GOLEM_ERR_TRUNCATED_JOURNAL;
        buffer += (size_t)amount;
        offset += (size_t)amount;
        size -= (size_t)amount;
    }
    return GOLEM_OK;
}
static golem_status sync_file(int fd)
{
    int result;
    do {
        result = fsync(fd);
    } while (result < 0 && errno == EINTR);
    return result == 0 ? GOLEM_OK : GOLEM_ERR_IO;
}
static golem_status scan(golem_journal *j, golem_diagnostic *d)
{
    size_t offset = 0;
    while (offset < j->length) {
        if (j->length - offset < GOLEM_JOURNAL_HEADER_SIZE)
            return golem_journal_report(d, GOLEM_ERR_TRUNCATED_JOURNAL, j->length,
                                        "incomplete header");
        uint8_t header[GOLEM_JOURNAL_HEADER_SIZE];
        golem_status status = read_at(j->fd, header, sizeof(header), offset);
        if (status != GOLEM_OK)
            return golem_journal_report(d, status, offset, NULL);
        size_t size;
        golem_diagnostic detail;
        status = golem_journal_header_check(header, &size, &detail);
        if (status != GOLEM_OK)
            return golem_journal_report(d, status, offset + detail.offset, detail.message);
        if (size > j->length - offset)
            return golem_journal_report(d, GOLEM_ERR_TRUNCATED_JOURNAL, j->length,
                                        "incomplete payload");
        void *memory;
        status = golem_allocator_alloc(&j->allocator, size, &memory);
        if (status != GOLEM_OK)
            return golem_journal_report(d, status, offset, NULL);
        status = read_at(j->fd, memory, size, offset);
        golem_journal_record record;
        size_t consumed;
        if (status == GOLEM_OK) {
            status = golem_journal_record_decode((golem_bytes){memory, size}, &record, &consumed,
                                                 &detail);
        } else {
            (void)golem_diagnostic_set(&detail, status, 0, "cannot read existing frame");
        }
        if (status == GOLEM_OK && (j->next_sequence == 0 || record.sequence != j->next_sequence))
            status = golem_journal_report(&detail, GOLEM_ERR_CORRUPT_JOURNAL, 16,
                                          "noncontiguous sequence");
        if (status == GOLEM_OK)
            status = golem_journal_chain_extend(&j->chain_head, (golem_bytes){memory, size},
                                                &j->chain_head);
        if (status == GOLEM_OK)
            j->next_sequence = record.sequence == UINT64_MAX ? 0 : record.sequence + 1;
        (void)golem_allocator_free(&j->allocator, memory);
        if (status != GOLEM_OK)
            return golem_journal_report(d, status, offset + detail.offset, detail.message);
        offset += size;
    }
    return GOLEM_OK;
}
golem_status golem_journal_open(const char *path, const golem_allocator *allocator,
                                golem_journal **out, golem_diagnostic *d)
{
    if (path == NULL || path[0] == '\0' || out == NULL ||
        golem_allocator_validate(allocator) != GOLEM_OK)
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, NULL);
    void *memory;
    golem_status status = golem_allocator_alloc(allocator, sizeof(golem_journal), &memory);
    if (status != GOLEM_OK)
        return golem_journal_report(d, status, 0, NULL);
    golem_journal *j = memory;
    *j = (golem_journal){.allocator = allocator == NULL ? golem_allocator_default() : *allocator,
                         .fd = -1,
                         .next_sequence = 1};
    j->fd = open(path, O_RDWR | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK, 0600);
    if (j->fd < 0)
        status = GOLEM_ERR_IO;
    struct stat info;
    if (status == GOLEM_OK && (fstat(j->fd, &info) < 0 || !S_ISREG(info.st_mode) ||
                               info.st_size < 0 || (uintmax_t)info.st_size > SIZE_MAX))
        status = GOLEM_ERR_IO;
    if (status == GOLEM_OK && flock(j->fd, LOCK_EX | LOCK_NB) < 0)
        status = errno == EWOULDBLOCK || errno == EAGAIN ? GOLEM_ERR_JOURNAL_BUSY : GOLEM_ERR_IO;
    if (status != GOLEM_OK) {
        (void)golem_journal_report(d, status, 0, "cannot open and lock regular journal");
    } else {
        /* Sample length only after acquiring the writer lock. */
        if (fstat(j->fd, &info) < 0 || info.st_size < 0 || (uintmax_t)info.st_size > SIZE_MAX) {
            status = golem_journal_report(d, GOLEM_ERR_IO, 0, "cannot stat journal");
        } else {
            j->length = (size_t)info.st_size;
            status = scan(j, d);
        }
    }
    if (status != GOLEM_OK) {
        (void)golem_journal_close(j, NULL);
        return status;
    }
    *out = j;
    return golem_journal_report(d, GOLEM_OK, 0, NULL);
}
golem_status golem_journal_append(golem_journal *j, golem_journal_type type, golem_bytes payload,
                                  uint64_t *sequence, golem_diagnostic *d)
{
    if (j == NULL || sequence == NULL)
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, NULL);
    if (j->poisoned)
        return golem_journal_report(d, GOLEM_ERR_INVALID_STATE, j->length,
                                    "writer poisoned by I/O failure");
    if (j->next_sequence == 0)
        return golem_journal_report(d, GOLEM_ERR_OVERFLOW, j->length, "sequence exhausted");
    size_t size;
    golem_status status =
        golem_journal_record_encode(type, j->next_sequence, payload, NULL, 0, &size, d);
    if (status != GOLEM_ERR_BUFFER_TOO_SMALL)
        return status;
    if (size > SIZE_MAX - j->length || (uintmax_t)j->length + size > INT64_MAX)
        return golem_journal_report(d, GOLEM_ERR_OVERFLOW, j->length, "file offset overflow");
    void *memory;
    status = golem_allocator_alloc(&j->allocator, size, &memory);
    if (status != GOLEM_OK)
        return golem_journal_report(d, status, j->length, NULL);
    status = golem_journal_record_encode(type, j->next_sequence, payload, memory, size, &size, d);
    golem_digest next_head;
    if (status == GOLEM_OK)
        status =
            golem_journal_chain_extend(&j->chain_head, (golem_bytes){memory, size}, &next_head);
    struct stat info;
    if (status == GOLEM_OK &&
        (fstat(j->fd, &info) < 0 || info.st_size < 0 || (uintmax_t)info.st_size != j->length))
        status = GOLEM_ERR_IO;
    size_t written = 0;
    while (status == GOLEM_OK && written < size) {
        ssize_t amount = write(j->fd, (uint8_t *)memory + written, size - written);
        if (amount < 0 && errno == EINTR)
            continue;
        if (amount <= 0) {
            status = GOLEM_ERR_IO;
            break;
        }
        written += (size_t)amount;
    }
    if (status == GOLEM_OK)
        status = sync_file(j->fd);
    (void)golem_allocator_free(&j->allocator, memory);
    if (status != GOLEM_OK) {
        j->poisoned = true;
        return golem_journal_report(d, status, j->length + written,
                                    "append durability uncertain; inspect before retry");
    }
    *sequence = j->next_sequence;
    j->next_sequence = j->next_sequence == UINT64_MAX ? 0 : j->next_sequence + 1;
    j->length += size;
    j->chain_head = next_head;
    return golem_journal_report(d, GOLEM_OK, 0, NULL);
}
golem_status golem_journal_close(golem_journal *j, golem_diagnostic *d)
{
    golem_status status = GOLEM_OK;
    if (j != NULL) {
        /* Never retry close after EINTR: the descriptor may have been reused. */
        if (j->fd >= 0 && close(j->fd) < 0)
            status = GOLEM_ERR_IO;
        (void)golem_allocator_free(&j->allocator, j);
    }
    return golem_journal_report(d, status, 0, NULL);
}

golem_status golem_journal_recover(golem_journal *j, const golem_replay_options *options,
                                   golem_work_run **out, golem_replay_report *report,
                                   golem_diagnostic *d)
{
    if (j == NULL || out == NULL) {
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, NULL);
    }
    if (j->poisoned) {
        return golem_journal_report(d, GOLEM_ERR_INVALID_STATE, j->length, "journal is poisoned");
    }
    golem_replay *engine = NULL;
    golem_status status = golem_replay_create(options, &j->allocator, &engine, d);
    if (status != GOLEM_OK) {
        return status;
    }
    golem_journal_checkpoint checkpoint;
    status = golem_journal_checkpoint_get(j, &checkpoint);
    if (status == GOLEM_OK)
        status = golem_replay_expect_checkpoint(engine, &checkpoint);
    struct stat info;
    if (fstat(j->fd, &info) < 0 || info.st_size < 0 || (uintmax_t)info.st_size != j->length) {
        status = golem_journal_report(d, GOLEM_ERR_IO, 0, "journal length changed before recovery");
    }
    uint8_t buffer[16384];
    size_t offset = 0;
    while (status == GOLEM_OK && offset < j->length) {
        size_t amount = j->length - offset;
        if (amount > sizeof(buffer)) {
            amount = sizeof(buffer);
        }
        status = read_at(j->fd, buffer, amount, offset);
        if (status != GOLEM_OK) {
            (void)golem_journal_report(d, status, offset, "cannot read recovery input");
            break;
        }
        status = golem_replay_feed(engine, (golem_bytes){buffer, amount}, d);
        offset += amount;
    }
    if (status == GOLEM_OK &&
        (fstat(j->fd, &info) < 0 || info.st_size < 0 || (uintmax_t)info.st_size != j->length)) {
        status =
            golem_journal_report(d, GOLEM_ERR_IO, offset, "journal length changed during recovery");
    }
    if (status == GOLEM_OK) {
        status = golem_replay_finish(engine, out, report, d);
    }
    golem_replay_free(engine);
    if (status != GOLEM_OK) {
        j->poisoned = true;
    }
    return status;
}
