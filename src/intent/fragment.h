#ifndef GOLEM_INTENT_FRAGMENT_INTERNAL_H
#define GOLEM_INTENT_FRAGMENT_INTERNAL_H
#include "journal.h"

#define GI_FRAGMENT_HEADER 320u
/* Private, pure codec. These values must be independently observed under the
 * owner lock by the caller; successful decoding grants no write authority.
 * No filesystem writes, approvals, journal replay exceptions or cleanup. */
typedef struct gi_fragment_binding {
    gi_journal_partial_plan original;
    golem_digest original_approval, preservation_approval;
    uint64_t envelope_device, envelope_inode;
} gi_fragment_binding;

/* Shared existing GIQUA001 encoder; no format change. */
golem_status gi_quarantine_encode(const gi_fragment_binding *, golem_bytes source,
    uint8_t **out, size_t *size);

/* The original source and complete 320-byte header must match. Only a strict
 * prefix of the expected full envelope is accepted, never arbitrary damage.
 * Caller owns returned allocation. Outputs unchanged on failure. */
golem_status gi_fragment_encode(const gi_fragment_binding *, golem_bytes source,
    golem_bytes truncated, uint8_t **out, size_t *size);
golem_status gi_fragment_verify(const gi_fragment_binding *, golem_bytes source,
    golem_bytes preserved);
/* Actual inventory already includes the truncated original. New publication
 * retains one object, peaks at two names. Existing publication may add one
 * final name, or release its exact alias without moving lane/slot/payload. */
golem_status gi_fragment_check_quota(const gi_quota_state *, size_t truncated_bytes,
    bool final_present, bool pending_present);

#define GI_FRAGMENT_DAMAGE_HEADER 384u
/* One terminal preservation layer, not a recursive container. Callers must
 * bind both previous approvals independently, never trust input headers. */
typedef struct gi_fragment_damage_binding {
    gi_fragment_binding fragment;
    uint64_t device, inode;
    golem_digest approval;
} gi_fragment_damage_binding;
golem_status gi_fragment_damage_encode(const gi_fragment_damage_binding *,
    golem_bytes source, golem_bytes envelope, golem_bytes truncated,
    uint8_t **out, size_t *size);
golem_status gi_fragment_damage_verify(const gi_fragment_damage_binding *,
    golem_bytes source, golem_bytes envelope, golem_bytes preserved);
golem_status gi_fragment_damage_check_quota(const gi_quota_state *, size_t truncated_bytes,
    bool final_present, bool pending_present);
#endif
