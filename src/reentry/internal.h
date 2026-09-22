#ifndef GOLEM_REENTRY_INTERNAL_H
#define GOLEM_REENTRY_INTERNAL_H
#include "golem/reentry.h"
#include "../execution/internal.h"
#define RE_MAX_EVENTS 64
golem_status re_validate(struct json_object *request);
golem_status re_decide(golem_document_store *s, struct json_object *request,
    uint64_t now, const golem_digest *boot, struct json_object **out);
golem_status re_apply(golem_document_store *s, struct json_object *event,
    const golem_digest *payload, const golem_digest *frame);
golem_status re_markdown(struct json_object *decision, golem_execution_reply *out);
golem_status re_guard(golem_document_store *s, const char *kind, bool live);
golem_status re_deadline(golem_document_store *s);
golem_status re_next(golem_document_store *s, const char **action, const char **kind, const char **reason);
golem_status re_context(golem_document_store *s, struct json_object *manifest, uint64_t *total, uint64_t budget);
golem_status re_export(golem_document_store *s, struct json_object *manifest, struct json_object *reply);
golem_status re_rebase(golem_document_store *s, struct json_object *original, struct json_object *replacement);
#endif
