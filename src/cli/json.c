#include "work.h"
#include "../common/json.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

const char *cli_json_text(struct json_object *o)
{
    if (!json_object_is_type(o, json_type_string)) return NULL;
    const char *s = json_object_get_string(o);
    return strlen(s) == (size_t)json_object_get_string_len(o) ? s : NULL;
}
golem_status cli_json_parse(golem_bytes data, struct json_object **out)
{
    return golem_json_parse(data, CLI_BUNDLE_MAX, out);
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
