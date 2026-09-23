#ifndef GOLEM_EXECUTION_INTERNAL_H
#define GOLEM_EXECUTION_INTERNAL_H
#include "golem/execution.h"
#include "../workflow/internal.h"
#include "../discovery/internal.h"
golem_status ex_contract(struct json_object *o);
golem_status ex_snapshot(struct json_object *plan, struct json_object **out);
golem_status ex_inputs(golem_document_store *s, struct json_object *contract, const char *kind,
                       struct json_object **out);
golem_status ex_current(golem_document_store *s, struct json_object *manifest);
golem_status ex_load(golem_document_store *s, const golem_digest *key, const char *type,
                     struct json_object **out);
golem_status ex_markdown(golem_document_store *s, struct json_object *meta,
                         golem_execution_reply *out);
golem_status ex_document(golem_document_store *s, struct json_object *meta, golem_bytes body);
golem_status ex_live(golem_document_store *s, struct json_object *meta);
golem_status ex_pass(golem_document_store *s, struct json_object *meta);
golem_status ex_required(golem_document_store *s, struct json_object *meta);
golem_status ex_authorize(golem_document_store *s, struct json_object *token,
                          struct json_object *manifest);
golem_status ex_execute(golem_document_store *s, struct json_object *checkpoint,
                        const golem_digest *checkpoint_digest, struct json_object *manifest,
                        const char *attempt, struct json_object *token, struct json_object **out);
bool ex_text(struct json_object *o, const char *key, const char *text);
bool ex_uint(struct json_object *o, const char *key, uint64_t n);
golem_status ex_emit(struct json_object *o, golem_execution_reply *out);
golem_status ex_hash(struct json_object *o, golem_digest *out);
#endif
