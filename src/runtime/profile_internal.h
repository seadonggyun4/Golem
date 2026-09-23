#ifndef GOLEM_PROFILE_INTERNAL_H
#define GOLEM_PROFILE_INTERNAL_H
#include "golem/runtime_profile.h"
#include "../document/internal.h"

struct golem_runtime_profile {
    golem_allocator allocator;
    struct json_object *object;
    golem_digest digest;
};
golem_status rp_canonical(struct json_object *object, struct json_object **out);
golem_status rp_apply(golem_document_store *store, struct json_object *event,
                      const golem_digest *frame);
golem_status rp_claim(golem_document_store *store, struct json_object *claim);
golem_status rp_validate_claim(golem_document_store *store, struct json_object *claim);
golem_status rp_binding_claim(golem_document_store *store, const golem_digest *digest,
                              struct json_object **out);
golem_status rp_availability(golem_document_store *store, const golem_runtime_profile *profile);
golem_status rp_initial(golem_document_store *store, struct json_object *spec, bool publish);
golem_status rp_object(struct json_object *object, const golem_allocator *allocator,
                       golem_runtime_profile **out);
golem_status rp_link_apply(golem_document_store *store, struct json_object *event,
                           const golem_digest *payload, const golem_digest *frame);
#endif
