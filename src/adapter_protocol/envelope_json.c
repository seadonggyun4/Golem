#include "schema.h"
#include <json-c/json.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

typedef struct json_codec { struct json_object *object; bool reading; size_t fields; } json_codec;
static golem_status field(void *context, golem_wire_field id, golem_wire_value *v)
{
    json_codec *c = context; ++c->fields;
    const char *key = golem_wire_name(id);
    char text[GOLEM_ADAPTER_ID_CAPACITY];
    if (!c->reading) {
        if (v->kind == W_TEXT) strcpy(text, v->text);
        else if (v->kind == W_DIGEST) {
            size_t required; (void)golem_digest_format(&v->digest, text, sizeof(text), &required);
        } else (void)snprintf(text, sizeof(text), "%" PRIu64, v->number);
        struct json_object *value = json_object_new_string(text);
        if (value == NULL) return GOLEM_ERR_OUT_OF_MEMORY;
        if (json_object_object_add(c->object, key, value) != 0) {
            json_object_put(value); return GOLEM_ERR_OUT_OF_MEMORY;
        }
        return GOLEM_OK;
    }
    struct json_object *value = NULL;
    if (!json_object_object_get_ex(c->object, key, &value) || !json_object_is_type(value, json_type_string))
        return GOLEM_ERR_INVALID_ARGUMENT;
    size_t n = (size_t)json_object_get_string_len(value);
    const char *s = json_object_get_string(value);
    if (n >= sizeof(text) || strlen(s) != n) return GOLEM_ERR_INVALID_ARGUMENT;
    if (v->kind == W_TEXT) { memcpy(v->text, s, n + 1); return GOLEM_OK; }
    if (v->kind == W_DIGEST) return golem_digest_parse((golem_string_view){s, n}, &v->digest);
    if (n == 0 || (s[0] == '0' && n != 1)) return GOLEM_ERR_INVALID_ARGUMENT;
    uint64_t number = 0;
    for (size_t i = 0; i < n; ++i) {
        unsigned char digit = (unsigned char)s[i];
        if (digit < '0' || digit > '9' || number > UINT64_MAX / 10 ||
            (number == UINT64_MAX / 10 && (uint64_t)(digit - '0') > UINT64_MAX % 10)) return GOLEM_ERR_INVALID_ARGUMENT;
        number = number * 10 + (uint64_t)(digit - '0');
    }
    v->number = number; return GOLEM_OK;
}
golem_status golem_adapter_envelope_encode(const golem_adapter_envelope *e,
    char *buffer, size_t capacity, size_t *required, golem_diagnostic *d)
{
    if (e == NULL || required == NULL || (buffer == NULL && capacity != 0))
        return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    golem_status s = golem_adapter_envelope_valid(e);
    if (s != GOLEM_OK) return golem_adapter_report(d, s);
    json_codec json = {json_object_new_object(), false, 0};
    if (json.object == NULL) return golem_adapter_report(d, GOLEM_ERR_OUT_OF_MEMORY);
    golem_wire_codec c = {&json, false, GOLEM_OK, field};
    golem_adapter_envelope copy = *e; golem_wire_visit(&c, &copy);
    if (c.status == GOLEM_OK) {
        const char *text = json_object_to_json_string_ext(json.object, JSON_C_TO_STRING_PLAIN);
        if (text == NULL) c.status = GOLEM_ERR_OUT_OF_MEMORY;
        else {
            size_t n = strlen(text) + 1;
            if (capacity < n) { *required = n; c.status = GOLEM_ERR_BUFFER_TOO_SMALL; }
            else { memcpy(buffer, text, n); *required = n; }
        }
    }
    json_object_put(json.object); return golem_adapter_report(d, c.status);
}
golem_status golem_adapter_envelope_decode(golem_bytes bytes,
    golem_adapter_envelope *out, golem_diagnostic *d)
{
    if (out == NULL || bytes.data == NULL || bytes.size == 0 || bytes.size > GOLEM_ADAPTER_JSON_MAX)
        return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    /* json-c keeps the last duplicate key. Count flat source members separately. */
    bool quoted = false, escaped = false; size_t members = 0;
    for (size_t i = 0; i < bytes.size; ++i) {
        unsigned char ch = bytes.data[i];
        if (ch == 0 || (ch == '\\' && i + 5 < bytes.size && memcmp(bytes.data + i, "\\u0000", 6) == 0))
            return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
        if (escaped) { escaped = false; continue; }
        if (quoted && ch == '\\') { escaped = true; continue; }
        if (ch == '"') quoted = !quoted;
        else if (!quoted && ch == ':') ++members;
    }
    struct json_tokener *tok = json_tokener_new_ex(4);
    if (tok == NULL) return golem_adapter_report(d, GOLEM_ERR_OUT_OF_MEMORY);
    json_tokener_set_flags(tok, JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
    struct json_object *object = json_tokener_parse_ex(tok, (const char *)bytes.data, (int)bytes.size);
    bool valid = json_tokener_get_error(tok) == json_tokener_success && json_object_is_type(object, json_type_object);
    size_t end = json_tokener_get_parse_end(tok);
    for (size_t i = end; i < bytes.size; ++i)
        if (bytes.data[i] != ' ' && bytes.data[i] != '\t' && bytes.data[i] != '\r' && bytes.data[i] != '\n') valid = false;
    json_tokener_free(tok);
    json_codec json = {object, true, 0};
    golem_wire_codec c = {&json, true, GOLEM_ERR_INVALID_ARGUMENT, field};
    golem_adapter_envelope e = {0};
    if (valid && members == (size_t)json_object_object_length(object)) {
        c.status = GOLEM_OK; golem_wire_visit(&c, &e);
        if (json.fields != members) c.status = GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (c.status == GOLEM_OK) *out = e;
    json_object_put(object); return golem_adapter_report(d, c.status);
}
