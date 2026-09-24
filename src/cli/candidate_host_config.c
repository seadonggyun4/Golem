#include "candidate_host.h"
#include <string.h>

static bool path(struct json_object *o, const char *key)
{
    const char *p = dw_text(o, key);
    return p[0] == '/' && strlen(p) < 4096;
}

golem_status ch_validate(struct json_object *c)
{
    const char *keys[] = {"schema_version", "parent",          "admission",
                          "repository_id",  "repository_root", "worktree_root",
                          "limits",         "bindings",        "target"};
    const char *limits[] = {"slots", "cpu_millis", "memory_bytes"};
    struct json_object *l = dw_get(c, "limits"), *bindings = dw_get(c, "bindings");
    if (!dw_keys(c, keys, 9) || dw_uint(c, "schema_version") != 1 ||
        !dw_id(dw_text(c, "repository_id")) || !path(c, "parent") || !path(c, "admission") ||
        !path(c, "repository_root") || !path(c, "worktree_root") || !dw_keys(l, limits, 3) ||
        !ds_array(bindings, 1, GOLEM_CANDIDATE_MAX))
        return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < 3; ++i)
        if (!json_object_is_type(dw_get(l, limits[i]), json_type_int) ||
            json_object_get_int64(dw_get(l, limits[i])) <= 0)
            return GOLEM_ERR_PARSE;
    if (dw_uint(l, "slots") > GOLEM_CANDIDATE_MAX)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    for (size_t i = 0; i < json_object_array_length(bindings); ++i) {
        struct json_object *b = json_object_array_get_idx(bindings, i);
        const char *bk[] = {"candidate", "session", "runtime_binding", "work", "tree",
                            "build",     "temp",    "environment"};
        golem_digest digest;
        if (!dw_keys(b, bk, 8) || !ws_id(dw_text(b, "candidate")) ||
            strlen(dw_text(b, "candidate")) > 24 || !dw_id(dw_text(b, "session")) ||
            !dw_digest(b, "runtime_binding", &digest) || !dw_digest(b, "environment", &digest))
            return GOLEM_ERR_PARSE;
        for (size_t k = 3; k < 7; ++k)
            if (!path(b, bk[k]))
                return GOLEM_ERR_PARSE;
        for (size_t j = 0; j < i; ++j) {
            struct json_object *a = json_object_array_get_idx(bindings, j);
            if (!strcmp(dw_text(a, "candidate"), dw_text(b, "candidate")) ||
                !strcmp(dw_text(a, "work"), dw_text(b, "work")))
                return GOLEM_ERR_IDENTITY_MISMATCH;
        }
    }
    struct json_object *target = dw_get(c, "target");
    const char *tk[] = {"work", "tree", "environment"};
    golem_digest digest;
    if (target && (!dw_keys(target, tk, 3) || !path(target, "work") || !path(target, "tree") ||
                   !dw_digest(target, "environment", &digest)))
        return GOLEM_ERR_PARSE;
    return GOLEM_OK;
}
