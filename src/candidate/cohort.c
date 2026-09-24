#include "internal.h"
#include <stdio.h>
#include <string.h>

static struct json_object *cohort_record(golem_document_store *s, struct json_object *m)
{
    struct json_object *link = dw_get(m, "cohort");
    golem_digest digest;
    if (!link || !dw_digest(link, "cohort_digest", &digest))
        return NULL;
    for (size_t i = 0; i < s->research_count; ++i) {
        struct json_object *request = dw_get(s->research[i], "request");
        struct json_object *record = dw_get(request, "record");
        if (!strcmp(dw_text(request, "operation"), "cohort-create") &&
            !strcmp(dw_text(record, "cohort_id"), dw_text(link, "cohort_id")) &&
            dw_equal(&s->research_digests[i], &digest))
            return record;
    }
    return NULL;
}
golem_status cf_cohort_check(golem_document_store *s, struct json_object *m)
{
    struct json_object *link = dw_get(m, "cohort");
    if (!link)
        return GOLEM_OK;
    struct json_object *record = cohort_record(s, m);
    if (!record)
        return GOLEM_ERR_NOT_FOUND;
    if (strcmp(dw_text(record, "protocol_digest"), dw_text(m, "protocol_digest")) ||
        strcmp(dw_text(record, "task_digest"), dw_text(m, "task_digest")) ||
        strcmp(dw_text(record, "evaluation_digest"), dw_text(m, "gates_digest")))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *members = dw_get(record, "members");
    bool found = false;
    for (size_t i = 0; i < json_object_array_length(members); ++i) {
        struct json_object *v = json_object_array_get_idx(members, i);
        if (!strcmp(dw_text(v, "case_id"), dw_text(link, "case_id")) &&
            !strcmp(dw_text(v, "arm"), "FULL_USE"))
            found = true;
    }
    if (!found)
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    golem_digest digest;
    struct json_object *protocol = NULL, *expected = json_object_new_object();
    golem_status st = dw_digest(m, "protocol_digest", &digest) ? dw_cas_json(s, &digest, &protocol)
                                                               : GOLEM_ERR_PARSE;
    size_t n = json_object_array_length(dw_get(m, "candidates"));
    if (st == GOLEM_OK &&
        (!ex_uint(expected, "schema_version", 1) ||
         !ex_text(expected, "unit", n > 1 ? "TASK_BEST_OF_N" : "TASK_SINGLE_CANDIDATE") ||
         !ex_uint(expected, "candidate_count", n) ||
         !dw_add(expected, "limits", json_object_get(dw_get(m, "limits"))) ||
         !ex_text(expected, "currency", dw_text(m, "currency"))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && !json_object_equal(protocol, expected))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    json_object_put(protocol);
    json_object_put(expected);
    return st;
}

golem_status cf_cohort(cf_context *c, struct json_object *report, struct json_object **out)
{
    if (c->exported)
        return GOLEM_ERR_INVALID_STATE;
    golem_status st = cf_cohort_check(c->parent, c->manifest);
    struct json_object *cohort = cohort_record(c->parent, c->manifest),
                       *link = dw_get(c->manifest, "cohort");
    if (st == GOLEM_OK && !cohort)
        st = GOLEM_ERR_NOT_FOUND;
    for (size_t i = 0;
         st == GOLEM_OK && i < json_object_array_length(dw_get(c->manifest, "candidates")); ++i)
        if (strcmp(cf_state(c, i), "FINISHED"))
            st = GOLEM_ERR_INCOMPLETE_WORK;
    struct json_object *record = json_object_new_object(), *request = json_object_new_object();
    golem_digest evidence;
    if (st == GOLEM_OK)
        st = dw_put_json(c->parent, report, &evidence);
    const char *verdict = dw_text(report, "decision");
    const char *status = !strcmp(verdict, "INCOMPARABLE")  ? "NOT_DONE"
                         : !strcmp(verdict, "NO_ELIGIBLE") ? "FAIL"
                                                           : "PASS";
    bool leakage = false;
    for (size_t i = 0; i < json_object_array_length(dw_get(c->manifest, "candidates")); ++i)
        leakage = leakage || strcmp(dw_text(cf_spec(c, i), "environment_digest"),
                                    dw_text(cohort, "environment_digest")) != 0;
    if (st == GOLEM_OK &&
        (!ex_uint(record, "schema_version", 1) ||
         !ex_text(record, "work_id", dw_text(c->parent->spec, "work_id")) ||
         !ex_text(record, "cohort_id", dw_text(link, "cohort_id")) ||
         !ex_text(record, "cohort_digest", dw_text(link, "cohort_digest")) ||
         !ex_text(record, "case_id", dw_text(link, "case_id")) ||
         !ex_text(record, "supersedes", "") || !ex_text(record, "status", status) ||
         !ex_text(record, "observed_arm", "FULL_USE") ||
         !ex_text(record, "environment_digest", dw_text(cf_spec(c, 0), "environment_digest")) ||
         !dw_add_digest(record, "evidence_digest", &evidence) ||
         !dw_add(record, "leakage", json_object_new_boolean(leakage))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    char key[64];
    (void)snprintf(key, sizeof(key), "candidate-cohort-%s", dw_text(c->manifest, "group_id"));
    if (st == GOLEM_OK &&
        (!ex_uint(request, "schema_version", 1) ||
         !ex_text(request, "operation", "cohort-observe") || !ex_text(request, "key", key) ||
         !dw_add(request, "record", json_object_get(record))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_execution_reply reply = {0}, wire = {0};
    if (st == GOLEM_OK)
        st = ex_emit(request, &wire);
    if (st == GOLEM_OK)
        st = c->host->check(c->host->context, c->request_bytes);
    if (st == GOLEM_OK)
        st = golem_research_call(c->parent, (golem_bytes){wire.data, wire.size}, &reply, NULL);
    struct json_object *response = NULL;
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){reply.data, reply.size}, GOLEM_DOCUMENT_MAX_JSON,
                              &response);
    if (st == GOLEM_OK)
        st = cf_append(c, "COHORT", 0, response);
    if (st == GOLEM_OK)
        *out = response;
    else
        json_object_put(response);
    json_object_put(record);
    json_object_put(request);
    golem_execution_reply_free(&reply);
    golem_execution_reply_free(&wire);
    return st;
}
