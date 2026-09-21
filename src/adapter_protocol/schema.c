#include "schema.h"
#include <string.h>

const char *golem_wire_name(golem_wire_field id)
{
    static const char *const names[] = {
        "type", "version", "request_id", "run_id", "adapter_id", "stage", "sequence", "attempt",
        "context_version", "context_algorithm", "context_size", "context_digest", "has_predecessor",
        "predecessor_digest", "stages", "effect", "simulation", "outcome", "failure", "evidence_version",
        "evidence_algorithm", "evidence_size", "evidence_digest", "input_tokens", "cached_input_tokens",
        "output_tokens", "reasoning_tokens", "tool_calls", "nano_cost", "usage_known", "cost_known"
    };
    _Static_assert(sizeof(names) / sizeof(names[0]) == W_FIELD_COUNT, "every wire ID needs a JSON name");
    return id >= 0 && id < W_FIELD_COUNT ? names[id] : NULL;
}
golem_status golem_adapter_envelope_valid(const golem_adapter_envelope *e)
{
    if (e == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    switch (e->type) {
    case GOLEM_ADAPTER_CAPABILITY: return golem_adapter_capability_valid(&e->data.capability);
    case GOLEM_ADAPTER_RUN_STAGE: return golem_adapter_request_valid(&e->data.request);
    case GOLEM_ADAPTER_STAGE_RESULT: return golem_adapter_result_validate(&e->data.result.request, &e->data.result);
    default: return GOLEM_ERR_INVALID_ARGUMENT;
    }
}
static void number(golem_wire_codec *c, golem_wire_field id, uint64_t *n, uint64_t max, bool boolean)
{
    if (c->status != GOLEM_OK) return;
    golem_wire_value v = {0}; v.kind = boolean ? W_BOOL : W_UINT; v.number = *n;
    c->status = c->field(c->context, id, &v);
    if (c->status == GOLEM_OK && v.number > max) c->status = GOLEM_ERR_INVALID_ARGUMENT;
    if (c->reading && c->status == GOLEM_OK) *n = v.number;
}
#define NUM(id, member, max) do { \
    uint64_t n_ = (uint64_t)(member); number(c, id, &n_, max, false); \
    if (c->reading && c->status == GOLEM_OK) (member) = n_; \
} while (0)
#define BOOL(id, member) do { \
    uint64_t n_ = (member) ? 1 : 0; number(c, id, &n_, 1, true); \
    if (c->reading && c->status == GOLEM_OK) (member) = n_ != 0; \
} while (0)
static void text(golem_wire_codec *c, golem_wire_field id, char value[GOLEM_ADAPTER_ID_CAPACITY])
{
    if (c->status != GOLEM_OK) return;
    golem_wire_value v = {0}; v.kind = W_TEXT; memcpy(v.text, value, sizeof(v.text));
    c->status = c->field(c->context, id, &v);
    if (c->reading && c->status == GOLEM_OK) memcpy(value, v.text, sizeof(v.text));
}
static void digest(golem_wire_codec *c, golem_wire_field id, golem_digest *value)
{
    if (c->status != GOLEM_OK) return;
    golem_wire_value v = {0}; v.kind = W_DIGEST; v.digest = *value;
    c->status = c->field(c->context, id, &v);
    if (c->reading && c->status == GOLEM_OK) *value = v.digest;
}
static void request(golem_wire_codec *c, golem_adapter_request *r)
{
    NUM(W_VERSION, r->version, UINT32_MAX);
    text(c, W_REQUEST_ID, r->request_id); text(c, W_RUN_ID, r->run_id); text(c, W_ADAPTER_ID, r->adapter_id);
    NUM(W_STAGE, r->stage, GOLEM_STAGE_COUNT - 1);
    NUM(W_SEQUENCE, r->sequence, UINT64_MAX); NUM(W_ATTEMPT, r->attempt, UINT32_MAX);
    NUM(W_CONTEXT_VERSION, r->context.version, UINT32_MAX);
    NUM(W_CONTEXT_ALGORITHM, r->context.algorithm, GOLEM_DIGEST_SHA256);
    NUM(W_CONTEXT_SIZE, r->context.size, UINT64_MAX); digest(c, W_CONTEXT_DIGEST, &r->context.digest);
    BOOL(W_HAS_PREDECESSOR, r->has_predecessor); digest(c, W_PREDECESSOR_DIGEST, &r->predecessor);
}
void golem_wire_visit(golem_wire_codec *c, golem_adapter_envelope *e)
{
    NUM(W_TYPE, e->type, GOLEM_ADAPTER_STAGE_RESULT);
    if (e->type == GOLEM_ADAPTER_CAPABILITY) {
        golem_adapter_capability *p = &e->data.capability;
        NUM(W_VERSION, p->version, UINT32_MAX); text(c, W_ADAPTER_ID, p->adapter_id);
        NUM(W_STAGES, p->stages, UINT32_MAX); NUM(W_EFFECT, p->effect, GOLEM_EFFECT_EXTERNAL);
        BOOL(W_SIMULATION, p->simulation);
    } else if (e->type == GOLEM_ADAPTER_RUN_STAGE) request(c, &e->data.request);
    else if (e->type == GOLEM_ADAPTER_STAGE_RESULT) {
        golem_adapter_result *r = &e->data.result; request(c, &r->request);
        NUM(W_OUTCOME, r->outcome, GOLEM_STAGE_CANCELLED); NUM(W_FAILURE, r->failure, GOLEM_FAILURE_COUNT - 1);
        BOOL(W_SIMULATION, r->simulation);
        NUM(W_EVIDENCE_VERSION, r->evidence.version, UINT32_MAX);
        NUM(W_EVIDENCE_ALGORITHM, r->evidence.algorithm, GOLEM_DIGEST_SHA256);
        NUM(W_EVIDENCE_SIZE, r->evidence.size, UINT64_MAX); digest(c, W_EVIDENCE_DIGEST, &r->evidence.digest);
        NUM(W_INPUT_TOKENS, r->usage.usage.input_tokens, UINT64_MAX);
        NUM(W_CACHED_INPUT_TOKENS, r->usage.usage.cached_input_tokens, UINT64_MAX);
        NUM(W_OUTPUT_TOKENS, r->usage.usage.output_tokens, UINT64_MAX);
        NUM(W_REASONING_TOKENS, r->usage.usage.reasoning_tokens, UINT64_MAX);
        NUM(W_TOOL_CALLS, r->usage.usage.tool_calls, UINT64_MAX);
        NUM(W_NANO_COST, r->usage.nano_cost, UINT64_MAX);
        BOOL(W_USAGE_KNOWN, r->usage.usage_known); BOOL(W_COST_KNOWN, r->usage.cost_known);
    } else if (c->status == GOLEM_OK) c->status = GOLEM_ERR_INVALID_ARGUMENT;
    if (c->status == GOLEM_OK) c->status = golem_adapter_envelope_valid(e);
}
