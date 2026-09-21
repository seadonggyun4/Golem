#include "work.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

const char *cli_json_text(struct json_object *o)
{
    if (!json_object_is_type(o, json_type_string)) return NULL;
    const char *s = json_object_get_string(o);
    return strlen(s) == (size_t)json_object_get_string_len(o) ? s : NULL;
}
static bool members(struct json_object *o, size_t *count)
{
    if (json_object_is_type(o, json_type_string)) return cli_json_text(o) != NULL;
    if (json_object_is_type(o, json_type_array)) {
        for (size_t i = 0; i < json_object_array_length(o); ++i)
            if (!members(json_object_array_get_idx(o, i), count)) return false;
    } else if (json_object_is_type(o, json_type_object)) {
        *count += (size_t)json_object_object_length(o);
        json_object_object_foreach(o, key, value) { (void)key; if (!members(value, count)) return false; }
    }
    return true;
}
golem_status cli_json_parse(golem_bytes data, struct json_object **out)
{
    if (data.data == NULL || data.size == 0 || data.size > CLI_BUNDLE_MAX) return GOLEM_ERR_PARSE;
    bool quoted = false, escaped = false; size_t source_members = 0;
    for (size_t i = 0; i < data.size; ++i) {
        uint8_t ch = data.data[i];
        if (ch == 0 || (ch == '\\' && i + 5 < data.size && memcmp(data.data + i, "\\u0000", 6) == 0)) return GOLEM_ERR_PARSE;
        if (escaped) { escaped = false; continue; }
        if (quoted && ch == '\\') { escaped = true; continue; }
        if (ch == '"') quoted = !quoted;
        else if (!quoted && ch == ':') ++source_members;
    }
    struct json_tokener *tok = json_tokener_new_ex(16);
    if (tok == NULL) return GOLEM_ERR_OUT_OF_MEMORY;
    json_tokener_set_flags(tok, JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
    struct json_object *o = json_tokener_parse_ex(tok, (const char *)data.data, (int)data.size);
    bool valid = json_tokener_get_error(tok) == json_tokener_success && json_object_is_type(o, json_type_object);
    size_t end = json_tokener_get_parse_end(tok), decoded_members = 0;
    for (size_t i = end; i < data.size; ++i)
        if (data.data[i] != ' ' && data.data[i] != '\t' && data.data[i] != '\n' && data.data[i] != '\r') valid = false;
    json_tokener_free(tok);
    /* Total member counts also detect duplicate keys in nested objects: json-c
     * keeps only the last occurrence and its subtree. */
    if (!valid || !members(o, &decoded_members) || decoded_members != source_members) {
        json_object_put(o); return GOLEM_ERR_PARSE;
    }
    *out = o; return GOLEM_OK;
}
bool cli_json_keys(struct json_object *o, const char *const *keys, size_t count)
{
    if (!json_object_is_type(o, json_type_object)) return false;
    json_object_object_foreach(o, key, value) {
        (void)value; bool found = false;
        for (size_t i = 0; i < count; ++i) if (strcmp(keys[i], key) == 0) found = true;
        if (!found) return false;
    }
    return true;
}
bool cli_json_add(struct json_object *o, const char *key, struct json_object *value)
{
    if (o == NULL || value == NULL || json_object_object_add(o, key, value) != 0) { json_object_put(value); return false; }
    return true;
}
bool cli_json_append(struct json_object *o, struct json_object *value)
{
    if (o == NULL || value == NULL || json_object_array_add(o, value) != 0) { json_object_put(value); return false; }
    return true;
}
struct json_object *cli_json_u64(uint64_t value)
{
    char text[32]; (void)snprintf(text, sizeof(text), "%" PRIu64, value); return json_object_new_string(text);
}
