#include "golem/policy.h"
#include <string.h>

_Static_assert(GOLEM_STAGE_COUNT == 6, "GPOL v1 has six stage permissions");
_Static_assert(GOLEM_AUTONOMY_DENY == 0 && GOLEM_AUTONOMY_AUTO_LOCAL == 1 &&
    GOLEM_AUTONOMY_ASK_ON_EXTERNAL_EFFECT == 2 && GOLEM_AUTONOMY_ASK_ALWAYS == 3,
    "GPOL v1 permission codes are stable");

golem_status golem_policy_artifact_encode(const golem_policy_artifact *a,
    void *buffer, size_t capacity, size_t *required)
{
    if (a == NULL || required == NULL || (buffer == NULL && capacity != 0) || a->revision == 0)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status s = golem_policy_spec_validate(&a->policy);
    if (s != GOLEM_OK) return s;
    if (capacity < GOLEM_POLICY_ARTIFACT_SIZE) {
        *required = GOLEM_POLICY_ARTIFACT_SIZE;
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    }
    uint8_t wire[GOLEM_POLICY_ARTIFACT_SIZE] = {'G', 'P', 'O', 'L', 1};
    for (size_t i = 0; i < 8; ++i) wire[8 + i] = (uint8_t)(a->revision >> (8 * i));
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) wire[16 + i] = (uint8_t)a->policy.permissions[i];
    memcpy(buffer, wire, sizeof(wire));
    *required = sizeof(wire);
    return GOLEM_OK;
}

golem_status golem_policy_artifact_decode(golem_bytes bytes, golem_policy_artifact *out)
{
    if (out == NULL || (bytes.data == NULL && bytes.size != 0)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (bytes.size != GOLEM_POLICY_ARTIFACT_SIZE || memcmp(bytes.data, "GPOL", 4) != 0)
        return GOLEM_ERR_PARSE;
    const uint8_t *p = bytes.data;
    if (p[4] != GOLEM_POLICY_ARTIFACT_VERSION || p[5] != 0) return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (p[6] != 0 || p[7] != 0) return GOLEM_ERR_PARSE;
    for (size_t i = 22; i < GOLEM_POLICY_ARTIFACT_SIZE; ++i)
        if (p[i] != 0) return GOLEM_ERR_PARSE;
    golem_policy_artifact a = {0};
    a.policy.version = GOLEM_POLICY_VERSION;
    for (size_t i = 0; i < 8; ++i) a.revision |= (uint64_t)p[8 + i] << (8 * i);
    if (a.revision == 0) return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) {
        if (p[16 + i] > GOLEM_AUTONOMY_ASK_ALWAYS) return GOLEM_ERR_PARSE;
        a.policy.permissions[i] = (golem_autonomy)p[16 + i];
    }
    *out = a;
    return GOLEM_OK;
}
