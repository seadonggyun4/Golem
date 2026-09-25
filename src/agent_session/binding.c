#include "binding_internal.h"
#include "golem/adapter_descriptor.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static bool add_text(struct json_object *o, const char *key, const char *value)
{
    return dw_add(o, key, json_object_new_string(value));
}
static bool opaque_id(struct json_object *value)
{
    if (!json_object_is_type(value, json_type_string))
        return false;
    const unsigned char *p = (const unsigned char *)json_object_get_string(value);
    size_t n = (size_t)json_object_get_string_len(value);
    if (n > GOLEM_NATIVE_THREAD_MAX_BYTES || strlen((const char *)p) != n)
        return false;
    /* JSON parser validates UTF-8. Controls and credential-shaped fields are not IDs. */
    for (size_t i = 0; i < n; ++i)
        if (p[i] < 32 || p[i] == 127)
            return false;
    return true;
}
static bool shape(struct json_object *r)
{
    const char *inspect[] = {"schema_version", "operation", "work_id"};
    const char *attach[] = {
        "schema_version", "operation",         "work_id",          "key",   "expected_sequence",
        "session_id",     "descriptor_digest", "native_thread_id", "token", "ttl_ms"};
    if (dw_uint(r, "schema_version") != 1 || !dw_id(dw_text(r, "work_id")))
        return false;
    if (!strcmp(dw_text(r, "operation"), "inspect"))
        return dw_keys(r, inspect, 3);
    golem_digest digest;
    struct json_object *token = dw_get(r, "token");
    const char *tk[] = {"epoch", "attempt_id", "session_id"};
    return !strcmp(dw_text(r, "operation"), "attach") && dw_keys(r, attach, 10) &&
           dw_id(dw_text(r, "key")) && dw_id(dw_text(r, "session_id")) &&
           dw_uint(r, "expected_sequence") < GOLEM_AGENT_MAX_EVENTS &&
           dw_digest(r, "descriptor_digest", &digest) && opaque_id(dw_get(r, "native_thread_id")) &&
           dw_uint(r, "ttl_ms") > 0 && dw_uint(r, "ttl_ms") <= GOLEM_AGENT_MAX_TTL_MS &&
           (!token || (dw_keys(token, tk, 3) && dw_uint(token, "epoch") > 0 &&
                       dw_uint(token, "epoch") <= GOLEM_AGENT_MAX_EVENTS &&
                       dw_id(dw_text(token, "session_id")) && dw_id(dw_text(token, "attempt_id"))));
}
golem_status golem_session_binding_request_validate(golem_bytes bytes)
{
    struct json_object *r = NULL;
    golem_status st = golem_json_parse(bytes, GOLEM_SESSION_BINDING_MAX_BYTES, &r);
    if (st == GOLEM_OK && !shape(r))
        st = GOLEM_ERR_PARSE;
    json_object_put(r);
    return st;
}
golem_status ab_reply(struct json_object *object, golem_agent_reply *out)
{
    const char *text = json_object_to_json_string_ext(object, JSON_C_TO_STRING_PLAIN);
    if (!text)
        return GOLEM_ERR_OUT_OF_MEMORY;
    size_t n = strlen(text);
    if (n > GOLEM_AGENT_CONTEXT_MAX)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    uint8_t *copy = malloc(n);
    if (!copy)
        return GOLEM_ERR_OUT_OF_MEMORY;
    memcpy(copy, text, n);
    *out = (golem_agent_reply){copy, n};
    return GOLEM_OK;
}
static golem_status descriptor(golem_document_store *s, const golem_digest *key,
                               golem_adapter_descriptor *out)
{
    uint8_t *bytes = NULL;
    size_t n = 0;
    golem_status st =
        golem_evidence_read(s->cas, key, GOLEM_DESCRIPTOR_MAX_BYTES, NULL, &bytes, &n, NULL);
    if (st == GOLEM_OK)
        st = golem_adapter_descriptor_decode((golem_bytes){bytes, n}, out);
    golem_digest canonical;
    if (st == GOLEM_OK)
        st = golem_adapter_descriptor_digest(out, &canonical);
    if (st == GOLEM_OK && !dw_equal(key, &canonical))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    free(bytes);
    return st;
}
static bool record_shape(struct json_object *b)
{
    const char *keys[] = {"schema_version",
                          "binding_id",
                          "session_id",
                          "epoch",
                          "descriptor_digest",
                          "descriptor_version",
                          "adapter_id",
                          "adapter_version",
                          "native_thread_digest",
                          "native_thread_present",
                          "provenance",
                          "host_identity",
                          "reconnect",
                          "document_checkpoint"};
    golem_digest digest;
    const char *provenance = dw_text(b, "provenance"), *reconnect = dw_text(b, "reconnect");
    return dw_keys(b, keys, 14) && dw_uint(b, "schema_version") == 1 &&
           dw_id(dw_text(b, "binding_id")) && dw_id(dw_text(b, "session_id")) &&
           dw_uint(b, "epoch") > 0 && dw_uint(b, "epoch") <= GOLEM_AGENT_MAX_EVENTS &&
           dw_digest(b, "descriptor_digest", &digest) && dw_uint(b, "descriptor_version") == 1 &&
           dw_id(dw_text(b, "adapter_id")) &&
           json_object_is_type(dw_get(b, "adapter_version"), json_type_string) &&
           dw_digest(b, "native_thread_digest", &digest) &&
           json_object_is_type(dw_get(b, "native_thread_present"), json_type_boolean) &&
           dw_digest(b, "document_checkpoint", &digest) &&
           ((!strcmp(provenance, "SELF_REPORTED") && !strcmp(dw_text(b, "host_identity"), "")) ||
            (!strcmp(provenance, "HOST_OBSERVED") && dw_digest(b, "host_identity", &digest))) &&
           (!strcmp(reconnect, "UNAVAILABLE") || !strcmp(reconnect, "CLAIMED") ||
            (!strcmp(reconnect, "HOST_OBSERVED_CAPABILITY") &&
             !strcmp(provenance, "HOST_OBSERVED")));
}
golem_status ab_reduce(struct json_object *s, struct json_object *e)
{
    struct json_object *d = dw_get(e, "data"), *b = dw_get(d, "binding"), *a = dw_get(s, "active");
    const char *keys[] = {"binding", "token", "expires_ms"};
    uint64_t seq = dw_uint(e, "sequence"), now = dw_uint(e, "observed_ms");
    char expected_id[64];
    (void)snprintf(expected_id, sizeof(expected_id), "binding-%llu", (unsigned long long)seq);
    if (!s || !dw_keys(d, keys, 3) || !record_shape(b) || dw_uint(b, "epoch") != seq ||
        strcmp(expected_id, dw_text(b, "binding_id")) || dw_uint(d, "expires_ms") <= now ||
        dw_uint(d, "expires_ms") - now > GOLEM_AGENT_MAX_TTL_MS ||
        (a ? !as_token(a, dw_get(d, "token")) : dw_get(d, "token") != NULL))
        return GOLEM_ERR_INVALID_STATE;
    if (!dw_add(s, "binding", json_object_get(b)) ||
        !dw_add(s, "epoch", json_object_new_uint64(seq)))
        return GOLEM_ERR_OUT_OF_MEMORY;
    if (a) {
        /* A new attachment never redispatches possibly effected work. */
        if (!add_text(a, "state", "RECOVERY_REQUIRED") ||
            !add_text(a, "session_id", dw_text(b, "session_id")) ||
            !add_text(a, "session_binding", dw_text(b, "binding_id")) ||
            !dw_add(a, "epoch", json_object_new_uint64(seq)) ||
            !dw_add(a, "expires_ms", json_object_get(dw_get(d, "expires_ms"))))
            return GOLEM_ERR_OUT_OF_MEMORY;
    }
    return GOLEM_OK;
}
bool ab_matches(struct json_object *s, struct json_object *r)
{
    struct json_object *b = dw_get(s, "binding");
    return b && dw_uint(r, "schema_version") == 2 &&
           !strcmp(dw_text(b, "binding_id"), dw_text(r, "binding_id")) &&
           !strcmp(dw_text(b, "session_id"), dw_text(r, "session_id"));
}
golem_status ab_claim_validate(golem_document_store *s, struct json_object *state,
                               struct json_object *claim)
{
    struct json_object *binding = dw_get(state, "binding");
    if (!binding || !dw_get(claim, "runtime_binding"))
        return GOLEM_OK;
    golem_digest key;
    struct json_object *runtime = NULL, *profile = NULL;
    if (!dw_digest(claim, "runtime_binding", &key))
        return GOLEM_ERR_PARSE;
    golem_status st = dw_cas_json(s, &key, &runtime);
    if (st == GOLEM_OK && !dw_digest(runtime, "profile_digest", &key))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = dw_cas_json(s, &key, &profile);
    if (st == GOLEM_OK && strcmp(dw_text(profile, "adapter_descriptor_digest"),
                                 dw_text(binding, "descriptor_digest")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    json_object_put(runtime);
    json_object_put(profile);
    return st;
}
golem_status ab_validate(golem_document_store *s, struct json_object *e)
{
    struct json_object *b = dw_get(dw_get(e, "data"), "binding");
    golem_digest key;
    golem_adapter_descriptor desc;
    if (!record_shape(b) || !dw_digest(b, "descriptor_digest", &key))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    golem_status st = descriptor(s, &key, &desc);
    if (st == GOLEM_OK &&
        (strcmp(desc.adapter_id, dw_text(b, "adapter_id")) ||
         strcmp(desc.adapter_version, dw_text(b, "adapter_version")) ||
         (desc.session_id[0] && strcmp(desc.session_id, dw_text(b, "session_id")))))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    bool resume = st == GOLEM_OK &&
                  (desc.features_known & desc.features_supported & GOLEM_HARNESS_RESUME) &&
                  json_object_get_boolean(dw_get(b, "native_thread_present"));
    const char *expected = !resume ? "UNAVAILABLE"
                           : !strcmp(dw_text(b, "provenance"), "HOST_OBSERVED")
                               ? "HOST_OBSERVED_CAPABILITY"
                               : "CLAIMED";
    if (st == GOLEM_OK && strcmp(expected, dw_text(b, "reconnect")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    /* This cross-stream reference must belong to the same Work's verified log. */
    golem_digest checkpoint;
    (void)dw_digest(b, "document_checkpoint", &checkpoint);
    bool found = dw_equal(&checkpoint, &s->last);
    for (size_t i = 1; st == GOLEM_OK && !found && i <= s->event_count; ++i) {
        char name[32];
        (void)snprintf(name, sizeof(name), "%08u.evt", (unsigned)i);
        uint8_t *bytes = NULL;
        size_t size = 0;
        golem_digest frame;
        st = dw_read_at(s->events, name, DW_FRAME, &bytes, &size);
        if (st == GOLEM_OK && size != DW_FRAME)
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        if (st == GOLEM_OK)
            st = golem_digest_bytes((golem_bytes){bytes, size}, &frame);
        if (st == GOLEM_OK)
            found = dw_equal(&checkpoint, &frame);
        free(bytes);
    }
    if (st == GOLEM_OK && !found)
        st = GOLEM_ERR_MISSING_RECORD;
    return st;
}
static golem_status prepare_binding(golem_document_store *s, as_log *l, struct json_object *r,
                                    uint64_t now, const golem_session_binding_host *host,
                                    struct json_object **out)
{
    struct json_object *a = dw_get(l->state, "active");
    if (!l->state || dw_uint(r, "expected_sequence") != l->sequence ||
        (a ? !as_token(a, dw_get(r, "token")) : dw_get(r, "token") != NULL))
        return GOLEM_ERR_STALE_RESULT;
    uint64_t ttl = dw_uint(r, "ttl_ms");
    if (now > UINT64_MAX - ttl)
        return GOLEM_ERR_OVERFLOW;
    golem_digest key, native;
    (void)dw_digest(r, "descriptor_digest", &key);
    golem_adapter_descriptor desc;
    golem_status st = descriptor(s, &key, &desc);
    if (st == GOLEM_OK && desc.session_id[0] && strcmp(desc.session_id, dw_text(r, "session_id")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    const char *id = dw_text(r, "native_thread_id");
    if (st == GOLEM_OK)
        st = golem_digest_bytes((golem_bytes){(const uint8_t *)id, strlen(id)}, &native);
    struct json_object *b = json_object_new_object(), *d = json_object_new_object();
    char binding_id[64];
    (void)snprintf(binding_id, sizeof(binding_id), "binding-%llu",
                   (unsigned long long)(l->sequence + 1));
    if (st == GOLEM_OK &&
        (!b || !d || !dw_add(b, "schema_version", json_object_new_int(1)) ||
         !add_text(b, "binding_id", binding_id) ||
         !add_text(b, "session_id", dw_text(r, "session_id")) ||
         !dw_add(b, "epoch", json_object_new_uint64(l->sequence + 1)) ||
         !dw_add_digest(b, "descriptor_digest", &key) ||
         !dw_add(b, "descriptor_version", json_object_new_int((int)desc.version)) ||
         !add_text(b, "adapter_id", desc.adapter_id) ||
         !add_text(b, "adapter_version", desc.adapter_version) ||
         !dw_add_digest(b, "native_thread_digest", &native) ||
         !dw_add(b, "native_thread_present", json_object_new_boolean(id[0] != 0)) ||
         !dw_add_digest(b, "document_checkpoint", &s->last)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_digest identity;
    if (st == GOLEM_OK && host) {
        const char *bytes = json_object_to_json_string_ext(b, JSON_C_TO_STRING_PLAIN);
        st = !host->observe || !bytes
                 ? GOLEM_ERR_INVALID_ARGUMENT
                 : host->observe(host->context,
                                 (golem_bytes){(const uint8_t *)bytes, strlen(bytes)}, &identity);
    }
    bool resume = st == GOLEM_OK && id[0] &&
                  (desc.features_known & desc.features_supported & GOLEM_HARNESS_RESUME);
    if (st == GOLEM_OK &&
        (!add_text(b, "provenance", host ? "HOST_OBSERVED" : "SELF_REPORTED") ||
         !(host ? dw_add_digest(b, "host_identity", &identity)
                : add_text(b, "host_identity", "")) ||
         !add_text(b, "reconnect",
                   !resume ? "UNAVAILABLE"
                   : host  ? "HOST_OBSERVED_CAPABILITY"
                           : "CLAIMED") ||
         !dw_add(d, "binding", json_object_get(b)) ||
         json_object_object_add(d, "token", json_object_get(dw_get(r, "token"))) != 0 ||
         !dw_add(d, "expires_ms", json_object_new_uint64(now + ttl))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(b);
    if (st == GOLEM_OK)
        *out = d;
    else
        json_object_put(d);
    return st;
}
golem_status golem_session_binding_call(golem_document_store *s, golem_bytes bytes,
                                        const golem_agent_clock *clock,
                                        const golem_session_binding_host *host,
                                        golem_agent_reply *out, golem_diagnostic *diagnostic)
{
    if (!s || !out || s->poisoned)
        return dw_report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *r = NULL, *d = NULL, *e = NULL, *response = NULL;
    as_log l = {.directory = -1};
    golem_status st = golem_json_parse(bytes, GOLEM_SESSION_BINDING_MAX_BYTES, &r);
    if (st == GOLEM_OK && !shape(r))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK && strcmp(dw_text(r, "work_id"), dw_text(s->spec, "work_id")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    bool inspect = !strcmp(dw_text(r, "operation"), "inspect");
    golem_digest request;
    if (st == GOLEM_OK)
        st = golem_digest_bytes(bytes, &request);
    if (st == GOLEM_OK)
        st = as_load(s, inspect ? NULL : dw_text(r, "key"), &request, &l);
    if (st == GOLEM_OK && l.key_conflict)
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK && inspect) {
        response = json_object_new_object();
        if (!response || !dw_add(response, "schema_version", json_object_new_int(1)) ||
            !dw_add(response, "sequence", json_object_new_uint64(l.sequence)) ||
            json_object_object_add(response, "binding",
                                   json_object_get(dw_get(l.state, "binding"))) != 0 ||
            !add_text(response, "native_conversation", "NOT_RECONNECTED") ||
            !dw_add(response, "execution_authorized", json_object_new_boolean(false)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    } else if (st == GOLEM_OK && l.duplicate)
        response = json_object_get(l.duplicate);
    else if (st == GOLEM_OK) {
        if (!s->writable || !strcmp(dw_text(s->spec, "permission"), "DENY"))
            st = GOLEM_ERR_POLICY_DENIED;
        else if (!strcmp(dw_text(s->spec, "permission"), "ASK_ALWAYS"))
            st = GOLEM_ERR_APPROVAL_REQUIRED;
        uint64_t now = 0;
        golem_digest boot, spec;
        if (st == GOLEM_OK)
            st = as_clock_read(clock, &now, &boot);
        if (st == GOLEM_OK)
            st = prepare_binding(s, &l, r, now, host, &d);
        if (st == GOLEM_OK)
            st = dw_put_json(s, s->spec, &spec);
        if (st == GOLEM_OK) {
            e = json_object_new_object();
            if (!e || !dw_add(e, "schema_version", json_object_new_int(3)) ||
                !dw_add(e, "sequence", json_object_new_uint64(l.sequence + 1)) ||
                !add_text(e, "operation", "bind") || !add_text(e, "key", dw_text(r, "key")) ||
                !dw_add_digest(e, "request_digest", &request) ||
                !dw_add(e, "observed_ms", json_object_new_uint64(now)) ||
                !dw_add_digest(e, "boot_id", &boot) ||
                !dw_add_digest(e, "work_spec_digest", &spec) ||
                !dw_add(e, "data", json_object_get(d)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        if (st == GOLEM_OK) {
            uint64_t final_now;
            golem_digest final_boot;
            st = as_clock_read(clock, &final_now, &final_boot);
            if (st == GOLEM_OK && (!dw_equal(&boot, &final_boot) || final_now < now ||
                                   final_now >= dw_uint(d, "expires_ms")))
                st = GOLEM_ERR_STALE_RESULT;
            if (st == GOLEM_OK && !dw_add(e, "observed_ms", json_object_new_uint64(final_now)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        if (st == GOLEM_OK)
            st = as_commit(s, &l, e, &response);
    }
    if (st == GOLEM_OK)
        st = ab_reply(response, out);
    json_object_put(r);
    json_object_put(d);
    json_object_put(e);
    json_object_put(response);
    as_close(&l);
    return dw_report(diagnostic, st, NULL);
}
golem_status golem_session_fence_check(golem_document_store *s, golem_bytes bytes,
                                       const golem_agent_clock *clock, golem_diagnostic *diagnostic)
{
    if (!s || s->poisoned)
        return dw_report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *r = NULL;
    const char *keys[] = {"binding_id", "token"};
    as_log l = {.directory = -1};
    golem_status st = golem_json_parse(bytes, GOLEM_SESSION_BINDING_MAX_BYTES, &r);
    if (st == GOLEM_OK && (!dw_keys(r, keys, 2) || !dw_id(dw_text(r, "binding_id"))))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = as_load(s, NULL, NULL, &l);
    uint64_t now;
    golem_digest boot;
    if (st == GOLEM_OK)
        st = as_clock_read(clock, &now, &boot);
    if (st == GOLEM_OK &&
        (!dw_get(l.state, "binding") ||
         strcmp(dw_text(dw_get(l.state, "binding"), "binding_id"), dw_text(r, "binding_id")) ||
         !as_token(dw_get(l.state, "active"), dw_get(r, "token")) || !as_live(&l, now, &boot)))
        st = GOLEM_ERR_STALE_RESULT;
    as_close(&l);
    json_object_put(r);
    return dw_report(diagnostic, st, NULL);
}
