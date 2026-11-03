#ifndef GOLEM_INTENT_PRODUCT_ACCESS_H
#define GOLEM_INTENT_PRODUCT_ACCESS_H
#include "product_gate.h"
#include "qa_resolve.h"
typedef struct gi_product_access gi_product_access;
/* Private exact-request scope. Caller holds D01 guard then Work writer lock.
 * Owns material/control JSON; borrows host and authority fd until close.
 * No service, approval issuance, retry, or mutation during open/check. */
golem_status gi_product_access_open(golem_document_store *, int, gi_review_host *,
                                    golem_bytes control, golem_bytes material,
                                    gi_product_access **);
golem_status gi_product_access_record(golem_document_store *, struct json_object *);
void gi_product_access_close(gi_product_access *);
golem_status gi_product_access_check(golem_document_store *, gi_product_boundary);
golem_status gi_product_request(golem_document_store *, gi_product_boundary, golem_bytes,
                                const char *channel);
typedef struct gi_product_qa_view {
    const gi_qa_paths_inputs *inputs;
    gi_review_host *host;
    int authority_fd;
    golem_digest material, baseline_operation, baseline_request;
    uint64_t review_epoch;
    struct json_object *control, *native_inputs;
} gi_product_qa_view;
golem_status gi_product_qa_scope(golem_document_store *, gi_product_qa_view *);
#endif
