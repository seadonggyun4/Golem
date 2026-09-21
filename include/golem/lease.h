#ifndef GOLEM_LEASE_H
#define GOLEM_LEASE_H
#include "golem/allocator.h"
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_LEASE_VERSION 1u
#define GOLEM_LEASE_TEXT_CAPACITY 96u
typedef struct golem_lease golem_lease;
typedef struct golem_lease_token {
    uint32_t version;
    uint8_t authority[16]; /* Random incarnation, never a pointer or signature. */
    uint64_t fence; /* Monotonic within this authority; never wraps. */
} golem_lease_token;
typedef struct golem_lease_snapshot {
    golem_lease_token token;
    char resource[GOLEM_LEASE_TEXT_CAPACITY];
    char owner[GOLEM_LEASE_TEXT_CAPACITY];
    uint64_t expires_ns;
    bool active; /* Acquired and not released; validate determines expiry. */
} golem_lease_snapshot;
typedef enum golem_lease_event_type {
    GOLEM_LEASE_ACQUIRED = 1, GOLEM_LEASE_HEARTBEAT, GOLEM_LEASE_RELEASED
} golem_lease_event_type;
typedef struct golem_lease_event {
    golem_lease_event_type type;
    uint64_t sequence, observed_ns;
    golem_lease_snapshot lease;
} golem_lease_event;
typedef struct golem_lease_ops {
    /* Required append-only durable audit sink, not journal v1's work-event codec.
     * Value is borrowed for call; copy/serialize fields, never native struct bytes.
     * OK means durable. An error poisons authority permanently: commit may be
     * ambiguous. No state is published and no automatic append retry occurs. */
    golem_status (*record)(void *context, const golem_lease_event *event);
} golem_lease_ops;

/* One trusted, serialized in-process authority per resource. No distributed lock,
 * authentication, thread synchronization, automatic timer or restart restoration.
 * Resource/owner are 1..95 non-space printable ASCII bytes. Create copies resource/ops and
 * allocator, borrows callback context until free. Allocator context must outlive
 * free. Owned output freed with lease_free; other outputs are caller-owned values.
 * Inputs borrowed for call; no aliasing. Failed calls preserve outputs. Valid
 * timestamps advance an internal watermark even on BUSY/STALE: observed expiry
 * cannot be undone by a later backward clock. Other state changes publish only
 * after record succeeds; sink failure poisons authority. No allocation after create.
 * All calls (including reads) must be serialized. Callbacks cannot reenter/free.
 * Free only after all runtimes borrowing the authority have been freed. */
golem_status golem_lease_create(const char *resource, const golem_lease_ops *ops,
    void *context, const golem_allocator *allocator, golem_lease **out);
void golem_lease_free(golem_lease *lease);
/* now_ns from ONE monotonic clock domain for entire lifetime; TTL positive.
 * Expiry equality is stale. Acquire never renews a live lease, even same owner.
 * Reacquisition after expiry/release increases fence and invalidates old tokens. */
golem_status golem_lease_acquire(golem_lease *lease, const char *owner,
    uint64_t now_ns, uint64_t ttl_ns, golem_lease_snapshot *out);
/* Heartbeat only for current unexpired token; cannot shorten existing expiry.
 * Tokens survive heartbeat, but expiry is always read from authority, not token. */
golem_status golem_lease_heartbeat(golem_lease *lease, const golem_lease_token *token,
    uint64_t now_ns, uint64_t ttl_ns, golem_lease_snapshot *out);
golem_status golem_lease_validate(golem_lease *lease, const golem_lease_token *token, uint64_t now_ns);
golem_status golem_lease_release(golem_lease *lease, const golem_lease_token *token, uint64_t now_ns);
/* Borrowed immutable resource until free; NULL input returns NULL. */
const char *golem_lease_resource_borrow(const golem_lease *lease);
#ifdef __cplusplus
}
#endif
#endif
