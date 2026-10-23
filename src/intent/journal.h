#ifndef GOLEM_INTENT_JOURNAL_INTERNAL_H
#define GOLEM_INTENT_JOURNAL_INTERNAL_H
#include "quota.h"

typedef struct gi_journal gi_journal;
typedef struct gi_journal_status {
    gi_quota_state usage;
    uint64_t committed;
    golem_digest head;
    bool pending;
} gi_journal_status;
typedef struct gi_journal_receipt {
    uint64_t sequence;
    golem_digest digest;
    bool replayed;
} gi_journal_receipt;
typedef struct gi_journal_operation {
    gi_quota_lane lane;
    uint64_t sequence;
    bool committed, pending;
    golem_digest digest;
} gi_journal_operation;
/* Internal transport prototype, not a baseline reducer/public API. Host must
 * validate D01 registration/common-dir pin and supply an owned private root.
 * Opens an independent fd and holds exclusive owner flock until close.
 * A handle is not thread-safe; serialize its use. Independent handles contend
 * on the same root lock. Inherited handles cannot be used after fork.
 * Never creates a root, migrates Work, or changes existing document journals. */
golem_status gi_journal_open(int registered_root_fd, gi_journal **out);
void gi_journal_close(gi_journal *journal);
/* Validates committed object history and reports attributed staging read-only.
 * Pending object publication is never a D01 recovery authorization. */
golem_status gi_journal_inspect(gi_journal *journal, gi_journal_status *out);
/* Read-only ordered metadata replay after full journal validation. The visitor
 * must not reenter or close this handle. Pending records are included. */
typedef golem_status (*gi_journal_visitor)(void *context, const golem_digest *operation,
    const golem_digest *request, const gi_journal_operation *record);
golem_status gi_journal_visit(gi_journal *journal, gi_journal_visitor visitor, void *context);
/* Read-only operation lookup, including prepared/uncommitted operations.
 * Does not clear poison or retry publication. Requires exact request identity. */
golem_status gi_journal_lookup(gi_journal *journal, const golem_digest *operation,
    const golem_digest *request, gi_journal_operation *out);
/* Trusted host callback, NOT model-supplied authorization. Runs under owner
 * lock, before preparation and again before commit. Must not reenter/close
 * this handle. It retains all semantic/issuer/owner/binding/protection checks. */
typedef golem_status (*gi_journal_guard)(void *context);
typedef struct gi_journal_pending_plan {
    uint64_t sequence, payload_bytes;
    golem_digest operation, request, head, preparation, payload, snapshot;
} gi_journal_pending_plan;
/* Complete final intake preparation only. No staging, retry, deletion or lane
 * transfer. Trusted D01 host must independently restrict operation semantics. */
golem_status gi_journal_pending_plan_get(gi_journal *journal, gi_journal_pending_plan *out);
golem_status gi_journal_pending_finish(gi_journal *journal, const golem_digest *snapshot,
    gi_journal_guard guard, void *context, gi_journal_receipt *out);
typedef struct gi_journal_alias_plan {
    uint64_t sequence, kind, device, inode, bytes;
    bool present;
    golem_digest operation, request, preparation, payload, final_digest, snapshot;
    gi_journal_status state;
} gi_journal_alias_plan;
/* kind: 0=prep, 1=payload, 2=event. Observe one final file and optional exact
 * staging hardlink on the final intake sequence; no independent staging files.
 * Removal requires explicit trusted-host approval and never changes final bytes. */
golem_status gi_journal_alias_observe(gi_journal *journal, unsigned kind, gi_journal_alias_plan *out);
golem_status gi_journal_alias_remove(gi_journal *journal, unsigned kind, const golem_digest *snapshot,
    gi_journal_guard guard, void *context, gi_journal_alias_plan *out);
typedef struct gi_journal_partial_plan {
    gi_journal_alias_plan source;
    bool archived, payload_ready, directory_present;
    uint64_t payload_bytes;
    golem_digest approval;
} gi_journal_partial_plan;
/* Independent staging only, on the final intake record. Quarantine preserves
 * bytes and attribution within the same authority. Replacement is payload-only
 * and requires a completed quarantine. Neither operation publishes an event.
 * Host must validate D01 semantics and persist explicit owner approval first. */
