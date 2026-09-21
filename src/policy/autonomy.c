#include "golem/policy.h"

struct golem_policy {
    golem_allocator allocator;
    golem_policy_spec spec;
};

static bool mode_valid(golem_autonomy mode)
{
    return mode >= GOLEM_AUTONOMY_DENY && mode <= GOLEM_AUTONOMY_ASK_ALWAYS;
}
static bool request_valid(const golem_policy_request *r)
{
    return r != NULL && r->stage >= GOLEM_STAGE_PLANNING && r->stage < GOLEM_STAGE_COUNT &&
        r->effect >= GOLEM_EFFECT_UNKNOWN && r->effect <= GOLEM_EFFECT_EXTERNAL &&
        r->authorization >= GOLEM_AUTHORIZATION_NONE && r->authorization <= GOLEM_AUTHORIZATION_REJECTED;
}
golem_status golem_policy_spec_init(golem_policy_spec *out)
{
    if (out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    *out = (golem_policy_spec){0};
    out->version = GOLEM_POLICY_VERSION;
    return GOLEM_OK;
}
golem_status golem_policy_spec_validate(const golem_policy_spec *spec)
{
    if (spec == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (spec->version != GOLEM_POLICY_VERSION) return GOLEM_ERR_UNSUPPORTED_VERSION;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i)
        if (!mode_valid(spec->permissions[i])) return GOLEM_ERR_INVALID_ARGUMENT;
    return GOLEM_OK;
}
golem_status golem_policy_create(const golem_policy_spec *spec, const golem_allocator *allocator,
    golem_policy **out, golem_diagnostic *d)
{
    golem_status status = GOLEM_ERR_INVALID_ARGUMENT;
    if (out != NULL && golem_allocator_validate(allocator) == GOLEM_OK) {
        status = golem_policy_spec_validate(spec);
        void *memory = NULL;
        if (status == GOLEM_OK) status = golem_allocator_alloc(allocator, sizeof(golem_policy), &memory);
        if (status == GOLEM_OK) {
            golem_policy *p = memory;
            *p = (golem_policy){allocator == NULL ? golem_allocator_default() : *allocator, *spec};
            *out = p;
        }
    }
    if (d != NULL) (void)golem_diagnostic_set(d, status, GOLEM_DIAGNOSTIC_NO_OFFSET, NULL);
    return status;
}
void golem_policy_free(golem_policy *policy)
{
    if (policy != NULL) (void)golem_allocator_free(&policy->allocator, policy);
}
golem_status golem_policy_spec_get(const golem_policy *policy, golem_policy_spec *out)
{
    if (policy == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    *out = policy->spec; return GOLEM_OK;
}

golem_status golem_autonomy_evaluate(golem_autonomy mode, const golem_policy_request *r,
    golem_policy_decision *out)
{
    if (!mode_valid(mode) || !request_valid(r) || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_policy_decision result = {GOLEM_POLICY_VERSION, GOLEM_POLICY_DENY,
        GOLEM_POLICY_STAGE_DENIED, mode, *r};
    if (mode == GOLEM_AUTONOMY_DENY) result.reason = GOLEM_POLICY_STAGE_DENIED;
    else if (r->effect == GOLEM_EFFECT_UNKNOWN) result.reason = GOLEM_POLICY_EFFECT_UNKNOWN;
    else if (r->authorization == GOLEM_AUTHORIZATION_REJECTED) result.reason = GOLEM_POLICY_AUTHORIZATION_REJECTED;
    else if (mode == GOLEM_AUTONOMY_ASK_ALWAYS || r->effect == GOLEM_EFFECT_EXTERNAL) {
        result.verdict = r->authorization == GOLEM_AUTHORIZATION_GRANTED ? GOLEM_POLICY_ALLOW : GOLEM_POLICY_ASK;
        result.reason = r->authorization == GOLEM_AUTHORIZATION_GRANTED ? GOLEM_POLICY_APPROVED :
            (mode == GOLEM_AUTONOMY_ASK_ALWAYS ? GOLEM_POLICY_ALWAYS_ASK : GOLEM_POLICY_EXTERNAL_ASK);
    } else {
        result.verdict = GOLEM_POLICY_ALLOW;
        result.reason = GOLEM_POLICY_LOCAL_ALLOWED;
    }
    *out = result; return GOLEM_OK;
}
golem_status golem_policy_evaluate(const golem_policy *policy, const golem_policy_request *r,
    golem_policy_decision *out)
{
    if (policy == NULL || !request_valid(r)) return GOLEM_ERR_INVALID_ARGUMENT;
    return golem_autonomy_evaluate(policy->spec.permissions[r->stage], r, out);
}
const char *golem_policy_verdict_name(golem_policy_verdict verdict)
{
    switch (verdict) {
    case GOLEM_POLICY_DENY: return "DENY";
    case GOLEM_POLICY_ASK: return "ASK";
    case GOLEM_POLICY_ALLOW: return "ALLOW";
    default: return "unknown";
    }
}
const char *golem_policy_reason_name(golem_policy_reason reason)
{
    switch (reason) {
    case GOLEM_POLICY_STAGE_DENIED: return "stage_denied";
    case GOLEM_POLICY_EFFECT_UNKNOWN: return "effect_unknown";
    case GOLEM_POLICY_AUTHORIZATION_REJECTED: return "authorization_rejected";
    case GOLEM_POLICY_ALWAYS_ASK: return "always_ask";
    case GOLEM_POLICY_EXTERNAL_ASK: return "external_ask";
    case GOLEM_POLICY_APPROVED: return "approved";
    case GOLEM_POLICY_LOCAL_ALLOWED: return "local_allowed";
    default: return "unknown";
    }
}
