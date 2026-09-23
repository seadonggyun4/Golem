#ifndef GOLEM_EVENTS_INTERNAL_H
#define GOLEM_EVENTS_INTERNAL_H
#include "golem/runtime_event.h"
typedef struct ge_ring {
    golem_digest stream;
    uint64_t sequence;
    golem_runtime_event records[GOLEM_RUNTIME_EVENT_CAPACITY];
} ge_ring;
/* Internal producers only. No allocation, callbacks or file writes. */
void ge_append(ge_ring *ring, golem_runtime_event event);
bool ge_initialize(ge_ring *ring);
golem_status ge_read(const ge_ring *ring, const golem_runtime_cursor *after,
                     golem_runtime_event *records, size_t capacity, golem_runtime_event_page *page);
#endif
