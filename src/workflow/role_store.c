#include "role_internal.h"
#include "template_internal.h"
#include "../reentry/internal.h"
#include <string.h>

struct json_object *rc_enrollment(golem_document_store *s, const char *id)
{
    for (size_t i = 0; i < s->role_count; ++i) {
        struct json_object *r = dw_get(s->roles[i], "request");
        if (!strcmp(dw_text(r, "selection_id"), id) && !strcmp(dw_text(r, "operation"), "enroll"))
            return s->roles[i];
    }
    return NULL;
}
struct json_object *rc_latest(golem_document_store *s, const char *id)
{
    for (size_t i = s->role_count; i > 0; --i) {
        struct json_object *r = dw_get(s->roles[i - 1], "request");
        if (!strcmp(dw_text(r, "selection_id"), id) && !strcmp(dw_text(r, "operation"), "assess"))
            return s->roles[i - 1];
    }
    return NULL;
}
static golem_status preconditions(golem_document_store *s, struct json_object *r)
{
    golem_status st = rc_request(r);
    if (st != GOLEM_OK)
        return st;
    if (s->role_count >= GOLEM_ROLE_MAX_EVENTS)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    if (dw_uint(r, "expected_generation") != s->count + 1)
        return GOLEM_ERR_STALE_RESULT;
    dw_entry *plan = dw_find(s, dw_text(r, "selection_id"), 0);
    if (!plan || dw_uint(plan->meta, "schema_version") != 3 ||
        strcmp(dw_text(plan->meta, "kind"), "stage-selection"))
        return GOLEM_ERR_NOT_FOUND;
    wf_graph graph = {0};
    st = wf_graph_make(s, &graph);
    if (st == GOLEM_OK && graph.states[plan - s->entries] != GOLEM_DOCUMENT_CURRENT)
        st = GOLEM_ERR_STALE_RESULT;
    wf_graph_free(s, &graph);
    if (st != GOLEM_OK)
        return st;
    struct json_object *enrolled = rc_enrollment(s, dw_text(r, "selection_id"));
    if (!strcmp(dw_text(r, "operation"), "enroll")) {
        /* Enrollment is a Work obligation; renaming a selection must not
         * create a second, weaker completion route. Revisions retain its ID. */
        if (s->role_count || enrolled)
            return GOLEM_ERR_IDENTITY_MISMATCH;
        struct json_object *c = dw_get(r, "contract"), *selection = dw_get(plan->meta, "selection");
        struct json_object *template = wt_definition(selection);
        if (template && !json_object_equal(c, dw_get(template, "role_contract")))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        if (strcmp(dw_text(c, "mode"), dw_text(selection, "mode")))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        struct json_object *rules = dw_get(c, "rules");
        for (size_t i = 0; i < json_object_array_length(rules); ++i) {
            int kind = wf_kind(dw_text(json_object_array_get_idx(rules, i), "kind"));
            struct json_object *decision =
                json_object_array_get_idx(dw_get(selection, "decisions"), (size_t)wf_stage(kind));
            if (!strcmp(dw_text(decision, "status"), "NOT_APPLICABLE"))
                return GOLEM_ERR_REQUIREMENTS_UNMET;
        }
    } else {
        if (!enrolled)
            return GOLEM_ERR_NOT_FOUND;
        size_t count = 0;
        for (size_t i = 0; i < s->role_count; ++i) {
            struct json_object *old = dw_get(s->roles[i], "request");
            if (!strcmp(dw_text(old, "selection_id"), dw_text(r, "selection_id")) &&
                !strcmp(dw_text(old, "operation"), "assess"))
                ++count;
        }
        if (count >= dw_uint(dw_get(dw_get(enrolled, "request"), "contract"), "max_assessments"))
            return GOLEM_ERR_ATTEMPT_LIMIT;
    }
    return GOLEM_OK;
}
static void adopt(golem_document_store *s, struct json_object *event, const golem_digest *payload,
                  const golem_digest *frame)
{
    s->roles[s->role_count] = json_object_get(event);
    s->role_digests[s->role_count++] = *payload;
    s->last = *frame;
    ++s->event_count;
}
golem_status rc_apply(golem_document_store *s, struct json_object *event,
                      const golem_digest *payload, const golem_digest *frame)
{
    const char *keys[] = {"schema_version", "type", "sequence", "request", "assessment"};
    if (!dw_keys(event, keys, 5) || dw_uint(event, "schema_version") != 1 ||
        strcmp(dw_text(event, "type"), "roles") || dw_uint(event, "sequence") != s->role_count + 1)
        return GOLEM_ERR_CORRUPT_JOURNAL;
    struct json_object *r = dw_get(event, "request"), *assessment = NULL;
    if (strcmp(dw_text(r, "operation"), "enroll") && strcmp(dw_text(r, "operation"), "assess"))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    for (size_t i = 0; i < s->role_count; ++i)
        if (!strcmp(dw_text(dw_get(s->roles[i], "request"), "key"), dw_text(r, "key")))
            return GOLEM_ERR_CORRUPT_JOURNAL;
    golem_status st = preconditions(s, r);
    if (st == GOLEM_OK && !strcmp(dw_text(r, "operation"), "assess"))
        st = rc_assess(s, r, false, dw_get(event, "assessment"), &assessment);
    else if (st == GOLEM_OK)
        assessment = json_object_new_object();
    if (st == GOLEM_OK && !json_object_equal(assessment, dw_get(event, "assessment")))
        st = GOLEM_ERR_CORRUPT_JOURNAL;
    if (st == GOLEM_OK)
        adopt(s, event, payload, frame);
    json_object_put(assessment);
    return st;
}
static golem_status reply(struct json_object *event, const golem_digest *digest,
                          golem_execution_reply *out)
{
    struct json_object *v = json_object_new_object();
    golem_status st = GOLEM_OK;
    if (!dw_add(v, "event", json_object_get(event)) || !dw_add_digest(v, "receipt_digest", digest))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ex_emit(v, out);
    json_object_put(v);
    return st;
}
golem_status golem_role_call(golem_document_store *s, golem_bytes bytes,
                             const golem_digest *approval, golem_execution_reply *out,
                             golem_diagnostic *d)
{
    if (!s || !out || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *r = NULL, *assessment = NULL, *event = NULL;
    golem_status st = golem_json_parse(bytes, GOLEM_ROLE_MAX_JSON, &r);
    if (st == GOLEM_OK)
        st = rc_request(r);
    const char *op = dw_text(r, "operation");
    if (st == GOLEM_OK && !strcmp(op, "status")) {
        struct json_object *latest = rc_latest(s, dw_text(r, "selection_id"));
        if (!latest)
            latest = rc_enrollment(s, dw_text(r, "selection_id"));
        st = latest ? ex_emit(latest, out) : GOLEM_ERR_NOT_FOUND;
        json_object_put(r);
        return dw_report(d, st, NULL);
    }
    bool evaluate = !strcmp(op, "evaluate");
    for (size_t i = 0; st == GOLEM_OK && !evaluate && i < s->role_count; ++i)
        if (!strcmp(dw_text(dw_get(s->roles[i], "request"), "key"), dw_text(r, "key"))) {
            st = json_object_equal(dw_get(s->roles[i], "request"), r)
                     ? reply(s->roles[i], &s->role_digests[i], out)
                     : GOLEM_ERR_IDENTITY_MISMATCH;
            json_object_put(r);
            return dw_report(d, st, NULL);
        }
    if (st == GOLEM_OK && !evaluate &&
        (!s->writable || !strcmp(dw_text(s->spec, "permission"), "DENY")))
        st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK && !evaluate && !strcmp(dw_text(s->spec, "permission"), "ASK_ALWAYS"))
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    if (st == GOLEM_OK && !strcmp(op, "enroll")) {
        golem_digest digest;
        st = ex_hash(dw_get(r, "contract"), &digest);
        if (st == GOLEM_OK && (!approval || !dw_equal(approval, &digest)))
            st = GOLEM_ERR_APPROVAL_REQUIRED;
    }
    if (st == GOLEM_OK && !evaluate)
        st = re_deadline(s);
    if (st == GOLEM_OK && !evaluate)
        st = preconditions(s, r);
    if (st == GOLEM_OK && strcmp(op, "enroll"))
        st = rc_assess(s, r, true, NULL, &assessment);
    else if (st == GOLEM_OK)
        assessment = json_object_new_object();
    if (st == GOLEM_OK && evaluate) {
        st = ex_emit(assessment, out);
        json_object_put(assessment);
        json_object_put(r);
        return dw_report(d, st, NULL);
    }
    golem_digest payload, frame;
    golem_execution_reply response = {0};
    if (st == GOLEM_OK) {
        event = json_object_new_object();
        if (!ex_uint(event, "schema_version", 1) || !ex_text(event, "type", "roles") ||
            !ex_uint(event, "sequence", s->role_count + 1) ||
            !dw_add(event, "request", json_object_get(r)) ||
            !dw_add(event, "assessment", json_object_get(assessment)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        st = dw_put_json(s, event, &payload);
    if (st == GOLEM_OK)
        st = reply(event, &payload, &response);
    if (st == GOLEM_OK)
        st = dw_event_write(s, &payload, &frame);
    if (st == GOLEM_OK) {
        adopt(s, event, &payload, &frame);
        *out = response;
        response = (golem_execution_reply){0};
    }
    if (st == GOLEM_ERR_IO)
        s->poisoned = true;
    golem_execution_reply_free(&response);
    json_object_put(r);
    json_object_put(assessment);
    json_object_put(event);
    return dw_report(d, st, NULL);
}

golem_status rc_hint(golem_document_store *s, const char *id, const char **action,
                     const char **kind, const char **reason)
{
    if (wt_guard(s, id) != GOLEM_OK) {
        *action = "BLOCKED";
        *kind = "stage-selection";
        *reason = "TEMPLATE_ROLE_ENROLLMENT_REQUIRED";
        return GOLEM_OK;
    }
    if (!s->role_count)
        return GOLEM_OK;
    if (!rc_enrollment(s, id)) {
        *action = "BLOCKED";
        *kind = "stage-selection";
        *reason = "ROLE_SELECTION_MISMATCH";
        return GOLEM_OK;
    }
    struct json_object *last = rc_latest(s, id), *current = NULL;
    *action = "ASSESS_DELIVERABLES";
    *kind = "completion";
    *reason = "ROLE_ASSESSMENT_REQUIRED";
    if (!last)
        return GOLEM_OK;
    golem_status st = rc_assess(s, dw_get(last, "request"), true, NULL, &current);
    if (st != GOLEM_OK && st != GOLEM_ERR_STALE_RESULT)
        return st;
    if (st == GOLEM_OK && !strcmp(dw_text(current, "state"), "SATISFIED") &&
        json_object_equal(current, dw_get(last, "assessment")))
        *action = NULL;
    else if (st == GOLEM_OK && json_object_equal(current, dw_get(last, "assessment"))) {
        *action = dw_text(dw_get(last, "assessment"), "next_action");
        *kind = dw_text(dw_get(last, "assessment"), "target_kind");
        *reason = "ROLE_EVIDENCE_UNSATISFIED";
    }
    size_t attempts = s->role_count - 1; /* One immutable enrollment per Work. */
    if (*action && attempts >= dw_uint(dw_get(dw_get(rc_enrollment(s, id), "request"), "contract"),
                                       "max_assessments")) {
        *action = "BLOCKED";
        *reason = "ROLE_ASSESSMENT_BUDGET_EXHAUSTED";
    }
    json_object_put(current);
    return GOLEM_OK;
}
