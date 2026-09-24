#include "internal.h"
#include <string.h>

static bool same_content(struct json_object *a, struct json_object *b)
{
    return !a || !b ? a == b
                    : !strcmp(dw_text(a, "mode"), dw_text(b, "mode")) &&
                          !strcmp(dw_text(a, "oid"), dw_text(b, "oid"));
}

static bool dirty(struct json_object *e)
{
    return e && (!same_content(dw_get(e, "head"), dw_get(e, "index")) ||
                 !same_content(dw_get(e, "index"), dw_get(e, "worktree")));
}

golem_status in_compare(struct json_object *base, struct json_object *now, const in_policy *policy,
                        struct json_object **out)
{
    golem_status st = in_snapshot_validate(base, policy);
    if (st == GOLEM_OK)
        st = in_snapshot_validate(now, policy);
    if (st == GOLEM_OK && !json_object_equal(dw_get(base, "root"), dw_get(now, "root")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *a = dw_get(base, "entries"), *b = dw_get(now, "entries");
    struct json_object *findings = json_object_new_array(), *result = json_object_new_object();
    if (!findings || !result)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    size_t i = 0, j = 0, changed = 0, protected = 0, preexisting = 0;
    while (st == GOLEM_OK && (i < json_object_array_length(a) || j < json_object_array_length(b))) {
        struct json_object *old =
            i < json_object_array_length(a) ? json_object_array_get_idx(a, i) : NULL;
        struct json_object *current =
            j < json_object_array_length(b) ? json_object_array_get_idx(b, j) : NULL;
        int cmp = !old       ? 1
                  : !current ? -1
                             : strcmp(dw_text(old, "path_hex"), dw_text(current, "path_hex"));
        if (cmp < 0)
            current = NULL;
        if (cmp > 0)
            old = NULL;
        const char *hex = dw_text(old ? old : current, "path_hex");
        char path[1025];
        st = in_unhex(hex, path, sizeof(path));
        if (st != GOLEM_OK)
            break;
        bool before = dirty(old), delta = !json_object_equal(old, current);
        bool hit = delta && in_any(policy->protected, policy->protected_count, path);
        changed += delta;
        protected += hit;
        preexisting += before;
        if (st == GOLEM_OK && (before || delta)) {
            struct json_object *f = json_object_new_object();
            if (!f || !dw_add(f, "path_hex", json_object_new_string(hex)) ||
                !dw_add(f, "preexisting", json_object_new_boolean(before)) ||
                !dw_add(f, "attempt_changed", json_object_new_boolean(delta)) ||
                !dw_add(f, "protected", json_object_new_boolean(hit)) ||
                !dw_add(
                    f, "staged",
                    json_object_new_boolean(current && !same_content(dw_get(current, "head"),
                                                                     dw_get(current, "index")))) ||
                !dw_add(f, "unstaged",
                        json_object_new_boolean(current &&
                                                !same_content(dw_get(current, "index"),
                                                              dw_get(current, "worktree")))) ||
                !dw_add(f, "untracked",
                        json_object_new_boolean(current && !dw_get(current, "index") &&
                                                dw_get(current, "worktree"))) ||
                !dw_add(f, "deleted",
                        json_object_new_boolean(!current || !dw_get(current, "worktree"))))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK && json_object_array_add(findings, json_object_get(f)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            json_object_put(f);
        }
        i += cmp <= 0;
        j += cmp >= 0;
    }
    bool moved = strcmp(dw_text(base, "head"), dw_text(now, "head")) != 0;
    bool exceeded = !policy->unlimited && changed > policy->maximum;
    if (st == GOLEM_OK &&
        (!dw_add(result, "schema_version", json_object_new_int(1)) ||
         !dw_add(result, "complete", json_object_new_boolean(true)) ||
         !dw_add(result, "allowed", json_object_new_boolean(!protected && !exceeded && !moved)) ||
         !dw_add(result, "head_changed", json_object_new_boolean(moved)) ||
         !dw_add(result, "limit_exceeded", json_object_new_boolean(exceeded)) ||
         !dw_add(result, "changed_paths", json_object_new_uint64(changed)) ||
         !dw_add(result, "preexisting_paths", json_object_new_uint64(preexisting)) ||
         !dw_add(result, "protected_paths", json_object_new_uint64(protected)) ||
         !dw_add_digest(result, "policy", &policy->digest) ||
         !dw_add(result, "findings", json_object_get(findings))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(findings);
    if (st == GOLEM_OK)
        *out = result;
    else
        json_object_put(result);
    return st;
}
