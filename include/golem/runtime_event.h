#ifndef GOLEM_RUNTIME_EVENT_H
#define GOLEM_RUNTIME_EVENT_H
#include "golem/evidence.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_RUNTIME_EVENT_VERSION 1u
#define GOLEM_RUNTIME_EVENT_CAPACITY 256u
#define GOLEM_RUNTIME_EVENT_PAGE_MAX 64u
#define GOLEM_RUNTIME_CURSOR_MAX 154u
typedef struct golem_worker_pool golem_worker_pool;
typedef struct golem_admission golem_admission;
/* Stable IDs; never reuse a retired value. Admission kinds reflect committed
 * journal operations, not necessarily successful work execution. */
typedef enum golem_runtime_event_kind {
    GOLEM_EVENT_INITIALIZED = 1,
    GOLEM_EVENT_RECOVERY = 2,
    GOLEM_EVENT_QUEUED = 3,
    GOLEM_EVENT_ADMITTED = 4,
    GOLEM_EVENT_BOUND = 5,
    GOLEM_EVENT_START_COMMITTED = 6,
    GOLEM_EVENT_SETTLED = 7,
    GOLEM_EVENT_CANCEL_REQUESTED = 8,
    GOLEM_EVENT_RELEASED = 9,
    GOLEM_EVENT_LIMITS_CHANGED = 10,
    GOLEM_EVENT_PREPARING = 11,
    GOLEM_EVENT_DISPATCHED = 12,
    GOLEM_EVENT_FINISHED = 13,
    GOLEM_EVENT_RECONCILE = 14,
    GOLEM_EVENT_PREPARATION_FAILED = 15,
    GOLEM_EVENT_CAPACITY_BLOCKED = 16,
    GOLEM_EVENT_ACKNOWLEDGED = 17,
    GOLEM_EVENT_RUNNING_COMMITTED = 18
} golem_runtime_event_kind;
typedef enum golem_runtime_event_origin {
    GOLEM_EVENT_ADMISSION_JOURNAL = 1,
    GOLEM_EVENT_WORKER_OBSERVATION = 2
} golem_runtime_event_origin;
typedef struct golem_runtime_cursor {
    golem_digest stream;
    uint64_t sequence;
    golem_digest anchor;
} golem_runtime_cursor;
typedef struct golem_runtime_event {
    uint32_t version;
    golem_runtime_event_kind kind;
    golem_runtime_event_origin origin;
    golem_runtime_cursor cursor;
    uint64_t subject, epoch;
    bool status_known, elapsed_known;
    golem_status status;
    /* Nanoseconds since this local worker pool opened, sampled by coordinator.
     * Not Unix time, child execution duration, or comparable across streams.
     * Admission records have no timestamp: elapsed_known=false. */
    uint64_t elapsed_ns;
} golem_runtime_event;
typedef struct golem_runtime_event_page {
    golem_runtime_cursor next;
    uint64_t oldest, newest, dropped, missed;
    size_t count;
} golem_runtime_event_page;
/* Read-only, copied records. No subscription registry, callbacks, I/O or reader
 * allocation in the live ring. Writer never waits for a reader. Calls must obey
 * the containing admission/worker object's serialization and process ownership.
 * Output capacity 1..64. after=NULL explicitly starts at oldest retained record.
 * Each observer keeps its own cursor. On overwritten cursor: STALE_RESULT,
 * page has bounds/missed count and count=0; records unchanged. Re-read with NULL
 * only after acknowledging the gap. On all other errors outputs unchanged.
 * Forged/future/cross-stream cursors are rejected. Cursors are not capabilities.
 * A worker read may harvest completed observations but never reaps/releases work.
 * This transient ring is neither an audit log nor completion evidence. If random
 * stream identity is unavailable at pool creation, diagnostics return CRYPTO but
 * execution remains available. Missing clock data is explicit, never fabricated.
 * Sequence exhaustion freezes diagnostics rather than wrapping/reusing IDs. */
golem_status golem_worker_events(golem_worker_pool *pool, const golem_runtime_cursor *after,
                                 golem_runtime_event *records, size_t capacity,
                                 golem_runtime_event_page *page);
golem_status golem_admission_events(golem_admission *admission, const golem_runtime_cursor *after,
                                    golem_runtime_event *records, size_t capacity,
                                    golem_runtime_event_page *page);
/* Opens an existing absolute private admission directory read-only, verifies its
 * complete journal prefix, returns a bounded page. No lock creation, boot event,
 * lease acquisition or mutation. Concurrent appends belong to a later snapshot.
 * Full replay is O(journal length); use the live API for frequent polling.
 * Journal identity/cursors survive restart; bounded ring history does not grow.
 * All parameters borrowed; caller owns outputs. allocator is optional and copied.
 * A poisoned/uncertain writer must be reconciled separately; a readable record
 * does not prove that an earlier failed fsync became durable. */
golem_status golem_runtime_events_snapshot(const char *directory, const golem_allocator *allocator,
                                           const golem_runtime_cursor *after,
                                           golem_runtime_event *records, size_t capacity,
                                           golem_runtime_event_page *page);
/* Canonical versioned cursor text; encoded length excludes NUL, capacity includes
 * it. NULL/0 sizing supported. Short buffers and parse outputs unchanged. */
golem_status golem_runtime_cursor_format(const golem_runtime_cursor *cursor, char *buffer,
                                         size_t capacity, size_t *required);
golem_status golem_runtime_cursor_parse(golem_string_view text, golem_runtime_cursor *cursor);
/* Borrowed static enum name, NULL for unknown IDs. */
const char *golem_runtime_event_name(golem_runtime_event_kind kind);
typedef enum golem_runtime_event_format {
    GOLEM_RUNTIME_EVENTS_JSONL = 1,
    GOLEM_RUNTIME_EVENTS_OTLP = 2,
    GOLEM_RUNTIME_EVENTS_PROV = 3
} golem_runtime_event_format;
/* Derived, fixed-allowlist export implemented in the research/observability
 * layer. No network/CAS/journal writes. Numeric IDs, hashes and timing remain
 * linkable private information: review before disclosure. No source text, paths,
 * argv, environment, stdout, stderr, credentials, actor names or trace IDs.
 * Input is a page from the read API, not authenticated merely by serialization.
 * JSONL starts with a page metadata line. OTLP has no invented Unix timestamps;
 * PROV expresses derivation only. Both are partial-page diagnostic exports,
 * not Phase29E case bundles or execution/QA/completion evidence.
 * Inputs borrowed, json-c owns temporaries; caller owns output. NULL/0 sizing,
 * short buffer unchanged, required excludes NUL (no NUL written).
 * page.count <=64; no input/output alias. */
golem_status golem_runtime_events_export(const golem_runtime_event *records,
                                         const golem_runtime_event_page *page,
                                         golem_runtime_event_format format, void *buffer,
                                         size_t capacity, size_t *required);
#ifdef __cplusplus
}
#endif
#endif
