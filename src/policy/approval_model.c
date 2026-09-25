#include "approval_internal.h"
#include <string.h>

golem_status ap_action(struct json_object *a)
{
    const char *keys[] = {
        "schema_version", "domain",          "work_id",      "operation",     "request_digest",
        "policy_digest",  "contract_digest", "input_digest", "source_digest", "executables_digest",
        "profile_digest", "role_digest",     "binding_id",   "token"};
    if (!dw_keys(a, keys, 14) || dw_uint(a, "schema_version") != 1 ||
        strcmp(dw_text(a, "domain"), "golem.approval-action.v1") || !dw_id(dw_text(a, "work_id")))
        return GOLEM_ERR_PARSE;
    const char *op = dw_text(a, "operation");
    if (strcmp(op, "prepare") && strcmp(op, "finish") && strcmp(op, "run"))
        return GOLEM_ERR_PARSE;
    golem_digest digest;
    for (size_t i = 4; i <= 11; ++i)
        if (!dw_digest(a, keys[i], &digest))
            return GOLEM_ERR_PARSE;
    const char *binding = dw_text(a, "binding_id");
    if (!json_object_is_type(dw_get(a, "binding_id"), json_type_string) ||
        (binding[0] && !dw_id(binding)))
        return GOLEM_ERR_PARSE;
    struct json_object *t = dw_get(a, "token");
    const char *tk[] = {"epoch", "attempt_id", "session_id"};
    if (t && (!dw_keys(t, tk, 3) || !dw_uint(t, "epoch") ||
              dw_uint(t, "epoch") > GOLEM_AGENT_MAX_EVENTS || !dw_id(dw_text(t, "attempt_id")) ||
              !dw_id(dw_text(t, "session_id"))))
        return GOLEM_ERR_PARSE;
    if (binding[0] && !t)
        return GOLEM_ERR_PARSE;
    return GOLEM_OK;
}
golem_status ap_request(struct json_object *r)
{
    const char *op = dw_text(r, "operation");
    const char *create[] = {"schema_version", "operation", "key", "action", "ttl_ms"};
    const char *mutation[] = {"schema_version", "operation", "key", "request_receipt", "reason"};
    const char *read[] = {"schema_version", "operation", "request_receipt"};
    if (dw_uint(r, "schema_version") != 1)
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (!strcmp(op, "request")) {
        if (!dw_keys(r, create, 5) || !dw_id(dw_text(r, "key")) || !dw_uint(r, "ttl_ms") ||
            dw_uint(r, "ttl_ms") > GOLEM_APPROVAL_MAX_TTL_MS)
            return GOLEM_ERR_PARSE;
        return ap_action(dw_get(r, "action"));
    }
    golem_digest digest;
    if (!dw_digest(r, "request_receipt", &digest))
        return GOLEM_ERR_PARSE;
    if (!strcmp(op, "status") || !strcmp(op, "recover"))
        return dw_keys(r, read, 3) ? GOLEM_OK : GOLEM_ERR_PARSE;
    if (strcmp(op, "approve") && strcmp(op, "deny") && strcmp(op, "revoke") && strcmp(op, "expire"))
        return GOLEM_ERR_PARSE;
    if (!dw_keys(r, mutation, 5) || !dw_id(dw_text(r, "key")) || !dw_id(dw_text(r, "reason")))
        return GOLEM_ERR_PARSE;
    return GOLEM_OK;
}
golem_status golem_approval_request_validate(golem_bytes bytes)
{
    struct json_object *r = NULL;
    golem_status st = golem_json_parse(bytes, GOLEM_APPROVAL_MAX_JSON, &r);
    if (st == GOLEM_OK)
        st = ap_request(r);
    json_object_put(r);
    return st;
}
