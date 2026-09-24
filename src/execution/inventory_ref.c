#include "internal.h"
#include "../inventory/internal.h"
#include <string.h>

golem_status ex_object_ref(golem_document_store *store, struct json_object *object,
                           const char *type, size_t limit, bool publish, struct json_object **out)
{
    const char *bytes = json_object_to_json_string_ext(object, JSON_C_TO_STRING_PLAIN);
    if (!bytes)
        return GOLEM_ERR_OUT_OF_MEMORY;
    size_t size = strlen(bytes);
    if (size > limit)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    golem_digest digest;
    golem_status st = ex_hash(object, &digest);
    /* Publish dependencies before the receipt. Interrupted writes can leave
     * unreferenced CAS objects, never a receipt claiming missing evidence. */
    if (st == GOLEM_OK && publish)
        st = dw_put_json(store, object, &digest);
    struct json_object *ref = json_object_new_object();
    if (st == GOLEM_OK &&
        (!ref || !ex_uint(ref, "schema_version", 1) || !ex_text(ref, "type", type) ||
         !ex_uint(ref, "size", size) || !dw_add_digest(ref, "digest", &digest)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        *out = ref;
    else
        json_object_put(ref);
    return st;
}

golem_status ex_inventory_load(golem_document_store *store, struct json_object *repo,
                               struct json_object **out)
{
    struct json_object *ref = dw_get(repo, "inventory_ref");
    const char *keys[] = {"schema_version", "type", "size", "digest"};
    golem_digest digest;
    if (!dw_keys(ref, keys, 4) || dw_uint(ref, "schema_version") != 1 ||
        !json_object_is_type(dw_get(ref, "size"), json_type_int) ||
        !json_object_is_type(dw_get(ref, "schema_version"), json_type_int) ||
        strcmp(dw_text(ref, "type"), "golem.inventory.v1") || !dw_digest(ref, "digest", &digest) ||
        !dw_uint(ref, "size") || dw_uint(ref, "size") > GOLEM_INVENTORY_MAX_JSON ||
        dw_get(repo, "inventory"))
        return GOLEM_ERR_PARSE;
    uint8_t *bytes = NULL;
    size_t size = 0;
    struct json_object *object = NULL;
    golem_status st = golem_evidence_read(store->cas, &digest, GOLEM_INVENTORY_MAX_JSON,
                                          &store->allocator, &bytes, &size, NULL);
    if (st == GOLEM_OK && size != dw_uint(ref, "size"))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){bytes, size}, GOLEM_INVENTORY_MAX_JSON, &object);
    dw_scratch_free(store, bytes);
    if (st == GOLEM_OK && (dw_uint(object, "schema_version") != 1 ||
                           strcmp(dw_text(object, "head"), dw_text(repo, "head"))))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        *out = object;
    else
        json_object_put(object);
    return st;
}

golem_status ex_snapshot_verify(golem_document_store *store, struct json_object *snapshot)
{
    struct json_object *repos = dw_get(snapshot, "repositories");
    if (!ds_array(repos, 1, 8))
        return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < json_object_array_length(repos); ++i) {
        struct json_object *inventory = NULL;
        golem_status st = ex_inventory_load(store, json_object_array_get_idx(repos, i), &inventory);
        json_object_put(inventory);
        if (st != GOLEM_OK)
            return st;
    }
    return GOLEM_OK;
}
