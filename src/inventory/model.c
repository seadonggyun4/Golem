#include "internal.h"
#include <string.h>

golem_status in_emit(struct json_object *o, golem_inventory_reply *out)
{
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (!text)
        return GOLEM_ERR_OUT_OF_MEMORY;
    size_t n = strlen(text);
    if (n > GOLEM_INVENTORY_MAX_JSON)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    void *copy = NULL;
    golem_status st = golem_allocator_alloc(NULL, n ? n : 1, &copy);
    if (st == GOLEM_OK) {
        memcpy(copy, text, n);
        *out = (golem_inventory_reply){copy, n};
    }
    return st;
}

void golem_inventory_reply_free(golem_inventory_reply *reply)
{
    if (reply) {
        (void)golem_allocator_free(NULL, reply->data);
        *reply = (golem_inventory_reply){0};
    }
}

static bool file(struct json_object *o, bool working, size_t oid_length)
{
    if (!o)
        return true;
    const char *keys[] = {"mode", "oid", "sha256", "size"};
    const char *mode = dw_text(o, "mode"), *oid = dw_text(o, "oid");
    golem_digest digest;
    return dw_keys(o, keys, working ? 4 : 2) &&
           (!strcmp(mode, "100644") || !strcmp(mode, "100755") || !strcmp(mode, "120000")) &&
           ws_oid(oid) && strlen(oid) == oid_length &&
           (!working || (dw_digest(o, "sha256", &digest) &&
                         json_object_is_type(dw_get(o, "size"), json_type_int) &&
                         json_object_get_int64(dw_get(o, "size")) >= 0 &&
                         dw_uint(o, "size") <= UINT64_C(67108864)));
}

static unsigned char lower(unsigned char c)
{
    return c >= 'A' && c <= 'Z' ? (unsigned char)(c - 'A' + 'a') : c;
}

/* Inputs have already passed in_unhex. Decode only the common prefix during
 * pairwise alias checks instead of decoding every complete path repeatedly. */
static unsigned char hex_byte(const char *p)
{
    unsigned high = p[0] <= '9' ? (unsigned)(p[0] - '0') : (unsigned)(p[0] - 'a' + 10);
    unsigned low = p[1] <= '9' ? (unsigned)(p[1] - '0') : (unsigned)(p[1] - 'a' + 10);
    return (unsigned char)((high << 4) | low);
}

static bool case_alias(const char *a, const char *b)
{
    bool different = false;
    while (*a && *b) {
        unsigned char left = hex_byte(a), right = hex_byte(b);
        if (lower(left) != lower(right))
            return false;
        different = different || left != right;
        if (left == '/' && different)
            return true;
        a += 2;
        b += 2;
    }
    return !*a && !*b;
}

golem_status in_snapshot_validate(struct json_object *o, const in_policy *policy)
{
    const char *keys[] = {"schema_version", "root", "head", "policy", "entries"};
    const char *rk[] = {"path", "device", "inode"};
    struct json_object *root = dw_get(o, "root"), *entries = dw_get(o, "entries");
    golem_digest digest;
    if (!dw_keys(o, keys, 5) || dw_uint(o, "schema_version") != 1 || !dw_keys(root, rk, 3) ||
        dw_text(root, "path")[0] != '/' ||
        !json_object_is_type(dw_get(root, "device"), json_type_int) ||
        !json_object_is_type(dw_get(root, "inode"), json_type_int) ||
        json_object_get_int64(dw_get(root, "device")) < 0 ||
        json_object_get_int64(dw_get(root, "inode")) < 0 || !ws_oid(dw_text(o, "head")) ||
        !dw_digest(o, "policy", &digest) || !dw_equal(&digest, &policy->digest) ||
        !json_object_is_type(entries, json_type_array) ||
        json_object_array_length(entries) > GOLEM_INVENTORY_MAX_PATHS)
        return GOLEM_ERR_PARSE;
    const char *last = "";
    const char *validated_paths[GOLEM_INVENTORY_MAX_PATHS];
    for (size_t i = 0; i < json_object_array_length(entries); ++i) {
        struct json_object *e = json_object_array_get_idx(entries, i);
        const char *ek[] = {"head", "index", "worktree", "path_hex"};
        char path[1025];
        const char *hex = dw_text(e, "path_hex");
        if (!dw_keys(e, ek, 4) || in_unhex(hex, path, sizeof(path)) != GOLEM_OK ||
            (!dw_get(e, "head") && !dw_get(e, "index") && !dw_get(e, "worktree")) ||
            !in_path(path) || strcmp(last, hex) >= 0 ||
            !file(dw_get(e, "head"), false, strlen(dw_text(o, "head"))) ||
            !file(dw_get(e, "index"), false, strlen(dw_text(o, "head"))) ||
            !file(dw_get(e, "worktree"), true, strlen(dw_text(o, "head"))) ||
            (in_any(policy->excluded, policy->excluded_count, path) &&
             !in_any(policy->protected, policy->protected_count, path)))
            return GOLEM_ERR_PARSE;
        for (size_t j = 0; j < i; ++j) {
            if (case_alias(hex, validated_paths[j]))
                return GOLEM_ERR_INCOMPLETE_WORK;
        }
        validated_paths[i] = hex;
        last = hex;
    }
    return GOLEM_OK;
}

golem_status golem_inventory_policy_validate(golem_bytes policy, golem_diagnostic *d)
{
    struct json_object *o = NULL;
    in_policy parsed;
    golem_status st = golem_json_parse(policy, GOLEM_INVENTORY_MAX_JSON, &o);
    if (st == GOLEM_OK)
        st = in_policy_parse(o, &parsed);
    json_object_put(o);
    return dw_report(d, st, NULL);
}

golem_status golem_inventory_capture(const char *root, golem_bytes policy,
                                     golem_inventory_reply *out, golem_diagnostic *d)
{
    if (!root || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = NULL, *snapshot = NULL;
    in_policy parsed;
    golem_status st = golem_json_parse(policy, GOLEM_INVENTORY_MAX_JSON, &o);
    if (st == GOLEM_OK)
        st = in_policy_parse(o, &parsed);
    if (st == GOLEM_OK)
        st = in_capture(root, &parsed, &snapshot);
    if (st == GOLEM_OK)
        st = in_emit(snapshot, out);
    json_object_put(o);
    json_object_put(snapshot);
    return dw_report(d, st, NULL);
}

golem_status golem_inventory_compare(golem_bytes baseline, golem_bytes current, golem_bytes policy,
                                     golem_inventory_reply *out, golem_diagnostic *d)
{
    if (!out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *p = NULL, *base = NULL, *now = NULL, *result = NULL;
    in_policy parsed;
    golem_status st = golem_json_parse(policy, GOLEM_INVENTORY_MAX_JSON, &p);
    if (st == GOLEM_OK)
        st = in_policy_parse(p, &parsed);
    if (st == GOLEM_OK)
        st = golem_json_parse(baseline, GOLEM_INVENTORY_MAX_JSON, &base);
    if (st == GOLEM_OK)
        st = golem_json_parse(current, GOLEM_INVENTORY_MAX_JSON, &now);
    if (st == GOLEM_OK)
        st = in_compare(base, now, &parsed, &result);
    if (st == GOLEM_OK)
        st = in_emit(result, out);
    json_object_put(p);
    json_object_put(base);
    json_object_put(now);
    json_object_put(result);
    return dw_report(d, st, NULL);
}
