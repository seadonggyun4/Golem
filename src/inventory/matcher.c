#include "internal.h"
#include <string.h>

bool in_path(const char *p)
{
    if (!p || !*p || *p == '/' || strlen(p) > GOLEM_INVENTORY_PATH_MAX)
        return false;
    const char *start = p;
    for (;;) {
        const char *end = strchr(start, '/');
        size_t n = end ? (size_t)(end - start) : strlen(start);
        if (!n || (n == 1 && *start == '.') || (n == 2 && !memcmp(start, "..", 2)) ||
            (n == 4 && !memcmp(start, ".git", 4)))
            return false;
        if (!end)
            return true;
        start = end + 1;
    }
}

static int digit(unsigned char c)
{
    return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1;
}

golem_status in_unhex(const char *hex, char *out, size_t capacity)
{
    size_t n = strlen(hex);
    if (!n || n % 2 || n / 2 >= capacity)
        return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < n; i += 2) {
        int a = digit((unsigned char)hex[i]), b = digit((unsigned char)hex[i + 1]);
        if (a < 0 || b < 0 || !(a || b))
            return GOLEM_ERR_PARSE;
        out[i / 2] = (char)(16 * a + b);
    }
    out[n / 2] = 0;
    return GOLEM_OK;
}

struct json_object *in_hex(const uint8_t *bytes, size_t n)
{
    char text[GOLEM_INVENTORY_PATH_MAX * 2 + 1];
    const char *digits = "0123456789abcdef";
    if (n > GOLEM_INVENTORY_PATH_MAX)
        return NULL;
    for (size_t i = 0; i < n; ++i) {
        text[2 * i] = digits[bytes[i] >> 4];
        text[2 * i + 1] = digits[bytes[i] & 15];
    }
    text[2 * n] = 0;
    return json_object_new_string(text);
}

bool in_matches(const in_rule *rule, const char *path)
{
    size_t n = strlen(path), length = strlen(rule->pattern);
    if (rule->kind == 1)
        return !strcmp(rule->pattern, path);
    if (rule->kind == 2)
        return n >= length && !memcmp(rule->pattern, path, length) &&
               (path[length] == 0 || path[length] == '/');
    /* Rolling dynamic programming avoids recursive/backtracking glob blowups. */
    bool previous[GOLEM_INVENTORY_PATH_MAX + 1] = {true};
    bool next[GOLEM_INVENTORY_PATH_MAX + 1];
    for (size_t i = 0; i < length; ++i) {
        memset(next, 0, sizeof(next));
        char c = rule->pattern[i];
        if (c == '*' && rule->pattern[i + 1] == '*') {
            bool prefix = false;
            bool slash = rule->pattern[i + 2] == '/';
            for (size_t j = 0; j <= n; ++j) {
                next[j] = previous[j] || (prefix && (!slash || (j && path[j - 1] == '/')));
                prefix = prefix || previous[j];
            }
            i += slash ? 2 : 1;
        } else if (c == '*') {
            next[0] = previous[0];
            for (size_t j = 1; j <= n; ++j)
                next[j] = previous[j] || (path[j - 1] != '/' && next[j - 1]);
        } else {
            for (size_t j = 1; j <= n; ++j)
                next[j] = previous[j - 1] && (c == '?' ? path[j - 1] != '/' : c == path[j - 1]);
        }
        memcpy(previous, next, sizeof(previous));
    }
    return previous[n];
}

bool in_any(const in_rule *rules, size_t count, const char *path)
{
    for (size_t i = 0; i < count; ++i)
        if (in_matches(&rules[i], path))
            return true;
    return false;
}

static golem_status rules(struct json_object *array, in_rule *out, size_t *count)
{
    if (!json_object_is_type(array, json_type_array) || json_object_array_length(array) > IN_RULES)
        return GOLEM_ERR_PARSE;
    *count = json_object_array_length(array);
    for (size_t i = 0; i < *count; ++i) {
        struct json_object *r = json_object_array_get_idx(array, i);
        bool hex = dw_get(r, "pattern_hex") != NULL;
        const char *keys[] = {"kind", hex ? "pattern_hex" : "pattern"};
        const char *kind = dw_text(r, "kind");
        if (!dw_keys(r, keys, 2))
            return GOLEM_ERR_PARSE;
        out[i].kind = !strcmp(kind, "EXACT")          ? 1
                      : !strcmp(kind, "DIR_PREFIX")   ? 2
                      : !strcmp(kind, "SEGMENT_GLOB") ? 3
                                                      : 0;
        if (!out[i].kind)
            return GOLEM_ERR_PARSE;
        if (hex) {
            if (in_unhex(dw_text(r, "pattern_hex"), out[i].pattern, sizeof(out[i].pattern)) !=
                GOLEM_OK)
                return GOLEM_ERR_PARSE;
        } else {
            const char *p = dw_text(r, "pattern");
            if (strlen(p) > IN_PATTERN)
                return GOLEM_ERR_PARSE;
            memcpy(out[i].pattern, p, strlen(p) + 1);
        }
        const char *p = out[i].pattern;
        if (!in_path(p))
            return GOLEM_ERR_PARSE;
        if (out[i].kind == 3) {
            for (size_t j = 0; p[j]; ++j) {
                if (p[j] == '*' && p[j + 1] == '*') {
                    if ((j && p[j - 1] != '/') || (p[j + 2] && p[j + 2] != '/'))
                        return GOLEM_ERR_PARSE;
                    ++j;
                }
                if (p[j] == '[' || p[j] == ']' || p[j] == '\\' || p[j] == '!')
                    return GOLEM_ERR_PARSE;
            }
        }
    }
    return GOLEM_OK;
}

golem_status in_policy_parse(struct json_object *o, in_policy *out)
{
    const char *keys[] = {"schema_version", "protected", "excluded", "limit"};
    struct json_object *limit = dw_get(o, "limit");
    bool unlimited = !strcmp(dw_text(limit, "mode"), "UNLIMITED");
    const char *lk[] = {"mode", "max_changed_paths"};
    if (!dw_keys(o, keys, 4) || dw_uint(o, "schema_version") != 1 ||
        !dw_keys(limit, lk, unlimited ? 1 : 2) ||
        (!unlimited && (strcmp(dw_text(limit, "mode"), "BOUNDED") ||
                        !json_object_is_type(dw_get(limit, "max_changed_paths"), json_type_int) ||
                        json_object_get_int64(dw_get(limit, "max_changed_paths")) < 0 ||
                        dw_uint(limit, "max_changed_paths") > GOLEM_INVENTORY_MAX_PATHS * 2)))
        return GOLEM_ERR_PARSE;
    in_policy p = {.unlimited = unlimited, .maximum = dw_uint(limit, "max_changed_paths")};
    golem_status st = rules(dw_get(o, "protected"), p.protected, &p.protected_count);
    if (st == GOLEM_OK)
        st = rules(dw_get(o, "excluded"), p.excluded, &p.excluded_count);
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (st == GOLEM_OK)
        st = text
                 ? golem_digest_bytes((golem_bytes){(const uint8_t *)text, strlen(text)}, &p.digest)
                 : GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        *out = p;
    return st;
}
