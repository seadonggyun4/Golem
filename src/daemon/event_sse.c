#include "golem/event_reader.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

golem_status golem_runtime_event_sse(const golem_runtime_event *e, void *buffer, size_t capacity,
                                     size_t *required)
{
    if (!e || !required || (!buffer && capacity) || e->version != GOLEM_RUNTIME_EVENT_VERSION ||
        (e->origin != GOLEM_EVENT_ADMISSION_JOURNAL && e->origin != GOLEM_EVENT_WORKER_OBSERVATION))
        return GOLEM_ERR_INVALID_ARGUMENT;
    const char *name = golem_runtime_event_name(e->kind);
    if (!name)
        return GOLEM_ERR_INVALID_ARGUMENT;
    char cursor[GOLEM_RUNTIME_CURSOR_MAX], frame[1024];
    size_t size;
    golem_status st = golem_runtime_cursor_format(&e->cursor, cursor, sizeof(cursor), &size);
    if (st != GOLEM_OK)
        return st;
    int n = snprintf(frame, sizeof(frame),
                     "id: %s\nevent: %s\ndata: {\"version\":1,\"origin\":%u,\"subject\":\"%" PRIu64
                     "\",\"epoch\":\"%" PRIu64 "\",\"status_known\":%s,\"status\":%d,"
                     "\"elapsed_known\":%s,\"elapsed_ns\":\"%" PRIu64 "\"}\n\n",
                     cursor, name, (unsigned)e->origin, e->subject, e->epoch,
                     e->status_known ? "true" : "false", e->status_known ? (int)e->status : 0,
                     e->elapsed_known ? "true" : "false", e->elapsed_known ? e->elapsed_ns : 0);
    if (n < 0 || (size_t)n >= sizeof(frame))
        return GOLEM_ERR_OVERFLOW;
    *required = (size_t)n;
    if (capacity < (size_t)n)
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    memcpy(buffer, frame, (size_t)n);
    return GOLEM_OK;
}
