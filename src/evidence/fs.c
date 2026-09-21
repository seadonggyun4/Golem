#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#define _FILE_OFFSET_BITS 64
#include "internal.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

_Static_assert(sizeof(off_t) >= 8, "evidence backend requires 64-bit file offsets");

int golem_evidence_path_open(const char *path, bool directory)
{
    if (path == NULL || path[0] == '\0') { errno = EINVAL; return -1; }
    int parent = open(path[0] == '/' ? "/" : ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (parent < 0) return -1;
    const char *cursor = path;
    while (*cursor != '\0') {
        if (*cursor == '/') { ++cursor; continue; }
        const char *start = cursor;
        while (*cursor != '/' && *cursor != '\0') ++cursor;
        size_t length = (size_t)(cursor - start);
        bool last = *cursor == '\0';
        if (length == 1 && start[0] == '.' && (!last || directory)) continue;
        if (length > NAME_MAX || (length == 2 && start[0] == '.' && start[1] == '.') ||
            (length == 1 && start[0] == '.')) {
            (void)close(parent); errno = EINVAL; return -1;
        }
        char name[NAME_MAX + 1];
        memcpy(name, start, length); name[length] = '\0';
        int flags = O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK;
        if (!last || directory) flags |= O_DIRECTORY;
        int child = openat(parent, name, flags);
        int error = errno;
        (void)close(parent);
        if (child < 0) { errno = error; return -1; }
        parent = child;
        if (last) return parent;
    }
    if (directory) return parent;
    (void)close(parent); errno = EINVAL; return -1;
}

static bool same_file(const struct stat *before, const struct stat *after)
{
#ifdef __APPLE__
    return before->st_size == after->st_size &&
        before->st_mtimespec.tv_sec == after->st_mtimespec.tv_sec &&
        before->st_mtimespec.tv_nsec == after->st_mtimespec.tv_nsec;
#else
    return before->st_size == after->st_size &&
        before->st_mtim.tv_sec == after->st_mtim.tv_sec && before->st_mtim.tv_nsec == after->st_mtim.tv_nsec;
#endif
}

golem_status golem_evidence_scan_fd(int fd, int copy_fd, golem_receipt *out)
{
    struct stat before, after;
    if (fstat(fd, &before) < 0 || !S_ISREG(before.st_mode) || before.st_size < 0) return GOLEM_ERR_IO;
    if ((uintmax_t)before.st_size > GOLEM_SHA256_MAX_BYTES) return GOLEM_ERR_OVERFLOW;
    EVP_MD_CTX *ctx = NULL;
    golem_status status = golem_evidence_hash_begin(&ctx);
    uint8_t buffer[GOLEM_EVIDENCE_CHUNK];
    golem_receipt receipt = {GOLEM_RECEIPT_VERSION, GOLEM_DIGEST_SHA256, 0, {{0}}};
    while (status == GOLEM_OK) {
        ssize_t amount = read(fd, buffer, sizeof(buffer));
        if (amount < 0 && errno == EINTR) continue;
        if (amount < 0) { status = GOLEM_ERR_IO; break; }
        if (amount == 0) break;
        if ((uint64_t)amount > GOLEM_SHA256_MAX_BYTES - receipt.size) {
            status = GOLEM_ERR_OVERFLOW; break;
        }
        receipt.size += (uint64_t)amount;
        if (receipt.size > (uint64_t)before.st_size) { status = GOLEM_ERR_IO; break; }
        if (EVP_DigestUpdate(ctx, buffer, (size_t)amount) != 1) { status = GOLEM_ERR_CRYPTO; break; }
        size_t offset = 0;
        while (copy_fd >= 0 && offset < (size_t)amount) {
            ssize_t written = write(copy_fd, buffer + offset, (size_t)amount - offset);
            if (written < 0 && errno == EINTR) continue;
            if (written <= 0) { status = GOLEM_ERR_IO; break; }
            offset += (size_t)written;
        }
    }
    /* Link publication/temporary unlink changes ctime without changing content.
     * Compare size and mtime, then rely on the expected digest for CAS reads. */
    if (status == GOLEM_OK && (fstat(fd, &after) < 0 || !same_file(&before, &after) ||
        receipt.size != (uint64_t)before.st_size)) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK) status = golem_evidence_hash_end(ctx, &receipt.digest);
    EVP_MD_CTX_free(ctx);
    if (status == GOLEM_OK) *out = receipt;
    return status;
}

golem_status golem_digest_file(const char *path, golem_receipt *out, golem_diagnostic *d)
{
    if (path == NULL || path[0] == '\0' || out == NULL)
        return golem_evidence_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    int fd = golem_evidence_path_open(path, false);
    if (fd < 0) return golem_evidence_report(d, errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO,
        "cannot open regular artifact without symlinks");
    golem_receipt receipt;
    golem_status status = golem_evidence_scan_fd(fd, -1, &receipt);
    if (close(fd) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK) *out = receipt;
    return golem_evidence_report(d, status, NULL);
}
