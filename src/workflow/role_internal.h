#ifndef GOLEM_ROLE_INTERNAL_H
#define GOLEM_ROLE_INTERNAL_H
#include "golem/role_contract.h"
#include "../execution/internal.h"
#define RC_PREDICATE "golem.completion.roles.v1"
golem_status rc_qa_cases(struct json_object *receipt, struct json_object *checkpoint);
golem_status rc_contract(struct json_object *contract);
golem_status rc_request(struct json_object *request);
struct json_object *rc_enrollment(golem_document_store *store, const char *selection);
struct json_object *rc_latest(golem_document_store *store, const char *selection);
golem_status rc_assess(golem_document_store *store, struct json_object *request, bool live,
                       struct json_object *historical, struct json_object **out);
golem_status rc_apply(golem_document_store *store, struct json_object *event,
                      const golem_digest *payload, const golem_digest *frame);
golem_status rc_completion(golem_document_store *store, struct json_object *request, bool live,
                           struct json_object **out);
golem_status rc_markdown(struct json_object *record, golem_execution_reply *out);
golem_status rc_hint(golem_document_store *store, const char *selection, const char **action,
                     const char **kind, const char **reason);
#endif