golem_status gi_journal_partial_observe(gi_journal *, unsigned kind, gi_journal_partial_plan *);
/* Pure peak check used again on freshly restored state under the owner lock. */
golem_status gi_journal_partial_check_quota(const gi_journal_partial_plan *, bool replace);
golem_status gi_journal_partial_quarantine(gi_journal *, unsigned kind, const golem_digest *snapshot,
    const golem_digest *approval, gi_journal_guard, void *, gi_journal_partial_plan *);
golem_status gi_journal_payload_replace(gi_journal *, const golem_digest *snapshot,
    golem_bytes payload, gi_journal_guard, void *, gi_journal_partial_plan *);
typedef struct gi_journal_envelope_plan {
    gi_journal_partial_plan partial;
    bool final_present, pending_present;
    uint64_t device, inode, bytes;
    golem_digest digest, snapshot;
} gi_journal_envelope_plan;
/* Recovery-only read surface: permits only complete quarantine publication
 * staging on the final record. Ordinary inspection/visitation stays strict. */
golem_status gi_journal_envelope_observe(gi_journal *, unsigned kind, gi_journal_envelope_plan *);
golem_status gi_journal_envelope_visit(gi_journal *, unsigned kind, gi_journal_visitor, void *);
golem_status gi_journal_envelope_check_quota(const gi_journal_envelope_plan *);
golem_status gi_journal_envelope_finish(gi_journal *, unsigned kind, const golem_digest *snapshot,
    const golem_digest *original_approval, gi_journal_guard, void *, gi_journal_envelope_plan *);
typedef struct gi_journal_fragment_plan {
    gi_journal_partial_plan original;
    bool truncated_present, final_present, pending_present;
    uint64_t device, inode, bytes, object_device, object_inode, object_bytes;
    golem_digest digest, object_digest, preservation_approval, snapshot;
    /* Only the terminal damage path uses this independently checked ancestry. */
    uint64_t envelope_device, envelope_inode, envelope_bytes;
    golem_digest envelope_digest, fragment_approval;
} gi_journal_fragment_plan;
golem_status gi_journal_fragment_observe(gi_journal *, unsigned kind, gi_journal_fragment_plan *);
golem_status gi_journal_fragment_visit(gi_journal *, unsigned kind, gi_journal_visitor, void *);
/* Separate explicit operations: 0=preserve, 1=finish preservation publication,
 * 2=detach original truncated envelope. Never advances the underlying Work. */
golem_status gi_journal_fragment_apply(gi_journal *, unsigned kind, unsigned action,
    const golem_digest *snapshot, const golem_digest *original_approval,
    const golem_digest *preservation_approval, gi_journal_guard, void *, gi_journal_fragment_plan *);
golem_status gi_journal_damage_observe(gi_journal *, unsigned, gi_journal_fragment_plan *);
golem_status gi_journal_damage_visit(gi_journal *, unsigned, gi_journal_visitor, void *);
golem_status gi_journal_damage_apply(gi_journal *, unsigned, unsigned,
    const golem_digest *, const golem_digest *, const golem_digest *,
    gi_journal_guard, void *, gi_journal_fragment_plan *);
golem_status gi_journal_append(gi_journal *journal, gi_quota_lane lane,
    const golem_digest *operation, const golem_digest *request,
    uint64_t expected_sequence, const golem_digest *expected_head,
    golem_bytes payload, gi_journal_guard guard, void *context,
    gi_journal_receipt *out);
struct gi_source_input;
/* Internal intake-only proposal storage, never adoption/ACTIVE. Inputs must
 * remain alive and immutable through the call. A trusted D01 host guard is
 * mandatory. Prepared failures are preserved and block subsequent writes. */
golem_status gi_journal_store_objects(gi_journal *, const golem_digest *operation, const golem_digest *request,
    uint64_t expected_sequence, const golem_digest *expected_head, golem_bytes baseline,
    const struct gi_source_input *, size_t source_count, gi_journal_guard, void *, gi_journal_receipt *);
#endif
