#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static golem_status record_empty(cf_context *c, const char *action, size_t i)
{
    struct json_object *o = json_object_new_object();
    if (!o)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = cf_append(c, action, i, o);
    json_object_put(o);
    return st;
}
static golem_status reserve(cf_context *c, size_t i)
{
    const char *state = cf_state(c, i);
    if (strcmp(state, "READY") && strcmp(state, "RESERVED"))
        return GOLEM_ERR_INVALID_STATE;
    golem_candidate_member member;
    golem_status st = cf_member(c, i, &member);
    for (size_t k = 0;
         st == GOLEM_OK && k < json_object_array_length(dw_get(c->manifest, "candidates")); ++k)
        if (!c->members[k])
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK && !strcmp(state, "READY")) {
        golem_digest ns;
        golem_admission_checkpoint checkpoint;
        struct json_object *data = json_object_new_object();
        st = golem_admission_identity(c->admission, &ns, &checkpoint);
        if (st == GOLEM_OK && !dw_add_digest(data, "namespace", &ns))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK)
            st = cf_append(c, "RESERVE", i, data);
        json_object_put(data);
    }
    golem_admission_request request = {0};
    struct json_object *spec = cf_spec(c, i), *r = dw_get(spec, "resources");
    cf_operation(c, i, request.operation);
    strcpy(request.work, dw_text(spec, "work_id"));
    strcpy(request.session, dw_text(spec, "session_id"));
    (void)dw_digest(spec, "runtime_binding", &request.runtime_binding);
    request.cpu_millis = dw_uint(r, "cpu");
    request.memory_bytes = dw_uint(r, "memory");
    uint64_t ticket;
    if (st == GOLEM_OK)
        st = golem_admission_enqueue(c->admission, &request, &ticket);
    golem_admission_ticket actual;
    if (st == GOLEM_OK)
        st = cf_ticket(c, i, &actual);
    if (st == GOLEM_OK && !dw_get(c->members[i], "token")) {
        struct json_object *token = cf_token(&actual.token);
        st = token ? cf_append(c, "TICKET", i, token) : GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(token);
    }
    return st;
}
static golem_status start(cf_context *c, size_t i)
{
    if (strcmp(cf_state(c, i), "RESERVED") || !c->host->start)
        return GOLEM_ERR_INVALID_STATE;
    golem_admission_ticket ticket;
    golem_status st = cf_ticket(c, i, &ticket);
    if (st == GOLEM_OK && (!cf_token_equal(dw_get(c->request, "token"), &ticket.token) ||
                           !cf_token_equal(dw_get(c->members[i], "token"), &ticket.token)))
        st = GOLEM_ERR_STALE_LEASE;
    if (st == GOLEM_OK && ticket.state != GOLEM_ADMISSION_GRANTED)
        st = GOLEM_ERR_LEASE_BUSY;
    if (st == GOLEM_OK)
        st = cf_budget(c, i);
    golem_candidate_member member;
    if (st == GOLEM_OK)
        st = cf_member(c, i, &member);
    if (st == GOLEM_OK)
        st = c->host->check(c->host->context, c->request_bytes);
    if (st == GOLEM_OK)
        st = record_empty(c, "START_INTENT", i);
    char operation[64];
    cf_operation(c, i, operation);
    if (st == GOLEM_OK)
        st =
            c->host->start(c->host->context, dw_text(cf_spec(c, i), "id"), c->admission, operation);
    if (st == GOLEM_OK)
        st = cf_ticket(c, i, &ticket);
    if (st == GOLEM_OK && ticket.state != GOLEM_ADMISSION_RUNNING)
        st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK)
        st = record_empty(c, "RUNNING", i);
    return st;
}
static golem_status finish(cf_context *c, size_t i)
{
    const char *keys[] = {"operation", "group_id",     "candidate",  "token",  "termination", "qa",
                          "cancelled", "tokens_known", "cost_known", "tokens", "nano_cost"};
    if (!dw_keys(c->request, keys, 11) ||
        (!cf_held(cf_state(c, i)) && strcmp(cf_state(c, i), "FINISHED")))
        return GOLEM_ERR_INVALID_STATE;
    for (size_t k = 6; k <= 8; ++k)
        if (!json_object_is_type(dw_get(c->request, keys[k]), json_type_boolean))
            return GOLEM_ERR_PARSE;
    for (size_t k = 9; k <= 10; ++k)
        if (!json_object_is_type(dw_get(c->request, keys[k]), json_type_int) ||
            json_object_get_int64(dw_get(c->request, keys[k])) < 0 ||
            dw_uint(c->request, keys[k]) > INT64_MAX ||
            (!json_object_get_boolean(dw_get(c->request, keys[k - 2])) &&
             dw_uint(c->request, keys[k])))
            return GOLEM_ERR_PARSE;
    golem_digest proof, qa;
    if (!dw_digest(c->request, "termination", &proof) ||
        !json_object_is_type(dw_get(c->request, "qa"), json_type_string) ||
        (*dw_text(c->request, "qa") && !dw_digest(c->request, "qa", &qa)))
        return GOLEM_ERR_PARSE;
    golem_admission_ticket ticket;
    golem_status st = cf_ticket(c, i, &ticket);
    if (st == GOLEM_OK && !cf_token_equal(dw_get(c->request, "token"), &ticket.token))
        st = GOLEM_ERR_STALE_LEASE;
    uint64_t size;
    if (st == GOLEM_OK)
        st = golem_evidence_verify(c->parent->cas, &proof, &size, NULL);
    /* A receipt must belong to THIS child. Freshness is re-evaluated at compare;
     * stale/error QA can still settle billing and release observed termination. */
    if (st == GOLEM_OK && *dw_text(c->request, "qa")) {
        golem_candidate_member member;
        struct json_object *record = NULL;
        st = cf_member(c, i, &member);
        if (st == GOLEM_OK)
            st = ex_load(member.work, &qa, "qa", &record);
        json_object_put(record);
    }
    struct json_object *result = json_object_new_object();
    for (size_t k = 4; st == GOLEM_OK && k < 11; ++k)
        if (!dw_add(result, keys[k], json_object_get(dw_get(c->request, keys[k]))))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *old = dw_get(c->members[i], "result");
    if (st == GOLEM_OK && old && !json_object_equal(old, result))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        st = c->host->check(c->host->context, c->request_bytes);
    if (st == GOLEM_OK && !old)
        st = cf_append(c, "SETTLING", i, result);
    if (st == GOLEM_OK &&
        (ticket.state == GOLEM_ADMISSION_QUEUED || ticket.state == GOLEM_ADMISSION_GRANTED)) {
        st = golem_admission_cancel(c->admission, ticket.token);
        if (st == GOLEM_OK)
            st = cf_ticket(c, i, &ticket);
    }
    if (st == GOLEM_OK && ticket.state != GOLEM_ADMISSION_CANCELLED) {
        st = golem_admission_settle(c->admission, ticket.token, proof);
        if (st == GOLEM_OK)
            st = golem_admission_release(c->admission, ticket.token);
    }
    if (st == GOLEM_OK && strcmp(cf_state(c, i), "FINISHED"))
        st = record_empty(c, "FINISHED", i);
    json_object_put(result);
    return st;
}

