#ifndef GOLEM_ADAPTER_INTERNAL_H
#define GOLEM_ADAPTER_INTERNAL_H
#include "golem/adapter_protocol.h"
struct golem_adapter {
    golem_adapter_ops ops;
    void *context;
    golem_allocator allocator;
};
bool golem_adapter_id_valid(const char *id);
golem_status golem_adapter_capability_valid(const golem_adapter_capability *c);
golem_status golem_adapter_request_valid(const golem_adapter_request *r);
golem_status golem_adapter_inputs_verify(const golem_adapter_request *r, golem_evidence_store *store);
golem_status golem_adapter_report(golem_diagnostic *d, golem_status status);
#endif
