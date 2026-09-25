#ifndef GOLEM_EVENT_READER_H
#define GOLEM_EVENT_READER_H
#include "golem/runtime_event.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct golem_event_reader golem_event_reader;
/* Read-only admission journal view. Pins a directory fd, never acquires a lease,
 * creates a lock, writes records or dispatches work. One caller at a time.
 * allocator is copied; directory borrowed during open. Output unchanged on error.
 * Refresh verifies a full bounded journal prefix once for all subscribers. Reads
 * thereafter are memory-only. Failed refresh poisons the view until a successful
 * refresh; it must not silently serve stale data as current. Close frees ownership.
 * Journal stream replacement/truncation is rejected. No transient worker events
 * are reconstructed. Same-UID modification and failed-writer fsync remain outside
 * the durability guarantee of this observer. */
golem_status golem_event_reader_open(const char *directory, const golem_allocator *allocator,
                                     golem_event_reader **out);
golem_status golem_event_reader_refresh(golem_event_reader *reader);
golem_status golem_event_reader_read(const golem_event_reader *reader,
                                     const golem_runtime_cursor *after,
                                     golem_runtime_event *records, size_t capacity,
                                     golem_runtime_event_page *page);
void golem_event_reader_close(golem_event_reader *reader);
/* Fixed allowlist UTF-8/ASCII SSE frame, including id/event/data and blank line.
 * No caller strings, paths, tokens or logs. No NUL in output; required excludes
 * NUL. NULL/0 sizing; short/error output unchanged. Input is not authenticated
 * merely by serialization. Client advances cursor only after a complete frame.
 * Transport reconnect may duplicate frames: deduplicate by complete cursor. */
golem_status golem_runtime_event_sse(const golem_runtime_event *event, void *buffer,
                                     size_t capacity, size_t *required);
#ifdef __cplusplus
}
#endif
#endif