static golem_status dispatch(cf_context *c, const char *op, size_t i, struct json_object **out)
{
    golem_status st = GOLEM_OK;
    if (!strcmp(op, "enroll")) {
        struct json_object *data = NULL;
        st = cf_enroll(c, i, &data);
        if (st == GOLEM_OK)
            st = cf_append(c, "ENROLL", i, data);
        json_object_put(data);
    } else if (!strcmp(op, "reserve"))
        st = reserve(c, i);
    else if (!strcmp(op, "start"))
        st = start(c, i);
    else if (!strcmp(op, "finish"))
        st = finish(c, i);
    else if (!strcmp(op, "cancel")) {
        golem_admission_ticket ticket;
        bool attempted = json_object_get_boolean(dw_get(c->members[i], "dispatch_intent"));
        st = attempted && !c->host->cancel ? GOLEM_ERR_APPROVAL_REQUIRED : cf_ticket(c, i, &ticket);
        if (st == GOLEM_OK && !cf_token_equal(dw_get(c->request, "token"), &ticket.token))
            st = GOLEM_ERR_STALE_LEASE;
        if (st == GOLEM_OK)
            st = c->host->check(c->host->context, c->request_bytes);
        if (st == GOLEM_OK && strcmp(cf_state(c, i), "CANCEL_REQUESTED"))
            st = record_empty(c, "CANCEL_REQUESTED", i);
        if (st == GOLEM_OK)
            st = golem_admission_cancel(c->admission, ticket.token);
        if (st == GOLEM_OK && attempted)
            st = c->host->cancel(c->host->context, dw_text(cf_spec(c, i), "id"));
    } else if (!strcmp(op, "target-check"))
        return cf_target(c, i, out);
    else if (!strcmp(op, "select") || !strcmp(op, "cohort-record")) {
        struct json_object *comparison = NULL;
        st = cf_report(c, true, &comparison);
        if (st == GOLEM_OK && !strcmp(op, "cohort-record"))
            st = cf_cohort(c, comparison, out);
        else if (st == GOLEM_OK) {
            struct json_object *row =
                json_object_array_get_idx(dw_get(comparison, "candidates"), i);
            if (strcmp(dw_text(row, "eligibility"), "PASS") ||
                !strcmp(dw_text(comparison, "decision"), "INCOMPARABLE"))
                st = GOLEM_ERR_REQUIREMENTS_UNMET;
            golem_digest digest;
            struct json_object *selection = json_object_new_object();
            if (st == GOLEM_OK)
                st = dw_put_json(c->parent, comparison, &digest);
            if (st == GOLEM_OK &&
                (!ex_uint(selection, "candidate", i) ||
                 !dw_add_digest(selection, "comparison", &digest) ||
                 !dw_add(selection, "requires_target_revalidation",
                         json_object_new_boolean(true)) ||
                 !dw_add(selection, "merge_authorized", json_object_new_boolean(false)) ||
                 !dw_add(selection, "push_authorized", json_object_new_boolean(false))))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK)
                st = c->host->check(c->host->context, c->request_bytes);
            if (st == GOLEM_OK)
                st = cf_append(c, "SELECT", i, selection);
            json_object_put(selection);
        }
        json_object_put(comparison);
        if (!strcmp(op, "cohort-record"))
            return st;
    }
    if (st == GOLEM_OK)
        st = cf_report(c, !strcmp(op, "compare"), out);
    return st;
}

