#ifndef GOLEM_SESSION_BINDING_INTERNAL_H
#define GOLEM_SESSION_BINDING_INTERNAL_H
#include "internal.h"
#include "golem/session_binding.h"
golem_status ab_reduce(struct json_object *state, struct json_object *event);
golem_status ab_validate(golem_document_store *store, struct json_object *event);
golem_status ab_reply(struct json_object *object, golem_agent_reply *out);
bool ab_matches(struct json_object *state, struct json_object *request);
golem_status ab_claim_validate(golem_document_store *store, struct json_object *state,
                               struct json_object *claim);
#endif
