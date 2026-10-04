#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include "binding_internal.h"
#include "../runtime/profile_internal.h"
#include <dirent.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

golem_status as_publication_guard(void *context)
{
    uint64_t now;
    golem_digest boot;
    golem_status st = as_clock_read(NULL, &now, &boot);
    return st == GOLEM_OK && !as_live(context, now, &boot) ? GOLEM_ERR_STALE_LEASE : st;
}

static golem_status validate(golem_document_store *s, as_log *l, struct json_object *e)
{
    golem_digest boot;
    if (!dw_digest(e, "boot_id", &boot))
        return GOLEM_ERR_PARSE;
    golem_digest spec, expected;
    const char *spec_bytes = json_object_to_json_string_ext(s->spec, JSON_C_TO_STRING_PLAIN);
    if (!spec_bytes)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status identity =
        golem_digest_bytes((golem_bytes){(const uint8_t *)spec_bytes, strlen(spec_bytes)}, &spec);
    if (identity != GOLEM_OK)
        return identity;
    if (!dw_digest(e, "work_spec_digest", &expected) || !dw_equal(&spec, &expected))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    const char *op = dw_text(e, "operation");
    uint64_t now = dw_uint(e, "observed_ms");
    struct json_object *d = dw_get(e, "data"), *a = dw_get(l->state, "active");
    if (l->sequence && strcmp(op, "resume") != 0 && strcmp(op, "bind") != 0 &&
        (!dw_equal(&boot, &l->boot) || now < l->observed_ms))
        return GOLEM_ERR_STALE_RESULT;
    if (strcmp(op, "begin") == 0 || strcmp(op, "heartbeat") == 0 || strcmp(op, "submit") == 0 ||
        strcmp(op, "reconcile") == 0)
        if (!as_live(l, now, &boot))
            return GOLEM_ERR_STALE_RESULT;
    if (strcmp(op, "resume") == 0 && as_live(l, now, &boot) &&
        strcmp(dw_text(a, "session_id"), dw_text(d, "session_id")) != 0)
        return GOLEM_ERR_JOURNAL_BUSY;
    if (strcmp(op, "claim") == 0) {
        golem_digest key;
        struct json_object *m = NULL;
        if (!dw_digest(d, "manifest_digest", &key))
            return GOLEM_ERR_PARSE;
        if (!dw_digest(d, "policy_digest", &expected) || !dw_equal(&expected, &spec))
            return GOLEM_ERR_IDENTITY_MISMATCH;
        golem_status st = dw_cas_json(s, &key, &m);
        if (st == GOLEM_OK &&
            ((dw_uint(m, "schema_version") != 1 && dw_uint(m, "schema_version") != 2 &&
              dw_uint(m, "schema_version") != 3) ||
             dw_uint(m, "generation") != dw_uint(d, "input_generation") ||
             strcmp(dw_text(m, "work_id"), dw_text(s->spec, "work_id")) != 0 ||
             strcmp(dw_text(m, "target_kind"), dw_text(d, "kind")) != 0 ||
             strcmp(dw_text(m, "source_snapshot"), dw_text(d, "source_snapshot")) != 0))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        json_object_put(m);
        if (st == GOLEM_OK && dw_get(d, "runtime_binding"))
            st = rp_validate_claim(s, d);
        if (st == GOLEM_OK && s->runtime_profile_count &&
            dw_uint(e, "sequence") > dw_uint(s->runtime_profiles[0], "agent_sequence") &&
            !dw_get(d, "runtime_binding"))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        if (st == GOLEM_OK)
            st = ab_claim_validate(s, l->state, d);
        if (st != GOLEM_OK)
            return st;
    }
    if (!strcmp(op, "bind"))
        return ab_validate(s, e);
    if (strcmp(op, "submit") == 0 || strcmp(op, "reconcile") == 0) {
        if (dw_get(d, "output") && !wf_resolve(s, dw_get(d, "output")))
            return GOLEM_ERR_IDENTITY_MISMATCH;
        struct json_object *evidence = dw_get(d, "evidence");
        if (!json_object_is_type(evidence, json_type_array))
            return GOLEM_ERR_PARSE;
        for (size_t i = 0; i < json_object_array_length(evidence); ++i) {
            const char *v = json_object_get_string(json_object_array_get_idx(evidence, i));
            golem_digest key;
            uint64_t size;
            if (!v || golem_digest_parse((golem_string_view){v, strlen(v)}, &key) != GOLEM_OK)
                return GOLEM_ERR_PARSE;
            golem_status st = golem_evidence_verify(s->cas, &key, &size, NULL);
            if (st != GOLEM_OK)
                return st;
        }
    }
    return GOLEM_OK;
}
void as_close(as_log *l)
{
    if (l->directory >= 0)
        close(l->directory);
    json_object_put(l->state);
    json_object_put(l->duplicate);
    json_object_put(l->history);
    memset(l, 0, sizeof(*l));
    l->directory = -1;
}
golem_status as_load(golem_document_store *s, const char *key, const golem_digest *request,
                     as_log *l)
{
    memset(l, 0, sizeof(*l));
    l->directory = -1;
    l->history = json_object_new_array();
    if (!l->history)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = dw_dir(s->root, "agent-events", false, &l->directory);
    if (st == GOLEM_ERR_NOT_FOUND)
        return GOLEM_OK;
    if (st != GOLEM_OK)
        return st;
    unsigned max = 0;
    st = dw_record_scan(l->directory, GOLEM_AGENT_MAX_EVENTS, false, &max);
    if (st != GOLEM_OK)
        return st;
    uint8_t *memory = NULL;
    st = dw_scratch(s, (max ? max : 1) * GOLEM_DOCUMENT_ID_CAPACITY, &memory);
    if (st != GOLEM_OK)
        return st;
    char (*keys)[GOLEM_DOCUMENT_ID_CAPACITY] = (void *)memory;
    for (unsigned n = 1; st == GOLEM_OK && n <= max; ++n) {
        golem_digest payload, digest, req;
        struct json_object *e = NULL, *state = NULL;
        st = dw_record_read(s, l->directory, true, n, &l->last, &payload, &digest, &e);
        if (st == GOLEM_OK)
            st = as_reduce(l->state, e, &state);
        if (st == GOLEM_OK)
            st = validate(s, l, e);
        if (st == GOLEM_OK) {
            const char *k = dw_text(e, "key");
            for (unsigned i = 0; i < n - 1; ++i)
                if (strcmp(keys[i], k) == 0)
                    st = GOLEM_ERR_CORRUPT_JOURNAL;
            if (st == GOLEM_OK)
                strcpy(keys[n - 1], k);
        }
        if (st == GOLEM_OK) {
            json_object_put(l->state);
            l->state = state;
            state = NULL;
            l->sequence = n;
            l->last = digest;
            l->observed_ms = dw_uint(e, "observed_ms");
            (void)dw_digest(e, "boot_id", &l->boot);
            (void)dw_digest(e, "request_digest", &req);
            if (n + 32 > max && !wf_append(l->history, json_object_get(e)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (key && strcmp(key, dw_text(e, "key")) == 0) {
                l->key_conflict = !dw_equal(request, &req);
                l->duplicate = as_receipt(e, l->state);
                if (!l->duplicate)
                    st = GOLEM_ERR_OUT_OF_MEMORY;
            }
        }
        json_object_put(state);
        json_object_put(e);
    }
    dw_scratch_free(s, keys);
    return st;
}
golem_status as_commit(golem_document_store *s, as_log *l, struct json_object *e,
                       struct json_object **out)
{
    if (l->sequence >= GOLEM_AGENT_MAX_EVENTS)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    struct json_object *state = NULL, *receipt = NULL;
    golem_status st = as_reduce(l->state, e, &state);
    if (st == GOLEM_OK)
        st = validate(s, l, e);
    if (st == GOLEM_OK) {
        receipt = as_receipt(e, state);
        if (!receipt)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_digest payload, digest;
    if (st == GOLEM_OK)
        st = dw_record_prepare(s, e, AS_EVENT_MAX, &payload);
    if (st == GOLEM_OK && l->directory < 0)
        st = dw_dir(s->root, "agent-events", true, &l->directory);
    if (st == GOLEM_OK)
        st = dw_record_event(s, l->directory, true, l->sequence + 1, &l->last, &payload, &digest);
    if (st == GOLEM_OK) {
        *out = receipt;
        receipt = NULL;
    }
    json_object_put(receipt);
    json_object_put(state);
    return st;
}
