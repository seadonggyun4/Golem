#ifndef GOLEM_INTENT_OBJECT_INTERNAL_H
#define GOLEM_INTENT_OBJECT_INTERNAL_H
#include "quota.h"

/* Pure internal publication codec. Not an object store or an authorization API. */
typedef struct gi_object_publication {
    golem_digest preparation, baseline, operation, request;
} gi_object_publication;
#define GI_OBJECT_PUBLICATION_CAPACITY 512u
golem_status gi_object_publication_encode(const gi_object_publication *, char *, size_t, size_t *);
golem_status gi_object_publication_decode(golem_bytes, gi_object_publication *);

/* Supplied by a trusted replay after validation, not user-provided evidence.
 * Count a reservation once whether objects-prep exists alone or journal prep
 * already accounts for it. Never removes bytes/entries or shifts lanes. */
typedef struct gi_object_reservation {
    uint64_t sequence;
    golem_digest head;
    gi_object_publication publication;
} gi_object_reservation;
typedef struct gi_object_journal_binding {
    gi_quota_lane lane;
    uint64_t sequence;
    golem_digest head;
    golem_bytes payload;
} gi_object_journal_binding;
golem_status gi_object_reservation_project(const gi_quota_state *, const gi_object_reservation *,
    const gi_object_journal_binding *, gi_quota_state *);
#endif
