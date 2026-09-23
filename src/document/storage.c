#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
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
        return GOLEM_ERR_IO;
    int fd = openat(parent, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0)
        return errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO;
    if (create && (fsync(fd) < 0 || fsync(parent) < 0)) {
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
        return errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO;
    struct stat st;
    golem_status s = GOLEM_OK;
    uint8_t *data = NULL;
    size_t n = 0;
    if (fstat(fd, &st) < 0 || !S_ISREG(st.st_mode) || st.st_size < 0 ||
        (uintmax_t)st.st_size > limit)
        s = GOLEM_ERR_IO;
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
            s = GOLEM_ERR_IO;
            break;
        }
        if (got == 0)
            break;
        n += (size_t)got;
    }
    if (s == GOLEM_OK && n != (size_t)st.st_size)
        s = GOLEM_ERR_IO;
    if (close(fd) < 0 && s == GOLEM_OK)
        s = GOLEM_ERR_IO;
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
        return GOLEM_ERR_IO;
    golem_status s = GOLEM_OK;
    size_t n = 0;
    while (n < b.size) {
        ssize_t put = write(fd, b.data + n, b.size - n);
        if (put < 0 && errno == EINTR)
            continue;
        if (put <= 0) {
            s = GOLEM_ERR_IO;
            break;
        }
        n += (size_t)put;
    }
    if (s == GOLEM_OK && (fchmod(fd, 0400) < 0 || fsync(fd) < 0))
        s = GOLEM_ERR_IO;
    if (close(fd) < 0 && s == GOLEM_OK)
        s = GOLEM_ERR_IO;
    if (s == GOLEM_OK && linkat(dir, tmp, dir, name, 0) < 0) {
        if (errno != EEXIST)
            s = GOLEM_ERR_IO;
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
        s = GOLEM_ERR_IO;
    if (s == GOLEM_OK && fsync(dir) < 0)
        s = GOLEM_ERR_IO;
    return s;
}
static void frame_make(uint8_t frame[DW_FRAME], uint64_t seq, const golem_digest *prev,
                       const golem_digest *payload)
{
    memcpy(frame, "GWDOC001", 8);
    for (unsigned i = 0; i < 8; ++i)
        frame[8 + i] = (uint8_t)(seq >> (8 * i));
    memcpy(frame + 16, prev->bytes, 32);
    memcpy(frame + 48, payload->bytes, 32);
}
golem_status dw_event_write(golem_document_store *s, const golem_digest *payload,
                            golem_digest *digest)
{
    uint64_t seq = s->event_count + 1;
    uint8_t frame[DW_FRAME];
    char name[32];
    frame_make(frame, seq, &s->last, payload);
    (void)snprintf(name, sizeof(name), "%08u.evt", (unsigned)seq);
    golem_status status = golem_digest_bytes((golem_bytes){frame, sizeof(frame)}, digest);
    if (status == GOLEM_OK)
        status = dw_publish(s->events, name, (golem_bytes){frame, sizeof(frame)});
    if (status != GOLEM_OK)
        s->poisoned = true;
    return status;
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
golem_status dw_put_json(golem_document_store *s, struct json_object *o, golem_digest *out)
{
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (!text)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_receipt r;
    golem_status st =
        golem_evidence_put(s->cas, (golem_bytes){(const uint8_t *)text, strlen(text)}, &r, NULL);
    if (st == GOLEM_OK)
        *out = r.digest;
    return st;
}
golem_status dw_replay(golem_document_store *s)
{
    int scan = openat(s->events, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (scan < 0)
        return GOLEM_ERR_IO;
    DIR *dir = fdopendir(scan);
    if (!dir) {
        close(scan);
        return GOLEM_ERR_IO;
    }
    size_t count = 0;
    unsigned max = 0;
    golem_status st = GOLEM_OK;
    struct dirent *item;
    errno = 0;
    while ((item = readdir(dir)) != NULL) {
        if (strcmp(item->d_name, ".") == 0 || strcmp(item->d_name, "..") == 0 ||
            strncmp(item->d_name, ".pending-", 9) == 0)
            continue;
        unsigned seq = 0;
        char trailing, expected[32];
        if (sscanf(item->d_name, "%8u.evt%c", &seq, &trailing) != 1 || seq < 1 ||
            seq > GOLEM_DOCUMENT_MAX_REVISIONS + 129 + GOLEM_RESEARCH_MAX_EVENTS + 64 + 256) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        (void)snprintf(expected, sizeof(expected), "%08u.evt", seq);
        if (strcmp(expected, item->d_name) != 0) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        ++count;
        if (seq > max)
            max = seq;
    }
    if (errno && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    if (closedir(dir) < 0 && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && (count == 0 || count != max))
        st = GOLEM_ERR_MISSING_RECORD;
    for (unsigned seq = 1; st == GOLEM_OK && seq <= max; ++seq) {
        char name[32];
        (void)snprintf(name, sizeof(name), "%08u.evt", seq);
        uint8_t *data = NULL;
        size_t n = 0;
        st = dw_read_at(s->events, name, DW_FRAME, &data, &n);
        golem_digest payload, digest;
        uint8_t expected[DW_FRAME];
        if (st == GOLEM_OK && n != DW_FRAME)
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        if (st == GOLEM_OK) {
            memcpy(payload.bytes, data + 48, 32);
            frame_make(expected, seq, &s->last, &payload);
            if (memcmp(data, expected, DW_FRAME) != 0)
                st = GOLEM_ERR_CORRUPT_JOURNAL;
        }
        if (st == GOLEM_OK)
            st = golem_digest_bytes((golem_bytes){data, n}, &digest);
        struct json_object *event = NULL;
        if (st == GOLEM_OK)
            st = dw_cas_json(s, &payload, &event);
        if (st == GOLEM_OK)
            st = dw_apply(s, event, &payload, &digest);
        json_object_put(event);
        free(data);
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
