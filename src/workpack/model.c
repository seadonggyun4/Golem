#include "internal.h"
#include <stdlib.h>
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


golem_status golem_workpack_inspect(golem_bytes input, char *buffer, size_t capacity,
                                   size_t *required, golem_diagnostic *diagnostic)
{
    if (!required || (!buffer && capacity)) return report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, "PACK_OUTPUT");
    golem_digest digest;
    golem_status status = golem_workpack_validate(input, &digest, diagnostic);
    if (status != GOLEM_OK) return status;
    struct json_object *o = NULL;
    status = golem_json_parse(input, GOLEM_WORKPACK_MAX_JSON, &o);
    if (status != GOLEM_OK) return report(diagnostic, status, "PACK_JSON");
    const char *encoded = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (!encoded) status = GOLEM_ERR_OUT_OF_MEMORY;
    else {
        size_t needed = strlen(encoded) + 1;
        *required = needed;
        if (capacity < needed) status = GOLEM_ERR_BUFFER_TOO_SMALL;
        else memcpy(buffer, encoded, needed);
    }
    json_object_put(o);
    return report(diagnostic, status, "PACK_METADATA_NO_AUTHORITY");
}

golem_status golem_workpack_compatibility(golem_bytes input, golem_string_view core_version,
                                         bool *compatible, golem_diagnostic *diagnostic)
{
    if (!compatible || !core_version.data || !core_version.size || core_version.size > 17 ||
        memchr(core_version.data, 0, core_version.size))
        return report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, "PACK_CORE_VERSION");
    char core[18]; memcpy(core, core_version.data, core_version.size); core[core_version.size] = 0;
    uint64_t value;
    if (!version(core, &value)) return report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, "PACK_CORE_VERSION");
    golem_digest digest;
    golem_status status = golem_workpack_validate(input, &digest, diagnostic);
    if (status != GOLEM_OK) return status;
    struct json_object *o = NULL;
    status = golem_json_parse(input, GOLEM_WORKPACK_MAX_JSON, &o);
    if (status != GOLEM_OK) return report(diagnostic, status, "PACK_JSON");
    uint64_t min, max;
    if (!version(string(o, "core_min"), &min) || !version(string(o, "core_max"), &max)) status = GOLEM_ERR_PARSE;
    else *compatible = value >= min && value <= max;
    json_object_put(o);
    return report(diagnostic, status, "PACK_DECLARED_COMPATIBILITY_ONLY");
}

/* Catalog lexical matching is deliberately byte-defined: ASCII case folding and
 * whitespace token boundaries, exact UTF-8 otherwise. No locale/provider state. */
