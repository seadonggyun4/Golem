#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "internal.h"
#include "golem/system_error.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <openssl/rand.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

golem_status dw_scratch(golem_document_store *store, size_t size, uint8_t **out)
{
    if (store == NULL || out == NULL)
        return GOLEM_ERR_INVALID_ARGUMENT;
    void *memory = NULL;
    golem_status status = golem_allocator_alloc(&store->allocator, size, &memory);
    if (status == GOLEM_OK)
        *out = memory;
    return status;
}

void dw_scratch_free(golem_document_store *store, void *memory)
{
    (void)golem_allocator_free(&store->allocator, memory);
}

golem_status dw_dir(int parent, const char *name, bool create, int *out)
{
    if (create && mkdirat(parent, name, 0700) < 0 && errno != EEXIST)
        return golem_system_error_note(GOLEM_ERR_IO, "document.directory", "mkdirat", errno);
    int fd = openat(parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0)
        return golem_system_error_note(errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO,
                                       "document.directory", "openat", errno);
    if (create && (fsync(fd) < 0 || fsync(parent) < 0)) {
        (void)golem_system_error_note(GOLEM_ERR_IO, "document.directory", "fsync", errno);
        close(fd);
        return GOLEM_ERR_IO;
    }
    *out = fd;
    return GOLEM_OK;
}
golem_status dw_read_at(int dir, const char *name, size_t limit, uint8_t **out, size_t *size)
{
    int fd = openat(dir, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0)
        return golem_system_error_note(errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO,
                                       "document.read", "openat", errno);
    struct stat st;
    golem_status s = GOLEM_OK;
    uint8_t *data = NULL;
    size_t n = 0;
    if (fstat(fd, &st) < 0)
        s = golem_system_error_note(GOLEM_ERR_IO, "document.read", "fstat", errno);
    if (s == GOLEM_OK && (!S_ISREG(st.st_mode) || st.st_size < 0 ||
        (uintmax_t)st.st_size > limit))
        s = golem_system_error_note(GOLEM_ERR_IO, "document.read", "file_shape", 0);
    if (s == GOLEM_OK) {
        data = malloc((size_t)st.st_size + 1);
        if (!data)
            s = GOLEM_ERR_OUT_OF_MEMORY;
    }
    while (s == GOLEM_OK && n <= (size_t)st.st_size) {
        ssize_t got = read(fd, data + n, (size_t)st.st_size + 1 - n);
        if (got < 0 && errno == EINTR)
            continue;
        if (got < 0) {
            s = golem_system_error_note(GOLEM_ERR_IO, "document.read", "read", errno);
            break;
        }
        if (got == 0)
            break;
        n += (size_t)got;
    }
    if (s == GOLEM_OK && n != (size_t)st.st_size)
        s = golem_system_error_note(GOLEM_ERR_IO, "document.read", "file_size_changed", 0);
    if (close(fd) < 0 && s == GOLEM_OK)
        s = golem_system_error_note(GOLEM_ERR_IO, "document.read", "close", errno);
    if (s == GOLEM_OK) {
        *out = data;
        *size = n;
    } else
        free(data);
    return s;
}
/* Publish complete immutable bytes with a no-replace link. Random pending names
 * survive interrupted writers without blocking subsequent attempts. */
