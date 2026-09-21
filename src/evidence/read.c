#define _POSIX_C_SOURCE 200809L
#define _FILE_OFFSET_BITS 64
#include "internal.h"
#include <errno.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

golem_status golem_evidence_read(golem_evidence_store *store, const golem_digest *digest,
    size_t max_size, const golem_allocator *allocator, uint8_t **out, size_t *size, golem_diagnostic *d)
{
    if (store == NULL || digest == NULL || out == NULL || size == NULL || golem_allocator_validate(allocator) != GOLEM_OK)
        return golem_evidence_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    int fd = -1;
    golem_status status = golem_evidence_object_open(store, digest, &fd);
    struct stat info;
    size_t length = 0;
    if (status == GOLEM_OK && (fstat(fd, &info) < 0 || info.st_size < 0)) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK && ((uintmax_t)info.st_size > max_size || (uintmax_t)info.st_size > GOLEM_SHA256_MAX_BYTES))
        status = GOLEM_ERR_OVERFLOW;
    void *memory = NULL;
    if (status == GOLEM_OK) {
        length = (size_t)info.st_size;
        status = golem_allocator_alloc(allocator, length == 0 ? 1 : length, &memory);
    }
    size_t offset = 0;
    while (status == GOLEM_OK && offset < length) {
        size_t amount = length - offset;
        if (amount > GOLEM_EVIDENCE_CHUNK) amount = GOLEM_EVIDENCE_CHUNK;
        ssize_t n = read(fd, (uint8_t *)memory + offset, amount);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { status = GOLEM_ERR_IO; break; }
        offset += (size_t)n;
    }
    if (status == GOLEM_OK) {
        uint8_t extra;
        ssize_t n;
        do { n = read(fd, &extra, 1); } while (n < 0 && errno == EINTR);
        if (n != 0) status = GOLEM_ERR_IO;
    }
    if (fd >= 0 && close(fd) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    golem_digest actual;
    if (status == GOLEM_OK) status = golem_digest_bytes((golem_bytes){memory, length}, &actual);
    if (status == GOLEM_OK && memcmp(actual.bytes, digest->bytes, GOLEM_DIGEST_SIZE) != 0)
        status = GOLEM_ERR_DIGEST_MISMATCH;
    if (status == GOLEM_OK) { *out = memory; *size = length; }
    else (void)golem_allocator_free(allocator, memory);
    return golem_evidence_report(d, status, NULL);
}
