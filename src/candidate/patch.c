#include "internal.h"
#include <string.h>

/* Called only after both issued QA receipts pass cf_qa's freshness and policy
 * checks. Physical root identity differs intentionally; content identity must
 * not. Exact scoped equivalence is stricter than patch applicability: unrelated
 * target edits are not silently accepted. No fuzzy rename/merge inference. */
static golem_status inventory_identity(struct json_object *a, struct json_object *b,
                                       golem_digest *out)
{
    golem_digest policy_a, policy_b;
    if (dw_uint(a, "schema_version") != 1 || dw_uint(b, "schema_version") != 1 ||
        !ws_oid(dw_text(a, "head")) || strcmp(dw_text(a, "head"), dw_text(b, "head")) ||
        !dw_digest(a, "policy", &policy_a) || !dw_digest(b, "policy", &policy_b) ||
        !dw_equal(&policy_a, &policy_b) ||
        !json_object_is_type(dw_get(a, "entries"), json_type_array) ||
        !json_object_is_type(dw_get(b, "entries"), json_type_array) ||
        !json_object_equal(dw_get(a, "entries"), dw_get(b, "entries")))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *identity = json_object_new_object();
    golem_status st = GOLEM_OK;
    if (!ex_uint(identity, "schema_version", 1) ||
        !ex_text(identity, "type", "golem.scoped-patch-identity.v1") ||
        !ex_text(identity, "head", dw_text(a, "head")) ||
        !dw_add_digest(identity, "policy", &policy_a) ||
        !dw_add(identity, "entries", json_object_get(dw_get(a, "entries"))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ex_hash(identity, out);
    json_object_put(identity);
    return st;
}

static golem_status inventory(golem_document_store *store, struct json_object *qa,
                              struct json_object **out)
{
    struct json_object *repos = dw_get(dw_get(qa, "snapshot"), "repositories");
    if (!ds_array(repos, 1, 1))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *repo = json_object_array_get_idx(repos, 0);
    if (dw_uint(qa, "schema_version") == 5)
        return store ? ex_inventory_load(store, repo, out) : GOLEM_ERR_INVALID_ARGUMENT;
    if (dw_get(repo, "inventory_ref") || !dw_get(repo, "inventory"))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    *out = json_object_get(dw_get(repo, "inventory"));
    return GOLEM_OK;
}

golem_status cf_patch_identity(golem_document_store *selected_store, struct json_object *selected,
                               golem_document_store *target_store, struct json_object *target,
                               golem_digest *out)
{
    if (!out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *a = NULL, *b = NULL;
    golem_status st = inventory(selected_store, selected, &a);
    if (st == GOLEM_OK)
        st = inventory(target_store, target, &b);
    if (st == GOLEM_OK)
        st = inventory_identity(a, b, out);
    json_object_put(a);
    json_object_put(b);
    return st;
}
