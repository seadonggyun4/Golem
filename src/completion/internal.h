#ifndef GOLEM_COMPLETION_INTERNAL_H
#define GOLEM_COMPLETION_INTERNAL_H
#include "golem/completion.h"
#include "../execution/internal.h"
#define CO_MAX_RECORDS 64
golem_status co_validate(struct json_object *request);
golem_status co_evaluate(golem_document_store *s, struct json_object *request,
    bool live, struct json_object **out);
golem_status co_quiescent(golem_document_store *s, const char **action,
    struct json_object **boundary);
golem_status co_boundary_verify(golem_document_store *s,struct json_object *boundary);
golem_status co_markdown(struct json_object *record, golem_execution_reply *out);
golem_status co_apply(golem_document_store *s, struct json_object *event,
    const golem_digest *payload, const golem_digest *frame);
golem_status co_hint(golem_document_store *s, const char *selection,
    const char **action);
#endif
