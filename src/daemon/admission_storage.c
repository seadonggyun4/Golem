#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE 1
#endif
#include "admission_internal.h"
#include "internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void put64(uint8_t *p, uint64_t n)
{
    for (unsigned i = 0; i < 8; ++i)
        p[i] = (uint8_t)(n >> (8 * i));
}
static uint64_t get64(const uint8_t *p)
{
    uint64_t n = 0;
    for (unsigned i = 0; i < 8; ++i)
        n |= (uint64_t)p[i] << (8 * i);
    return n;
}

golem_status ga_encode(const ga_event *e, golem_admission_checkpoint previous,
                       uint8_t frame[GA_FRAME_SIZE])
{
    if (previous.records == UINT64_MAX)
        return GOLEM_ERR_OVERFLOW;
    memset(frame, 0, GA_FRAME_SIZE);
    memcpy(frame, "GADM0001", 8);
    put64(frame + 8, previous.records + 1);
    memcpy(frame + 16, previous.head.bytes, 32);
    put64(frame + 48, (uint64_t)e->operation);
    put64(frame + 56, e->ticket);
    put64(frame + 64, e->request.cpu_millis);
    put64(frame + 72, e->request.memory_bytes);
    put64(frame + 80, e->request.foreground ? 1 : 0);
    put64(frame + 88, e->request.parent);
    memcpy(frame + 96, e->request.operation, 64);
    memcpy(frame + 160, e->request.work, 96);
    memcpy(frame + 256, e->request.session, 96);
    memcpy(frame + 352, e->request.runtime_binding.bytes, 32);
    memcpy(frame + 384, e->proof.bytes, 32);
    memcpy(frame + 416, e->nonce, 16);
    put64(frame + 432, e->epoch);
    memcpy(frame + 440, e->boot.bytes, 32);
    golem_digest digest;
    golem_status s = golem_digest_bytes((golem_bytes){frame, 480}, &digest);
    if (s == GOLEM_OK)
        memcpy(frame + 480, digest.bytes, 32);
    return s;
}

golem_status ga_decode(const uint8_t frame[GA_FRAME_SIZE], golem_admission_checkpoint previous,
                       ga_event *out)
{
    if (memcmp(frame, "GADM0001", 8))
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (previous.records == UINT64_MAX || get64(frame + 8) != previous.records + 1)
        return GOLEM_ERR_MISSING_RECORD;
    if (memcmp(frame + 16, previous.head.bytes, 32))
        return GOLEM_ERR_DIGEST_MISMATCH;
    if (get64(frame + 48) < GA_INIT || get64(frame + 48) > GA_RESIZE || get64(frame + 80) > 1 ||
        ga_nonzero(frame + 472, 8))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    golem_digest digest;
    golem_status s = golem_digest_bytes((golem_bytes){frame, 480}, &digest);
    if (s != GOLEM_OK)
        return s;
    if (memcmp(digest.bytes, frame + 480, 32))
        return GOLEM_ERR_DIGEST_MISMATCH;
    ga_event e = {0};
    e.operation = (ga_operation)get64(frame + 48);
    e.ticket = get64(frame + 56);
    e.request.cpu_millis = get64(frame + 64);
    e.request.memory_bytes = get64(frame + 72);
    e.request.foreground = get64(frame + 80) != 0;
    e.request.parent = get64(frame + 88);
    memcpy(e.request.operation, frame + 96, 64);
    memcpy(e.request.work, frame + 160, 96);
    memcpy(e.request.session, frame + 256, 96);
    if (!memchr(e.request.operation, 0, 64) || !memchr(e.request.work, 0, 96) ||
        !memchr(e.request.session, 0, 96))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    memcpy(e.request.runtime_binding.bytes, frame + 352, 32);
    memcpy(e.proof.bytes, frame + 384, 32);
    memcpy(e.nonce, frame + 416, 16);
    e.epoch = get64(frame + 432);
    memcpy(e.boot.bytes, frame + 440, 32);
    /* Reject ignored fields and string suffix bytes: one wire form per event. */
    ga_event canonical = e;
    memset(canonical.request.operation + strlen(e.request.operation), 0,
           64 - strlen(e.request.operation));
    memset(canonical.request.work + strlen(e.request.work), 0, 96 - strlen(e.request.work));
    memset(canonical.request.session + strlen(e.request.session), 0,
           96 - strlen(e.request.session));
    if (e.operation != GA_ENQUEUE) {
        memset(canonical.request.operation, 0, 64);
        memset(canonical.request.work, 0, 96);
        memset(canonical.request.session, 0, 96);
        canonical.request.parent = 0;
        canonical.request.foreground = false;
    }
    if (e.operation != GA_INIT && e.operation != GA_RESIZE && e.operation != GA_ENQUEUE) {
        canonical.request.cpu_millis = 0;
        canonical.request.memory_bytes = 0;
    }
    if (e.operation != GA_INIT && e.operation != GA_ENQUEUE)
        canonical.request.runtime_binding = (golem_digest){0};
    if (e.operation != GA_BIND && e.operation != GA_SETTLE)
        canonical.proof = (golem_digest){0};
    if (e.operation == GA_INIT || e.operation == GA_RESIZE || e.operation == GA_ENQUEUE) {
        memset(canonical.nonce, 0, 16);
        canonical.boot = (golem_digest){0};
    }
    if (e.operation == GA_ENQUEUE)
        canonical.epoch = 0;
    if (e.operation == GA_BOOT)
        canonical.ticket = 0;
    uint8_t encoded[GA_FRAME_SIZE];
    s = ga_encode(&canonical, previous, encoded);
    if (s != GOLEM_OK)
        return s;
    if (memcmp(frame, encoded, GA_FRAME_SIZE))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    *out = e;
    return GOLEM_OK;
}

