#include "golem/workpack.h"
#include "../common/json.h"
#include <string.h>

static const char *string(struct json_object *o, const char *key)
{
    struct json_object *v = NULL;
    if (!json_object_object_get_ex(o, key, &v) || !json_object_is_type(v, json_type_string)) return NULL;
    return json_object_get_string(v);
}
static bool identifier(const char *s)
{
    if (!s || !*s || strlen(s) > 128) return false;
    bool start = true;
    for (; *s; ++s) {
        if (*s == '.') { if (start) return false; start = true; continue; }
        if (start) { if (*s < 'a' || *s > 'z') return false; }
        else if (!((*s >= 'a' && *s <= 'z') || (*s >= '0' && *s <= '9') || *s == '-')) return false;
        start = false;
    }
    return !start;
}
static bool version(const char *s, uint64_t *out)
{
    if (!s || strlen(s) > 17) return false;
    uint64_t packed = 0;
    for (size_t part = 0; part < 3; ++part) {
        if (*s < '0' || *s > '9' || (*s == '0' && s[1] >= '0' && s[1] <= '9')) return false;
        uint32_t value = 0;
        do {
            value = value * 10u + (uint32_t)(*s++ - '0');
            if (value > 65535u) return false;
        } while (*s >= '0' && *s <= '9');
        packed = (packed << 16) | value;
        if (part < 2) { if (*s++ != '.') return false; }
        else if (*s) return false;
    }
    *out = packed; return true;
}
static bool text(const char *s)
{
    if (!s || !*s || strlen(s) > 256) return false;
    bool meaningful = false;
    for (; *s; ++s) {
        unsigned char ch = (unsigned char)*s;
        if (ch < 32 || ch == 127) return false;
        if (ch > 32) meaningful = true;
    }
    return meaningful;
}
static bool list(struct json_object *o, const char *key, size_t max, bool ids)
{
    struct json_object *a = NULL;
    if (!json_object_object_get_ex(o, key, &a) || !json_object_is_type(a, json_type_array)) return false;
    size_t count = json_object_array_length(a);
    if (!count || count > max) return false;
    for (size_t i = 0; i < count; ++i) {
        struct json_object *v = json_object_array_get_idx(a, i);
        if (!json_object_is_type(v, json_type_string)) return false;
        const char *s = json_object_get_string(v);
        if (!(ids ? identifier(s) : text(s))) return false;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(s, json_object_get_string(json_object_array_get_idx(a, j)))) return false;
    }
    return true;
}
static bool equals(struct json_object *o, const char *key, const char *expected)
{
    const char *s = string(o, key); return s && !strcmp(s, expected);
}
static golem_status report(golem_diagnostic *d, golem_status status, const char *tag)
{
    if (d) (void)golem_diagnostic_set(d, status, GOLEM_DIAGNOSTIC_NO_OFFSET, tag);
    return status;
}
golem_status golem_workpack_validate(golem_bytes input, golem_digest *digest, golem_diagnostic *diagnostic)
{
    if (!digest) return report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, "PACK_OUTPUT");
    struct json_object *o = NULL;
    golem_status status = golem_json_parse(input, GOLEM_WORKPACK_MAX_JSON, &o);
    if (status != GOLEM_OK) return report(diagnostic, status, "PACK_JSON");
    const char *tag = "PACK_FIELDS";
    const char *keys[] = {"schema", "id", "version", "status", "core_min", "core_max", "publisher",
        "provenance", "intent", "negative_intent", "roles", "capabilities", "prohibited_effects",
        "inputs", "evidence", "completion", "freshness", "recovery"};
    status = GOLEM_ERR_PARSE;
    if (json_object_object_length(o) != (int)(sizeof(keys) / sizeof(*keys))) goto done;
    for (size_t i = 0; i < sizeof(keys) / sizeof(*keys); ++i) {
        struct json_object *v = NULL;
        if (!json_object_object_get_ex(o, keys[i], &v)) goto done;
    }
    tag = "PACK_SCHEMA";
    if (!string(o, "schema")) goto done;
    if (!equals(o, "schema", GOLEM_WORKPACK_SCHEMA)) { status = GOLEM_ERR_UNSUPPORTED_VERSION; goto done; }
    tag = "PACK_ID";
    if (!identifier(string(o, "id")) || !identifier(string(o, "publisher"))) goto done;
    tag = "PACK_VERSION";
    uint64_t ver, min, max;
    if (!version(string(o, "version"), &ver) || !version(string(o, "core_min"), &min) ||
        !version(string(o, "core_max"), &max) || min > max) goto done;
    tag = "PACK_DECLARATION";
    const char *provenance = string(o, "provenance");
    golem_digest ignored;
    if (!provenance || golem_digest_parse((golem_string_view){provenance, strlen(provenance)}, &ignored) != GOLEM_OK ||
        !equals(o, "status", "experimental") || !equals(o, "completion", "READY_FOR_RELEASE") ||
        !equals(o, "freshness", "EXACT_SOURCE_AND_CURRENT_EVIDENCE") || !equals(o, "recovery", "STOP_ON_UNKNOWN")) goto done;
    tag = "PACK_TEXT";
    if (!list(o, "intent", 16, false) || !list(o, "negative_intent", 16, false)) goto done;
    tag = "PACK_LIST";
    if (!list(o, "roles", 16, true) || !list(o, "capabilities", 32, true) ||
        !list(o, "prohibited_effects", 32, true) || !list(o, "inputs", 32, true) || !list(o, "evidence", 32, true)) goto done;
    status = golem_digest_bytes(input, digest); tag = status == GOLEM_OK ? "PACK_VALIDATED_NO_AUTHORITY" : "PACK_DIGEST";
done:
    json_object_put(o);
    return report(diagnostic, status, tag);
}
