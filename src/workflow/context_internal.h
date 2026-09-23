#ifndef GOLEM_CONTEXT_INTERNAL_H
#define GOLEM_CONTEXT_INTERNAL_H
#include "golem/context.h"
#include "internal.h"
golem_status cx_request(golem_bytes bytes, struct json_object **out);
golem_status cx_build(golem_document_store *store, struct json_object *request,
                      const golem_context_tokenizer *tokenizer, struct json_object **out);
#endif
