#ifndef GOLEM_INTENT_REVIEW_INTERNAL_H
#define GOLEM_INTENT_REVIEW_INTERNAL_H
#include "journal.h"
#include "golem/document.h"

/* QC1 is a private local-cooperative control plane, not a product gate or a
 * public MCP capability. Trusted host hooks must authenticate exact evidence;
 * model supplied labels and same-uid possession are not authentication. */
typedef enum gi_review_purpose {
    GI_REVIEW_CONTROL, GI_REVIEW_SOURCE_ADOPTION, GI_REVIEW_STAGE,
    GI_REVIEW_ACTIVATION, GI_REVIEW_ANSWER, GI_REVIEW_RESOLUTION
} gi_review_purpose;
typedef golem_status (*gi_review_authorize)(void *context, gi_review_purpose purpose,
    const golem_digest *baseline, const golem_digest *evidence,
    const char *project, const char *work, const char *producer, const char *reviewer);

typedef struct gi_review_inputs {
    golem_bytes baseline;
    const gi_source_input *sources;
    size_t source_count;
    const golem_bytes *definitions;
    size_t definition_count;
} gi_review_inputs;
typedef struct gi_review_binding {
    golem_digest baseline, definitions;
    size_t requirements, constraints;
    bool has_questions;
} gi_review_binding;
/* Exact source coverage plus all requirement/constraint referents and spans.
 * No ACTIVE, issuer or semantic truth claim. Definitions use QC1 closed shape.
 * Output is failure-atomic. */
golem_status gi_review_bind(const gi_review_inputs *, gi_review_binding *, golem_diagnostic *);

typedef struct gi_review_state gi_review_state;
/* All controls and states are private and owned. Baseline/source/definitions
 * are validated through borrowed immutable inputs; parsed baseline and exact
 * definition identities are retained, not the original source buffers.
 * No registry mutation, key creation or file discovery. */
golem_status gi_review_create(const gi_review_inputs *, gi_review_state **);
void gi_review_free(gi_review_state *);
/* Applies a closed JSON control atomically to an in-memory candidate. Reuse of
 * control bytes is not a retry permission. The store wrapper owns publication.
 * Callback may not reenter state; failed callback leaves state unchanged. */
golem_status gi_review_apply(gi_review_state *, golem_bytes control,
    gi_review_authorize, void *context);
typedef struct gi_review_status {
    uint64_t epoch;
    size_t open_questions;
    bool active, requirements_reviewed;
    bool execution_authorized; /* Always false: QC3 owns product gates. */
    bool authority_current_verified; /* Always false for historical/query state. */
    golem_digest activation_decision; /* historical exact owner decision, not current authority */
} gi_review_status;
golem_status gi_review_inspect(const gi_review_state *, gi_review_status *);
typedef struct gi_review_stage_status {
    bool passed;
    golem_digest evidence,input,definitions;
    char producer[GOLEM_DOCUMENT_ID_CAPACITY],reviewer[GOLEM_DOCUMENT_ID_CAPACITY];
} gi_review_stage_status;
golem_status gi_review_stage_inspect(const gi_review_state *,unsigned,gi_review_stage_status *);
/* Committed baseline -> resolver -> control replay -> exact current policy
 * callback -> append under existing journal owner lock. guard validates D01
 * registration/pins. No Work journal write; no product execution authorization.
 * controls must be submitted in exact order; pending/unknown never retries. */
golem_status gi_review_load(gi_journal *, const golem_digest *baseline_operation,
    const golem_digest *baseline_request, const golem_digest *baseline,
    const golem_bytes *definitions, size_t definition_count, gi_review_state **);
golem_status gi_review_publish(gi_journal *, const golem_digest *baseline_operation,
    const golem_digest *baseline_request, const golem_digest *baseline,
    const golem_bytes *definitions, size_t definition_count,
    golem_bytes control, const golem_digest *operation,
    uint64_t expected_sequence, const golem_digest *expected_head,
    gi_journal_guard, gi_review_authorize, void *context, gi_journal_receipt *);
#endif
