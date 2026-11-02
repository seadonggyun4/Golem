#ifndef GOLEM_WORKPACK_RECEIPT_INTERNAL_H
#define GOLEM_WORKPACK_RECEIPT_INTERNAL_H
#include "golem/workpack.h"
#include "../workflow/role_internal.h"
typedef struct wp_object { uint8_t *data; size_t size; golem_digest digest; const char *type; } wp_object;
typedef struct wp_bundle {
    wp_object objects[256]; size_t count, total;
    struct json_object *manifest;
    golem_execution_reply encoded, markdown;
    golem_digest digest;
} wp_bundle;
golem_status wp_document_closure(golem_document_store *store, struct json_object *binding, bool *selected);
golem_status wp_receipt_build(golem_document_store *store, golem_bytes request, const char *format, wp_bundle *out);
golem_status wp_receipt_validate(wp_bundle *bundle, const golem_digest *expected);
golem_status wp_receipt_markdown(struct json_object *manifest, golem_execution_reply *out);
void wp_receipt_free(wp_bundle *bundle);
#endif
