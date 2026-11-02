#ifndef GOLEM_WORKPACK_BINDING_INTERNAL_H
#define GOLEM_WORKPACK_BINDING_INTERNAL_H
#include "../document/internal.h"
golem_status wp_apply(golem_document_store *store, struct json_object *event,
                      const golem_digest *payload, const golem_digest *frame);
#endif
