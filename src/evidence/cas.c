#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#define _FILE_OFFSET_BITS 64
#include "internal.h"
#include <errno.h>
#include <fcntl.h>
#include <openssl/rand.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static golem_status sync_fd(int fd)
{
    int result;
    do { result = fsync(fd); } while (result < 0 && errno == EINTR);
    return result == 0 ? GOLEM_OK : GOLEM_ERR_IO;
}

static golem_status directory_open(int parent, const char *name, bool create, int *out)
{
    if (create && mkdirat(parent, name, 0700) < 0 && errno != EEXIST) return GOLEM_ERR_IO;
    int fd = openat(parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) return errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO;
    /* Sync even existing directories: another concurrent writer may have created them. */
    if (create && (sync_fd(fd) != GOLEM_OK || sync_fd(parent) != GOLEM_OK)) {
        (void)close(fd); return GOLEM_ERR_IO;
    }
    *out = fd;
    return GOLEM_OK;
}

golem_status golem_evidence_open(const char *root, bool create, const golem_allocator *allocator,
    golem_evidence_store **out, golem_diagnostic *d)
{
    if (root == NULL || root[0] == '\0' || out == NULL || golem_allocator_validate(allocator) != GOLEM_OK)
        return golem_evidence_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    void *memory = NULL;
    golem_status status = golem_allocator_alloc(allocator, sizeof(golem_evidence_store), &memory);
    if (status != GOLEM_OK) return golem_evidence_report(d, status, NULL);
    int root_fd = golem_evidence_path_open(root, true), objects = -1, sha256 = -1;
    if (root_fd < 0) status = errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO;
    if (status == GOLEM_OK) status = directory_open(root_fd, "objects", create, &objects);
    if (status == GOLEM_OK) status = directory_open(objects, "sha256", create, &sha256);
    if (objects >= 0 && close(objects) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (root_fd >= 0 && close(root_fd) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (status != GOLEM_OK) {
        if (sha256 >= 0) (void)close(sha256);
        (void)golem_allocator_free(allocator, memory);
    } else {
        golem_evidence_store *store = memory;
        *store = (golem_evidence_store){allocator == NULL ? golem_allocator_default() : *allocator, sha256, create};
        *out = store;
    }
    return golem_evidence_report(d, status, NULL);
}

golem_status golem_evidence_close(golem_evidence_store *store)
{
    if (store == NULL) return GOLEM_OK;
    golem_status status = close(store->fd) == 0 ? GOLEM_OK : GOLEM_ERR_IO;
    (void)golem_allocator_free(&store->allocator, store);
    return status;
}

static void key_names(const golem_digest *digest, char hex[GOLEM_DIGEST_HEX_CAPACITY], char shard[3])
{
    size_t required;
    (void)golem_digest_format(digest, hex, GOLEM_DIGEST_HEX_CAPACITY, &required);
    shard[0] = hex[0]; shard[1] = hex[1]; shard[2] = '\0';
}

golem_status golem_evidence_object_open(golem_evidence_store *store, const golem_digest *digest, int *out)
{
    char hex[GOLEM_DIGEST_HEX_CAPACITY], shard[3];
    key_names(digest, hex, shard);
    int directory = -1;
    golem_status status = directory_open(store->fd, shard, false, &directory);
    if (status != GOLEM_OK) return status;
    int fd = openat(directory, hex + 2, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) status = errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO;
    if (close(directory) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    struct stat info;
    if (status == GOLEM_OK && (fstat(fd, &info) < 0 || !S_ISREG(info.st_mode))) status = GOLEM_ERR_IO;
    if (status != GOLEM_OK) { if (fd >= 0) (void)close(fd); }
    else *out = fd;
    return status;
}

golem_status golem_evidence_verify(golem_evidence_store *store, const golem_digest *digest,
    uint64_t *size, golem_diagnostic *d)
{
    if (store == NULL || digest == NULL || size == NULL)
        return golem_evidence_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    int fd = -1;
    golem_status status = golem_evidence_object_open(store, digest, &fd);
    golem_receipt actual;
    if (status == GOLEM_OK) status = golem_evidence_scan_fd(fd, -1, &actual);
    if (fd >= 0 && close(fd) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK && memcmp(actual.digest.bytes, digest->bytes, GOLEM_DIGEST_SIZE) != 0)
        status = GOLEM_ERR_DIGEST_MISMATCH;
    if (status == GOLEM_OK) *size = actual.size;
    return golem_evidence_report(d, status, NULL);
}

static golem_status temporary_open(int directory, char name[38], int *out)
{
    for (unsigned int attempt = 0; attempt < 8; ++attempt) {
        unsigned char random[16];
        if (RAND_bytes(random, sizeof(random)) != 1) return GOLEM_ERR_CRYPTO;
        memcpy(name, ".tmp-", 5);
        const char hex[] = "0123456789abcdef";
        for (size_t i = 0; i < sizeof(random); ++i) {
            name[5 + i * 2] = hex[random[i] >> 4];
            name[6 + i * 2] = hex[random[i] & 15];
        }
        name[37] = '\0';
        int fd = openat(directory, name, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
        if (fd >= 0) { *out = fd; return GOLEM_OK; }
        if (errno != EEXIST) return GOLEM_ERR_IO;
    }
    return GOLEM_ERR_IO;
}

static golem_status copy_bytes(int fd, golem_bytes bytes, golem_receipt *out)
{
    EVP_MD_CTX *ctx = NULL;
    golem_status status = golem_evidence_hash_begin(&ctx);
    size_t offset = 0;
    while (status == GOLEM_OK && offset < bytes.size) {
        size_t amount = bytes.size - offset;
        if (amount > GOLEM_EVIDENCE_CHUNK) amount = GOLEM_EVIDENCE_CHUNK;
        ssize_t written = write(fd, bytes.data + offset, amount);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) { status = GOLEM_ERR_IO; break; }
        if (EVP_DigestUpdate(ctx, bytes.data + offset, (size_t)written) != 1) status = GOLEM_ERR_CRYPTO;
        offset += (size_t)written;
    }
    golem_receipt receipt = {GOLEM_RECEIPT_VERSION, GOLEM_DIGEST_SHA256, bytes.size, {{0}}};
    if (status == GOLEM_OK) status = golem_evidence_hash_end(ctx, &receipt.digest);
    EVP_MD_CTX_free(ctx);
    if (status == GOLEM_OK) *out = receipt;
    return status;
}

static golem_status publish(golem_evidence_store *store, int source_fd, golem_bytes bytes,
    golem_receipt *out)
{
    char temporary[38];
    int fd = -1;
    golem_status status = temporary_open(store->fd, temporary, &fd);
    if (status != GOLEM_OK) return status;
    golem_receipt receipt;
    status = source_fd >= 0 ? golem_evidence_scan_fd(source_fd, fd, &receipt) : copy_bytes(fd, bytes, &receipt);
    if (status == GOLEM_OK && fchmod(fd, 0400) < 0) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK) status = sync_fd(fd);
    if (close(fd) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    int shard_fd = -1;
    if (status == GOLEM_OK) {
        char hex[GOLEM_DIGEST_HEX_CAPACITY], shard[3];
        key_names(&receipt.digest, hex, shard);
        status = directory_open(store->fd, shard, true, &shard_fd);
        if (status == GOLEM_OK && linkat(store->fd, temporary, shard_fd, hex + 2, 0) < 0) {
            if (errno != EEXIST) status = GOLEM_ERR_IO;
            else {
                uint64_t size;
                status = golem_evidence_verify(store, &receipt.digest, &size, NULL);
                if (status == GOLEM_OK && size != receipt.size) status = GOLEM_ERR_SIZE_MISMATCH;
            }
        }
        if (status == GOLEM_OK) status = sync_fd(shard_fd);
    }
    if (shard_fd >= 0 && close(shard_fd) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    /* Only our unpublished temporary name is removed; never delete a CAS key. */
    if (unlinkat(store->fd, temporary, 0) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK) status = sync_fd(store->fd);
    if (status == GOLEM_OK) *out = receipt;
    return status;
}

golem_status golem_evidence_put(golem_evidence_store *store, golem_bytes bytes,
    golem_receipt *out, golem_diagnostic *d)
{
    if (store == NULL || out == NULL || (bytes.data == NULL && bytes.size != 0))
        return golem_evidence_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (!store->writable) return golem_evidence_report(d, GOLEM_ERR_POLICY_DENIED, "read-only evidence handle");
    if (bytes.size > GOLEM_SHA256_MAX_BYTES) return golem_evidence_report(d, GOLEM_ERR_OVERFLOW, NULL);
    return golem_evidence_report(d, publish(store, -1, bytes, out), NULL);
}

golem_status golem_evidence_import(golem_evidence_store *store, const char *path,
    golem_receipt *out, golem_diagnostic *d)
{
    if (store == NULL || path == NULL || path[0] == '\0' || out == NULL)
        return golem_evidence_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (!store->writable) return golem_evidence_report(d, GOLEM_ERR_POLICY_DENIED, "read-only evidence handle");
    int fd = golem_evidence_path_open(path, false);
    if (fd < 0) return golem_evidence_report(d, errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO, NULL);
    golem_receipt receipt;
    golem_status status = publish(store, fd, (golem_bytes){NULL, 0}, &receipt);
    if (close(fd) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK) *out = receipt;
    return golem_evidence_report(d, status, NULL);
}

golem_status golem_evidence_receipt_verify(golem_evidence_store *store,
    const golem_digest *key, golem_receipt *out, golem_diagnostic *d)
{
    if (store == NULL || key == NULL || out == NULL)
        return golem_evidence_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    int fd = -1;
    golem_status status = golem_evidence_object_open(store, key, &fd);
    /* One extra byte detects trailing data without trusting metadata or allocating. */
    uint8_t bytes[GOLEM_RECEIPT_SIZE + 1];
    size_t length = 0;
    while (status == GOLEM_OK && length < sizeof(bytes)) {
        ssize_t amount = read(fd, bytes + length, sizeof(bytes) - length);
        if (amount < 0 && errno == EINTR) continue;
        if (amount < 0) { status = GOLEM_ERR_IO; break; }
        if (amount == 0) break;
        length += (size_t)amount;
    }
    if (fd >= 0 && close(fd) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK && length != GOLEM_RECEIPT_SIZE) status = GOLEM_ERR_PARSE;
    golem_digest actual;
    if (status == GOLEM_OK) status = golem_digest_bytes((golem_bytes){bytes, length}, &actual);
    if (status == GOLEM_OK && memcmp(actual.bytes, key->bytes, GOLEM_DIGEST_SIZE) != 0)
        status = GOLEM_ERR_DIGEST_MISMATCH;
    golem_receipt receipt;
    if (status == GOLEM_OK) status = golem_receipt_decode((golem_bytes){bytes, length}, &receipt);
    uint64_t size;
    if (status == GOLEM_OK) status = golem_evidence_verify(store, &receipt.digest, &size, NULL);
    if (status == GOLEM_OK && size != receipt.size) status = GOLEM_ERR_SIZE_MISMATCH;
    if (status == GOLEM_OK) *out = receipt;
    return golem_evidence_report(d, status, NULL);
}
