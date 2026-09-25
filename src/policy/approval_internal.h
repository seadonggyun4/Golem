#ifndef GOLEM_APPROVAL_INTERNAL_H
#define GOLEM_APPROVAL_INTERNAL_H
#include "golem/approval.h"
#include "../execution/internal.h"
golem_status ap_request(struct json_object *request);
golem_status ap_action(struct json_object *action);
golem_status ap_apply(golem_document_store *s, struct json_object *e, const golem_digest *payload,
                      const golem_digest *frame);
golem_status ap_scope(golem_document_store *s, golem_bytes bytes, struct json_object **out);
typedef struct ap_dispatch {
    golem_document_store *store;
    const golem_approval_host *host;
    struct json_object *request_event;
    struct json_object *approval_event;
    golem_bytes execution_request;
    uint64_t last_ms;
} ap_dispatch;
golem_status ap_guard(ap_dispatch *dispatch);
golem_status ap_current(ap_dispatch *dispatch);
golem_status ex_receipted(golem_document_store *s, golem_bytes bytes,
                          const golem_execution_approval *approval, ap_dispatch *dispatch,
                          golem_execution_reply *out, golem_diagnostic *diagnostic);
#endif
