#include "json.h"
#include <limits.h>
#include <string.h>

static bool members(struct json_object *o, size_t *count)
{
    if (json_object_is_type(o, json_type_string))
        return strlen(json_object_get_string(o)) == (size_t)json_object_get_string_len(o);
    if (json_object_is_type(o, json_type_array)) {
        for (size_t i = 0; i < json_object_array_length(o); ++i)
            if (!members(json_object_array_get_idx(o, i), count)) return false;
    } else if (json_object_is_type(o, json_type_object)) {
        *count += (size_t)json_object_object_length(o);
        json_object_object_foreach(o, key, value) {
            (void)key;
            if (!members(value, count)) return false;
        }
    }
    return true;
}
golem_status golem_json_parse(golem_bytes b, size_t limit, struct json_object **out)
{
    if (out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (b.data == NULL || b.size == 0 || b.size > limit || b.size > INT_MAX) return GOLEM_ERR_PARSE;
    bool quoted = false, escaped = false;
    size_t source = 0, decoded = 0;
    for (size_t i = 0; i < b.size; ++i) {
        unsigned char c = b.data[i];
        if (c == 0)
            return GOLEM_ERR_PARSE;
        if (escaped) { escaped = false; continue; }
        /* Reject decoded NUL, including object keys, but preserve an escaped
         * backslash followed by the ordinary characters u0000. */
        if (quoted && c == '\\' && i + 5 < b.size &&
            memcmp(b.data + i, "\\u0000", 6) == 0)
            return GOLEM_ERR_PARSE;
        if (quoted && c == '\\') { escaped = true; continue; }
        if (c == '"') quoted = !quoted;
        else if (!quoted && c == ':') ++source;
    }
    struct json_tokener *tok = json_tokener_new_ex(16);
    if (!tok) return GOLEM_ERR_OUT_OF_MEMORY;
    json_tokener_set_flags(tok, JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
    struct json_object *o = json_tokener_parse_ex(tok, (const char *)b.data, (int)b.size);
    bool valid = json_tokener_get_error(tok) == json_tokener_success && json_object_is_type(o, json_type_object);
    size_t end = json_tokener_get_parse_end(tok);
    for (size_t i = end; i < b.size; ++i)
        if (b.data[i] != ' ' && b.data[i] != '\t' && b.data[i] != '\r' && b.data[i] != '\n') valid = false;
    json_tokener_free(tok);
    if (!valid || !members(o, &decoded) || source != decoded) {
        json_object_put(o); return GOLEM_ERR_PARSE;
    }
    *out = o; return GOLEM_OK;
}
