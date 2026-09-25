#define _POSIX_C_SOURCE 200809L
#include "golem/event_reader.h"
#include "admission_internal.h"
#include "../evidence/internal.h"
#include <string.h>
#include <unistd.h>

struct golem_event_reader {
    golem_allocator allocator;
    int directory;
    pid_t owner;
    bool valid;
    ge_ring ring;
    golem_admission_checkpoint checkpoint;
};

golem_status golem_event_reader_refresh(golem_event_reader *r)
{
    if (!r || r->owner != getpid())
        return GOLEM_ERR_INVALID_ARGUMENT;
    r->valid = false;
    golem_admission *a = NULL;
    golem_status st = golem_allocator_alloc(&r->allocator, sizeof(*a), (void **)&a);
    if (st != GOLEM_OK)
        return st;
    memset(a, 0, sizeof(*a));
    a->directory = r->directory;
    st = ga_load(a, r->checkpoint.records ? &r->checkpoint : NULL);
    if (st == GOLEM_OK && !a->checkpoint.records)
        st = GOLEM_ERR_NOT_FOUND;
    if (st == GOLEM_OK && r->ring.sequence &&
        (memcmp(&r->ring.stream, &a->events.stream, sizeof(r->ring.stream)) ||
         a->events.sequence < r->ring.sequence))
        st = GOLEM_ERR_REPLAY_MISMATCH;
    if (st == GOLEM_OK) {
        r->ring = a->events;
        r->checkpoint = a->checkpoint;
        r->valid = true;
    }
    (void)golem_allocator_free(&r->allocator, a);
    return st;
}
golem_status golem_event_reader_open(const char *path, const golem_allocator *allocator,
                                     golem_event_reader **out)
{
    if (!path || path[0] != '/' || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status st = golem_allocator_validate(allocator);
    if (st != GOLEM_OK)
        return st;
    golem_allocator alloc = allocator ? *allocator : golem_allocator_default();
    golem_event_reader *r = NULL;
    st = golem_allocator_alloc(&alloc, sizeof(*r), (void **)&r);
    if (st != GOLEM_OK)
        return st;
    memset(r, 0, sizeof(*r));
    r->allocator = alloc;
    r->owner = getpid();
    r->directory = golem_evidence_path_open(path, true);
    st = r->directory < 0 ? GOLEM_ERR_IO : golem_event_reader_refresh(r);
    if (st == GOLEM_OK)
        *out = r;
    else
        golem_event_reader_close(r);
    return st;
}
golem_status golem_event_reader_read(const golem_event_reader *r, const golem_runtime_cursor *after,
                                     golem_runtime_event *records, size_t capacity,
                                     golem_runtime_event_page *page)
{
    if (!r || r->owner != getpid())
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (!r->valid)
        return GOLEM_ERR_INVALID_STATE;
    return ge_read(&r->ring, after, records, capacity, page);
}
void golem_event_reader_close(golem_event_reader *r)
{
    if (!r)
        return;
    golem_allocator alloc = r->allocator;
    if (r->directory >= 0)
        (void)close(r->directory);
    (void)golem_allocator_free(&alloc, r);
}
