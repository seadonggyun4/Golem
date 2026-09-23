#ifndef GOLEM_RESEARCH_INTERNAL_H
#define GOLEM_RESEARCH_INTERNAL_H
#include "golem/research.h"
#include "../document/internal.h"
#include "../execution/internal.h"
golem_status rs_validate(struct json_object *request);
bool rs_is_cohort(struct json_object *request);
golem_status rs_cohort_model(struct json_object *request);
golem_status rs_cohort_check(golem_document_store *s, struct json_object *request);
bool rs_is_outcome(struct json_object *request);
golem_status rs_outcome_check(golem_document_store *s, struct json_object *request, struct json_object **out);
golem_status rs_outcome_completion(golem_document_store *s, const char *selection,
    const golem_digest *qa, struct json_object **out);
golem_status rs_apply(golem_document_store *store, struct json_object *event,
    const golem_digest *payload, const golem_digest *frame);
golem_status rs_markdown(struct json_object *event, golem_execution_reply *out);
golem_status rs_metrics(golem_document_store *store, const char *case_id, struct json_object **out);
#endif
