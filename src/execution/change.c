#include "internal.h"
#include "../inventory/internal.h"
#include <string.h>
#include <unistd.h>

/* A checkpoint remains the baseline for every attempt. An observation never
 * grants permission to adopt the current bytes as a replacement baseline. */
golem_status ex_inventory_check(golem_document_store *store, struct json_object *cp,
                                struct json_object *snapshot, bool publish)
{
    struct json_object *contract = dw_get(cp, "contract");
    if (dw_uint(contract, "schema_version") < 4)
        return GOLEM_OK;
    bool external = dw_uint(contract, "schema_version") == 5;
    struct json_object *plans = dw_get(dw_get(contract, "snapshot_plan"), "repositories");
    struct json_object *before = dw_get(dw_get(cp, "baseline"), "repositories");
    struct json_object *after = dw_get(snapshot, "repositories");
    if (json_object_array_length(before) != json_object_array_length(plans) ||
        json_object_array_length(after) != json_object_array_length(plans))
        return GOLEM_ERR_PARSE;
    struct json_object *findings = json_object_new_array(), *receipt = json_object_new_object();
    golem_status st = findings && receipt ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    bool allowed = true;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(plans); ++i) {
        struct json_object *plan = json_object_array_get_idx(plans, i), *finding = NULL;
        struct json_object *old = json_object_array_get_idx(before, i),
                           *now = json_object_array_get_idx(after, i);
        in_policy policy;
        st = in_policy_parse(dw_get(plan, "change_policy"), &policy);
        if (st == GOLEM_OK && (strcmp(dw_text(plan, "id"), dw_text(old, "id")) ||
                               strcmp(dw_text(plan, "id"), dw_text(now, "id"))))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        struct json_object *old_inventory = NULL, *new_inventory = NULL;
        if (st == GOLEM_OK && external)
            st = ex_inventory_load(store, old, &old_inventory);
        if (st == GOLEM_OK && external)
            st = ex_inventory_load(store, now, &new_inventory);
        if (st == GOLEM_OK)
            st = in_compare(external ? old_inventory : dw_get(old, "inventory"),
                            external ? new_inventory : dw_get(now, "inventory"), &policy, &finding);
        json_object_put(old_inventory);
        json_object_put(new_inventory);
        if (st == GOLEM_OK) {
            allowed = allowed && json_object_get_boolean(dw_get(finding, "allowed"));
            if (!ex_text(finding, "repository", dw_text(plan, "id")) ||
                json_object_array_add(findings, json_object_get(finding)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        json_object_put(finding);
    }
    if (st == GOLEM_OK && publish) {
        golem_digest checkpoint, digest;
        st = ex_hash(cp, &checkpoint);
        struct json_object *reference = NULL;
        if (st == GOLEM_OK && external)
            st = ex_object_ref(store, findings, "golem.change-findings-array.v1",
                               8u * GOLEM_INVENTORY_MAX_JSON, true, &reference);
        if (st == GOLEM_OK &&
            (!ex_uint(receipt, "schema_version", external ? 2 : 1) ||
             !ex_text(receipt, "type",
                      external ? "golem.change-findings.v2" : "golem.change-findings.v1") ||
             !dw_add_digest(receipt, "checkpoint", &checkpoint) ||
             !dw_add(receipt, "snapshot", json_object_get(snapshot)) ||
             !dw_add(receipt, external ? "findings_ref" : "findings",
                     json_object_get(external ? reference : findings)) ||
             !dw_add(receipt, "allowed", json_object_new_boolean(allowed))))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(reference);
        golem_execution_reply encoded = {0};
        if (st == GOLEM_OK)
            st = ex_emit(receipt, &encoded);
        golem_execution_reply_free(&encoded);
        if (st == GOLEM_OK)
            st = dw_put_json(store, receipt, &digest);
        int dir = -1;
        if (st == GOLEM_OK)
            st = dw_dir(store->root, "change-findings", true, &dir);
        char name[65];
        size_t length;
        if (st == GOLEM_OK)
            st = golem_digest_format(&digest, name, sizeof(name), &length);
        if (st == GOLEM_OK)
            st = dw_publish(dir, name, (golem_bytes){digest.bytes, sizeof(digest.bytes)});
        if (dir >= 0)
            close(dir);
    }
    json_object_put(receipt);
    json_object_put(findings);
    return st != GOLEM_OK ? st : allowed ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED;
}
