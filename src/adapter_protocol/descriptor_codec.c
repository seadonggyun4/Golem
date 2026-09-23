#include "descriptor_internal.h"
#include <stdlib.h>
#include <string.h>

static struct json_object *get(struct json_object *o, const char *key)
{
    struct json_object *v = NULL;
    (void)json_object_object_get_ex(o, key, &v);
    return v;
}
static bool add(struct json_object *o, const char *key, struct json_object *value)
{
    if (!o || !value || json_object_object_add(o, key, value) != 0) {
        json_object_put(value);
        return false;
    }
    return true;
}
static bool number(struct json_object *o, const char *key, uint32_t *out)
{
    struct json_object *v = get(o, key);
    if (!json_object_is_type(v, json_type_int) || json_object_get_int64(v) < 0 ||
        json_object_get_uint64(v) > UINT32_MAX)
        return false;
    *out = (uint32_t)json_object_get_uint64(v);
    return true;
}
static bool text(struct json_object *o, const char *key, char *out, size_t cap)
{
    struct json_object *v = get(o, key);
    if (!json_object_is_type(v, json_type_string) || (size_t)json_object_get_string_len(v) >= cap)
        return false;
    strcpy(out, json_object_get_string(v));
    return true;
}
static int compare_tools(const void *a, const void *b)
{
    return strcmp(((const golem_harness_tool *)a)->id, ((const golem_harness_tool *)b)->id);
}
golem_status golem_adapter_descriptor_decode(golem_bytes bytes, golem_adapter_descriptor *out)
{
    if (!out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = NULL;
    golem_status s = golem_json_parse(bytes, GOLEM_DESCRIPTOR_MAX_BYTES, &o);
    if (s != GOLEM_OK)
        return s;
    golem_adapter_descriptor d = {0};
    uint32_t current, simulation, hidden, sandbox, effect;
    char domain[64];
    if (json_object_object_length(o) != 17 || !text(o, "domain", domain, sizeof(domain)) ||
        strcmp(domain, "golem.adapter-descriptor.v1") || !number(o, "schema_version", &d.version) ||
        !number(o, "protocol_version", &d.protocol_version) ||
        !text(o, "adapter_id", d.adapter_id, sizeof(d.adapter_id)) ||
        !text(o, "adapter_version", d.adapter_version, sizeof(d.adapter_version)) ||
        !text(o, "session_id", d.session_id, sizeof(d.session_id)) ||
        !number(o, "current_agent", &current) || current > 1 || !number(o, "stages", &d.stages) ||
        !number(o, "features_known", &d.features_known) ||
        !number(o, "features_supported", &d.features_supported) ||
        !number(o, "inputs_known", &d.inputs_known) ||
        !number(o, "inputs_supported", &d.inputs_supported) ||
        !number(o, "simulation", &simulation) || simulation > GOLEM_HARNESS_YES ||
        !number(o, "hidden_prompt_known", &hidden) || hidden > GOLEM_HARNESS_YES ||
        !number(o, "sandbox", &sandbox) || sandbox > GOLEM_SANDBOX_VM ||
        !number(o, "effect", &effect) || effect > GOLEM_EFFECT_EXTERNAL)
        s = GOLEM_ERR_PARSE;
    struct json_object *tools = get(o, "tools");
    if (s == GOLEM_OK && (!json_object_is_type(tools, json_type_array) ||
                          json_object_array_length(tools) > GOLEM_DESCRIPTOR_MAX_TOOLS))
        s = GOLEM_ERR_PARSE;
    if (s == GOLEM_OK) {
        d.current_agent = current != 0;
        d.simulation = (golem_harness_truth)simulation;
        d.hidden_prompt_known = (golem_harness_truth)hidden;
        d.sandbox = (golem_harness_sandbox)sandbox;
        d.effect = (golem_effect)effect;
        d.tool_count = json_object_array_length(tools);
        for (size_t i = 0; s == GOLEM_OK && i < d.tool_count; ++i) {
            struct json_object *tool = json_object_array_get_idx(tools, i);
            char hex[GOLEM_DIGEST_HEX_CAPACITY];
            if (!json_object_is_type(tool, json_type_object) ||
                json_object_object_length(tool) != 2 ||
                !text(tool, "id", d.tools[i].id, sizeof(d.tools[i].id)) ||
                !text(tool, "digest", hex, sizeof(hex)) ||
                golem_digest_parse((golem_string_view){hex, strlen(hex)}, &d.tools[i].digest) !=
                    GOLEM_OK)
                s = GOLEM_ERR_PARSE;
        }
    }
    if (s == GOLEM_OK)
        s = golem_adapter_descriptor_validate(&d);
    if (s == GOLEM_OK) {
        qsort(d.tools, d.tool_count, sizeof(*d.tools), compare_tools);
        *out = d;
    }
    json_object_put(o);
    return s;
}
golem_status golem_descriptor_object(const golem_adapter_descriptor *input,
                                     struct json_object **out)
{
    golem_status s = golem_adapter_descriptor_validate(input);
    if (s != GOLEM_OK)
        return s;
    golem_adapter_descriptor d = *input;
    qsort(d.tools, d.tool_count, sizeof(*d.tools), compare_tools);
    struct json_object *o = json_object_new_object(), *tools = json_object_new_array();
    if (!o || !tools) {
        json_object_put(o);
        json_object_put(tools);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    /* Fixed lexical key order and sorted tool IDs define this schema's digest.
     * This is not a general JSON canonicalization algorithm. */
    bool ok = add(o, "adapter_id", json_object_new_string(d.adapter_id)) &&
              add(o, "adapter_version", json_object_new_string(d.adapter_version)) &&
              add(o, "current_agent", json_object_new_int(d.current_agent ? 1 : 0)) &&
              add(o, "domain", json_object_new_string("golem.adapter-descriptor.v1")) &&
              add(o, "effect", json_object_new_int((int)d.effect)) &&
              add(o, "features_known", json_object_new_int64(d.features_known)) &&
              add(o, "features_supported", json_object_new_int64(d.features_supported)) &&
              add(o, "hidden_prompt_known", json_object_new_int((int)d.hidden_prompt_known)) &&
              add(o, "inputs_known", json_object_new_int64(d.inputs_known)) &&
              add(o, "inputs_supported", json_object_new_int64(d.inputs_supported)) &&
              add(o, "protocol_version", json_object_new_int64(d.protocol_version)) &&
              add(o, "sandbox", json_object_new_int((int)d.sandbox)) &&
              add(o, "schema_version", json_object_new_int64(d.version)) &&
              add(o, "session_id", json_object_new_string(d.session_id)) &&
              add(o, "simulation", json_object_new_int((int)d.simulation)) &&
              add(o, "stages", json_object_new_int64(d.stages));
    for (size_t i = 0; ok && i < d.tool_count; ++i) {
        char hex[GOLEM_DIGEST_HEX_CAPACITY];
        size_t n;
        s = golem_digest_format(&d.tools[i].digest, hex, sizeof(hex), &n);
        struct json_object *tool = json_object_new_object();
        ok = s == GOLEM_OK && tool && add(tool, "digest", json_object_new_string(hex)) &&
             add(tool, "id", json_object_new_string(d.tools[i].id));
        if (!ok || json_object_array_add(tools, tool) != 0) {
            json_object_put(tool);
            ok = false;
        }
    }
    if (ok) {
        ok = add(o, "tools", tools);
        tools = NULL;
    }
    json_object_put(tools);
    if (!ok) {
        json_object_put(o);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    *out = o;
    return GOLEM_OK;
}
golem_status golem_descriptor_copy_json(struct json_object *o, void *buffer, size_t capacity,
                                        size_t *required)
{
    if (!required || (!buffer && capacity))
        return GOLEM_ERR_INVALID_ARGUMENT;
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (!text)
        return GOLEM_ERR_OUT_OF_MEMORY;
    size_t n = strlen(text);
    if (n > GOLEM_DESCRIPTOR_MAX_BYTES)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    *required = n;
    if (capacity < n)
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    memcpy(buffer, text, n);
    return GOLEM_OK;
}
golem_status golem_adapter_descriptor_encode(const golem_adapter_descriptor *d, void *buffer,
                                             size_t capacity, size_t *required)
{
    struct json_object *o = NULL;
    golem_status s = golem_descriptor_object(d, &o);
    if (s == GOLEM_OK)
        s = golem_descriptor_copy_json(o, buffer, capacity, required);
    json_object_put(o);
    return s;
}
golem_status golem_adapter_descriptor_digest(const golem_adapter_descriptor *d, golem_digest *out)
{
    if (!out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    uint8_t buffer[GOLEM_DESCRIPTOR_MAX_BYTES];
    size_t n;
    golem_status s = golem_adapter_descriptor_encode(d, buffer, sizeof(buffer), &n);
    if (s == GOLEM_OK)
        s = golem_digest_bytes((golem_bytes){buffer, n}, out);
    return s;
}
