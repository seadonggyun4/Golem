#include "approval_internal.h"
#include "../agent_session/internal.h"
#include <string.h>

static bool host_valid(const golem_approval_host *h)
{
    return h && h->struct_size == sizeof(*h) && h->version == 1 && h->recheck;
}
static struct json_object *root_event(golem_document_store *s, const golem_digest *key)
{
    for (size_t i = 0; i < s->approval_count; ++i)
        if (dw_equal(key, &s->approval_digests[i]) &&
            !strcmp(dw_text(dw_get(s->approvals[i], "request"), "operation"), "request"))
            return s->approvals[i];
    return NULL;
}
static struct json_object *latest(golem_document_store *s, const golem_digest *key)
{
    for (size_t i = s->approval_count; i > 0; --i) {
        golem_digest root;
        if (dw_equal(key, &s->approval_digests[i - 1]) ||
            (dw_digest(dw_get(s->approvals[i - 1], "request"), "request_receipt", &root) &&
             dw_equal(key, &root)))
            return s->approvals[i - 1];
    }
    return NULL;
}
static bool expired(struct json_object *root, struct json_object *prior, uint64_t now,
                    const golem_digest *boot)
{
    golem_digest recorded;
    return !dw_digest(root, "boot_id", &recorded) || !dw_equal(boot, &recorded) ||
           now < dw_uint(prior, "observed_ms") || now >= dw_uint(root, "expires_ms");
}
static golem_status transition(golem_document_store *s, struct json_object *e)
{
    const char *keys[] = {"schema_version", "type",         "sequence",     "request",
                          "state",          "boot_id",      "observed_ms",  "expires_ms",
                          "issuer",         "policy_epoch", "result_digest"};
    if (!dw_keys(e, keys, 11) || dw_uint(e, "schema_version") != 1 ||
        strcmp(dw_text(e, "type"), "approval") || dw_uint(e, "sequence") != s->approval_count + 1 ||
        s->approval_count >= GOLEM_APPROVAL_MAX_EVENTS)
        return GOLEM_ERR_CORRUPT_JOURNAL;
    struct json_object *r = dw_get(e, "request");
    const char *op = dw_text(r, "operation"), *state = dw_text(e, "state");
    bool consume = !strcmp(op, "consume"), result = !strcmp(op, "result");
    golem_digest boot, digest;
    if (!dw_digest(e, "boot_id", &boot) || dw_uint(e, "observed_ms") == UINT64_MAX ||
        dw_uint(e, "expires_ms") == UINT64_MAX ||
        !json_object_is_type(dw_get(e, "issuer"), json_type_string) ||
        dw_uint(e, "policy_epoch") == UINT64_MAX ||
        !json_object_is_type(dw_get(e, "result_digest"), json_type_string))
        return GOLEM_ERR_PARSE;
    if (consume || result) {
        const char *internal[] = {"schema_version", "operation", "request_receipt"};
        if (!dw_keys(r, internal, 3) || dw_uint(r, "schema_version") != 1 ||
            !dw_digest(r, "request_receipt", &digest))
            return GOLEM_ERR_PARSE;
    } else {
        golem_status st = ap_request(r);
        if (st != GOLEM_OK || !strcmp(op, "status") || !strcmp(op, "recover"))
            return GOLEM_ERR_PARSE;
        for (size_t i = 0; i < s->approval_count; ++i)
            if (!strcmp(dw_text(dw_get(s->approvals[i], "request"), "key"), dw_text(r, "key")))
                return GOLEM_ERR_IDENTITY_MISMATCH;
    }
    uint64_t now = dw_uint(e, "observed_ms");
    if (!strcmp(op, "request")) {
        struct json_object *a = dw_get(r, "action");
        if (strcmp(state, "PENDING") ||
            strcmp(dw_text(a, "work_id"), dw_text(s->spec, "work_id")) ||
            now > UINT64_MAX - dw_uint(r, "ttl_ms") ||
            dw_uint(e, "expires_ms") != now + dw_uint(r, "ttl_ms") || dw_text(e, "issuer")[0] ||
            dw_uint(e, "policy_epoch") || dw_text(e, "result_digest")[0])
            return GOLEM_ERR_INVALID_STATE;
        size_t pending = 0;
        for (size_t i = 0; i < s->approval_count; ++i)
            if (!strcmp(dw_text(dw_get(s->approvals[i], "request"), "operation"), "request")) {
                const char *v = dw_text(latest(s, &s->approval_digests[i]), "state");
                if (!strcmp(v, "PENDING") || !strcmp(v, "APPROVED"))
                    ++pending;
            }
        return pending < GOLEM_APPROVAL_MAX_PENDING ? GOLEM_OK : GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    if (!dw_digest(r, "request_receipt", &digest))
        return GOLEM_ERR_PARSE;
    struct json_object *root = root_event(s, &digest), *prior = latest(s, &digest);
    if (!root || !prior || dw_uint(e, "expires_ms") != dw_uint(root, "expires_ms"))
        return GOLEM_ERR_NOT_FOUND;
    const char *before = dw_text(prior, "state");
    bool live = !expired(root, prior, now, &boot);
    bool pending = !strcmp(before, "PENDING"), approved = !strcmp(before, "APPROVED");
    if (!strcmp(op, "approve") || !strcmp(op, "deny") || !strcmp(op, "revoke")) {
        if (!dw_digest(e, "issuer", &digest) || !dw_uint(e, "policy_epoch") ||
            dw_text(e, "result_digest")[0])
            return GOLEM_ERR_PARSE;
        if (!strcmp(op, "revoke"))
            return (pending || approved) && !strcmp(state, "REVOKED") ? GOLEM_OK
                                                                      : GOLEM_ERR_INVALID_STATE;
        return pending && live && !strcmp(state, !strcmp(op, "approve") ? "APPROVED" : "DENIED")
                   ? GOLEM_OK
                   : GOLEM_ERR_STALE_RESULT;
    }
    if (!strcmp(op, "expire"))
        return (pending || approved) && !live && !strcmp(state, "EXPIRED") &&
                       !dw_text(e, "issuer")[0] && !dw_uint(e, "policy_epoch") &&
                       !dw_text(e, "result_digest")[0]
                   ? GOLEM_OK
                   : GOLEM_ERR_INVALID_STATE;
    if (strcmp(dw_text(e, "issuer"), dw_text(prior, "issuer")) ||
        dw_uint(e, "policy_epoch") != dw_uint(prior, "policy_epoch"))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    if (consume)
        return approved && live && !strcmp(state, "CONSUMED") && !dw_text(e, "result_digest")[0]
                   ? GOLEM_OK
                   : GOLEM_ERR_STALE_RESULT;
    if (result && !strcmp(before, "CONSUMED") && !strcmp(state, "RECORDED") &&
        dw_digest(e, "result_digest", &digest)) {
        struct json_object *response = NULL;
        golem_status st = dw_cas_json(s, &digest, &response);
        json_object_put(response);
        return st;
    }
    return GOLEM_ERR_INVALID_STATE;
}
static void adopt(golem_document_store *s, struct json_object *e, const golem_digest *key,
                  const golem_digest *frame)
{
    s->approvals[s->approval_count] = json_object_get(e);
    s->approval_digests[s->approval_count++] = *key;
    s->last = *frame;
    ++s->event_count;
}
golem_status ap_apply(golem_document_store *s, struct json_object *e, const golem_digest *key,
                      const golem_digest *frame)
{
    golem_status st = transition(s, e);
    if (st == GOLEM_OK)
        adopt(s, e, key, frame);
    return st;
}
static golem_status append(golem_document_store *s, struct json_object *e, golem_digest *key)
{
    golem_status st = transition(s, e);
    golem_digest frame;
    if (st == GOLEM_OK)
        st = dw_put_json(s, e, key);
    if (st == GOLEM_OK)
        st = dw_event_write(s, key, &frame);
    if (st == GOLEM_OK)
        adopt(s, e, key, &frame);
    return st;
}
static struct json_object *event(golem_document_store *s, struct json_object *r, const char *state,
                                 uint64_t now, const golem_digest *boot, uint64_t expires,
                                 const golem_digest *issuer, uint64_t epoch,
                                 const golem_digest *result)
{
    struct json_object *e = json_object_new_object();
    if (!ex_uint(e, "schema_version", 1) || !ex_text(e, "type", "approval") ||
        !ex_uint(e, "sequence", s->approval_count + 1) ||
        !dw_add(e, "request", json_object_get(r)) || !ex_text(e, "state", state) ||
        !dw_add_digest(e, "boot_id", boot) || !ex_uint(e, "observed_ms", now) ||
        !ex_uint(e, "expires_ms", expires) ||
        !(issuer ? dw_add_digest(e, "issuer", issuer) : ex_text(e, "issuer", "")) ||
        !ex_uint(e, "policy_epoch", epoch) ||
        !(result ? dw_add_digest(e, "result_digest", result) : ex_text(e, "result_digest", ""))) {
        json_object_put(e);
        return NULL;
    }
    return e;
}
static golem_status emit_event(struct json_object *e, const golem_digest *key,
                               golem_execution_reply *out)
{
    struct json_object *r = json_object_new_object();
    golem_status st = GOLEM_OK;
    if (!dw_add(r, "event", json_object_get(e)) || !dw_add_digest(r, "receipt_digest", key) ||
        !ex_text(r, "authority", "TRUSTED_HOST_REQUIRED"))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ex_emit(r, out);
    json_object_put(r);
    return st;
}
golem_status golem_approval_call(golem_document_store *s, golem_bytes bytes,
                                 const golem_approval_host *host, const golem_agent_clock *clock,
                                 golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *r = NULL, *e = NULL;
    golem_status st = golem_json_parse(bytes, GOLEM_APPROVAL_MAX_JSON, &r);
    if (st == GOLEM_OK)
        st = ap_request(r);
    const char *op = dw_text(r, "operation");
    bool read = !strcmp(op, "status") || !strcmp(op, "recover"), create = !strcmp(op, "request");
    golem_digest key = {{0}}, boot, issuer, action;
    struct json_object *root = NULL, *prior = NULL;
    if (st == GOLEM_OK && !create) {
        (void)dw_digest(r, "request_receipt", &key);
        root = root_event(s, &key);
        prior = latest(s, &key);
        if (!root || !prior)
            st = GOLEM_ERR_NOT_FOUND;
    }
    for (size_t i = 0; st == GOLEM_OK && !read && i < s->approval_count; ++i)
        if (!strcmp(dw_text(dw_get(s->approvals[i], "request"), "key"), dw_text(r, "key"))) {
            st = json_object_equal(dw_get(s->approvals[i], "request"), r)
                     ? emit_event(s->approvals[i], &s->approval_digests[i], out)
                     : GOLEM_ERR_IDENTITY_MISMATCH;
            json_object_put(r);
            return dw_report(d, st, NULL);
        }
    uint64_t now = 0, epoch = 0;
    if (st == GOLEM_OK)
        st = as_clock_read(clock, &now, &boot);
    if (st == GOLEM_OK && read) {
        struct json_object *reply = json_object_new_object();
        const char *state = dw_text(prior, "state");
        if ((!strcmp(state, "PENDING") || !strcmp(state, "APPROVED")) &&
            expired(root, prior, now, &boot))
            state = "EXPIRED";
        if (!ex_text(reply, "state", state) ||
            !ex_text(reply, "dispatch",
                     !strcmp(state, "CONSUMED") ? "UNCERTAIN" : "NOT_REDISPATCHED") ||
            !dw_add(reply, "record", json_object_get(prior)) ||
            !dw_add_digest(reply, "request_receipt", &key))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && !strcmp(op, "recover") && !strcmp(state, "RECORDED")) {
            struct json_object *result = NULL;
            golem_digest result_key;
            if (!dw_digest(prior, "result_digest", &result_key))
                st = GOLEM_ERR_PARSE;
            if (st == GOLEM_OK)
                st = dw_cas_json(s, &result_key, &result);
            if (st == GOLEM_OK && !dw_add(reply, "result", json_object_get(result)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            json_object_put(result);
        }
        if (st == GOLEM_OK)
            st = ex_emit(reply, out);
        json_object_put(reply);
        json_object_put(r);
        return dw_report(d, st, NULL);
    }
    if (st == GOLEM_OK && (!s->writable || !strcmp(dw_text(s->spec, "permission"), "DENY")))
        st = GOLEM_ERR_POLICY_DENIED;
    const char *state = create                   ? "PENDING"
                        : !strcmp(op, "approve") ? "APPROVED"
                        : !strcmp(op, "deny")    ? "DENIED"
                        : !strcmp(op, "revoke")  ? "REVOKED"
                                                 : "EXPIRED";
    bool decision = !create && strcmp(op, "expire");
    if (st == GOLEM_OK && decision) {
        st = ex_hash(dw_get(dw_get(root, "request"), "action"), &action);
        if (st == GOLEM_OK && (!host_valid(host) || !host->decide))
            st = GOLEM_ERR_APPROVAL_REQUIRED;
        if (st == GOLEM_OK)
            st = host->decide(host->context, &action, op, &issuer, &epoch);
        if (st == GOLEM_OK && (!epoch || epoch == UINT64_MAX))
            st = GOLEM_ERR_INVALID_ARGUMENT;
        if (st == GOLEM_OK)
            st = host->recheck(host->context, &action, &issuer, epoch);
        if (st == GOLEM_OK)
            st = as_clock_read(clock, &now, &boot);
    }
    if (st == GOLEM_OK && create && now >= UINT64_MAX - dw_uint(r, "ttl_ms"))
        st = GOLEM_ERR_OVERFLOW;
    if (st == GOLEM_OK) {
        e = event(s, r, state, now, &boot,
                  create ? now + dw_uint(r, "ttl_ms") : dw_uint(root, "expires_ms"),
                  decision ? &issuer : NULL, epoch, NULL);
        if (!e)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        st = append(s, e, &key);
    if (st == GOLEM_OK)
        st = emit_event(e, &key, out);
    json_object_put(e);
    json_object_put(r);
    return dw_report(d, st, NULL);
}
golem_status ap_guard(ap_dispatch *p)
{
    if (!p || !host_valid(p->host))
        return GOLEM_ERR_APPROVAL_REQUIRED;
    uint64_t now;
    golem_digest boot, issuer, action;
    golem_status st = as_clock_read(NULL, &now, &boot);
    if (st == GOLEM_OK &&
        (expired(p->request_event, p->approval_event, now, &boot) || now < p->last_ms))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK)
        p->last_ms = now;
    if (st == GOLEM_OK && !strcmp(dw_text(p->store->spec, "permission"), "DENY"))
        st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK)
        st = ex_hash(dw_get(dw_get(p->request_event, "request"), "action"), &action);
    if (st == GOLEM_OK && !dw_digest(p->approval_event, "issuer", &issuer))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = p->host->recheck(p->host->context, &action, &issuer,
                              dw_uint(p->approval_event, "policy_epoch"));
    return st;
}
golem_status ap_current(ap_dispatch *p)
{
    struct json_object *scope = NULL;
    golem_status st = ap_scope(p->store, p->execution_request, &scope);
    if (st == GOLEM_OK &&
        !json_object_equal(scope, dw_get(dw_get(p->request_event, "request"), "action")))
        st = GOLEM_ERR_STALE_RESULT;
    json_object_put(scope);
    return st == GOLEM_OK ? ap_guard(p) : st;
}
static struct json_object *internal_request(const char *op, const golem_digest *key)
{
    struct json_object *r = json_object_new_object();
    if (!ex_uint(r, "schema_version", 1) || !ex_text(r, "operation", op) ||
        !dw_add_digest(r, "request_receipt", key)) {
        json_object_put(r);
        return NULL;
    }
    return r;
}
golem_status golem_execution_call_receipted(golem_document_store *s, golem_bytes bytes,
                                            const golem_digest *key,
                                            const golem_approval_host *host,
                                            const golem_execution_approval *approval,
                                            golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !key || !out || s->poisoned ||
        (approval && (approval->version != 1 || approval->struct_size != sizeof(*approval))))
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (!s->writable || !strcmp(dw_text(s->spec, "permission"), "DENY"))
        return dw_report(d, GOLEM_ERR_POLICY_DENIED, NULL);
    struct json_object *root = root_event(s, key), *prior = latest(s, key), *scope = NULL;
    golem_status st = root && prior ? GOLEM_OK : GOLEM_ERR_NOT_FOUND;
    if (st == GOLEM_OK && strcmp(dw_text(prior, "state"), "APPROVED"))
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    /* Reserve a result slot before consuming; orphan CAS alone is not a result. */
    if (st == GOLEM_OK && s->approval_count > GOLEM_APPROVAL_MAX_EVENTS - 2)
        st = GOLEM_ERR_BUDGET_EXHAUSTED;
    if (st == GOLEM_OK)
        st = ap_scope(s, bytes, &scope);
    if (st == GOLEM_OK && !json_object_equal(scope, dw_get(dw_get(root, "request"), "action")))
        st = GOLEM_ERR_STALE_RESULT;
    ap_dispatch dispatch = {s, host, root, prior, bytes, 0};
    if (st == GOLEM_OK)
        st = ap_guard(&dispatch);
    struct json_object *r = NULL, *e = NULL;
    uint64_t now = 0;
    golem_digest boot, issuer, digest;
    if (st == GOLEM_OK)
        st = as_clock_read(NULL, &now, &boot);
    if (st == GOLEM_OK) {
        (void)dw_digest(prior, "issuer", &issuer);
        r = internal_request("consume", key);
        e = r ? event(s, r, "CONSUMED", now, &boot, dw_uint(root, "expires_ms"), &issuer,
                      dw_uint(prior, "policy_epoch"), NULL)
              : NULL;
        if (!e)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        st = append(s, e, &digest);
    golem_execution_reply response = {0};
    if (st == GOLEM_OK)
        st = ex_receipted(s, bytes, approval, &dispatch, &response, d);
    if (st == GOLEM_OK) {
        struct json_object *result = NULL;
        st = golem_json_parse((golem_bytes){response.data, response.size}, GOLEM_DOCUMENT_MAX_JSON,
                              &result);
        if (st == GOLEM_OK)
            st = dw_put_json(s, result, &digest);
        json_object_put(result);
        json_object_put(r);
        json_object_put(e);
        r = NULL;
        e = NULL;
        if (st == GOLEM_OK)
            st = as_clock_read(NULL, &now, &boot);
        if (st == GOLEM_OK) {
            r = internal_request("result", key);
            e = r ? event(s, r, "RECORDED", now, &boot, dw_uint(root, "expires_ms"), &issuer,
                          dw_uint(prior, "policy_epoch"), &digest)
                  : NULL;
            if (!e)
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        if (st == GOLEM_OK)
            st = append(s, e, &digest);
    }
    if (st == GOLEM_OK) {
        *out = response;
        response = (golem_execution_reply){0};
    }
    golem_execution_reply_free(&response);
    json_object_put(scope);
    json_object_put(r);
    json_object_put(e);
    return dw_report(d, st, NULL);
}
