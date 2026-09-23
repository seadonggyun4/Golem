#include "context_internal.h"
#include <string.h>

golem_status cx_request(golem_bytes bytes, struct json_object **out)
{
    static const char *const keys[] = {"schema_version", "renderer_version", "recipe",
                                       "selection_id",   "target_kind",      "source_snapshot",
                                       "byte_budget",    "excerpt_bytes",    "token_budget",
                                       "tokenizer_id",   "agent_note"};
    struct json_object *input = NULL, *canonical = NULL;
    golem_status s = golem_json_parse(bytes, GOLEM_CONTEXT_REQUEST_MAX, &input);
    if (s != GOLEM_OK)
        return s;
    if (!dw_keys(input, keys, sizeof(keys) / sizeof(keys[0])))
        s = GOLEM_ERR_PARSE;
    const char *numbers[] = {"schema_version", "renderer_version", "byte_budget", "excerpt_bytes",
                             "token_budget"};
    for (size_t i = 0; s == GOLEM_OK && i < sizeof(numbers) / sizeof(numbers[0]); ++i) {
        struct json_object *v = dw_get(input, numbers[i]);
        if (!json_object_is_type(v, json_type_int) || json_object_get_int64(v) < 0)
            s = GOLEM_ERR_PARSE;
    }
    if (s == GOLEM_OK &&
        (dw_uint(input, "schema_version") != 1 || dw_uint(input, "renderer_version") != 1))
        s = GOLEM_ERR_UNSUPPORTED_VERSION;
    const char *strings[] = {"recipe",          "selection_id", "target_kind",
                             "source_snapshot", "tokenizer_id", "agent_note"};
    for (size_t i = 0; s == GOLEM_OK && i < sizeof(strings) / sizeof(strings[0]); ++i)
        if (!json_object_is_type(dw_get(input, strings[i]), json_type_string))
            s = GOLEM_ERR_PARSE;
    golem_digest source;
    if (s == GOLEM_OK && strcmp(dw_text(input, "recipe"), "extractive-v1") &&
        strcmp(dw_text(input, "recipe"), "original-v1"))
        s = GOLEM_ERR_UNSUPPORTED_VERSION;
    if (s == GOLEM_OK &&
        (!dw_id(dw_text(input, "selection_id")) || wf_kind(dw_text(input, "target_kind")) < 0 ||
         !dw_digest(input, "source_snapshot", &source) || !dw_uint(input, "byte_budget") ||
         dw_uint(input, "byte_budget") > GOLEM_CONTEXT_MAX ||
         dw_uint(input, "excerpt_bytes") > GOLEM_DOCUMENT_MAX_BODY ||
         !dw_id(dw_text(input, "tokenizer_id")) || strlen(dw_text(input, "agent_note")) > 16384 ||
         (!dw_uint(input, "token_budget") && strcmp(dw_text(input, "tokenizer_id"), "none")) ||
         (dw_uint(input, "token_budget") && !strcmp(dw_text(input, "tokenizer_id"), "none"))))
        s = GOLEM_ERR_PARSE;
    if (s == GOLEM_OK) {
        canonical = json_object_new_object();
        if (!canonical)
            s = GOLEM_ERR_OUT_OF_MEMORY;
    }
    for (size_t i = 0; s == GOLEM_OK && i < sizeof(keys) / sizeof(keys[0]); ++i)
        if (!dw_add(canonical, keys[i], json_object_get(dw_get(input, keys[i]))))
            s = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(input);
    if (s == GOLEM_OK)
        *out = canonical;
    else
        json_object_put(canonical);
    return s;
}
golem_status golem_context_request_validate(golem_bytes request, golem_diagnostic *d)
{
    struct json_object *o = NULL;
    golem_status s = cx_request(request, &o);
    json_object_put(o);
    return dw_report(d, s, NULL);
}
