#include "binding_internal.h"
#include <string.h>

static bool text(struct json_object *o, const char *key, const char *value)
{
    return dw_add(o, key, json_object_new_string(value));
}

static golem_status documents(golem_document_store *s, struct json_object *docs,
                              struct json_object *assessments, size_t budget)
{
    wf_graph graph = {0};
    golem_status st = wf_graph_make(s, &graph);
    size_t used = 0;
    for (size_t i = 0; st == GOLEM_OK && i < s->count; ++i) {
        dw_entry *e = &s->entries[i];
        struct json_object *meta = json_object_new_object(), *row = wf_ref(e);
        if (!meta || !row)
            st = GOLEM_ERR_OUT_OF_MEMORY;
        /* Never remove fields from the registry's borrowed metadata. */
        json_object_object_foreach(e->meta, key, value) {
            if (st == GOLEM_OK && strcmp(key, "assessment") &&
                !dw_add(meta, key, json_object_get(value)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        struct json_object *assessment = dw_get(e->meta, "assessment");
        if (st == GOLEM_OK && assessment) {
            const char *bytes = json_object_to_json_string_ext(assessment, JSON_C_TO_STRING_PLAIN);
            golem_digest digest;
            char hex[65];
            size_t required;
            st = bytes ? golem_digest_bytes((golem_bytes){(const uint8_t *)bytes, strlen(bytes)},
                                            &digest) : GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK)
                st = golem_digest_format(&digest, hex, sizeof(hex), &required);
            if (st == GOLEM_OK && !dw_get(assessments, hex)) {
                size_t n = strlen(bytes);
                if (n > budget - used)
                    st = GOLEM_ERR_BUDGET_EXHAUSTED;
                else {
                    used += n;
                    if (!dw_add(assessments, hex, json_object_get(assessment)))
                        st = GOLEM_ERR_OUT_OF_MEMORY;
                }
            }
            if (st == GOLEM_OK && !text(row, "assessment_ref", hex))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        if (st == GOLEM_OK &&
            (!dw_add(row, "metadata", json_object_get(meta)) ||
             !dw_add_digest(row, "body_digest", &e->result.body_digest) ||
             !dw_add_digest(row, "event_digest", &e->result.event_digest) ||
             !text(row, "freshness", graph.states[i] == GOLEM_DOCUMENT_CURRENT ? "CURRENT"
                                    : graph.states[i] == GOLEM_DOCUMENT_STALE ? "STALE"
                                                                            : "SUPERSEDED")))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) {
            const char *bytes = json_object_to_json_string_ext(row, JSON_C_TO_STRING_PLAIN);
            size_t n = bytes ? strlen(bytes) : SIZE_MAX;
            if (n > budget - used)
                st = GOLEM_ERR_BUDGET_EXHAUSTED;
            else {
                used += n;
                if (!wf_append(docs, json_object_get(row)))
                    st = GOLEM_ERR_OUT_OF_MEMORY;
            }
        }
        json_object_put(meta);
        json_object_put(row);
    }
    wf_graph_free(s, &graph);
    return st;
}

golem_status golem_work_record(golem_document_store *s, golem_bytes bytes,
                               const golem_agent_clock *clock, golem_agent_reply *out,
                               golem_diagnostic *d)
{
    if (!s || !out || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, "record.arguments");
    struct json_object *r = NULL, *o = NULL, *docs = NULL, *assessments = NULL,
                       *rows = NULL, *status = NULL, *request = NULL;
    golem_agent_reply reply = {0};
    as_log log = {.directory = -1};
    const char *phase = "record.request";
    const char *keys[] = {"schema_version", "work_id", "byte_budget", "document_head", "agent_head"};
    golem_status st = golem_json_parse(bytes, GOLEM_SESSION_BINDING_MAX_BYTES, &r);
    if (st == GOLEM_OK &&
        (!dw_keys(r, keys, 5) || dw_uint(r, "schema_version") != 1 ||
         !dw_id(dw_text(r, "work_id")) || !dw_uint(r, "byte_budget") ||
         dw_uint(r, "byte_budget") > GOLEM_AGENT_CONTEXT_MAX ||
         !json_object_is_type(dw_get(r, "document_head"), json_type_string) ||
         !json_object_is_type(dw_get(r, "agent_head"), json_type_string)))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK && strcmp(dw_text(r, "work_id"), dw_text(s->spec, "work_id")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK) {
        phase = "record.agent_replay";
        st = as_load(s, NULL, NULL, &log);
    }
    if (st == GOLEM_OK && (dw_text(r, "document_head")[0] || dw_text(r, "agent_head")[0])) {
        golem_digest doc, agent;
        phase = "record.heads";
        if (!dw_digest(r, "document_head", &doc) || !dw_digest(r, "agent_head", &agent) ||
            !dw_equal(&doc, &s->last) || !dw_equal(&agent, &log.last))
            st = GOLEM_ERR_STALE_RESULT;
    }
    if (st == GOLEM_OK) {
        o = json_object_new_object();
        docs = json_object_new_array();
        assessments = json_object_new_object();
        rows = json_object_new_array();
        request = json_object_new_object();
        if (!o || !docs || !assessments || !rows || !request ||
            !dw_add(request, "schema_version", json_object_new_int(1)) ||
            !text(request, "operation", "status") ||
            !text(request, "work_id", dw_text(s->spec, "work_id")))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK) {
        const char *query = json_object_to_json_string_ext(request, JSON_C_TO_STRING_PLAIN);
        phase = "record.status";
        st = query ? golem_agent_session_call(s, (golem_bytes){(const uint8_t *)query, strlen(query)},
                                               clock, &reply, d) : GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK)
            st = golem_json_parse((golem_bytes){reply.data, reply.size}, GOLEM_AGENT_CONTEXT_MAX, &status);
    }
    if (st == GOLEM_OK) {
        phase = "record.documents";
        st = documents(s, docs, assessments, (size_t)dw_uint(r, "byte_budget"));
    }
    uint64_t ordinal = 0;
    if (st == GOLEM_OK) {
        phase = "record.journal";
        st = ab_project_stream(s, s->events, false, s->event_count, &s->last,
                                0, UINT64_MAX, &ordinal, rows);
    }
    if (st == GOLEM_OK)
        st = ab_project_stream(s, log.directory, true, (size_t)log.sequence,
                                &log.last, 0, UINT64_MAX, &ordinal, rows);
    if (st == GOLEM_OK &&
        (!text(o, "schema", "golem.work-record.v1") ||
         !dw_add(o, "schema_version", json_object_new_int(1)) ||
         !text(o, "work_id", dw_text(s->spec, "work_id")) ||
         !dw_add_digest(o, "document_head", &s->last) ||
         !dw_add_digest(o, "agent_head", &log.last) ||
         !text(o, "ordering", "STREAM_THEN_SEQUENCE_NOT_GLOBAL_TIME") ||
         !text(o, "assessment_identity", "SHA256_JSON_C_COMPACT_MEMBER_ORDER") ||
         !dw_add(o, "derived_only", json_object_new_boolean(true)) ||
         !dw_add(o, "execution_authorized", json_object_new_boolean(false)) ||
         !dw_add(o, "acceptance_verified", json_object_new_boolean(false)) ||
         !dw_add(o, "work_specification", json_object_get(s->spec)) ||
         !dw_add(o, "assessments", json_object_get(assessments)) ||
         !dw_add(o, "documents", json_object_get(docs)) ||
         !dw_add(o, "status", json_object_get(status)) ||
         !dw_add(o, "journal", json_object_get(rows))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        phase = "record.output_budget";
        const char *encoded = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
        if (!encoded)
            st = GOLEM_ERR_OUT_OF_MEMORY;
        else if (strlen(encoded) > dw_uint(r, "byte_budget"))
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
        else
            st = ab_reply(o, out);
    }
    golem_agent_reply_free(&reply);
    as_close(&log);
    json_object_put(r);
    json_object_put(o);
    json_object_put(docs);
    json_object_put(assessments);
    json_object_put(rows);
    json_object_put(status);
    json_object_put(request);
    /* Preserve the session's more precise clock/storage diagnostic. */
    return !strcmp(phase, "record.status") && st != GOLEM_OK ? st : dw_report(d, st, phase);
}
