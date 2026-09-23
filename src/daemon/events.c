#include "events_internal.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <openssl/rand.h>

bool ge_initialize(ge_ring *r)
{
    memset(r, 0, sizeof(*r));
    return RAND_bytes(r->stream.bytes, sizeof(r->stream.bytes)) == 1;
}

const char *golem_runtime_event_name(golem_runtime_event_kind kind)
{
    static const char *const names[] = {NULL,
                                        "initialized",
                                        "recovery",
                                        "queued",
                                        "admitted",
                                        "bound",
                                        "start_committed",
                                        "settlement_recorded",
                                        "cancel_requested",
                                        "released",
                                        "limits_changed",
                                        "preparing",
                                        "dispatched",
                                        "finished",
                                        "reconcile",
                                        "preparation_failed",
                                        "capacity_blocked",
                                        "acknowledged",
                                        "running_committed"};
    return kind > 0 && (size_t)kind < sizeof(names) / sizeof(names[0]) ? names[kind] : NULL;
}
void ge_append(ge_ring *r, golem_runtime_event event)
{
    /* Saturation cannot affect execution. No sequence wrapping / cursor reuse. */
    if (r->sequence == UINT64_MAX)
        return;
    event.version = GOLEM_RUNTIME_EVENT_VERSION;
    event.cursor.stream = r->stream;
    event.cursor.sequence = ++r->sequence;
    r->records[(r->sequence - 1) % GOLEM_RUNTIME_EVENT_CAPACITY] = event;
}
golem_status ge_read(const ge_ring *r, const golem_runtime_cursor *after,
                     golem_runtime_event *records, size_t capacity, golem_runtime_event_page *page)
{
    if (!r || !records || !capacity || capacity > GOLEM_RUNTIME_EVENT_PAGE_MAX || !page)
        return GOLEM_ERR_INVALID_ARGUMENT;
    uint64_t oldest = r->sequence > GOLEM_RUNTIME_EVENT_CAPACITY
                          ? r->sequence - GOLEM_RUNTIME_EVENT_CAPACITY + 1
                          : 1;
    golem_runtime_event_page p = {.oldest = r->sequence ? oldest : 0,
                                  .newest = r->sequence,
                                  .dropped = oldest - 1,
                                  .next = {.stream = r->stream}};
    uint64_t start = oldest;
    if (after) {
        if (memcmp(&after->stream, &r->stream, sizeof(r->stream)) || !after->sequence ||
            after->sequence > r->sequence)
            return GOLEM_ERR_INVALID_ARGUMENT;
        if (after->sequence < oldest) {
            p.missed = oldest - after->sequence - 1;
            *page = p;
            return GOLEM_ERR_STALE_RESULT;
        }
        const golem_runtime_event *e =
            &r->records[(after->sequence - 1) % GOLEM_RUNTIME_EVENT_CAPACITY];
        if (memcmp(&e->cursor.anchor, &after->anchor, sizeof(after->anchor)))
            return GOLEM_ERR_REPLAY_MISMATCH;
        p.next = *after;
        if (after->sequence == r->sequence) {
            *page = p;
            return GOLEM_OK;
        }
        start = after->sequence + 1;
    }
    for (uint64_t i = start; i <= r->sequence && p.count < capacity; ++i) {
        records[p.count++] = r->records[(i - 1) % GOLEM_RUNTIME_EVENT_CAPACITY];
        p.next = records[p.count - 1].cursor;
        if (i == UINT64_MAX)
            break;
    }
    *page = p;
    return GOLEM_OK;
}
golem_status golem_runtime_cursor_format(const golem_runtime_cursor *c, char *buffer,
                                         size_t capacity, size_t *required)
{
    if (!c || !c->sequence || !required || (!buffer && capacity))
        return GOLEM_ERR_INVALID_ARGUMENT;
    char stream[65], anchor[65], encoded[GOLEM_RUNTIME_CURSOR_MAX];
    size_t n;
    golem_status st = golem_digest_format(&c->stream, stream, sizeof(stream), &n);
    if (st == GOLEM_OK)
        st = golem_digest_format(&c->anchor, anchor, sizeof(anchor), &n);
    if (st != GOLEM_OK)
        return st;
    int len =
        snprintf(encoded, sizeof(encoded), "1:%s:%" PRIu64 ":%s", stream, c->sequence, anchor);
    if (len < 0 || (size_t)len >= sizeof(encoded))
        return GOLEM_ERR_OVERFLOW;
    *required = (size_t)len;
    if (capacity <= (size_t)len)
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    memcpy(buffer, encoded, (size_t)len + 1);
    return GOLEM_OK;
}
golem_status golem_runtime_cursor_parse(golem_string_view text, golem_runtime_cursor *out)
{
    if (!out || !text.data || text.size < 133 || text.size >= GOLEM_RUNTIME_CURSOR_MAX)
        return GOLEM_ERR_INVALID_ARGUMENT;
    const char *p = text.data;
    if (p[0] != '1' || p[1] != ':' || p[66] != ':' || p[67] == '0')
        return GOLEM_ERR_PARSE;
    golem_runtime_cursor c = {0};
    golem_status st = golem_digest_parse((golem_string_view){p + 2, 64}, &c.stream);
    size_t i = 67;
    for (; i < text.size && p[i] != ':'; ++i) {
        if (p[i] < '0' || p[i] > '9' || c.sequence > (UINT64_MAX - (uint64_t)(p[i] - '0')) / 10)
            return GOLEM_ERR_PARSE;
        c.sequence = c.sequence * 10 + (uint64_t)(p[i] - '0');
    }
    if (!c.sequence || i + 65 != text.size)
        return GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = golem_digest_parse((golem_string_view){p + i + 1, 64}, &c.anchor);
    if (st == GOLEM_OK)
        *out = c;
    return st;
}