golem_status dw_publish(int dir, const char *name, golem_bytes b)
{
    unsigned char rand[12];
    char tmp[34];
    if (RAND_bytes(rand, sizeof(rand)) != 1)
        return GOLEM_ERR_CRYPTO;
    memcpy(tmp, ".pending-", 9);
    for (size_t i = 0; i < sizeof(rand); ++i)
        (void)snprintf(tmp + 9 + i * 2, 3, "%02x", rand[i]);
    int fd = openat(dir, tmp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0)
        return golem_system_error_note(GOLEM_ERR_IO, "document.publish", "openat", errno);
    golem_status s = GOLEM_OK;
    size_t n = 0;
    while (n < b.size) {
        ssize_t put = write(fd, b.data + n, b.size - n);
        if (put < 0 && errno == EINTR)
            continue;
        if (put <= 0) {
            s = golem_system_error_note(GOLEM_ERR_IO, "document.publish", put < 0 ? "write" : "write_no_progress", put < 0 ? errno : 0);
            break;
        }
        n += (size_t)put;
    }
    if (s == GOLEM_OK && fchmod(fd, 0400) < 0)
        s = golem_system_error_note(GOLEM_ERR_IO, "document.publish", "fchmod", errno);
    if (s == GOLEM_OK && fsync(fd) < 0)
        s = golem_system_error_note(GOLEM_ERR_IO, "document.publish", "fsync_file", errno);
    if (close(fd) < 0 && s == GOLEM_OK)
        s = golem_system_error_note(GOLEM_ERR_IO, "document.publish", "close", errno);
    if (s == GOLEM_OK && linkat(dir, tmp, dir, name, 0) < 0) {
        if (errno != EEXIST)
            s = golem_system_error_note(GOLEM_ERR_IO, "document.publish", "linkat", errno);
        else {
            uint8_t *old = NULL;
            size_t size = 0;
            s = dw_read_at(dir, name, b.size, &old, &size);
            if (s == GOLEM_OK && (size != b.size || memcmp(old, b.data, b.size) != 0))
                s = GOLEM_ERR_DIGEST_MISMATCH;
            free(old);
        }
    }
    if (unlinkat(dir, tmp, 0) < 0 && s == GOLEM_OK)
        s = golem_system_error_note(GOLEM_ERR_IO, "document.publish", "unlinkat", errno);
    if (s == GOLEM_OK && fsync(dir) < 0)
        s = golem_system_error_note(GOLEM_ERR_IO, "document.publish", "fsync_directory", errno);
    return s;
}
golem_status dw_cas_json(golem_document_store *s, const golem_digest *key, struct json_object **out)
{
    uint8_t *data = NULL;
    size_t n = 0;
    golem_status st =
        golem_evidence_read(s->cas, key, GOLEM_DOCUMENT_MAX_JSON, &s->allocator, &data, &n, NULL);
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){data, n}, GOLEM_DOCUMENT_MAX_JSON, out);
    dw_scratch_free(s, data);
    return st;
}
golem_status dw_put_json_bounded(golem_document_store *s, struct json_object *o,
                                size_t limit, golem_digest *out)
{
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (!text)
        return GOLEM_ERR_OUT_OF_MEMORY;
    size_t size = strlen(text);
    if (size > limit)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    golem_receipt r;
    golem_status st =
        golem_evidence_put(s->cas, (golem_bytes){(const uint8_t *)text, size}, &r, NULL);
    if (st == GOLEM_OK)
        *out = r.digest;
    return st;
}
golem_status dw_put_json(golem_document_store *s, struct json_object *o, golem_digest *out)
{
    return dw_put_json_bounded(s, o, SIZE_MAX, out);
}
golem_status dw_replay(golem_document_store *s)
{
    unsigned max = 0;
    golem_status st = dw_record_scan(s->events,
        GOLEM_DOCUMENT_MAX_REVISIONS + 129 + GOLEM_RESEARCH_MAX_EVENTS + 64 + 256,
        true, &max);
    for (unsigned seq = 1; st == GOLEM_OK && seq <= max; ++seq) {
        golem_digest payload, digest;
        struct json_object *event = NULL;
        st = dw_record_read(s, s->events, false, seq, &s->last, &payload, &digest, &event);
        if (st == GOLEM_OK)
            st = dw_apply(s, event, &payload, &digest);
        json_object_put(event);
    }
    return st;
}
golem_status dw_project(golem_document_store *s, dw_entry *e, bool create)
{
    uint8_t *body = NULL;
    size_t n = 0;
    int docs = -1, doc = -1;
    golem_status st = golem_evidence_read(s->cas, &e->result.body_digest, GOLEM_DOCUMENT_MAX_BODY,
                                          NULL, &body, &n, NULL);
    if (st == GOLEM_OK)
        st = dw_dir(s->root, "documents", create, &docs);
    if (st == GOLEM_OK)
        st = dw_dir(docs, dw_text(e->meta, "document_id"), create, &doc);
    char name[32];
    (void)snprintf(name, sizeof(name), "r%04u.md", e->result.revision);
    if (st == GOLEM_OK && create)
        st = dw_publish(doc, name, (golem_bytes){body, n});
    else if (st == GOLEM_OK) {
        uint8_t *current = NULL;
        size_t size = 0;
        st = dw_read_at(doc, name, GOLEM_DOCUMENT_MAX_BODY, &current, &size);
        if (st == GOLEM_OK && (size != n || memcmp(current, body, n) != 0))
            st = GOLEM_ERR_DIGEST_MISMATCH;
        free(current);
    }
    if (doc >= 0)
        close(doc);
    if (docs >= 0)
        close(docs);
    free(body);
    return st;
}
