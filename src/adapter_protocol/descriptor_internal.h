#ifndef GOLEM_DESCRIPTOR_INTERNAL_H
#define GOLEM_DESCRIPTOR_INTERNAL_H
#include "golem/adapter_descriptor.h"
#include "internal.h"
#include "../common/json.h"
golem_status golem_descriptor_object(const golem_adapter_descriptor *d, struct json_object **out);
golem_status golem_descriptor_copy_json(struct json_object *o, void *buffer, size_t capacity,
                                        size_t *required);
golem_status golem_harness_guard_check(const golem_harness_guard *guard,
                                       const golem_adapter_request *request,
                                       const golem_adapter_capability *capability,
                                       golem_evidence_store *store);
#endif
