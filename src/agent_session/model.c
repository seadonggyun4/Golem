#include "internal.h"
#include "binding_internal.h"
#include <string.h>

bool as_active(struct json_object *state)
{
    return dw_get(state, "active") != NULL;
}
bool as_token(struct json_object *a, struct json_object *token)
{
    const char *keys[] = {"epoch", "attempt_id", "session_id"};
    return a && dw_keys(token, keys, 3) && dw_uint(a, "epoch") == dw_uint(token, "epoch") &&
           strcmp(dw_text(a, "attempt_id"), dw_text(token, "attempt_id")) == 0 &&
           strcmp(dw_text(a, "session_id"), dw_text(token, "session_id")) == 0;
}
bool as_live(const as_log *l, uint64_t now, const golem_digest *boot)
{
    return as_active(l->state) && dw_equal(&l->boot, boot) && now >= l->observed_ms &&
           now < dw_uint(dw_get(l->state, "active"), "expires_ms");
}
static bool text(struct json_object *o, const char *k, const char *v)
{
    return dw_add(o, k, json_object_new_string(v));
}
static bool number(struct json_object *o, const char *k, uint64_t v)
{
    return dw_add(o, k, json_object_new_uint64(v));
}
golem_status as_reduce(struct json_object *prior, struct json_object *e, struct json_object **out)
{
    const char *ek[] = {"schema_version", "sequence", "operation",        "key", "request_digest",
                        "observed_ms",    "boot_id",  "work_spec_digest", "data"};
    golem_digest digest;
    uint64_t seq = dw_uint(e, "sequence"), now = dw_uint(e, "observed_ms");
    const char *op = dw_text(e, "operation");
    struct json_object *d = dw_get(e, "data"), *s = NULL;
    bool session_event = dw_uint(e, "schema_version") == 3 &&
                         (!strcmp(op, "bind") || !strcmp(op, "claim") || !strcmp(op, "resume"));
    bool bound_claim = (dw_uint(e, "schema_version") == 2 || session_event) &&
                       !strcmp(op, "claim") && dw_get(d, "runtime_binding");
    if (!dw_keys(e, ek, 9) ||
        (dw_uint(e, "schema_version") != 1 && !bound_claim && !session_event) ||
        seq != (prior ? dw_uint(prior, "sequence") : 0) + 1 || now == UINT64_MAX ||
        !dw_digest(e, "work_spec_digest", &digest) || !dw_id(dw_text(e, "key")) ||
        !dw_digest(e, "request_digest", &digest) || !dw_digest(e, "boot_id", &digest))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    if (!prior) {
        const char *keys[] = {"selection_id"};
        if (strcmp(op, "start") != 0 || !dw_keys(d, keys, 1) || !dw_id(dw_text(d, "selection_id")))
            return GOLEM_ERR_INVALID_STATE;
        s = json_object_new_object();
        if (!s || !text(s, "selection_id", dw_text(d, "selection_id")) || !number(s, "epoch", 0) ||
            !number(s, "attempts", 0) || json_object_object_add(s, "active", NULL) != 0 ||
            !dw_add(s, "completed", json_object_new_array())) {
            json_object_put(s);
            return GOLEM_ERR_OUT_OF_MEMORY;
        }
    } else if (json_object_deep_copy(prior, &s, NULL) != 0)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = GOLEM_OK;
    struct json_object *a = dw_get(s, "active");
    const char *state = dw_text(a, "state");
    if (strcmp(op, "start") == 0) {
        if (prior)
            st = GOLEM_ERR_INVALID_STATE;
    } else if (strcmp(op, "bind") == 0) {
        st = ab_reduce(s, e);
    } else if (strcmp(op, "claim") == 0) {
        const char *keys[] = {"attempt_id",      "session_id",       "epoch", "expires_ms",
                              "manifest_digest", "input_generation", "kind",  "policy_digest",
                              "source_snapshot", "scope_revision",   "state", "runtime_binding",
                              "session_binding"};
        if (session_event && !bound_claim)
            keys[11] = "session_binding";
        struct json_object *binding = dw_get(s, "binding");
        if (a || !dw_keys(d, keys, 11 + (bound_claim ? 1 : 0) + (session_event ? 1 : 0)) ||
            ((binding != NULL) != session_event) ||
            (session_event &&
             (strcmp(dw_text(binding, "binding_id"), dw_text(d, "session_binding")) ||
              strcmp(dw_text(binding, "session_id"), dw_text(d, "session_id")))) ||
            (bound_claim && !dw_digest(d, "runtime_binding", &digest)) ||
            !dw_id(dw_text(d, "attempt_id")) || !dw_id(dw_text(d, "session_id")) ||
            dw_uint(d, "epoch") != seq || dw_uint(d, "expires_ms") <= now ||
            dw_uint(d, "expires_ms") - now > GOLEM_AGENT_MAX_TTL_MS ||
            !dw_uint(d, "input_generation") || wf_kind(dw_text(d, "kind")) < 0 ||
            dw_uint(d, "scope_revision") != 1 || !dw_digest(d, "manifest_digest", &digest) ||
            !dw_digest(d, "policy_digest", &digest) || !dw_digest(d, "source_snapshot", &digest) ||
            strcmp(dw_text(d, "state"), "CLAIMED") != 0 ||
            dw_uint(s, "attempts") >= GOLEM_AGENT_MAX_ATTEMPTS)
            st = GOLEM_ERR_INVALID_STATE;
        else if (!dw_add(s, "active", json_object_get(d)) || !number(s, "epoch", seq) ||
                 !number(s, "attempts", dw_uint(s, "attempts") + 1))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    } else if (strcmp(op, "resume") == 0) {
        const char *keys[] = {"session_id", "expires_ms", "session_binding", "token"};
        struct json_object *binding = dw_get(s, "binding");
        if (!dw_keys(d, keys, session_event ? 4 : 2) || !dw_id(dw_text(d, "session_id")) ||
            ((binding != NULL) != session_event) ||
            (session_event &&
             (strcmp(dw_text(binding, "binding_id"), dw_text(d, "session_binding")) ||
              strcmp(dw_text(binding, "session_id"), dw_text(d, "session_id")) ||
              (a ? !as_token(a, dw_get(d, "token")) : dw_get(d, "token") != NULL))) ||
            dw_uint(d, "expires_ms") <= now ||
            dw_uint(d, "expires_ms") - now > GOLEM_AGENT_MAX_TTL_MS)
            st = GOLEM_ERR_PARSE;
        else {
            if (a && strcmp(state, "CLAIMED") != 0) {
                if (!text(a, "state", "RECOVERY_REQUIRED") ||
                    !text(a, "session_id", dw_text(d, "session_id")) || !number(a, "epoch", seq) ||
                    !number(a, "expires_ms", dw_uint(d, "expires_ms")))
                    st = GOLEM_ERR_OUT_OF_MEMORY;
            } else if (json_object_object_add(s, "active", NULL) != 0)
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (!number(s, "epoch", seq))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
    } else if (strcmp(op, "begin") == 0 || strcmp(op, "heartbeat") == 0) {
        const char *keys[] = {"token", "expires_ms"};
        if (!dw_keys(d, keys, 2) || !as_token(a, dw_get(d, "token")) ||
            (strcmp(op, "begin") == 0 && strcmp(state, "CLAIMED") != 0) ||
            dw_uint(d, "expires_ms") < dw_uint(a, "expires_ms") ||
            dw_uint(d, "expires_ms") <= now ||
            dw_uint(d, "expires_ms") - now > GOLEM_AGENT_MAX_TTL_MS)
            st = GOLEM_ERR_INVALID_STATE;
        else if (!number(a, "expires_ms", dw_uint(d, "expires_ms")) ||
                 (strcmp(op, "begin") == 0 && !text(a, "state", "RUNNING")))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    } else if (strcmp(op, "submit") == 0 || strcmp(op, "reconcile") == 0) {
        const char *keys[] = {"token", "resolution", "output", "evidence", "trust"};
        const char *resolution = dw_text(d, "resolution");
        bool adopt = strcmp(resolution, "ADOPT_OUTPUT") == 0;
        if (!dw_keys(d, keys, 5) || !as_token(a, dw_get(d, "token")) ||
            strcmp(dw_text(d, "trust"), "self_reported") != 0 ||
            (strcmp(op, "submit") == 0 && (strcmp(state, "RUNNING") != 0 || !adopt)) ||
            (strcmp(op, "reconcile") == 0 && strcmp(state, "RECOVERY_REQUIRED") != 0) ||
            (!adopt && strcmp(resolution, "NO_EFFECTS") != 0) ||
            (adopt && !wf_reference(dw_get(d, "output"))) || (!adopt && dw_get(d, "output")) ||
            !json_object_is_type(dw_get(d, "evidence"), json_type_array) ||
            !json_object_array_length(dw_get(d, "evidence")) ||
            json_object_array_length(dw_get(d, "evidence")) > 64)
            st = GOLEM_ERR_INVALID_STATE;
        for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(dw_get(d, "evidence"));
             ++i) {
            const char *v =
                json_object_get_string(json_object_array_get_idx(dw_get(d, "evidence"), i));
            if (!v || golem_digest_parse((golem_string_view){v, strlen(v)}, &digest) != GOLEM_OK)
                st = GOLEM_ERR_PARSE;
        }
        if (st == GOLEM_OK && adopt &&
            !wf_append(dw_get(s, "completed"), json_object_get(dw_get(d, "output"))))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && json_object_object_add(s, "active", NULL) != 0)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    } else
        st = GOLEM_ERR_UNSUPPORTED_VERSION;
    if (st == GOLEM_OK && !number(s, "sequence", seq))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        *out = s;
    else
        json_object_put(s);
    return st;
}
struct json_object *as_receipt(struct json_object *event, struct json_object *state)
{
    struct json_object *r = json_object_new_object();
    const char *bytes = json_object_to_json_string_ext(event, JSON_C_TO_STRING_PLAIN);
    golem_digest digest;
    if (!bytes || golem_digest_bytes((golem_bytes){(const uint8_t *)bytes, strlen(bytes)},
                                     &digest) != GOLEM_OK) {
        json_object_put(r);
        return NULL;
    }
    if (!dw_add(r, "schema_version", json_object_new_int(1)) ||
        !dw_add(r, "committed", json_object_new_boolean(true)) ||
        !dw_add(r, "sequence", json_object_get(dw_get(event, "sequence"))) ||
        !dw_add(r, "operation", json_object_get(dw_get(event, "operation"))) ||
        !dw_add(r, "state", json_object_get(state)) ||
        !dw_add(r, "acceptance_verified", json_object_new_boolean(false)) ||
        !dw_add(r, "execution_authorized", json_object_new_boolean(false)) ||
        !dw_add_digest(r, "receipt_digest", &digest) ||
        !dw_add(r, "record", json_object_get(event))) {
        json_object_put(r);
        return NULL;
    }
    return r;
}
