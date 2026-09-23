#include "profile_internal.h"
#include <string.h>

static bool bounded_text(struct json_object *o, const char *key, bool empty)
{
    struct json_object *v = dw_get(o, key);
    const char *s = dw_text(o, key);
    if (!json_object_is_type(v, json_type_string) || strlen(s) > 256 || (!empty && !*s))
        return false;
    for (; *s; ++s)
        if ((unsigned char)*s < 32 || (unsigned char)*s == 127)
            return false;
    return true;
}

static golem_status schema(struct json_object *o)
{
    const char *keys[] = {"schema_version",
                          "domain",
                          "engine_abi",
                          "engine_build_digest",
                          "adapter_executable_digest",
                          "adapter_descriptor_digest",
                          "config_digest",
                          "policy_digest",
                          "platform",
                          "provider_reported",
                          "model_reported",
                          "provider_observed",
                          "model_observed",
                          "observation_digest",
                          "restore_level",
                          "tools"};
    if (!dw_keys(o, keys, sizeof(keys) / sizeof(*keys)))
        return GOLEM_ERR_PARSE;
    if (dw_uint(o, "schema_version") != 1 ||
        strcmp(dw_text(o, "domain"), "golem.runtime-profile.v1"))
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    const char *hashes[] = {"engine_build_digest", "adapter_executable_digest",
                            "adapter_descriptor_digest", "config_digest", "policy_digest"};
    golem_digest digest;
    for (size_t i = 0; i < sizeof(hashes) / sizeof(*hashes); ++i)
        if (!dw_digest(o, hashes[i], &digest))
            return GOLEM_ERR_PARSE;
    const char *strings[] = {"platform", "provider_reported", "model_reported"};
    for (size_t i = 0; i < sizeof(strings) / sizeof(*strings); ++i)
        if (!bounded_text(o, strings[i], false))
            return GOLEM_ERR_PARSE;
    if (!dw_uint(o, "engine_abi") || dw_uint(o, "engine_abi") > UINT32_MAX ||
        !bounded_text(o, "provider_observed", true) || !bounded_text(o, "model_observed", true) ||
        !bounded_text(o, "observation_digest", true))
        return GOLEM_ERR_PARSE;
    bool observed = *dw_text(o, "observation_digest") != 0;
    if (observed != (*dw_text(o, "provider_observed") != 0) ||
        observed != (*dw_text(o, "model_observed") != 0) ||
        (observed && !dw_digest(o, "observation_digest", &digest)))
        return GOLEM_ERR_PARSE;
    const char *restore = dw_text(o, "restore_level");
    if (strcmp(restore, "IDENTITY_ONLY") && strcmp(restore, "LOCAL_ARTIFACTS_AVAILABLE"))
        return GOLEM_ERR_PARSE;
    struct json_object *tools = dw_get(o, "tools");
    if (!json_object_is_type(tools, json_type_array) ||
        json_object_array_length(tools) > GOLEM_RUNTIME_PROFILE_MAX_TOOLS)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    for (size_t i = 0; i < json_object_array_length(tools); ++i) {
        struct json_object *tool = json_object_array_get_idx(tools, i);
        const char *tk[] = {"id", "digest"};
        if (!dw_keys(tool, tk, 2) || !dw_id(dw_text(tool, "id")) ||
            !dw_digest(tool, "digest", &digest))
            return GOLEM_ERR_PARSE;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(dw_text(tool, "id"), dw_text(json_object_array_get_idx(tools, j), "id")))
                return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}

golem_status golem_runtime_profile_parse(golem_bytes bytes, const golem_allocator *allocator,
                                         golem_runtime_profile **out, golem_diagnostic *diagnostic)
{
    if (!out || golem_allocator_validate(allocator) != GOLEM_OK)
        return dw_report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *input = NULL, *canonical = NULL;
    golem_status status = golem_json_parse(bytes, GOLEM_RUNTIME_PROFILE_MAX_BYTES, &input);
    if (status == GOLEM_OK)
        status = schema(input);
    if (status == GOLEM_OK)
        status = rp_canonical(input, &canonical);
    golem_digest digest;
    const char *text =
        canonical ? json_object_to_json_string_ext(canonical, JSON_C_TO_STRING_PLAIN) : NULL;
    if (status == GOLEM_OK && (!text || strlen(text) > GOLEM_RUNTIME_PROFILE_MAX_BYTES))
        status = GOLEM_ERR_BUDGET_EXHAUSTED;
    if (status == GOLEM_OK)
        status = golem_digest_bytes((golem_bytes){(const uint8_t *)text, strlen(text)}, &digest);
    void *memory = NULL;
    if (status == GOLEM_OK)
        status = golem_allocator_alloc(allocator, sizeof(golem_runtime_profile), &memory);
    if (status == GOLEM_OK) {
        golem_runtime_profile *p = memory;
        *p = (golem_runtime_profile){allocator ? *allocator : golem_allocator_default(), canonical,
                                     digest};
        canonical = NULL;
        *out = p;
    }
    json_object_put(input);
    json_object_put(canonical);
    return dw_report(diagnostic, status, NULL);
}

void golem_runtime_profile_free(golem_runtime_profile *p)
{
    if (!p)
        return;
    golem_allocator allocator = p->allocator;
    json_object_put(p->object);
    (void)golem_allocator_free(&allocator, p);
}

golem_status golem_runtime_profile_digest(const golem_runtime_profile *p, golem_digest *out)
{
    if (!p || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    *out = p->digest;
    return GOLEM_OK;
}

golem_status golem_runtime_profile_encode(const golem_runtime_profile *p, void *buffer,
                                          size_t capacity, size_t *required)
{
    if (!p || !required || (!buffer && capacity))
        return GOLEM_ERR_INVALID_ARGUMENT;
    const char *text = json_object_to_json_string_ext(p->object, JSON_C_TO_STRING_PLAIN);
    if (!text)
        return GOLEM_ERR_OUT_OF_MEMORY;
    size_t n = strlen(text);
    *required = n;
    if (capacity < n)
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    memcpy(buffer, text, n);
    return GOLEM_OK;
}
