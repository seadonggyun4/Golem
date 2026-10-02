#ifndef GOLEM_SESSION_BINDING_INTERNAL_H
#define GOLEM_SESSION_BINDING_INTERNAL_H
#include "internal.h"
#include "golem/session_binding.h"
golem_status ab_reduce(struct json_object *state, struct json_object *event);
golem_status ab_validate(golem_document_store *store, struct json_object *event);
golem_status ab_reply(struct json_object *object, golem_agent_reply *out);
bool ab_matches(struct json_object *state, struct json_object *request);
golem_status ab_history_incremental(golem_document_store *store, struct json_object *request,
                                    golem_agent_reply *out, golem_diagnostic *diagnostic);
golem_status ab_project_stream(golem_document_store *store, int directory, const char *stream,
                               const char *magic, size_t count, const golem_digest *head,
                               uint64_t after, uint64_t limit, uint64_t *ordinal,
                               struct json_object *rows);
golem_status ab_claim_validate(golem_document_store *store, struct json_object *state,
                               struct json_object *claim);
#endif
