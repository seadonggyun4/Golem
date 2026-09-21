#include "internal.h"
#include <string.h>

static golem_status probe(void *context, golem_adapter_capability *out, golem_diagnostic *d)
{
    (void)context;
    *out = (golem_adapter_capability){GOLEM_ADAPTER_VERSION, "local.noop",
        GOLEM_ADAPTER_ALL_STAGES, GOLEM_EFFECT_LOCAL, true};
    return golem_adapter_report(d, GOLEM_OK);
}
golem_status golem_adapter_noop_run_stage(const golem_adapter_request *r,
    golem_evidence_store *store, golem_adapter_result *out, golem_diagnostic *d)
{
    golem_status s = golem_adapter_request_valid(r);
    if (s != GOLEM_OK) return golem_adapter_report(d, s);
    if (store == NULL || out == NULL) return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    if (strcmp(r->adapter_id, "local.noop") != 0) return golem_adapter_report(d, GOLEM_ERR_IDENTITY_MISMATCH);
    s = golem_adapter_inputs_verify(r, store);
    if (s != GOLEM_OK) return golem_adapter_report(d, s);
    char evidence[GOLEM_ADAPTER_JSON_MAX + 128] = "Golem local.noop v1: simulation only; no task acceptance attested.\n";
    size_t prefix = strlen(evidence), required;
    golem_adapter_envelope envelope = {.type = GOLEM_ADAPTER_RUN_STAGE, .data.request = *r};
    s = golem_adapter_envelope_encode(&envelope, evidence + prefix, sizeof(evidence) - prefix, &required, d);
    golem_adapter_result result = {0};
    result.request = *r; result.outcome = GOLEM_STAGE_PASSED; result.simulation = true;
    result.usage.usage_known = true; result.usage.cost_known = true;
    if (s == GOLEM_OK) s = golem_evidence_put(store,
        (golem_bytes){(const uint8_t *)evidence, prefix + required - 1}, &result.evidence, d);
    if (s == GOLEM_OK) *out = result;
    return golem_adapter_report(d, s);
}
static golem_status run(void *context, const golem_adapter_request *r,
    golem_evidence_store *store, golem_adapter_result *out, golem_diagnostic *d)
{
    (void)context;
    return golem_adapter_noop_run_stage(r, store, out, d);
}
golem_status golem_adapter_noop_create(const golem_allocator *allocator, golem_adapter **out)
{
    const golem_adapter_ops ops = {probe, run};
    return golem_adapter_create(&ops, NULL, allocator, out);
}
