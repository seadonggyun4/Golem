#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include "../evidence/internal.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

static bool same(const struct stat *a, const struct stat *b)
{
#ifdef __APPLE__
    bool times = a->st_mtimespec.tv_sec == b->st_mtimespec.tv_sec &&
        a->st_mtimespec.tv_nsec == b->st_mtimespec.tv_nsec &&
        a->st_ctimespec.tv_sec == b->st_ctimespec.tv_sec && a->st_ctimespec.tv_nsec == b->st_ctimespec.tv_nsec;
#else
    bool times = a->st_mtim.tv_sec == b->st_mtim.tv_sec && a->st_mtim.tv_nsec == b->st_mtim.tv_nsec &&
        a->st_ctim.tv_sec == b->st_ctim.tv_sec && a->st_ctim.tv_nsec == b->st_ctim.tv_nsec;
#endif
    return times && a->st_dev == b->st_dev && a->st_ino == b->st_ino &&
        a->st_size == b->st_size && a->st_mode == b->st_mode && a->st_nlink == b->st_nlink;
}
static golem_status snapshot(int fd, uint8_t *bytes, size_t *size, size_t limit)
{
    *size = 0;
    while (*size <= limit) {
        ssize_t n = read(fd, bytes + *size, limit + 1u - *size);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) return GOLEM_ERR_IO;
        if (!n) return GOLEM_OK;
        *size += (size_t)n;
    }
    return GOLEM_ERR_OVERFLOW;
}
golem_status golem_workpack_read_limit(const char *path, uint8_t *buffer, size_t capacity, size_t limit,
                                size_t *size, golem_diagnostic *diagnostic)
{
    golem_status status = GOLEM_ERR_INVALID_ARGUMENT;
    const char *tag = "PACK_PATH";
    if (!limit || limit > GOLEM_WORKPACK_CATALOG_MAX_JSON || !path || !*path || strnlen(path, 4096) >= 4096 || !buffer || !size) goto done;
    if (capacity < limit) { status = GOLEM_ERR_BUFFER_TOO_SMALL; goto done; }
    int fd = golem_evidence_path_open(path, false), named = -1;
    if (fd < 0) { status = errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO; goto done; }
    struct stat before, after, current;
    uint8_t *first = NULL, *second = NULL; size_t n = 0, m = 0;
    tag = "PACK_FILE"; status = GOLEM_ERR_IO;
    if (fstat(fd, &before) || !S_ISREG(before.st_mode) || before.st_nlink != 1 || before.st_size < 0) goto close;
    if ((uintmax_t)before.st_size > limit) { status = GOLEM_ERR_OVERFLOW; goto close; }
    if (flock(fd, LOCK_SH | LOCK_NB)) { status = GOLEM_ERR_JOURNAL_BUSY; goto close; }
    first = malloc(limit + 1u); second = malloc(limit + 1u);
    if (!first || !second) { status = GOLEM_ERR_OUT_OF_MEMORY; goto close; }
    status = snapshot(fd, first, &n, limit);
    if (status != GOLEM_OK) goto close;
    if (lseek(fd, 0, SEEK_SET) < 0) { status = GOLEM_ERR_IO; goto close; }
    status = snapshot(fd, second, &m, limit);
    if (status != GOLEM_OK) goto close;
    tag = "PACK_FILE_CHANGED"; status = GOLEM_ERR_STALE_RESULT;
    if (fstat(fd, &after) || !same(&before, &after) || n != (size_t)before.st_size || n != m || memcmp(first, second, n)) goto close;
    named = golem_evidence_path_open(path, false);
    if (named < 0 || fstat(named, &current) || !same(&after, &current)) goto close;
    status = GOLEM_OK;
close:
    if (named >= 0 && close(named) && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (close(fd) && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK) { memcpy(buffer, first, n); *size = n; tag = "PACK_SNAPSHOT_ONLY"; }
    free(first); free(second);
done:
    if (diagnostic) (void)golem_diagnostic_set(diagnostic, status, GOLEM_DIAGNOSTIC_NO_OFFSET, tag);
    return status;
}

golem_status golem_workpack_read(const char *path, uint8_t *buffer, size_t capacity,
                                size_t *size, golem_diagnostic *diagnostic)
{
    return golem_workpack_read_limit(path, buffer, capacity, GOLEM_WORKPACK_MAX_JSON, size, diagnostic);
}