golem_status golem_candidate_call(golem_document_store *s, const golem_candidate_host *host,
                                  golem_admission *admission, golem_bytes bytes,
                                  golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || s->poisoned || !out)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    cf_context c = {
        .parent = s, .host = host, .admission = admission, .request_bytes = bytes, .dir = -1};
    golem_status st = golem_json_parse(bytes, GOLEM_DOCUMENT_MAX_JSON, &c.request);
    const char *op = dw_text(c.request, "operation"), *group = dw_text(c.request, "group_id");
    bool create = !strcmp(op, "create"),
         readonly = !strcmp(op, "status") || !strcmp(op, "compare") || !strcmp(op, "target-check");
    const char *keys[] = {"operation", "group_id", "candidate", "token"};
    const char *create_keys[] = {"operation", "manifest"};
    const char *target_keys[] = {"operation", "group_id", "candidate", "qa"};
    if (create) {
        if (!dw_keys(c.request, create_keys, 2))
            st = GOLEM_ERR_PARSE;
        if (st == GOLEM_OK)
            st = cf_model(dw_get(c.request, "manifest"));
        if (st == GOLEM_OK)
            st = cf_cohort_check(s, dw_get(c.request, "manifest"));
        group = dw_text(dw_get(c.request, "manifest"), "group_id");
    } else if (!strcmp(op, "target-check")) {
        if (!dw_keys(c.request, target_keys, 4))
            st = GOLEM_ERR_PARSE;
    } else if (strcmp(op, "finish")) {
        bool general =
            !strcmp(op, "status") || !strcmp(op, "compare") || !strcmp(op, "cohort-record");
        bool token = !strcmp(op, "start") || !strcmp(op, "cancel");
        if ((!general && !token && strcmp(op, "enroll") && strcmp(op, "reserve") &&
             strcmp(op, "select")) ||
            !dw_keys(c.request, keys,
                     general ? 2
                     : token ? 4
                             : 3))
            st = GOLEM_ERR_PARSE;
    }
    if (st == GOLEM_OK && (!ws_id(group) || strlen(group) > 24))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK && !readonly &&
        (!s->writable || !strcmp(dw_text(s->spec, "permission"), "DENY")))
        st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK && strcmp(op, "status") &&
        (!host || host->size != sizeof(*host) || host->version != 1 || !host->resolve ||
         !host->check))
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    if (st == GOLEM_OK && strcmp(op, "status"))
        st = host->check(host->context, bytes);
    int groups = -1;
    if (st == GOLEM_OK)
        st = dw_dir(s->root, "candidate-groups", create, &groups);
    if (st == GOLEM_OK)
        st = dw_dir(groups, group, create, &c.dir);
    if (groups >= 0 && close(groups) != 0 && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK)
        st = cf_load(&c);
    if (st == GOLEM_OK && create) {
        if (c.manifest)
            st = json_object_equal(c.manifest, dw_get(c.request, "manifest"))
                     ? GOLEM_OK
                     : GOLEM_ERR_IDENTITY_MISMATCH;
        else
            st = cf_append(&c, "CREATE", 0, dw_get(c.request, "manifest"));
    }
    if (st == GOLEM_OK && !c.manifest)
        st = GOLEM_ERR_NOT_FOUND;
    size_t i = 0;
    bool member_operation =
        !create && strcmp(op, "status") && strcmp(op, "compare") && strcmp(op, "cohort-record");
    if (st == GOLEM_OK && member_operation &&
        (!ws_id(dw_text(c.request, "candidate")) || strlen(dw_text(c.request, "candidate")) > 24))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK && *dw_text(c.request, "candidate")) {
        size_t count = json_object_array_length(dw_get(c.manifest, "candidates"));
        for (; i < count; ++i)
            if (!strcmp(dw_text(cf_spec(&c, i), "id"), dw_text(c.request, "candidate")))
                break;
        if (i == count)
            st = GOLEM_ERR_NOT_FOUND;
    }
    if (st == GOLEM_OK &&
        (!strcmp(op, "reserve") || !strcmp(op, "start") || !strcmp(op, "finish") ||
         !strcmp(op, "cancel")) &&
        !admission)
        st = GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *response = NULL;
    if (st == GOLEM_OK)
        st = dispatch(&c, create ? "status" : op, i, &response);
    if (c.dir >= 0 && close(c.dir) != 0 && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK)
        st = ex_emit(response, out);
    for (size_t k = 0; k < GOLEM_CANDIDATE_MAX; ++k)
        json_object_put(c.members[k]);
    json_object_put(c.manifest);
    json_object_put(c.selection);
    json_object_put(c.request);
    json_object_put(response);
    return dw_report(d, st, NULL);
}
