#include "internal.h"
#include "../discovery/internal.h"
#include "../workflow/internal.h"
#include <string.h>

golem_status dw_report(golem_diagnostic *d, golem_status s, const char *message)
{
    if (d)
        (void)golem_diagnostic_set(d, s, GOLEM_DIAGNOSTIC_NO_OFFSET, message);
    return s;
}
struct json_object *dw_get(struct json_object *o, const char *key)
{
    struct json_object *v = NULL;
    if (o)
        (void)json_object_object_get_ex(o, key, &v);
    return v;
}
const char *dw_text(struct json_object *o, const char *key)
{
    struct json_object *v = dw_get(o, key);
    return json_object_is_type(v, json_type_string) ? json_object_get_string(v) : "";
}
uint64_t dw_uint(struct json_object *o, const char *key)
{
    struct json_object *v = dw_get(o, key);
    if (!json_object_is_type(v, json_type_int) || json_object_get_int64(v) < 0)
        return UINT64_MAX;
    return json_object_get_uint64(v);
}
bool dw_id(const char *s)
{
    if (!s || !*s || strlen(s) >= GOLEM_DOCUMENT_ID_CAPACITY)
        return false;
    for (size_t i = 0; s[i]; ++i)
        if (!((s[i] >= 'a' && s[i] <= 'z') || (s[i] >= 'A' && s[i] <= 'Z') ||
              (s[i] >= '0' && s[i] <= '9') || s[i] == '_' || s[i] == '-'))
            return false;
    return true;
}
bool dw_keys(struct json_object *o, const char *const *keys, size_t count)
{
    if (!json_object_is_type(o, json_type_object) || (size_t)json_object_object_length(o) != count)
        return false;
    for (size_t i = 0; i < count; ++i)
        if (!json_object_object_get_ex(o, keys[i], NULL))
            return false;
    return true;
}
bool dw_digest(struct json_object *o, const char *key, golem_digest *out)
{
    const char *s = dw_text(o, key);
    return golem_digest_parse((golem_string_view){s, strlen(s)}, out) == GOLEM_OK;
}
bool dw_equal(const golem_digest *a, const golem_digest *b)
{
    return memcmp(a->bytes, b->bytes, GOLEM_DIGEST_SIZE) == 0;
}
bool dw_add(struct json_object *o, const char *key, struct json_object *v)
{
    if (!o || !v || json_object_object_add(o, key, v) != 0) {
        json_object_put(v);
        return false;
    }
    return true;
}
bool dw_add_digest(struct json_object *o, const char *key, const golem_digest *digest)
{
    char hex[GOLEM_DIGEST_HEX_CAPACITY];
    size_t n;
    if (golem_digest_format(digest, hex, sizeof(hex), &n) != GOLEM_OK)
        return false;
    return dw_add(o, key, json_object_new_string(hex));
}
static bool prose(const char *s)
{
    size_t meaningful = 0;
    for (; *s; ++s)
        if ((unsigned char)*s > 32)
            ++meaningful;
    return meaningful >= 4;
}
golem_status dw_spec(golem_bytes b, struct json_object **out)
{
    struct json_object *o = NULL;
    golem_status s = golem_json_parse(b, GOLEM_DOCUMENT_MAX_JSON, &o);
    if (s != GOLEM_OK)
        return s;
    const char *keys[] = {"schema_version", "work_id",    "request",
                          "scope",          "non_goals",  "permission",
                          "max_revisions",  "acceptance", "policy_version"};
    struct json_object *a = dw_get(o, "acceptance");
    const char *p = dw_text(o, "permission");
    bool ok = dw_keys(o, keys, 9) && dw_id(dw_text(o, "work_id")) && prose(dw_text(o, "request")) &&
              prose(dw_text(o, "scope")) && prose(dw_text(o, "non_goals")) &&
              (strcmp(p, "AUTO_LOCAL") == 0 || strcmp(p, "ASK_ALWAYS") == 0 ||
               strcmp(p, "DENY") == 0 || strcmp(p, "ASK_ON_EXTERNAL_EFFECT") == 0) &&
              dw_uint(o, "max_revisions") > 0 &&
              dw_uint(o, "max_revisions") <= GOLEM_DOCUMENT_MAX_REVISIONS &&
              json_object_is_type(a, json_type_array) && json_object_array_length(a) > 0 &&
              json_object_array_length(a) <= 256;
    if (ok)
        for (size_t i = 0; i < json_object_array_length(a); ++i) {
            struct json_object *v = json_object_array_get_idx(a, i);
            const char *ak[] = {"id", "criterion"};
            if (!dw_keys(v, ak, 2) || !dw_id(dw_text(v, "id")) || !prose(dw_text(v, "criterion")))
                ok = false;
            for (size_t j = 0; j < i; ++j)
                if (strcmp(dw_text(v, "id"), dw_text(json_object_array_get_idx(a, j), "id")) == 0)
                    ok = false;
        }
    if (!ok)
        s = GOLEM_ERR_PARSE;
    else if (dw_uint(o, "schema_version") != 1 || dw_uint(o, "policy_version") != 1)
        s = GOLEM_ERR_UNSUPPORTED_VERSION;
    if (s == GOLEM_OK)
        *out = o;
    else
        json_object_put(o);
    return s;
}
golem_status dw_meta(golem_bytes b, struct json_object **out)
{
    struct json_object *o = NULL;
    golem_status s = golem_json_parse(b, GOLEM_DOCUMENT_MAX_JSON, &o);
    if (s != GOLEM_OK)
        return s;
    const char *keys[] = {"schema_version",
                          "work_id",
                          "document_id",
                          "revision",
                          "kind",
                          "stage",
                          "producer_attempt",
                          "parents",
                          "requirement_ids",
                          "scope_revision",
                          "template_version",
                          "policy_version",
                          "source_snapshot",
                          "supersedes",
                          "expected_generation",
                          "assessment",
                          "execution_receipt"};
    const char *kinds[] = {"planning",           "ux",      "publishing", "development-plan",
                           "development-result", "qa-plan", "qa-result",  "completion",
                           "research",           "failure", "discovery",  "scope",
                           "stage-selection"};
    const char *stages[] = {"planning", "ux",       "publishing", "development", "development",
                            "qa",       "qa",       "audit",      "planning",    "qa",
                            "planning", "planning", "planning"};
    int kind = -1;
    for (size_t i = 0; i < 13; ++i)
        if (strcmp(dw_text(o, "kind"), kinds[i]) == 0)
            kind = (int)i;
    bool v2 = dw_uint(o, "schema_version") == 2;
    bool v3 = dw_uint(o, "schema_version") == 3, v4 = dw_uint(o, "schema_version") == 4,
         v5 = dw_uint(o, "schema_version") == 5;
    if (v3)
        keys[15] = "selection";
    if (v4 || v5)
        keys[15] = "input_manifest";
    golem_digest d;
    struct json_object *parents = dw_get(o, "parents"), *req = dw_get(o, "requirement_ids");
    bool ok = dw_keys(o, keys,
                      v5                 ? 17
                      : (v2 || v3 || v4) ? 16
                                         : 15) &&
              kind >= 0 &&
              (v5   ? (kind == 4 || kind == 6)
               : v3 ? kind == 12
               : v4 ? kind < 8
               : v2 ? (kind == 8 || kind == 10 || kind == 11)
                    : kind < 10) &&
              strcmp(dw_text(o, "stage"), stages[kind]) == 0 &&
              (!v5 || dw_digest(o, "execution_receipt", &d)) && dw_id(dw_text(o, "work_id")) &&
              dw_id(dw_text(o, "document_id")) && dw_id(dw_text(o, "producer_attempt")) &&
              dw_uint(o, "revision") > 0 &&
              dw_uint(o, "revision") <= GOLEM_DOCUMENT_MAX_REVISIONS &&
              dw_uint(o, "expected_generation") >= 1 &&
              dw_uint(o, "expected_generation") <= GOLEM_DOCUMENT_MAX_REVISIONS &&
              dw_digest(o, "source_snapshot", &d) &&
              json_object_is_type(dw_get(o, "supersedes"), json_type_string) &&
              (dw_uint(o, "revision") == 1 ? strlen(dw_text(o, "supersedes")) == 0
                                           : dw_digest(o, "supersedes", &d)) &&
              json_object_is_type(parents, json_type_array) &&
              json_object_array_length(parents) <= GOLEM_DOCUMENT_MAX_PARENTS &&
              json_object_is_type(req, json_type_array) && json_object_array_length(req) > 0 &&
              json_object_array_length(req) <= 256;
    if (ok)
        for (size_t i = 0; i < json_object_array_length(parents); ++i) {
            struct json_object *p = json_object_array_get_idx(parents, i);
            const char *pk[] = {"document_id", "revision", "digest"};
            if (!dw_keys(p, pk, 3) || !dw_id(dw_text(p, "document_id")) ||
                dw_uint(p, "revision") < 1 ||
                dw_uint(p, "revision") > GOLEM_DOCUMENT_MAX_REVISIONS ||
                !dw_digest(p, "digest", &d) ||
                strcmp(dw_text(p, "document_id"), dw_text(o, "document_id")) == 0)
                ok = false;
            for (size_t j = 0; j < i; ++j)
                if (strcmp(dw_text(p, "document_id"),
                           dw_text(json_object_array_get_idx(parents, j), "document_id")) == 0)
                    ok = false;
        }
    if (ok)
        for (size_t i = 0; i < json_object_array_length(req); ++i) {
            struct json_object *v = json_object_array_get_idx(req, i);
            if (!json_object_is_type(v, json_type_string) || !dw_id(json_object_get_string(v))) {
                ok = false;
                break;
            }
            for (size_t j = 0; j < i; ++j)
                if (strcmp(json_object_get_string(v),
                           json_object_get_string(json_object_array_get_idx(req, j))) == 0)
                    ok = false;
        }
    if (!ok)
        s = GOLEM_ERR_PARSE;
    else if ((dw_uint(o, "schema_version") != 1 && !v2 && !v3 && !v4 && !v5) ||
             dw_uint(o, "scope_revision") != 1 || dw_uint(o, "template_version") != 1 ||
             dw_uint(o, "policy_version") != 1)
        s = GOLEM_ERR_UNSUPPORTED_VERSION;
    if (s == GOLEM_OK && v2)
        s = ds_metadata(o);
    if (s == GOLEM_OK && (v3 || v4 || v5))
        s = wf_metadata(o);
    if (s == GOLEM_OK)
        *out = o;
    else
        json_object_put(o);
    return s;
}
golem_status golem_work_spec_validate(golem_bytes b, golem_diagnostic *d)
{
    struct json_object *o = NULL;
    golem_status s = dw_spec(b, &o);
    json_object_put(o);
    return dw_report(d, s, s == GOLEM_OK ? "structural work validation only" : NULL);
}
golem_status golem_document_validate(golem_bytes m, golem_bytes b, golem_diagnostic *d)
{
    struct json_object *o = NULL;
    golem_status s = dw_meta(m, &o);
    if (s == GOLEM_OK)
        s = dw_markdown(o, b);
    json_object_put(o);
    return dw_report(d, s,
                     s == GOLEM_OK ? "structural validation; acceptance not verified"
                                   : "invalid document contract, sections, links or encoding");
}
