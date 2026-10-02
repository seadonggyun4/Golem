#include "binding_internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* The caller has replayed both full streams under the Work lock. A historical
 * frame hash therefore pins a verified prefix, not merely an unchecked offset. */
static golem_status prefix(int directory, uint64_t sequence, golem_digest *out)
{
    if (!sequence) {
        *out = (golem_digest){{0}};
        return GOLEM_OK;
    }
    char name[32];
    (void)snprintf(name, sizeof(name), "%08u.evt", (unsigned)sequence);
    uint8_t *bytes = NULL;
    size_t size = 0;
    golem_status st = dw_read_at(directory, name, 80, &bytes, &size);
    if (st == GOLEM_OK)
        st = size == 80 ? golem_digest_bytes((golem_bytes){bytes, size}, out)
                        : GOLEM_ERR_CORRUPT_JOURNAL;
    free(bytes);
    return st;
}

static bool text(struct json_object *o, const char *k, const char *v)
{
    return dw_add(o, k, json_object_new_string(v));
}

golem_status ab_history_incremental(golem_document_store *s, struct json_object *r,
                                    golem_agent_reply *out, golem_diagnostic *d)
{
    const char *keys[] = {"schema_version", "work_id", "limit", "cursor"};
    if (!dw_keys(r, keys, 4) || !dw_id(dw_text(r, "work_id")) ||
        !dw_uint(r, "limit") || dw_uint(r, "limit") > GOLEM_HISTORY_PAGE_MAX)
        return dw_report(d, GOLEM_ERR_PARSE, "history.request");
    if (strcmp(dw_text(r, "work_id"), dw_text(s->spec, "work_id")))
        return dw_report(d, GOLEM_ERR_IDENTITY_MISMATCH, "history.work_identity");
    as_log log = {.directory = -1};
    golem_status st = as_load(s, NULL, NULL, &log);
    golem_digest anchor;
    if (st == GOLEM_OK)
        st = prefix(s->events, 1, &anchor);
    struct json_object *c = dw_get(r, "cursor");
    const char *fallback = c ? "CURSOR_INVALID" : "BASELINE_REQUIRED";
    const char *ck[] = {"schema_version", "work_id", "work_anchor", "document_sequence",
                       "document_head", "agent_sequence", "agent_head"};
    uint64_t after[2] = {0, 0}, totals[2] = {s->event_count, log.sequence};
    int directories[2] = {s->events, log.directory};
    const char *seqs[2] = {"document_sequence", "agent_sequence"};
    const char *heads[2] = {"document_head", "agent_head"};
    if (st == GOLEM_OK && dw_keys(c, ck, 7) && dw_uint(c, "schema_version") == 1 &&
        dw_uint(c, seqs[0]) != UINT64_MAX && dw_uint(c, seqs[1]) != UINT64_MAX) {
        golem_digest expected;
        fallback = "PREFIX_MISMATCH";
        bool valid = !strcmp(dw_text(c, "work_id"), dw_text(s->spec, "work_id")) &&
                     dw_digest(c, "work_anchor", &expected) && dw_equal(&expected, &anchor);
        for (size_t i = 0; valid && i < 2; ++i) {
            uint64_t n = dw_uint(c, seqs[i]);
            golem_digest actual;
            valid = n <= totals[i] && dw_digest(c, heads[i], &expected);
            if (valid) {
                st = prefix(directories[i], n, &actual);
                valid = st == GOLEM_OK && dw_equal(&actual, &expected);
            }
        }
        if (valid) {
            fallback = NULL;
            after[0] = dw_uint(c, seqs[0]);
            after[1] = dw_uint(c, seqs[1]);
        }
    }
    struct json_object *rows = json_object_new_array(), *response = json_object_new_object(),
                       *next = json_object_new_object();
    if (st == GOLEM_OK && (!rows || !response || !next))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    uint64_t ordinal = 0, limit = dw_uint(r, "limit");
    if (st == GOLEM_OK)
        st = ab_project_stream(s, s->events, "document", "GWDOC001", s->event_count, &s->last,
                                after[0], limit, &ordinal, rows);
    size_t doc_rows = rows ? json_object_array_length(rows) : 0;
    ordinal = 0;
    if (st == GOLEM_OK)
        st = ab_project_stream(s, log.directory, "agent", "GWAGN001", (size_t)log.sequence,
                                &log.last, after[1], doc_rows + limit, &ordinal, rows);
    uint64_t positions[2] = {after[0] + doc_rows,
                            after[1] + (rows ? json_object_array_length(rows) : 0) - doc_rows};
    for (size_t i = 0; st == GOLEM_OK && i < 2; ++i) {
        golem_digest hash;
        st = prefix(directories[i], positions[i], &hash);
        if (st == GOLEM_OK && (!dw_add(next, seqs[i], json_object_new_uint64(positions[i])) ||
                               !dw_add_digest(next, heads[i], &hash)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK &&
        (!dw_add(next, "schema_version", json_object_new_int(1)) ||
         !text(next, "work_id", dw_text(s->spec, "work_id")) ||
         !dw_add_digest(next, "work_anchor", &anchor) ||
         !dw_add(response, "schema_version", json_object_new_int(2)) ||
         !text(response, "work_id", dw_text(s->spec, "work_id")) ||
         !text(response, "mode", fallback ? "FULL" : "DELTA") ||
         !text(response, "fallback", fallback ? fallback : "") ||
         !text(response, "ordering", "PER_STREAM_SEQUENCE_NOT_GLOBAL_TIME") ||
         !dw_add(response, "source_prefix_verified", json_object_new_boolean(true)) ||
         !dw_add(response, "execution_authorized", json_object_new_boolean(false)) ||
         !dw_add(response, "acceptance_verified", json_object_new_boolean(false)) ||
         !dw_add_digest(response, "document_head", &s->last) ||
         !dw_add_digest(response, "agent_head", &log.last) ||
         !dw_add(response, "document_total", json_object_new_uint64(totals[0])) ||
         !dw_add(response, "agent_total", json_object_new_uint64(totals[1])) ||
         !dw_add(response, "has_more", json_object_new_boolean(
             positions[0] < totals[0] || positions[1] < totals[1])) ||
         !dw_add(response, "cursor", json_object_get(next)) ||
         !dw_add(response, "events", json_object_get(rows))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ab_reply(response, out);
    as_close(&log);
    json_object_put(rows);
    json_object_put(response);
    json_object_put(next);
    return dw_report(d, st, st == GOLEM_OK ? NULL : "history.incremental_source");
}
