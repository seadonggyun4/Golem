#ifndef GOLEM_WORKPACK_BINDING_INTERNAL_H
#define GOLEM_WORKPACK_BINDING_INTERNAL_H
#include "../document/internal.h"
golem_status wp_apply(golem_document_store *store, struct json_object *event,
                      const golem_digest *payload, const golem_digest *frame);
golem_status wp_binding_request(golem_bytes input, struct json_object **request, struct json_object **pack, golem_digest *manifest);
#endif
