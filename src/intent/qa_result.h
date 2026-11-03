#include "golem/execution.h"

#ifndef GOLEM_INTENT_QA_RESULT_H
#define GOLEM_INTENT_QA_RESULT_H
#include "product_access.h"
/* Internal synthesis only. Native caller must load receipt via ex_load; this
 * pure helper never publishes or proves currentness/issuer authority. */
golem_status gi_qa_native_results(struct json_object *obligations, struct json_object *mapping,
                                  struct json_object *contract, struct json_object *receipt,
                                  struct json_object **out);
/* Compare already native-validated input manifests across result submission.
 * Only a monotonic document generation counter may differ. This pure comparison
 * grants nothing; callers still require native receipt/current scope checks. */
golem_status gi_qa_manifest_matches(struct json_object *recorded, struct json_object *current);
/* Exact native receipt currentness, reuses existing snapshot/inventory checks. */
golem_status gi_qa_review_digest(const golem_digest *, struct json_object *receipt,
                                 struct json_object *obligation, golem_digest *);
golem_status gi_qa_assess(golem_document_store *, golem_bytes request, golem_execution_reply *);
golem_status gi_qa_accept(golem_document_store *, golem_bytes request, golem_execution_reply *);
golem_status gi_qa_accepted(golem_document_store *, struct json_object **);
golem_status gi_qa_current(golem_document_store *, golem_execution_reply *);
golem_status gi_qa_observation_apply(golem_document_store *, struct json_object *,
                                     const golem_digest *);
#endif
