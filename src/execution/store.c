#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include "../agent_session/internal.h"
#include "../reentry/internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void hex(const golem_digest *d, char name[65])
{
    size_t n;
    (void)golem_digest_format(d, name, 65, &n);
}
golem_status ex_authorize(golem_document_store *s, struct json_object *token,
                          struct json_object *manifest)
{
    as_log log = {.directory = -1};
    golem_status st = as_load(s, NULL, NULL, &log);
    if (st == GOLEM_OK && log.state) {
        uint64_t now;
        golem_digest boot;
        struct json_object *active = dw_get(log.state, "active"), *pinned = NULL;
        st = as_clock_read(NULL, &now, &boot);
        if (st == GOLEM_OK && (!as_token(active, token) || !as_live(&log, now, &boot) ||
                               strcmp(dw_text(active, "state"), "RUNNING")))
            st = GOLEM_ERR_STALE_RESULT;
        if (st == GOLEM_OK)
            st = as_fresh(s, active, false, &pinned);
        if (st == GOLEM_OK && !json_object_equal(pinned, manifest))
            st = GOLEM_ERR_STALE_RESULT;
        json_object_put(pinned);
    } else if (st == GOLEM_OK && (token || s->runtime_profile_count))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    as_close(&log);
    return st;
}
static golem_status enrollment(golem_document_store *s, struct json_object *manifest,
                               const golem_digest *contract, bool create)
{
    golem_digest selection;
    char name[65];
    int dir = -1;
    if (!dw_digest(dw_get(manifest, "selection"), "digest", &selection))
        return GOLEM_ERR_PARSE;
    hex(&selection, name);
    golem_status st = dw_dir(s->root, "execution-policies", create, &dir);
    if (st == GOLEM_OK && create)
        st = dw_publish(dir, name, (golem_bytes){contract->bytes, 32});
    else if (st == GOLEM_OK) {
        uint8_t *data = NULL;
        size_t n = 0;
        st = dw_read_at(dir, name, 32, &data, &n);
        if (st == GOLEM_OK && n != 32)
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        free(data);
    }
    if (dir >= 0) {
        close(dir);
    }
    return st;
}
golem_status ex_required(golem_document_store *s, struct json_object *m)
{
    if (dw_uint(m, "schema_version") != 4 || (strcmp(dw_text(m, "kind"), "development-result") &&
                                              strcmp(dw_text(m, "kind"), "qa-result")))
        return GOLEM_OK;
    golem_status st = enrollment(s, dw_get(m, "input_manifest"), NULL, false);
    return st == GOLEM_ERR_NOT_FOUND ? GOLEM_OK
           : st == GOLEM_OK          ? GOLEM_ERR_REQUIREMENTS_UNMET
                                     : st;
}
static golem_status issue(golem_document_store *s, struct json_object *o, golem_digest *out)
{
    golem_execution_reply bytes = {0};
    golem_status st = ex_emit(o, &bytes);
    int dir = -1;
    if (st == GOLEM_OK)
        st = dw_put_json(s, o, out);
    if (st == GOLEM_OK && dw_uint(o, "schema_version") >= 2 && !strcmp(dw_text(o, "type"), "qa"))
        st = ex_bundle_check(s, out, o, true);
    if (st == GOLEM_OK)
        st = dw_dir(s->root, "execution-receipts", true, &dir);
    char name[65];
    if (st == GOLEM_OK) {
        hex(out, name);
        st = dw_publish(dir, name, (golem_bytes){out->bytes, 32});
    }
    if (dir >= 0)
        close(dir);
    golem_execution_reply_free(&bytes);
    return st;
}
golem_status ex_load(golem_document_store *s, const golem_digest *key, const char *type,
                     struct json_object **out)
{
    int dir = -1;
    golem_status st = dw_dir(s->root, "execution-receipts", false, &dir);
    uint8_t *marker = NULL;
    size_t n = 0;
    char name[65];
    hex(key, name);
    if (st == GOLEM_OK)
        st = dw_read_at(dir, name, 32, &marker, &n);
    if (st == GOLEM_OK && (n != 32 || memcmp(marker, key->bytes, 32)))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    free(marker);
    if (dir >= 0)
        close(dir);
    struct json_object *o = NULL;
    if (st == GOLEM_OK)
        st = dw_cas_json(s, key, &o);
    if (st == GOLEM_OK && ((dw_uint(o, "schema_version") < 1 || dw_uint(o, "schema_version") > 5) ||
                           strcmp(dw_text(o, "work_id"), dw_text(s->spec, "work_id")) != 0 ||
                           (type && strcmp(dw_text(o, "type"), type) != 0)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK && dw_uint(o, "schema_version") == 5)
        st = ex_snapshot_verify(
            s, dw_get(o, !strcmp(dw_text(o, "type"), "checkpoint") ? "baseline" : "snapshot"));
    if (st == GOLEM_OK && strcmp(dw_text(o, "type"), "qa") == 0) {
        struct json_object *gates = dw_get(o, "gates");
        for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(gates); ++i) {
            struct json_object *g = json_object_array_get_idx(gates, i), *observed = NULL,
                               *copy = NULL;
            golem_digest observation;
            if (!dw_digest(g, "observation_digest", &observation))
                st = GOLEM_ERR_PARSE;
            if (st == GOLEM_OK)
                st = dw_cas_json(s, &observation, &observed);
            if (st == GOLEM_OK && json_object_deep_copy(g, &copy, NULL) != 0)
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK) {
                json_object_object_del(copy, "observation_digest");
                if (!json_object_equal(copy, observed))
                    st = GOLEM_ERR_DIGEST_MISMATCH;
            }
            json_object_put(copy);
            json_object_put(observed);
        }
        if (st == GOLEM_OK && dw_uint(o, "schema_version") >= 2)
            st = ex_bundle_check(s, key, o, false);
    }
    if (st == GOLEM_OK)
        *out = o;
    else
        json_object_put(o);
    return st;
}
static struct json_object *base(golem_document_store *s, const char *type,
                                struct json_object *manifest)
{
    struct json_object *o = json_object_new_object();
    if (!ex_uint(o, "schema_version", 1) || !ex_text(o, "type", type) ||
        !ex_text(o, "work_id", dw_text(s->spec, "work_id")) ||
        !dw_add(o, "manifest", json_object_get(manifest))) {
        json_object_put(o);
        return NULL;
    }
    return o;
}
static golem_status prepare(golem_document_store *s, struct json_object *c,
                            const golem_digest *approval, const golem_digest *shell,
                            struct json_object *token, struct json_object **out)
{
    golem_status st = ex_contract(c);
    golem_digest digest;
    if (st == GOLEM_OK)
        st = ex_hash(c, &digest);
    if (st == GOLEM_OK && (!approval || !dw_equal(approval, &digest)))
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    if (st == GOLEM_OK)
        st = ex_command_approve(c, shell);
    struct json_object *m = NULL, *snap = NULL, *o = NULL, *executables = json_object_new_array();
    if (!executables)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ex_inputs(s, c, "development-result", &m);
    if (st == GOLEM_OK)
        st = ex_authorize(s, token, m);
    if (st == GOLEM_OK)
        st = ex_snapshot(s, dw_get(c, "snapshot_plan"), true, &snap);
    struct json_object *gates = dw_get(c, "gates");
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(gates); ++i) {
        st = ex_command_check(json_object_array_get_idx(gates, i), dw_get(c, "snapshot_plan"));
        if (st != GOLEM_OK)
            break;
        const char *path = json_object_get_string(
            json_object_array_get_idx(dw_get(json_object_array_get_idx(gates, i), "argv"), 0));
        golem_receipt file;
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
    if (st == GOLEM_OK) {
        o = base(s, "checkpoint", m);
        if (!ex_uint(o, "schema_version", dw_uint(c, "schema_version")) ||
            !dw_add(o, "contract", json_object_get(c)) ||
            !dw_add_digest(o, "contract_digest", &digest) ||
            !dw_add(o, "baseline", json_object_get(snap)) ||
            !dw_add(o, "executables", json_object_get(executables)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    /* Re-preparing must not bless weakened tests as a new baseline under the
     * same policy. Pin the entire first checkpoint, not only its contract. */
    golem_digest checkpoint;
    if (st == GOLEM_OK)
        st = ex_hash(o, &checkpoint);
    if (st == GOLEM_OK) {
        int dir = -1;
        golem_digest selection, oldkey;
        uint8_t *data = NULL;
        size_t n = 0;
        char name[65];
        golem_status prior = dw_dir(s->root, "execution-policies", false, &dir);
        if (prior == GOLEM_OK && !dw_digest(dw_get(m, "selection"), "digest", &selection))
            prior = GOLEM_ERR_PARSE;
        if (prior == GOLEM_OK) {
            hex(&selection, name);
            prior = dw_read_at(dir, name, 32, &data, &n);
        }
        if (prior == GOLEM_OK && n != 32)
            prior = GOLEM_ERR_CORRUPT_JOURNAL;
        if (prior == GOLEM_OK) {
            memcpy(oldkey.bytes, data, 32);
            if (!dw_equal(&oldkey, &checkpoint)) {
                struct json_object *original = NULL;
                st = ex_load(s, &oldkey, "checkpoint", &original);
                if (st == GOLEM_OK)
                    st = re_rebase(s, original, o);
                json_object_put(original);
            }
        } else if (prior == GOLEM_ERR_NOT_FOUND)
            st = enrollment(s, m, &checkpoint, true);
        else
            st = prior;
        free(data);
        if (dir >= 0)
            close(dir);
    }
    if (st == GOLEM_OK)
        *out = o;
    else
        json_object_put(o);
    json_object_put(m);
    json_object_put(snap);
    json_object_put(executables);
    return st;
}
static golem_status finish(golem_document_store *s, struct json_object *cp, const golem_digest *key,
                           struct json_object *token, struct json_object **out)
{
    struct json_object *m = NULL, *snap = NULL, *o = NULL;
    golem_status st = ex_inputs(s, dw_get(cp, "contract"), "development-result", &m);
    if (st == GOLEM_OK)
        st = ex_current(s, dw_get(cp, "manifest"));
    if (st == GOLEM_OK &&
        (!json_object_equal(dw_get(m, "direct"), dw_get(dw_get(cp, "manifest"), "direct")) ||
         !json_object_equal(dw_get(m, "documents"), dw_get(dw_get(cp, "manifest"), "documents"))))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK)
        st = ex_snapshot(s, dw_get(dw_get(cp, "contract"), "snapshot_plan"), true, &snap);
    if (st == GOLEM_OK && dw_uint(cp, "schema_version") >= 4)
        st = ex_authorize(s, token, m);
    if (st == GOLEM_OK)
        st = ex_inventory_check(s, cp, snap, true);
    if (st == GOLEM_OK) {
        o = base(s, "development", m);
        if (!ex_uint(o, "schema_version", dw_uint(cp, "schema_version")) ||
            !dw_add_digest(o, "checkpoint", key) || !dw_add(o, "snapshot", json_object_get(snap)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        *out = o;
    else
        json_object_put(o);
    json_object_put(m);
    json_object_put(snap);
    return st;
}
static golem_status live(golem_document_store *s, struct json_object *r)
{
    golem_digest key;
    struct json_object *cp = NULL, *now = NULL;
    if (!dw_digest(r, "checkpoint", &key))
        return GOLEM_ERR_PARSE;
    golem_status st = ex_load(s, &key, "checkpoint", &cp);
    if (st == GOLEM_OK)
        st = ex_current(s, dw_get(r, "manifest"));
    if (st == GOLEM_OK)
        st = ex_snapshot(s, dw_get(dw_get(cp, "contract"), "snapshot_plan"), false, &now);
    /* A changed v5 read-only capture is intentionally not in CAS. Reject it
     * before resolving references; retain the historical v1-v4 check order. */
    if (st == GOLEM_OK && dw_uint(r, "schema_version") == 5 &&
        !json_object_equal(now, dw_get(r, "snapshot")))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK)
        st = ex_inventory_check(s, cp, now, false);
    if (st == GOLEM_OK && !json_object_equal(now, dw_get(r, "snapshot")))
        st = GOLEM_ERR_STALE_RESULT;
    json_object_put(cp);
    json_object_put(now);
    return st;
}
golem_status ex_live(golem_document_store *s, struct json_object *meta)
{
    if (dw_uint(meta, "schema_version") != 5)
        return GOLEM_OK;
    golem_digest key;
    struct json_object *r = NULL;
    if (!dw_digest(meta, "execution_receipt", &key))
        return GOLEM_ERR_PARSE;
    golem_status st = ex_load(s, &key, NULL, &r);
    if (st == GOLEM_OK)
        st = live(s, r);
    json_object_put(r);
    return st;
}
golem_status ex_pass(golem_document_store *s, struct json_object *meta)
{
    if (dw_uint(meta, "schema_version") != 5 || strcmp(dw_text(meta, "kind"), "qa-result"))
        return GOLEM_OK;
    golem_digest key;
    struct json_object *r = NULL;
    if (!dw_digest(meta, "execution_receipt", &key))
        return GOLEM_ERR_PARSE;
    golem_status st = ex_load(s, &key, "qa", &r);
    if (st == GOLEM_OK && strcmp(dw_text(r, "status"), "PASS"))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    json_object_put(r);
    return st;
}
static golem_status call(golem_document_store *s, golem_bytes bytes, const golem_digest *approval,
                         const golem_digest *shell, golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *req = NULL, *result = NULL, *cp = NULL, *reply = NULL, *manifest = NULL;
    golem_status st = golem_json_parse(bytes, GOLEM_DOCUMENT_MAX_JSON, &req);
    const char *op = dw_text(req, "operation");
    bool is_prepare = strcmp(op, "prepare") == 0, is_run = strcmp(op, "run") == 0,
         is_verify = strcmp(op, "verify") == 0;
    bool has_token = dw_get(req, "token") != NULL;
    const char *keys[] = {"schema_version", "operation",
                          is_prepare  ? "contract"
                          : is_verify ? "receipt"
                                      : "checkpoint",
                          is_run ? "attempt_id" : "token", "token"};
    if (st == GOLEM_OK && (!dw_keys(req, keys, (is_run ? 4 : 3) + (has_token ? 1 : 0)) ||
                           (is_verify && has_token) || dw_uint(req, "schema_version") != 1 ||
                           (!is_prepare && !is_run && !is_verify && strcmp(op, "finish")) ||
                           (is_run && !dw_id(dw_text(req, "attempt_id")))))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK && !is_verify &&
        (!s->writable || strcmp(dw_text(s->spec, "permission"), "DENY") == 0))
        st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK && !is_verify && strcmp(dw_text(s->spec, "permission"), "ASK_ALWAYS") == 0)
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    golem_digest key = {0}, result_key = {0};
    if (st == GOLEM_OK && is_prepare)
        st = prepare(s, dw_get(req, "contract"), approval, shell, dw_get(req, "token"), &result);
    else if (st == GOLEM_OK) {
        if (!dw_digest(req, is_verify ? "receipt" : "checkpoint", &key))
            st = GOLEM_ERR_PARSE;
        if (st == GOLEM_OK)
            st = ex_load(s, &key, is_verify ? NULL : "checkpoint", &cp);
        if (st == GOLEM_OK && is_verify) {
            st = live(s, cp);
            if (st == GOLEM_OK)
                result = json_object_get(cp);
            result_key = key;
        } else if (st == GOLEM_OK && !is_run) {
            st = finish(s, cp, &key, dw_get(req, "token"), &result);
            if (st == GOLEM_OK)
                st = ex_authorize(s, dw_get(req, "token"), dw_get(result, "manifest"));
        } else if (st == GOLEM_OK) {
            golem_digest approved;
            if (!dw_digest(cp, "contract_digest", &approved) || !approval ||
                !dw_equal(&approved, approval))
                st = GOLEM_ERR_APPROVAL_REQUIRED;
            if (st == GOLEM_OK)
                st = ex_command_approve(dw_get(cp, "contract"), shell);
            if (st == GOLEM_OK)
                st = ex_inputs(s, dw_get(cp, "contract"), "qa-result", &manifest);
            if (st == GOLEM_OK)
                st = ex_authorize(s, dw_get(req, "token"), manifest);
            if (st == GOLEM_OK)
                st = ex_execute(s, cp, &key, manifest, dw_text(req, "attempt_id"),
                                dw_get(req, "token"), &result);
        }
    }
    if (st == GOLEM_OK && !is_verify)
        st = issue(s, result, &result_key);
    if (st == GOLEM_OK) {
        reply = json_object_new_object();
        if (!dw_add_digest(reply, "receipt_digest", &result_key) ||
            !dw_add(reply, "record", json_object_get(result)) ||
            !dw_add(reply, "acceptance_verified", json_object_new_boolean(false)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        st = ex_emit(reply, out);
    if (st == GOLEM_ERR_IO && !is_verify)
        s->poisoned = true;
    json_object_put(req);
    json_object_put(result);
    json_object_put(cp);
    json_object_put(reply);
    json_object_put(manifest);
    return dw_report(d, st, NULL);
}

golem_status golem_execution_call(golem_document_store *s, golem_bytes bytes,
                                  const golem_digest *approval, golem_execution_reply *out,
                                  golem_diagnostic *d)
{
    return call(s, bytes, approval, NULL, out, d);
}

golem_status golem_execution_call_authorized(golem_document_store *s, golem_bytes bytes,
                                             const golem_execution_approval *approval,
                                             golem_execution_reply *out, golem_diagnostic *d)
{
    if (approval && (approval->struct_size != sizeof(*approval) || approval->version != 1))
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    return call(s, bytes, approval ? approval->contract : NULL,
                approval ? approval->shell_contract : NULL, out, d);
}
