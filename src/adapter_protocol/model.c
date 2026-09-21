#include "internal.h"
#include "../core/internal.h"
#include "../cost/internal.h"
#include <string.h>

golem_status golem_adapter_report(golem_diagnostic *d, golem_status status)
{
    if (d != NULL) (void)golem_diagnostic_set(d, status, GOLEM_DIAGNOSTIC_NO_OFFSET, NULL);
    return status;
}
bool golem_adapter_id_valid(const char *id)
{
    if (id == NULL || id[0] == '\0') return false;
    for (size_t i = 0; i < GOLEM_ADAPTER_ID_CAPACITY; ++i) {
        unsigned char c = (unsigned char)id[i];
        if (c == 0) return true;
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
            c == '_' || c == '.' || c == ':' || c == '-')) return false;
    }
    return false;
}
static bool receipt_valid(const golem_receipt *r)
{
    return r->version == GOLEM_RECEIPT_VERSION && r->algorithm == GOLEM_DIGEST_SHA256;
}
golem_status golem_adapter_capability_valid(const golem_adapter_capability *c)
{
    if (c == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (c->version != GOLEM_ADAPTER_VERSION) return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (!golem_adapter_id_valid(c->adapter_id) || c->stages == 0 ||
        (c->stages & ~GOLEM_ADAPTER_ALL_STAGES) != 0 ||
        (c->effect != GOLEM_EFFECT_LOCAL && c->effect != GOLEM_EFFECT_EXTERNAL)) return GOLEM_ERR_INVALID_ARGUMENT;
    return GOLEM_OK;
}
golem_status golem_adapter_request_valid(const golem_adapter_request *r)
{
    if (r == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->version != GOLEM_ADAPTER_VERSION) return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (!golem_adapter_id_valid(r->run_id) || !golem_adapter_id_valid(r->request_id) ||
        !golem_adapter_id_valid(r->adapter_id) || !golem_core_stage_valid(r->stage) ||
        r->sequence == 0 || r->attempt == 0 || !receipt_valid(&r->context)) return GOLEM_ERR_INVALID_ARGUMENT;
    static const golem_digest zero = {{0}};
    if (!r->has_predecessor && memcmp(&r->predecessor, &zero, sizeof(zero)) != 0) return GOLEM_ERR_INVALID_ARGUMENT;
    return GOLEM_OK;
}
static bool request_equal(const golem_adapter_request *a, const golem_adapter_request *b)
{
    return strcmp(a->run_id, b->run_id) == 0 && strcmp(a->request_id, b->request_id) == 0 &&
        strcmp(a->adapter_id, b->adapter_id) == 0 && a->stage == b->stage && a->sequence == b->sequence && a->attempt == b->attempt &&
        a->context.size == b->context.size && memcmp(&a->context.digest, &b->context.digest, sizeof(a->context.digest)) == 0 &&
        a->has_predecessor == b->has_predecessor && memcmp(&a->predecessor, &b->predecessor, sizeof(a->predecessor)) == 0;
}
golem_status golem_adapter_result_validate(const golem_adapter_request *r, const golem_adapter_result *result)
{
    golem_status s = golem_adapter_request_valid(r);
    if (s != GOLEM_OK) return s;
    if (result == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    s = golem_adapter_request_valid(&result->request);
    if (s != GOLEM_OK) return s;
    if (!request_equal(r, &result->request)) return GOLEM_ERR_IDENTITY_MISMATCH;
    if (!receipt_valid(&result->evidence) || !golem_cost_amount_valid(&result->usage)) return GOLEM_ERR_INVALID_ARGUMENT;
    switch (result->outcome) {
    case GOLEM_STAGE_PASSED:
    case GOLEM_STAGE_CANCELLED:
        return result->failure == GOLEM_FAILURE_NONE ? GOLEM_OK : GOLEM_ERR_INVALID_ARGUMENT;
    case GOLEM_STAGE_BLOCKED:
        return golem_core_failure_blocks(result->failure) ? GOLEM_OK : GOLEM_ERR_INVALID_ARGUMENT;
    case GOLEM_STAGE_FAILED:
        return golem_core_failure_valid(result->failure) && !golem_core_failure_blocks(result->failure) ?
            GOLEM_OK : GOLEM_ERR_INVALID_ARGUMENT;
    default: return GOLEM_ERR_INVALID_ARGUMENT;
    }
}
golem_status golem_adapter_request_init(const golem_work_run *run, const char *adapter_id,
    const char *request_id, const golem_receipt *context, const golem_digest *predecessor, golem_adapter_request *out)
{
    if (run == NULL || context == NULL || out == NULL || !golem_adapter_id_valid(adapter_id) ||
        !golem_adapter_id_valid(request_id) || !golem_adapter_id_valid(run->id)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (run->status != GOLEM_WORK_RUNNING) return GOLEM_ERR_INVALID_STATE;
    golem_adapter_request r = {0}; r.version = GOLEM_ADAPTER_VERSION;
    strcpy(r.run_id, run->id); strcpy(r.adapter_id, adapter_id); strcpy(r.request_id, request_id);
    r.stage = run->latest.snapshot.stage; r.sequence = run->sequence; r.attempt = run->latest.snapshot.attempt;
    r.context = *context; r.has_predecessor = predecessor != NULL;
    if (predecessor != NULL) r.predecessor = *predecessor;
    golem_status s = golem_adapter_request_valid(&r);
    if (s == GOLEM_OK) *out = r;
    return s;
}
golem_status golem_adapter_inputs_verify(const golem_adapter_request *r, golem_evidence_store *store)
{
    uint64_t size;
    golem_status s = golem_evidence_verify(store, &r->context.digest, &size, NULL);
    if (s != GOLEM_OK) return s;
    if (size != r->context.size) return GOLEM_ERR_SIZE_MISMATCH;
    return r->has_predecessor ? golem_evidence_verify(store, &r->predecessor, &size, NULL) : GOLEM_OK;
}
