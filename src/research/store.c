#include "internal.h"
#include <string.h>

static struct json_object *request_at(golem_document_store *s, size_t i)
{ return dw_get(s->research[i], "request"); }
static struct json_object *record_at(golem_document_store *s, size_t i)
{ return dw_get(request_at(s, i), "record"); }
static size_t find(golem_document_store *s, const char *op, const char *case_id, const char *attempt)
{
    for (size_t i = s->research_count; i > 0; --i) {
        struct json_object *r = request_at(s, i - 1), *v = dw_get(r, "record");
        if (!strcmp(dw_text(r, "operation"), op) && !strcmp(dw_text(v, "case_id"), case_id) &&
            (!attempt || !strcmp(dw_text(v, "attempt_id"), attempt))) return i - 1;
    }
    return SIZE_MAX;
}
static bool matches(struct json_object *o, const char *key, const golem_digest *digest)
{
    golem_digest actual;
    return dw_digest(o, key, &actual) && dw_equal(&actual, digest);
}
static golem_status evidence(golem_document_store *s, struct json_object *o, const char *key)
{
    if (!*dw_text(o, key)) return GOLEM_OK;
    golem_digest digest; uint64_t size;
    if (!dw_digest(o, key, &digest)) return GOLEM_ERR_PARSE;
    return golem_evidence_verify(s->cas, &digest, &size, NULL);
}
static golem_status preconditions(golem_document_store *s, struct json_object *r)
{
    if (s->research_count >= GOLEM_RESEARCH_MAX_EVENTS) return GOLEM_ERR_BUDGET_EXHAUSTED;
    const char *permission = dw_text(s->spec, "permission");
    if (!strcmp(permission, "DENY")) return GOLEM_ERR_POLICY_DENIED;
    if (!strcmp(permission, "ASK_ALWAYS")) return GOLEM_ERR_APPROVAL_REQUIRED;
    struct json_object *o = dw_get(r, "record");
    if (strcmp(dw_text(o, "work_id"), dw_text(s->spec, "work_id"))) return GOLEM_ERR_IDENTITY_MISMATCH;
    for (size_t i = 0; i < s->research_count; ++i)
        if (!strcmp(dw_text(request_at(s, i), "key"), dw_text(r, "key"))) return GOLEM_ERR_IDENTITY_MISMATCH;
    const char *op = dw_text(r, "operation"), *case_id = dw_text(o, "case_id");
    if (rs_is_cohort(r)) return rs_cohort_check(s, r);
    size_t c = find(s, "case-create", case_id, NULL);
    if (!strcmp(op, "case-create")) {
        if (c != SIZE_MAX) return GOLEM_ERR_IDENTITY_MISMATCH;
        return evidence(s, o, "pre_registered_plan_digest");
    }
    if (c == SIZE_MAX) return GOLEM_ERR_NOT_FOUND;
    if (!matches(o, "case_digest", &s->research_digests[c])) return GOLEM_ERR_IDENTITY_MISMATCH;
    if (rs_is_outcome(r)) return rs_outcome_check(s, r, NULL);
    const char *attempt = dw_text(o, "attempt_id");
    size_t last = find(s, "attempt-record", case_id, NULL);
    if (last == SIZE_MAX ? *dw_text(o, "previous_attempt_digest") != '\0' :
        !matches(o, "previous_attempt_digest", &s->research_digests[last])) return GOLEM_ERR_STALE_RESULT;
    if (find(s, "attempt-record", case_id, attempt) != SIZE_MAX) return GOLEM_ERR_IDENTITY_MISMATCH;
    size_t plan = find(s, "attempt-plan", case_id, attempt);
    if (!strcmp(op, "attempt-plan")) {
        if (plan != SIZE_MAX) return GOLEM_ERR_IDENTITY_MISMATCH;
    } else if (plan == SIZE_MAX) {
        if (*dw_text(o, "plan_digest")) return GOLEM_ERR_NOT_FOUND;
    } else {
        if (!matches(o, "plan_digest", &s->research_digests[plan])) return GOLEM_ERR_IDENTITY_MISMATCH;
        /* An observation cannot silently rewrite its predeclared hypothesis. */
        struct json_object *p = record_at(s, plan);
        json_object_object_foreach(p, key, value) {
            if (!json_object_equal(value, dw_get(o, key))) return GOLEM_ERR_IDENTITY_MISMATCH;
        }
    }
    struct json_object *refs = dw_get(o, "input_refs");
    golem_status st = GOLEM_OK;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(refs); ++i)
        st = evidence(s, json_object_array_get_idx(refs, i), "digest");
    struct json_object *obs = dw_get(o, "observations");
    if (obs) for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(obs); ++i)
        st = evidence(s, json_object_array_get_idx(obs, i), "digest");
    return st;
}
static void adopt(golem_document_store *s, struct json_object *event,
    const golem_digest *payload, const golem_digest *frame)
{
    size_t i = s->research_count++;
    s->research[i] = json_object_get(event);
    s->research_digests[i] = *payload;
    s->research_frames[i] = *frame;
    s->last = *frame;
    ++s->event_count;
}
golem_status rs_apply(golem_document_store *s, struct json_object *event,
    const golem_digest *payload, const golem_digest *frame)
{
    struct json_object *r = dw_get(event, "request");
    bool adjudicate = !strcmp(dw_text(r, "operation"), "adjudicate");
    const char *keys[] = {"schema_version", "type", "sequence", "request", "assessment"};
    if (!dw_keys(event, keys, adjudicate ? 5 : 4) || dw_uint(event, "schema_version") != ((rs_is_outcome(r) || rs_is_cohort(r)) ? 2u : 1u) ||
        strcmp(dw_text(event, "type"), "research") || dw_uint(event, "sequence") != s->research_count + 1)
        return GOLEM_ERR_CORRUPT_JOURNAL;
    const char *encoded = json_object_to_json_string_ext(r, JSON_C_TO_STRING_PLAIN);
    if (!encoded) return GOLEM_ERR_OUT_OF_MEMORY;
    if (strlen(encoded) > GOLEM_RESEARCH_MAX_JSON) return GOLEM_ERR_BUDGET_EXHAUSTED;
    golem_status st = rs_validate(r);
    if (st == GOLEM_OK) st = preconditions(s, r);
    struct json_object *expected = NULL;
    if (st == GOLEM_OK && adjudicate) {
        st = rs_outcome_check(s, r, &expected);
        if (st == GOLEM_OK && !json_object_equal(expected, dw_get(event, "assessment"))) st = GOLEM_ERR_CORRUPT_JOURNAL;
    }
    json_object_put(expected);
    if (st == GOLEM_OK) adopt(s, event, payload, frame);
    return st;
}
static golem_status reply(struct json_object *event, const golem_digest *payload,
    const golem_digest *frame, golem_execution_reply *out)
{
    struct json_object *o = json_object_new_object();
    golem_status st = GOLEM_OK;
    if (!ex_uint(o, "schema_version", 1) || !ex_text(o, "status", "RECORDED") ||
        !dw_add(o, "adjudicated", json_object_new_boolean(dw_get(event, "assessment") != NULL)) ||
        !dw_add(o, "execution_authorized", json_object_new_boolean(false)) || !dw_add_digest(o, "record_digest", payload) ||
        !dw_add_digest(o, "event_digest", frame) || !dw_add(o, "event", json_object_get(event)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) st = ex_emit(o, out);
    json_object_put(o);
    return st;
}
golem_status golem_research_call(golem_document_store *s, golem_bytes b,
    golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out) return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (s->poisoned) return dw_report(d, GOLEM_ERR_INVALID_STATE, NULL);
    if (!s->writable) return dw_report(d, GOLEM_ERR_POLICY_DENIED, NULL);
    struct json_object *r = NULL, *event = NULL;
    golem_status st = golem_json_parse(b, GOLEM_RESEARCH_MAX_JSON, &r);
    if (st == GOLEM_OK) st = rs_validate(r);
    if (st == GOLEM_OK) {
        const char *encoded = json_object_to_json_string_ext(r, JSON_C_TO_STRING_PLAIN);
        if (!encoded) st = GOLEM_ERR_OUT_OF_MEMORY;
        else if (strlen(encoded) > GOLEM_RESEARCH_MAX_JSON) st = GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    for (size_t i = 0; st == GOLEM_OK && i < s->research_count; ++i) {
        struct json_object *old = request_at(s, i);
        if (strcmp(dw_text(old, "key"), dw_text(r, "key"))) continue;
        st = json_object_equal(old, r) ? reply(s->research[i], &s->research_digests[i], &s->research_frames[i], out)
            : GOLEM_ERR_IDENTITY_MISMATCH;
        json_object_put(r);
        return dw_report(d, st, NULL);
    }
    if (st == GOLEM_OK) st = preconditions(s, r);
    if (st == GOLEM_OK) {
        event = json_object_new_object();
        if (!ex_uint(event, "schema_version", (rs_is_outcome(r) || rs_is_cohort(r)) ? 2 : 1) || !ex_text(event, "type", "research") ||
            !ex_uint(event, "sequence", s->research_count + 1) || !dw_add(event, "request", json_object_get(r)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK && !strcmp(dw_text(r, "operation"), "adjudicate")) {
        struct json_object *assessment = NULL;
        st = rs_outcome_check(s, r, &assessment);
        if (st == GOLEM_OK && !dw_add(event, "assessment", assessment)) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_digest payload, frame;
    golem_execution_reply result = {0};
    if (st == GOLEM_OK) st = dw_put_json(s, event, &payload);
    /* Adoption cannot allocate. If reply allocation fails after commit, poison
     * the handle and recover the original receipt by replay and same-key retry. */
    if (st == GOLEM_OK) st = dw_event_write(s, &payload, &frame);
    if (st == GOLEM_OK) {
        adopt(s, event, &payload, &frame);
        st = reply(event, &payload, &frame, &result);
        if (st != GOLEM_OK) s->poisoned = true;
    }
    if (st == GOLEM_ERR_IO) s->poisoned = true;
    if (st == GOLEM_OK) *out = result;
    else golem_execution_reply_free(&result);
    json_object_put(event); json_object_put(r);
    return dw_report(d, st, st == GOLEM_OK ? "recorded declaration; not semantic acceptance" : NULL);
}
static golem_status lookup(golem_document_store *s, uint32_t seq, golem_execution_reply *out)
{
    if (!s || !out || !seq) return GOLEM_ERR_INVALID_ARGUMENT;
    if (s->poisoned) return GOLEM_ERR_INVALID_STATE;
    return seq > s->research_count ? GOLEM_ERR_NOT_FOUND : GOLEM_OK;
}
golem_status golem_research_inspect(golem_document_store *s, uint32_t seq,
    golem_execution_reply *out, golem_diagnostic *d)
{
    golem_status st = lookup(s, seq, out);
    if (st == GOLEM_OK) st = reply(s->research[seq - 1], &s->research_digests[seq - 1], &s->research_frames[seq - 1], out);
    return dw_report(d, st, NULL);
}
golem_status golem_research_report(golem_document_store *s, uint32_t seq,
    golem_execution_reply *out, golem_diagnostic *d)
{
    golem_status st = lookup(s, seq, out);
    if (st == GOLEM_OK) st = rs_markdown(s->research[seq - 1], out);
    return dw_report(d, st, NULL);
}
golem_status golem_research_status(golem_document_store *s, golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out) return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (s->poisoned) return dw_report(d, GOLEM_ERR_INVALID_STATE, NULL);
    struct json_object *o = json_object_new_object(), *items = json_object_new_array();
    golem_status st = items && o ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < s->research_count; ++i) {
        struct json_object *v = json_object_new_object(), *r = request_at(s, i), *record = dw_get(r, "record");
        if (!ex_uint(v, "sequence", i + 1) || !ex_text(v, "operation", dw_text(r, "operation")) ||
            !ex_text(v, "case_id", dw_text(record, "case_id")) ||
            !ex_text(v, "attempt_id", dw_text(record, "attempt_id")) ||
            !dw_add_digest(v, "record_digest", &s->research_digests[i])) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && rs_is_cohort(r) && !ex_text(v, "cohort_id", dw_text(record, "cohort_id")))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && json_object_array_add(items, v) == 0) v = NULL;
        else st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(v);
    }
    if (st == GOLEM_OK && (!ex_uint(o, "schema_version", 1) || !ex_uint(o, "count", s->research_count) ||
        !dw_add(o, "records", json_object_get(items))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) st = ex_emit(o, out);
    json_object_put(items); json_object_put(o);
    return dw_report(d, st, NULL);
}
