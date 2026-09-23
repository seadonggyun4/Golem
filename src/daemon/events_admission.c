#define _POSIX_C_SOURCE 200809L
#include "admission_internal.h"
#include "internal.h"
#include "../evidence/internal.h"
#include <string.h>
#include <unistd.h>

void ga_observe(golem_admission *a, const ga_event *event)
{
    static const golem_runtime_event_kind kinds[] = {0,
                                                     GOLEM_EVENT_INITIALIZED,
                                                     GOLEM_EVENT_RECOVERY,
                                                     GOLEM_EVENT_QUEUED,
                                                     GOLEM_EVENT_ADMITTED,
                                                     GOLEM_EVENT_BOUND,
                                                     GOLEM_EVENT_START_COMMITTED,
                                                     GOLEM_EVENT_RUNNING_COMMITTED,
                                                     GOLEM_EVENT_CANCEL_REQUESTED,
                                                     GOLEM_EVENT_SETTLED,
                                                     GOLEM_EVENT_RELEASED,
                                                     GOLEM_EVENT_LIMITS_CHANGED};
    if (event->operation == GA_INIT)
        a->events.stream = a->checkpoint.head;
    golem_runtime_event e = {.kind = kinds[event->operation],
                             .origin = GOLEM_EVENT_ADMISSION_JOURNAL,
                             .epoch = a->model.epoch,
                             .cursor = {.anchor = a->checkpoint.head}};
    if (event->operation != GA_INIT && event->operation != GA_BOOT && event->operation != GA_RESIZE)
        e.subject = event->ticket;
    ge_append(&a->events, e);
}
golem_status golem_admission_events(golem_admission *a, const golem_runtime_cursor *after,
                                    golem_runtime_event *records, size_t capacity,
                                    golem_runtime_event_page *page)
{
    if (!a)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (a->owner != getpid() || a->busy || a->poisoned)
        return GOLEM_ERR_INVALID_STATE;
    return ge_read(&a->events, after, records, capacity, page);
}
golem_status golem_runtime_events_snapshot(const char *directory, const golem_allocator *allocator,
                                           const golem_runtime_cursor *after,
                                           golem_runtime_event *records, size_t capacity,
                                           golem_runtime_event_page *page)
{
    if (!directory || directory[0] != '/' || !records || !capacity ||
        capacity > GOLEM_RUNTIME_EVENT_PAGE_MAX || !page)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status st = golem_allocator_validate(allocator);
    if (st != GOLEM_OK)
        return st;
    golem_allocator alloc = allocator ? *allocator : golem_allocator_default();
    golem_admission *a = NULL;
    st = golem_allocator_alloc(&alloc, sizeof(*a), (void **)&a);
    if (st != GOLEM_OK)
        return st;
    memset(a, 0, sizeof(*a));
    a->directory = golem_evidence_path_open(directory, true);
    if (a->directory < 0)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK)
        st = ga_load(a, NULL);
    if (st == GOLEM_OK && !a->checkpoint.records)
        st = GOLEM_ERR_NOT_FOUND;
    /* Close before publishing outputs, including a stale-cursor gap report. */
    if (a->directory >= 0 && close(a->directory) && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK)
        st = ge_read(&a->events, after, records, capacity, page);
    (void)golem_allocator_free(&alloc, a);
    return st;
}
