#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

golem_status golem_completion_report(golem_document_store *s, uint32_t seq, bool project,
                                     golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out || !seq || seq > s->completion_count || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (project && !s->writable)
        return dw_report(d, GOLEM_ERR_POLICY_DENIED, NULL);
    struct json_object *event = s->completions[seq - 1];
    golem_digest key;
    if (!dw_digest(event, "report_digest", &key))
        return dw_report(d, GOLEM_ERR_PARSE, NULL);
    uint8_t *bytes = NULL;
    size_t n = 0;
    golem_status st =
        golem_evidence_read(s->cas, &key, GOLEM_DOCUMENT_MAX_BODY, NULL, &bytes, &n, NULL);
    if (project) {
        struct json_object *docs =
            dw_get(dw_get(dw_get(event, "record"), "assessment"), "documents");
        for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(docs); ++i) {
            struct json_object *v = json_object_array_get_idx(docs, i);
            dw_entry *e = dw_find(s, dw_text(v, "document_id"), (uint32_t)dw_uint(v, "revision"));
            st = e ? dw_project(s, e, true) : GOLEM_ERR_MISSING_RECORD;
        }
        int top = -1, dir = -1;
        char name[32];
        (void)snprintf(name, sizeof(name), "r%04u", seq);
        if (st == GOLEM_OK)
            st = dw_dir(s->root, "completions", true, &top);
        if (st == GOLEM_OK)
            st = dw_dir(top, name, true, &dir);
        if (st == GOLEM_OK)
            st = dw_publish(dir, "completion.md", (golem_bytes){bytes, n});
        if (dir >= 0)
            close(dir);
        if (top >= 0)
            close(top);
    }
    if (st == GOLEM_OK)
        *out = (golem_execution_reply){bytes, n};
    else
        free(bytes);
    return dw_report(d, st, NULL);
}
