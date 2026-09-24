#include "internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static golem_status gate_key(struct json_object *cp, golem_digest *out)
{
    struct json_object *contract = dw_get(cp, "contract"),
                       *plan = dw_get(contract, "snapshot_plan");
    uint64_t version = dw_uint(contract, "schema_version");
    if ((version != 4 && version != 5) || !ds_array(dw_get(plan, "repositories"), 1, 1))
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    struct json_object *repo = json_object_array_get_idx(dw_get(plan, "repositories"), 0);
    const char *root = dw_text(repo, "root");
    size_t prefix = strlen(root);
    struct json_object *gates = NULL, *oracles = json_object_new_array(),
                       *identity = json_object_new_object();
    golem_status st = json_object_deep_copy(dw_get(contract, "gates"), &gates, NULL) == 0
                          ? GOLEM_OK
                          : GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *baseline =
        json_object_array_get_idx(dw_get(dw_get(cp, "baseline"), "repositories"), 0);
    struct json_object *files = dw_get(baseline, "files");
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(gates); ++i) {
        struct json_object *gate = json_object_array_get_idx(gates, i),
                           *argv = dw_get(gate, "argv");
        for (size_t j = 0; st == GOLEM_OK && j < json_object_array_length(argv); ++j) {
            const char *arg = json_object_get_string(json_object_array_get_idx(argv, j));
            if (strlen(arg) > prefix && !memcmp(root, arg, prefix) && arg[prefix] == '/') {
                char normalized[4096];
                int n = snprintf(normalized, sizeof(normalized), "$CANDIDATE%s", arg + prefix);
                if (n < 0 || (size_t)n >= sizeof(normalized))
                    st = GOLEM_ERR_OVERFLOW;
                else {
                    struct json_object *v = json_object_new_string(normalized);
                    if (!v || json_object_array_put_idx(argv, j, v) != 0) {
                        json_object_put(v);
                        st = GOLEM_ERR_OUT_OF_MEMORY;
                    }
                }
            }
        }
        struct json_object *protected = dw_get(gate, "protected_paths");
        if (!ds_array(protected, 1, 64))
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
        for (size_t j = 0; st == GOLEM_OK && j < json_object_array_length(protected); ++j) {
            const char *name = json_object_get_string(json_object_array_get_idx(protected, j));
            struct json_object *found = NULL;
            for (size_t k = 0; k < json_object_array_length(files); ++k) {
                struct json_object *file = json_object_array_get_idx(files, k);
                if (!strcmp(dw_text(file, "path"), name))
                    found = file;
            }
            if (!found)
                st = GOLEM_ERR_REQUIREMENTS_UNMET;
            else if (!wf_append(oracles, json_object_get(found)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    if (st == GOLEM_OK &&
        (!ex_uint(identity, "schema_version", 1) ||
         !dw_add(identity, "gates", json_object_get(gates)) ||
         !dw_add(identity, "executables", json_object_get(dw_get(cp, "executables"))) ||
         !dw_add(identity, "oracles", json_object_get(oracles)) ||
         !dw_add(identity, "change_policy", json_object_get(dw_get(repo, "change_policy"))) ||
         !dw_add(identity, "log_retention", json_object_get(dw_get(contract, "log_retention"))) ||
         !ex_text(identity, "toolchain", dw_text(repo, "toolchain")) ||
         !ex_text(identity, "test_configuration", dw_text(repo, "test_configuration"))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ex_hash(identity, out);
    json_object_put(identity);
    json_object_put(oracles);
    json_object_put(gates);
    return st;
}
golem_status golem_candidate_gate_digest(golem_document_store *s, const golem_digest *key,
                                         golem_digest *out, golem_diagnostic *d)
{
    if (!s || !key || !out || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *cp = NULL;
    golem_digest digest;
    golem_status st = ex_load(s, key, "checkpoint", &cp);
    if (st == GOLEM_OK)
        st = gate_key(cp, &digest);
    json_object_put(cp);
    if (st == GOLEM_OK)
        *out = digest;
    return dw_report(d, st, NULL);
}
golem_status cf_qa(golem_document_store *s, const golem_digest *key, const char *root,
                   const char *base, golem_digest *gates, struct json_object **out)
{
    struct json_object *qa = NULL, *cp = NULL, *now = NULL;
    golem_digest checkpoint;
    golem_status st = ex_load(s, key, "qa", &qa);
    if (st == GOLEM_OK && !dw_digest(qa, "checkpoint", &checkpoint))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = ex_load(s, &checkpoint, "checkpoint", &cp);
    if (st == GOLEM_OK)
        st = gate_key(cp, gates);
    struct json_object *plan = dw_get(dw_get(cp, "contract"), "snapshot_plan");
    struct json_object *repos = dw_get(plan, "repositories");
    if (st == GOLEM_OK && strcmp(dw_text(json_object_array_get_idx(repos, 0), "root"), root))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        st = ex_current(s, dw_get(qa, "manifest"));
    if (st == GOLEM_OK)
        st = ex_snapshot(s, plan, false, &now);
    if (st == GOLEM_OK)
        st = ex_inventory_check(s, cp, now, false);
    if (st == GOLEM_OK && !json_object_equal(now, dw_get(qa, "snapshot")))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK) {
        struct json_object *original =
            json_object_array_get_idx(dw_get(dw_get(cp, "baseline"), "repositories"), 0);
        struct json_object *current = json_object_array_get_idx(dw_get(now, "repositories"), 0);
        if (strcmp(dw_text(original, "head"), base) || strcmp(dw_text(current, "head"), base))
            st = GOLEM_ERR_STALE_RESULT;
    }
    json_object_put(cp);
    json_object_put(now);
    if (st == GOLEM_OK)
        *out = qa;
    else
        json_object_put(qa);
    return st;
}
