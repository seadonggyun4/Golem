#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include <stdio.h>
#include <stdlib.h>

golem_status golem_research_metrics_report(golem_document_store *s, const char *filter,
    golem_execution_reply *out, golem_diagnostic *d)
{
    if (!out) return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *o = NULL;
    golem_status st = rs_metrics(s, filter, &o);
    if (st != GOLEM_OK) return dw_report(d, st, NULL);
    char *data = NULL; size_t size = 0;
    FILE *f = open_memstream(&data, &size);
    if (!f) { json_object_put(o); return dw_report(d, GOLEM_ERR_OUT_OF_MEMORY, NULL); }
    /* All displayed names are fixed schema labels or validated ASCII IDs.
     * No authored hypothesis, raw status, observations or privacy prose leaks. */
    fprintf(f, "# Research Metrics\n\nWork: `%s`\n\nScope: %s `%s`\n\nRule: `%s`\n\n",
        dw_text(o, "work_id"), dw_text(o, "scope"), dw_text(o, "case_id"), dw_text(o, "rule"));
    fprintf(f, "Journal head: `%s`\n\nProjection: `%s`\n\n",
        dw_text(dw_get(o, "boundary"), "work_head"), dw_text(o, "projection_digest"));
    fputs("Historical replay only. Not current completion, causal effect, independent review or publication permission.\n\n"
          "## Recorded Counts\n\n| Measure | Count |\n| --- | ---: |\n", f);
    struct json_object *counts = dw_get(o, "counts");
    json_object_object_foreach(counts, key, value)
        fprintf(f, "| %s | %llu |\n", key, (unsigned long long)json_object_get_uint64(value));
    struct json_object *recovery = dw_get(o, "adjudication_recovery");
    fprintf(f, "\n## Adjudication Recovery\n\nRecovered episodes: %llu / %llu; open: %llu.\n\n",
        (unsigned long long)dw_uint(recovery, "rate_numerator"), (unsigned long long)dw_uint(recovery, "rate_denominator"),
        (unsigned long long)dw_uint(recovery, "open_episode_count"));
    fputs("Zero denominator means undefined, not 0% or 100%. This is a recorded not-eligible to eligible transition, not proof of product repair or crash recovery.\n\n"
          "## Cases\n\n| Case | Latest recorded state | Attempts | Adjudications |\n| --- | --- | ---: | ---: |\n", f);
    struct json_object *rows = dw_get(o, "cases");
    for (size_t i = 0; i < json_object_array_length(rows); ++i) {
        struct json_object *r = json_object_array_get_idx(rows, i);
        fprintf(f, "| %s | %s | %llu | %llu |\n", dw_text(r, "case_id"), dw_text(r, "state"),
            (unsigned long long)dw_uint(r, "attempt_count"), (unsigned long long)dw_uint(r, "adjudication_revision_count"));
    }
    fputs("\n## Measurement Availability\n\n", f);
    struct json_object *unknown = dw_get(o, "unavailable");
    json_object_object_foreach(unknown, name, entry)
        fprintf(f, "- %s: unmeasured (%s).\n", name, dw_text(entry, "reason"));
    fputs("\n## Reproducible Projection\n\n```json\n", f);
    const char *encoded = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PRETTY);
    if (encoded) fputs(encoded, f); else st = GOLEM_ERR_OUT_OF_MEMORY;
    fputs("\n```\n", f);
    bool bad = ferror(f) != 0;
    if (fclose(f) != 0) bad = true;
    if (bad) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && size > GOLEM_DOCUMENT_MAX_BODY) st = GOLEM_ERR_BUDGET_EXHAUSTED;
    if (st == GOLEM_OK) *out = (golem_execution_reply){(uint8_t *)data, size}; else free(data);
    json_object_put(o);
    return dw_report(d, st, NULL);
}
