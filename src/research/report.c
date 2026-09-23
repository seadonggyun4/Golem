#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Render nested authored data as escaped prose, never executable Markdown. */
static void prose(FILE *f, const char *text)
{
    for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
        if (*p < 32 || *p == 127) fputc(' ', f);
        else {
            if (*p < 128 && ispunct(*p)) fputc('\\', f);
            fputc(*p, f);
        }
    }
}
golem_status rs_markdown(struct json_object *event, golem_execution_reply *out)
{
    char *data = NULL; size_t n = 0;
    FILE *f = open_memstream(&data, &n);
    if (!f) return GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *request = dw_get(event, "request"), *record = dw_get(request, "record");
    fprintf(f, "# Research Record %llu\n\n", (unsigned long long)dw_uint(event, "sequence"));
    fputs(rs_is_outcome(request)
        ? "Private local projection. Rule-based adjudication of declared observations; not independent review, execution permission or completion.\n\n"
        : "Private local projection. Declared observations, not adjudication, execution permission or completion.\n\n", f);
    fputs("Operation: ", f); prose(f, dw_text(request, "operation")); fputs("\n\n", f);
    const char *op = dw_text(request, "operation");
    const char *mode = rs_is_cohort(request) ? "Fixed assignment or declared comparison observation; not causal inference or completion authority."
        : rs_is_outcome(request) ? "Enrollment is immutable; only the latest linked adjudication can satisfy completion."
        : !strcmp(op, "case-create") ? "Study context only; no observed outcome."
        : !strcmp(op, "attempt-plan") ? "Plan recorded without outcome; external timing is not attested."
        : *dw_text(record, "plan_digest") ? "Linked to an earlier recorded plan; external timing is not attested."
        : "No linked prior plan. This completed-attempt narrative is retrospective.";
    fputs(mode, f); fputs("\n\n", f);
    json_object_object_foreach(record, key, value) {
        fputs("## ", f); prose(f, key); fputs("\n\n", f);
        const char *text = json_object_is_type(value, json_type_string) ? json_object_get_string(value)
            : json_object_to_json_string_ext(value, JSON_C_TO_STRING_PLAIN);
        if (!text) { fclose(f); free(data); return GOLEM_ERR_OUT_OF_MEMORY; }
        prose(f, text); fputs("\n\n", f);
    }
    struct json_object *assessment = dw_get(event, "assessment");
    if (assessment) {
        fputs("## Derived Assessment\n\n", f);
        json_object_object_foreach(assessment, field, value) {
            prose(f, field); fputs(": ", f);
            const char *encoded = json_object_to_json_string_ext(value, JSON_C_TO_STRING_PLAIN);
            if (!encoded) { fclose(f); free(data); return GOLEM_ERR_OUT_OF_MEMORY; }
            prose(f, encoded); fputs("\n\n", f);
        }
    }
    bool bad = ferror(f) != 0;
    if (fclose(f) != 0) bad = true;
    if (bad || n > GOLEM_DOCUMENT_MAX_BODY) { free(data); return bad ? GOLEM_ERR_IO : GOLEM_ERR_BUDGET_EXHAUSTED; }
    *out = (golem_execution_reply){(uint8_t *)data, n};
    return GOLEM_OK;
}
