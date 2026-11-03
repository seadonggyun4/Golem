#ifndef GOLEM_INTENT_PRODUCT_GATE_H
#define GOLEM_INTENT_PRODUCT_GATE_H
#include "qa_paths.h"
#include "golem/document.h"
struct json_object;
typedef enum gi_product_boundary {
    GI_PRODUCT_DEVELOPMENT,
    GI_PRODUCT_QA_DISPATCH,
    GI_PRODUCT_QA_ACCEPTANCE,
    GI_PRODUCT_COMPLETION,
    GI_PRODUCT_QA_INSPECTION,
    GI_PRODUCT_PUBLICATION
} gi_product_boundary;
/* v1/v2 retain their existing semantics. v3 never falls back to a legacy gate.
 * Exact product-access scopes may open development/QA dispatch after live
 * QC2/stage checks. QC4 and QC5 use distinct exact QA/completion scopes; neither inherits execution
 * permission. This is a mandatory additional denial, not a substitute native approval. */
golem_status gi_product_check(golem_document_store *, gi_product_boundary);
golem_status gi_product_spec(struct json_object *);
golem_status gi_product_record(golem_document_store *, struct json_object *);
golem_status gi_product_apply(golem_document_store *, struct json_object *, const golem_digest *);
/* Private trusted-host binding: caller holds D01 common-dir guard before opening
 * Work. Opens authority only after that Work lock; closes it before return.
 * Exact owner digest binds enrollment SHA, spec/registration and both CAS heads,
 * operations and sequences; it is not execution permission.
 * Both publications retain CAS; partial/unknown is preserved, never retried. */
golem_status gi_product_enrollment_approval(
    golem_document_store *, const golem_digest *request, const golem_digest *baseline_operation,
    const golem_digest *baseline_request, const golem_digest *operation,
    uint64_t authority_sequence, const golem_digest *authority_head, uint64_t work_sequence,
    const golem_digest *work_head, golem_digest *out);
golem_status gi_product_enroll(golem_document_store *, int authority_fd, const gi_review_inputs *,
                               golem_bytes enrollment, const golem_digest *owner_digest,
                               const golem_digest *baseline_operation,
                               const golem_digest *baseline_request, const golem_digest *operation,
                               uint64_t authority_sequence, const golem_digest *authority_head,
                               uint64_t work_sequence, const golem_digest *work_head,
                               gi_journal_guard, void *, gi_journal_receipt *);
/* Read-only cross-journal receipt/payload comparison under the same lock order.
 * Success proves binding integrity only, never current stage/QA permission. */
golem_status gi_product_enrollment_verify(golem_document_store *, int authority_fd,
                                          gi_journal_guard, void *);
#endif