static golem_status event_count(int root, uint64_t *out)
{
    int scan = openat(root, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (scan < 0)
        return GOLEM_ERR_IO;
    DIR *dir = fdopendir(scan);
    if (!dir) {
        (void)close(scan);
        return GOLEM_ERR_IO;
    }
    uint64_t count = 0, maximum = 0;
    golem_status s = GOLEM_OK;
    struct dirent *entry;
    errno = 0;
    while ((entry = readdir(dir))) {
        if (entry->d_name[0] == '.')
            continue; /* Owner lock / unpublished temporary objects. */
        if (strlen(entry->d_name) != 20) {
            s = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        uint64_t n = 0;
        for (size_t i = 0; i < 20; ++i) {
            unsigned char c = (unsigned char)entry->d_name[i];
            if (c < '0' || c > '9' || n > (UINT64_MAX - (uint64_t)(c - '0')) / 10) {
                s = GOLEM_ERR_CORRUPT_JOURNAL;
                break;
            }
            n = n * 10 + (uint64_t)(c - '0');
        }
        if (s != GOLEM_OK)
            break;
        if (!n || n > GOLEM_ADMISSION_MAX_EVENTS || ++count > GOLEM_ADMISSION_MAX_EVENTS) {
            s = GOLEM_ERR_OVERFLOW;
            break;
        }
        if (n > maximum)
            maximum = n;
    }
    if (s == GOLEM_OK && errno)
        s = GOLEM_ERR_IO;
    if (closedir(dir) != 0 && s == GOLEM_OK)
        s = GOLEM_ERR_IO;
    if (s == GOLEM_OK && count != maximum)
        s = GOLEM_ERR_MISSING_RECORD;
    if (s == GOLEM_OK)
        *out = count;
    return s;
}

static golem_status read_event(int root, uint64_t sequence, uint8_t frame[GA_FRAME_SIZE])
{
    char name[21];
    (void)snprintf(name, sizeof(name), "%020" PRIu64, sequence);
    int fd = openat(root, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0)
        return GOLEM_ERR_IO;
    struct stat st;
    golem_status s = GOLEM_OK;
    if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode) || st.st_size != GA_FRAME_SIZE)
        s = GOLEM_ERR_CORRUPT_JOURNAL;
    size_t offset = 0;
    while (s == GOLEM_OK && offset < GA_FRAME_SIZE) {
        ssize_t n = read(fd, frame + offset, GA_FRAME_SIZE - offset);
        if (n > 0)
            offset += (size_t)n;
        else if (n < 0 && errno == EINTR)
            continue;
        else
            s = GOLEM_ERR_IO;
    }
    if (close(fd) != 0 && s == GOLEM_OK)
        s = GOLEM_ERR_IO;
    return s;
}

golem_status ga_load(golem_admission *a, const golem_admission_checkpoint *expected)
{
    uint64_t count;
    golem_status s = event_count(a->directory, &count);
    if (s != GOLEM_OK)
        return s;
    if (expected &&
        (expected->records > count || (!expected->records && ga_nonzero(&expected->head, 32))))
        return GOLEM_ERR_REPLAY_MISMATCH;
    for (uint64_t i = 1; i <= count; ++i) {
        uint8_t frame[GA_FRAME_SIZE];
        ga_event event;
        s = read_event(a->directory, i, frame);
        if (s == GOLEM_OK)
            s = ga_decode(frame, a->checkpoint, &event);
        if (s == GOLEM_OK)
            s = ga_apply(&a->model, &event);
        if (s != GOLEM_OK)
            return s;
        a->checkpoint.records = i;
        memcpy(a->checkpoint.head.bytes, frame + 480, 32);
        if (expected && i == expected->records && memcmp(&a->checkpoint.head, &expected->head, 32))
            return GOLEM_ERR_REPLAY_MISMATCH;
        ga_observe(a, &event);
    }
    return GOLEM_OK;
}

golem_status ga_commit(golem_admission *a, const ga_event *event)
{
    if (a->poisoned)
        return GOLEM_ERR_INVALID_STATE;
    if (a->checkpoint.records == GOLEM_ADMISSION_MAX_EVENTS)
        return GOLEM_ERR_OVERFLOW;
    a->scratch = a->model;
    golem_status s = ga_apply(&a->scratch, event);
    if (s != GOLEM_OK)
        return s;
    uint8_t frame[GA_FRAME_SIZE];
    s = ga_encode(event, a->checkpoint, frame);
    if (s != GOLEM_OK)
        return s;
    char name[21];
    (void)snprintf(name, sizeof(name), "%020" PRIu64, a->checkpoint.records + 1);
    s = gd_write(a->directory, name, (golem_bytes){frame, sizeof(frame)});
    if (s != GOLEM_OK) {
        a->poisoned = true;
        return s;
    }
    a->model = a->scratch;
    ++a->checkpoint.records;
    memcpy(a->checkpoint.head.bytes, frame + 480, 32);
    ga_observe(a, event);
    return GOLEM_OK;
}
