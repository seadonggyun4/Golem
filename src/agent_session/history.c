#include "binding_internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static bool text(struct json_object *o, const char *k, const char *v)
{
    return dw_add(o, k, json_object_new_string(v));
}
static golem_status document_fields(golem_document_store *s, struct json_object *e,
                                    struct json_object *row)
{
    struct json_object *request = dw_get(e, "request");
    if (request && (!text(row, "action", dw_text(request, "operation")) ||
                    !text(row, "selection_id", dw_text(request, "selection_id"))))
        return GOLEM_ERR_OUT_OF_MEMORY;
    if (strcmp(dw_text(e, "type"), "document"))
        return GOLEM_OK;
    golem_digest digest;
    if (!dw_digest(e, "metadata_digest", &digest))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    struct json_object *meta = NULL;
    golem_status st = dw_cas_json(s, &digest, &meta);
    if (st == GOLEM_OK &&
        (!text(row, "document_id", dw_text(meta, "document_id")) ||
         !text(row, "kind", dw_text(meta, "kind")) ||
         !dw_add(row, "revision", json_object_new_uint64(dw_uint(meta, "revision"))) ||
         !text(row, "producer_attempt", dw_text(meta, "producer_attempt"))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(meta);
    return st;
}
/* Both streams have already been replayed under the store lock. Recheck frames
 * while projecting so a missing prefix never becomes an empty successful page. */
static golem_status project_stream(golem_document_store *s, int dir, const char *stream,
                                   const char *magic, size_t count, const golem_digest *head,
                                   uint64_t after, uint64_t limit, uint64_t *ordinal,
                                   struct json_object *rows)
{
    golem_digest previous = {{0}};
    struct json_object *state = NULL;
    golem_status result = GOLEM_OK;
    for (size_t i = 1; i <= count; ++i) {
        char name[32];
        (void)snprintf(name, sizeof(name), "%08u.evt", (unsigned)i);
        uint8_t *bytes = NULL;
        size_t n = 0;
        golem_status st = dw_read_at(dir, name, 80, &bytes, &n);
        golem_digest payload, frame;
        if (st == GOLEM_OK &&
            (n != 80 || memcmp(bytes, magic, 8) || memcmp(bytes + 16, previous.bytes, 32)))
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        uint64_t sequence = 0;
        if (st == GOLEM_OK) {
            for (unsigned j = 0; j < 8; ++j)
                sequence |= (uint64_t)bytes[8 + j] << (8 * j);
            if (sequence != i)
                st = GOLEM_ERR_MISSING_RECORD;
        }
        if (st == GOLEM_OK) {
            memcpy(payload.bytes, bytes + 48, 32);
            st = golem_digest_bytes((golem_bytes){bytes, n}, &frame);
        }
        free(bytes);
        struct json_object *e = NULL, *row = NULL;
        if (st == GOLEM_OK)
            st = dw_cas_json(s, &payload, &e);
        if (st == GOLEM_OK && *ordinal >= after && json_object_array_length(rows) < limit) {
            row = json_object_new_object();
            const char *operation =
                !strcmp(stream, "agent") ? dw_text(e, "operation") : dw_text(e, "type");
            if (!row || !text(row, "stream", stream) ||
                !dw_add(row, "sequence", json_object_new_uint64(i)) ||
                !dw_add_digest(row, "event_digest", &frame) ||
                !dw_add_digest(row, "payload_digest", &payload) ||
                !text(row, "operation", operation))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            struct json_object *data = dw_get(e, "data");
            if (st == GOLEM_OK && !strcmp(stream, "agent")) {
                struct json_object *token = dw_get(data, "token"),
                                   *binding = dw_get(data, "binding");
                if (!binding)
                    binding = dw_get(state, "binding");
                const char *attempt = dw_text(data, "attempt_id");
                if (!attempt[0])
                    attempt = dw_text(token, "attempt_id");
                if (!attempt[0])
                    attempt = dw_text(dw_get(state, "active"), "attempt_id");
                if (!text(row, "attempt_id", attempt) ||
                    !text(row, "session_id",
                          dw_get(data, "session_id") ? dw_text(data, "session_id")
                          : token                    ? dw_text(token, "session_id")
                                                     : dw_text(binding, "session_id")) ||
                    !dw_add(row, "epoch",
                            json_object_new_uint64(
                                !strcmp(operation, "bind") || !strcmp(operation, "resume") ? i
                                : dw_get(data, "epoch")  ? dw_uint(data, "epoch")
                                : dw_get(token, "epoch") ? dw_uint(token, "epoch")
                                                         : 0)) ||
                    !text(row, "binding_id",
                          binding ? dw_text(binding, "binding_id")
                                  : dw_text(data, "session_binding")) ||
                    !text(row, "runtime_binding",
                          dw_get(data, "runtime_binding")
                              ? dw_text(data, "runtime_binding")
                              : dw_text(dw_get(state, "active"), "runtime_binding")) ||
                    json_object_object_add(row, "output",
                                           json_object_get(dw_get(data, "output"))) != 0)
                    st = GOLEM_ERR_OUT_OF_MEMORY;
            }
            if (st == GOLEM_OK && !strcmp(stream, "document"))
                st = document_fields(s, e, row);
            if (st == GOLEM_OK && !wf_append(rows, row))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            else if (st != GOLEM_OK)
                json_object_put(row);
        }
        if (st == GOLEM_OK && !strcmp(stream, "agent")) {
            struct json_object *next = NULL;
            st = as_reduce(state, e, &next);
            json_object_put(state);
            state = next;
        }
        json_object_put(e);
        if (st != GOLEM_OK) {
            result = st;
            break;
        }
        previous = frame;
        ++*ordinal;
    }
    json_object_put(state);
    if (result != GOLEM_OK)
        return result;
    return dw_equal(&previous, head) ? GOLEM_OK : GOLEM_ERR_CORRUPT_JOURNAL;
}
golem_status golem_work_history(golem_document_store *s, golem_bytes bytes, golem_agent_reply *out,
                                golem_diagnostic *diagnostic)
{
    if (!s || !out || s->poisoned)
        return dw_report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *r = NULL, *response = NULL, *rows = NULL;
    as_log l = {.directory = -1};
    const char *keys[] = {"schema_version", "work_id",       "after",
                          "limit",          "document_head", "agent_head"};
    golem_status st = golem_json_parse(bytes, GOLEM_SESSION_BINDING_MAX_BYTES, &r);
    if (st == GOLEM_OK &&
        (!dw_keys(r, keys, 6) || dw_uint(r, "schema_version") != 1 ||
         !dw_id(dw_text(r, "work_id")) || !dw_uint(r, "limit") ||
         dw_uint(r, "limit") > GOLEM_HISTORY_PAGE_MAX || dw_uint(r, "after") == UINT64_MAX ||
         !json_object_is_type(dw_get(r, "document_head"), json_type_string) ||
         !json_object_is_type(dw_get(r, "agent_head"), json_type_string)))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK && strcmp(dw_text(r, "work_id"), dw_text(s->spec, "work_id")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        st = as_load(s, NULL, NULL, &l);
    uint64_t after = dw_uint(r, "after"), total = s->event_count + l.sequence;
    if (st == GOLEM_OK && after > total)
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK &&
        (after || dw_text(r, "document_head")[0] || dw_text(r, "agent_head")[0])) {
        golem_digest doc, agent;
        if (!dw_digest(r, "document_head", &doc) || !dw_digest(r, "agent_head", &agent) ||
            !dw_equal(&doc, &s->last) || !dw_equal(&agent, &l.last))
            st = GOLEM_ERR_STALE_RESULT;
    }
    uint64_t ordinal = 0;
    if (st == GOLEM_OK) {
        rows = json_object_new_array();
        response = json_object_new_object();
        if (!rows || !response)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        st = project_stream(s, s->events, "document", "GWDOC001", s->event_count, &s->last, after,
                            dw_uint(r, "limit"), &ordinal, rows);
    if (st == GOLEM_OK)
        st = project_stream(s, l.directory, "agent", "GWAGN001", (size_t)l.sequence, &l.last, after,
                            dw_uint(r, "limit"), &ordinal, rows);
    if (st == GOLEM_OK &&
        (!dw_add(response, "schema_version", json_object_new_int(1)) ||
         !text(response, "work_id", dw_text(s->spec, "work_id")) ||
         !text(response, "ordering", "STREAM_THEN_SEQUENCE_NOT_GLOBAL_TIME") ||
         !text(response, "agent_history", l.sequence ? "RECORDED" : "NOT_RECORDED") ||
         !dw_add(response, "source_prefix_verified", json_object_new_boolean(true)) ||
         !dw_add_digest(response, "document_head", &s->last) ||
         !dw_add_digest(response, "agent_head", &l.last) ||
         !dw_add(response, "total", json_object_new_uint64(total)) ||
         !dw_add(response, "next_after",
                 json_object_new_uint64(after + json_object_array_length(rows))) ||
         !dw_add(response, "has_more",
                 json_object_new_boolean(after + json_object_array_length(rows) < total)) ||
         !dw_add(response, "events", json_object_get(rows))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ab_reply(response, out);
    as_close(&l);
    json_object_put(r);
    json_object_put(rows);
    json_object_put(response);
    return dw_report(diagnostic, st, NULL);
}