static size_t words(const char *input, char output[258])
{
    size_t n = 0; bool space = true;
    for (const unsigned char *s = (const unsigned char *)input; *s; ++s) {
        if (*s == ' ' || (*s >= 9 && *s <= 13)) {
            if (!space) output[n++] = ' ';
            space = true;
        } else {
            output[n++] = (char)(*s >= 'A' && *s <= 'Z' ? *s + ('a' - 'A') : *s);
            space = false;
        }
    }
    if (n && output[n - 1] == ' ') --n;
    output[n] = 0; return n;
}
static bool phrase(const char *haystack, const char *needle)
{
    size_t n = strlen(needle);
    for (const char *p = haystack; (p = strstr(p, needle)) != NULL; ++p)
        if ((p == haystack || p[-1] == ' ') && (!p[n] || p[n] == ' ')) return true;
    return false;
}
static bool matches(struct json_object *entry, const char *field, const char *token)
{
    struct json_object *v = NULL;
    (void)json_object_object_get_ex(entry, field, &v);
    size_t count = json_object_is_type(v, json_type_array) ? json_object_array_length(v) : 1;
    for (size_t i = 0; i < count; ++i) {
        const char *s = json_object_get_string(json_object_is_type(v, json_type_array) ? json_object_array_get_idx(v, i) : v);
        char normalized[258]; (void)words(s, normalized);
        if (phrase(normalized, token)) return true;
    }
    return false;
}
struct catalog_item { struct json_object *entry; uint64_t version; unsigned score; bool excluded; };
static bool before(const struct catalog_item *a, const struct catalog_item *b)
{
    if (a->score != b->score) return a->score > b->score;
    int order = strcmp(string(a->entry, "id"), string(b->entry, "id"));
    if (order) return order < 0;
    if (a->version != b->version) return a->version < b->version;
    return strcmp(string(a->entry, "digest"), string(b->entry, "digest")) < 0;
}
static bool relative_manifest(const char *s)
{
    if (!s || !*s || *s == '/' || strlen(s) > 1024) return false;
    const char *part = s;
    for (;;) {
        const char *end = strchr(part, '/'); size_t n = end ? (size_t)(end - part) : strlen(part);
        if (!n || (n == 1 && *part == '.') || (n == 2 && !memcmp(part, "..", 2))) return false;
        for (size_t i = 0; i < n; ++i)
            if ((unsigned char)part[i] < 32 || part[i] == 127 || part[i] == '\\' || part[i] == ':') return false;
        if (!end) return true;
        part = end + 1;
    }
}
static bool member(struct json_object *o, const char *key, struct json_object *value)
{
    if (!value) return false;
    if (json_object_object_add(o, key, value)) { json_object_put(value); return false; }
    return true;
}
golem_status golem_workpack_catalog(const char *path, golem_string_view query,
                                   char *buffer, size_t capacity, size_t *required,
                                   golem_diagnostic *diagnostic)
{
    if (!path || !required || (!buffer && capacity) || query.size > 256 ||
        (!query.data && query.size) || (query.data && (!query.size || memchr(query.data, 0, query.size))))
        return report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, "CATALOG_ARGUMENT");
    /* Let the existing strict JSON parser validate query UTF-8, including control
     * bytes, before matching. json-c escaping alone does not validate UTF-8. */
    char normalized[258] = {0};
    if (query.data) {
        struct json_object *q = json_object_new_object(), *parsed = NULL;
        if (!q) return report(diagnostic, GOLEM_ERR_OUT_OF_MEMORY, "CATALOG_QUERY");
        struct json_object *value = json_object_new_string_len(query.data, (int)query.size);
        if (!value) { json_object_put(q); return report(diagnostic, GOLEM_ERR_OUT_OF_MEMORY, "CATALOG_QUERY"); }
        if (!member(q, "q", value)) { json_object_put(q); return report(diagnostic, GOLEM_ERR_OUT_OF_MEMORY, "CATALOG_QUERY"); }
        const char *encoded = json_object_to_json_string_ext(q, JSON_C_TO_STRING_PLAIN);
        golem_status qs = encoded ? golem_json_parse((golem_bytes){(const uint8_t *)encoded, strlen(encoded)}, 2048, &parsed) : GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(parsed);
        if (qs == GOLEM_OK) {
            for (size_t i = 0; i < query.size; ++i) {
                unsigned char ch = (unsigned char)query.data[i];
                if ((ch < 32 && !(ch >= 9 && ch <= 13)) || ch == 127) qs = GOLEM_ERR_INVALID_ARGUMENT;
            }
            if (!words(json_object_get_string(value), normalized)) qs = GOLEM_ERR_INVALID_ARGUMENT;
        }
        json_object_put(q);
        if (qs != GOLEM_OK) return report(diagnostic, qs, "CATALOG_QUERY");
    }
    uint8_t *input = malloc(GOLEM_WORKPACK_CATALOG_MAX_JSON), *again = malloc(GOLEM_WORKPACK_CATALOG_MAX_JSON);
    struct json_object *catalog = NULL, *output = NULL, *entries = NULL;
    struct catalog_item items[GOLEM_WORKPACK_CATALOG_MAX_ENTRIES]; size_t count = 0, size = 0;
    golem_status status = GOLEM_ERR_OUT_OF_MEMORY; const char *tag = "CATALOG_MEMORY";
    if (!input || !again) goto done;
    tag = "CATALOG_READ";
    status = golem_workpack_read_limit(path, input, GOLEM_WORKPACK_CATALOG_MAX_JSON, GOLEM_WORKPACK_CATALOG_MAX_JSON, &size, diagnostic);
    if (status != GOLEM_OK) goto done;
    tag = "CATALOG_JSON";
    status = golem_json_parse((golem_bytes){input, size}, GOLEM_WORKPACK_CATALOG_MAX_JSON, &catalog);
    if (status != GOLEM_OK) goto done;
    status = GOLEM_ERR_PARSE; tag = "CATALOG_SCHEMA";
    if (json_object_object_length(catalog) != 2 || !equals(catalog, "schema", "golem.workpack.catalog.v0") ||
        !json_object_object_get_ex(catalog, "entries", &entries) || !json_object_is_type(entries, json_type_array)) goto done;
    count = json_object_array_length(entries);
    if (count > GOLEM_WORKPACK_CATALOG_MAX_ENTRIES) { status = GOLEM_ERR_OVERFLOW; goto done; }
    const char *slash = strrchr(path, '/'); size_t prefix = slash ? (size_t)(slash - path) + 1 : 0;
    const char *fields[] = {"id", "version", "schema", "status", "intent", "negative_intent", "capabilities"};
    for (size_t i = 0; i < count; ++i) {
        struct json_object *e = json_object_array_get_idx(entries, i), *manifest = NULL;
        tag = "CATALOG_ENTRY"; status = GOLEM_ERR_PARSE;
        if (!json_object_is_type(e, json_type_object) || json_object_object_length(e) != 11 ||
            !identifier(string(e, "id")) || !version(string(e, "version"), &items[i].version) ||
            !equals(e, "schema", GOLEM_WORKPACK_SCHEMA) || !equals(e, "status", "experimental") ||
            !list(e, "intent", 16, false) || !list(e, "negative_intent", 16, false) ||
            !list(e, "capabilities", 32, true) || !list(e, "aliases", 16, false) || !text(string(e, "category")) ||
            !relative_manifest(string(e, "manifest"))) goto done;
        const char *hex = string(e, "digest"); golem_digest expected, actual;
        if (!hex || strlen(hex) != 64 || strspn(hex, "0123456789abcdef") != 64 ||
            golem_digest_parse((golem_string_view){hex, 64}, &expected) != GOLEM_OK) goto done;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(string(e, "id"), string(items[j].entry, "id")) && items[i].version == items[j].version) {
                tag = "CATALOG_DUPLICATE"; goto done;
            }
        char target[4096]; const char *ref = string(e, "manifest");
        if (prefix + strlen(ref) >= sizeof(target)) { status = GOLEM_ERR_OVERFLOW; goto done; }
        memcpy(target, path, prefix); strcpy(target + prefix, ref);
        size_t manifest_size = 0;
        tag = "CATALOG_MANIFEST_READ";
        status = golem_workpack_read(target, again, GOLEM_WORKPACK_CATALOG_MAX_JSON, &manifest_size, diagnostic);
        if (status != GOLEM_OK) goto done;
        tag = "CATALOG_MANIFEST";
        status = golem_workpack_validate((golem_bytes){again, manifest_size}, &actual, diagnostic);
        if (status != GOLEM_OK) goto done;
        char actual_hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t needed;
        status = golem_digest_format(&actual, actual_hex, sizeof(actual_hex), &needed);
        if (status != GOLEM_OK) goto done;
        tag = "CATALOG_DIGEST";
        if (strcmp(actual_hex, hex)) { status = GOLEM_ERR_STALE_RESULT; goto done; }
        status = golem_json_parse((golem_bytes){again, manifest_size}, GOLEM_WORKPACK_MAX_JSON, &manifest);
        if (status != GOLEM_OK) goto done;
        bool equal = true;
        for (size_t f = 0; f < sizeof(fields)/sizeof(*fields); ++f) {
            struct json_object *a = NULL, *b = NULL;
            (void)json_object_object_get_ex(e, fields[f], &a); (void)json_object_object_get_ex(manifest, fields[f], &b);
            if (!json_object_equal(a, b)) equal = false;
        }
        json_object_put(manifest);
        if (!equal) { tag = "CATALOG_METADATA"; status = GOLEM_ERR_STALE_RESULT; goto done; }
        items[i].entry = e; items[i].score = 0; items[i].excluded = false;
        if (query.data) {
            struct json_object *negative = NULL; (void)json_object_object_get_ex(e, "negative_intent", &negative);
            for (size_t n = 0; n < json_object_array_length(negative); ++n) {
                char term[258]; (void)words(json_object_get_string(json_object_array_get_idx(negative, n)), term);
                if (phrase(normalized, term)) items[i].excluded = true;
            }
            char tokens[258]; strcpy(tokens, normalized); char *seen[128]; size_t used = 0;
            char *start = tokens;
            while (*start) {
                char *end = strchr(start, ' '); if (end) *end = 0;
                bool duplicate = false;
                for (size_t n = 0; n < used; ++n) if (!strcmp(seen[n], start)) duplicate = true;
                if (!duplicate) {
                    seen[used++] = start;
                    if (matches(e, "intent", start) || matches(e, "aliases", start) ||
                        matches(e, "category", start) || matches(e, "capabilities", start)) ++items[i].score;
                }
                if (!end) break;
                start = end + 1;
            }
        }
    }
    /* Revalidate the index snapshot after all references. Referenced bytes are
     * observations at their read time, not a cross-file transactional snapshot. */
    size_t second = 0; tag = "CATALOG_RECHECK";
    status = golem_workpack_read_limit(path, again, GOLEM_WORKPACK_CATALOG_MAX_JSON, GOLEM_WORKPACK_CATALOG_MAX_JSON, &second, diagnostic);
    if (status != GOLEM_OK) goto done;
    if (size != second || memcmp(input, again, size)) { status = GOLEM_ERR_STALE_RESULT; tag = "CATALOG_CHANGED"; goto done; }
    for (size_t i = 1; i < count; ++i) {
        struct catalog_item item = items[i]; size_t j = i;
        while (j && before(&item, &items[j - 1])) { items[j] = items[j - 1]; --j; }
        items[j] = item;
    }
    output = json_object_new_object(); struct json_object *results = json_object_new_array();
    if (!output || !results) { json_object_put(results); status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    if (!member(output, "entries", results)) { status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    unsigned best = 0; size_t ties = 0;
    for (size_t i = 0; i < count; ++i) {
        if (query.data && (items[i].excluded || !items[i].score)) continue;
        if (!ties) best = items[i].score;
        if (items[i].score == best) ++ties;
        struct json_object *row = json_object_new_object();
        if (!row) { status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
        const char *keys[] = {"id", "version", "digest", "manifest", "status"};
        for (size_t k = 0; k < sizeof(keys)/sizeof(*keys); ++k) {
            struct json_object *v = NULL; (void)json_object_object_get_ex(items[i].entry, keys[k], &v);
            if (!member(row, keys[k], json_object_get(v))) { json_object_put(row); status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
        }
        if (!member(row, "score", json_object_new_int((int)items[i].score)) || json_object_array_add(results, row)) { json_object_put(row); status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    }
    if (!member(output, "schema", json_object_new_string("golem.workpack.discovery.v0")) ||
        !member(output, "result", json_object_new_string(!query.data ? "LISTED" : !ties ? "NO_MATCH" : ties > 1 ? "AMBIGUOUS" : "MATCH")) ||
        !member(output, "authorized", json_object_new_boolean(false)) ||
        !member(output, "bound", json_object_new_boolean(false)) ||
        !member(output, "runtime_availability", json_object_new_string("NOT_EVALUATED"))) {
        status = GOLEM_ERR_OUT_OF_MEMORY; goto done;
    }
    const char *encoded = json_object_to_json_string_ext(output, JSON_C_TO_STRING_PLAIN);
    if (!encoded) { status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    size_t needed = strlen(encoded) + 1;
    if (needed > GOLEM_WORKPACK_CATALOG_REPORT_MAX) { status = GOLEM_ERR_OVERFLOW; goto done; }
    *required = needed;
    status = capacity < needed ? GOLEM_ERR_BUFFER_TOO_SMALL : GOLEM_OK;
    if (status == GOLEM_OK) memcpy(buffer, encoded, needed);
    tag = "CATALOG_DISCOVERY_NO_AUTHORITY";
done:
    json_object_put(output); json_object_put(catalog); free(input); free(again);
    return report(diagnostic, status, tag);
}
