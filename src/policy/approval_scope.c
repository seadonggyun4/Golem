#include "approval_internal.h"
#include "../agent_session/internal.h"
#include <string.h>

static golem_status hash_field(struct json_object *action, const char *field,
                               struct json_object *value)
{
    golem_digest digest;
    golem_status st = ex_hash(value, &digest);
    if (st == GOLEM_OK && !dw_add_digest(action, field, &digest))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    return st;
}
golem_status ap_scope(golem_document_store *s, golem_bytes bytes, struct json_object **out)
{
    struct json_object *r = NULL, *cp = NULL, *manifest = NULL, *snapshot = NULL;
    struct json_object *a = NULL, *executables = NULL;
    as_log log = {.directory = -1};
    golem_status st = golem_json_parse(bytes, GOLEM_DOCUMENT_MAX_JSON, &r);
    const char *op = dw_text(r, "operation");
    bool prepare = !strcmp(op, "prepare"), run = !strcmp(op, "run");
    bool token = dw_get(r, "token") != NULL;
    const char *keys[] = {"schema_version", "operation", prepare ? "contract" : "checkpoint",
                          run ? "attempt_id" : "token", "token"};
    if (st == GOLEM_OK &&
        (!dw_keys(r, keys, (run ? 4 : 3) + (token ? 1 : 0)) || dw_uint(r, "schema_version") != 1 ||
         (!prepare && !run && strcmp(op, "finish")) || (run && !dw_id(dw_text(r, "attempt_id")))))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK && !prepare) {
        golem_digest key;
        st = dw_digest(r, "checkpoint", &key) ? ex_load(s, &key, "checkpoint", &cp)
                                              : GOLEM_ERR_PARSE;
    }
    struct json_object *contract = prepare ? dw_get(r, "contract") : dw_get(cp, "contract");
    if (st == GOLEM_OK)
        st = ex_contract(contract);
    if (st == GOLEM_OK)
        st = ex_inputs(s, contract, run ? "qa-result" : "development-result", &manifest);
    if (st == GOLEM_OK)
        st = ex_authorize(s, dw_get(r, "token"), manifest);
    if (st == GOLEM_OK)
        st = ex_snapshot(s, dw_get(contract, "snapshot_plan"), false, &snapshot);
    if (st == GOLEM_OK)
        st = as_load(s, NULL, NULL, &log);
    if (st == GOLEM_OK) {
        a = json_object_new_object();
        executables = json_object_new_array();
        if (!a || !executables)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    struct json_object *gates = dw_get(contract, "gates");
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(gates); ++i) {
        struct json_object *gate = json_object_array_get_idx(gates, i);
        st = ex_command_check(gate, dw_get(contract, "snapshot_plan"));
        const char *path =
            json_object_get_string(json_object_array_get_idx(dw_get(gate, "argv"), 0));
        golem_receipt file;
        if (st == GOLEM_OK)
            st = golem_digest_file(path, &file, NULL);
        struct json_object *v = json_object_new_object();
        if (st == GOLEM_OK &&
            (!dw_add_digest(v, "digest", &file.digest) || !ex_uint(v, "size", file.size)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) {
            if (!wf_append(executables, v))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        } else
            json_object_put(v);
    }
    if (st == GOLEM_OK &&
        (!ex_uint(a, "schema_version", 1) || !ex_text(a, "domain", "golem.approval-action.v1") ||
         !ex_text(a, "work_id", dw_text(s->spec, "work_id")) || !ex_text(a, "operation", op) ||
         !ex_text(a, "binding_id", dw_text(dw_get(log.state, "binding"), "binding_id")) ||
         json_object_object_add(a, "token", json_object_get(dw_get(r, "token"))) != 0))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    const char *names[] = {"request_digest", "policy_digest", "contract_digest",
                           "input_digest",   "source_digest", "executables_digest",
                           "profile_digest", "role_digest"};
    struct json_object *values[] = {
        r,
        s->spec,
        contract,
        manifest,
        snapshot,
        executables,
        s->runtime_profile_count ? s->runtime_profiles[s->runtime_profile_count - 1] : NULL,
        s->role_count ? s->roles[0] : NULL};
    for (size_t i = 0; st == GOLEM_OK && i < 8; ++i)
        st = hash_field(a, names[i], values[i]);
    if (st == GOLEM_OK)
        st = ap_action(a);
    if (st == GOLEM_OK)
        *out = a;
    else
        json_object_put(a);
    as_close(&log);
    json_object_put(r);
    json_object_put(cp);
    json_object_put(manifest);
    json_object_put(snapshot);
    json_object_put(executables);
    return st;
}
golem_status golem_approval_describe(golem_document_store *s, golem_bytes bytes,
                                     golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *a = NULL, *r = NULL;
    golem_digest digest;
    golem_status st = ap_scope(s, bytes, &a);
    if (st == GOLEM_OK)
        st = ex_hash(a, &digest);
    if (st == GOLEM_OK) {
        r = json_object_new_object();
        if (!dw_add(r, "action", json_object_get(a)) || !dw_add_digest(r, "action_digest", &digest))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        st = ex_emit(r, out);
    json_object_put(a);
    json_object_put(r);
    return dw_report(d, st, NULL);
}
