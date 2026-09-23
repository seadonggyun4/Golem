#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void prose(FILE *f, const char *s)
{
    for (const unsigned char *p = (const unsigned char *)s; *p; ++p) {
        if (*p < 32 || *p == 127)
            fputc(' ', f);
        else {
            if (*p < 128 && ispunct(*p))
                fputc('\\', f);
            fputc(*p, f);
        }
    }
}
golem_status co_markdown_v1(struct json_object *r, golem_execution_reply *out)
{
    char *data = NULL;
    size_t n = 0;
    FILE *f = open_memstream(&data, &n);
    if (!f)
        return GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *a = dw_get(r, "assessment");
    fprintf(f, "# Completion %llu\n\nWork: `%s`\n\nRecorded at Unix seconds: %llu\n\n",
            (unsigned long long)dw_uint(r, "sequence"), dw_text(a, "work_id"),
            (unsigned long long)dw_uint(r, "completed_at_unix_seconds"));
    fputs("## Goal\n\n", f);
    prose(f, dw_text(a, "goal"));
    fprintf(f,
            "\n\n## Engine Assessment\n\nDeclared development gates passed for this recorded "
            "snapshot.\n\nPolicy: `%s`\n\nEvidence root: `%s`\n\n",
            dw_text(a, "policy_digest"), dw_text(r, "evidence_root"));
    fputs("This is not a proof of bug absence. Independent review: **not established**.\n"
          "Authored documents and issue classifications remain agent statements.\n"
          "Current completion requires fresh validation; this report is historical evidence.\n\n## "
          "Documents\n\n",
          f);
    struct json_object *docs = dw_get(a, "documents");
    for (size_t i = 0; i < json_object_array_length(docs); ++i) {
        struct json_object *d = json_object_array_get_idx(docs, i);
        fprintf(f, "- [%s r%llu](../../documents/%s/r%04llu.md), `%s`\n", dw_text(d, "document_id"),
                (unsigned long long)dw_uint(d, "revision"), dw_text(d, "document_id"),
                (unsigned long long)dw_uint(d, "revision"), dw_text(d, "digest"));
    }
    fputs("\n## Selected Stages\n\n", f);
    struct json_object *decisions = dw_get(a, "stage_decisions");
    for (size_t i = 0; i < json_object_array_length(decisions); ++i) {
        struct json_object *d = json_object_array_get_idx(decisions, i);
        fprintf(f, "- %s: %s. ", wf_stages[i], dw_text(d, "status"));
        prose(f, dw_text(d, "reason"));
        fputc('\n', f);
    }
    fprintf(f, "\n## QA\n\nReceipt: `%s`\n\n| Gate | Version | Result |\n| --- | --- | --- |\n",
            dw_text(a, "qa_receipt"));
    struct json_object *gates = dw_get(a, "gates");
    for (size_t i = 0; i < json_object_array_length(gates); ++i) {
        struct json_object *g = json_object_array_get_idx(gates, i);
        fprintf(f, "| %s | %llu | %s |\n", dw_text(g, "gate_id"),
                (unsigned long long)dw_uint(g, "version"), dw_text(g, "status"));
    }
    struct json_object *outcomes = dw_get(a, "outcome_adjudications");
    if (outcomes) {
        fputs("\n### Outcome Adjudications\n\nDeclared observations satisfied their enrolled rules "
              "and this QA receipt.\n\n",
              f);
        for (size_t i = 0; i < json_object_array_length(outcomes); ++i) {
            struct json_object *v = json_object_array_get_idx(outcomes, i);
            fprintf(f, "- %s: policy `%s`, adjudication `%s`\n", dw_text(v, "case_id"),
                    dw_text(v, "policy_digest"), dw_text(v, "adjudication_digest"));
        }
    }
    fputs("\n### Declared Requirement Coverage\n\n| Requirement | Gate | Case | Result |\n| --- | "
          "--- | --- | --- |\n",
          f);
    struct json_object *definitions = dw_get(a, "gate_definitions");
    for (size_t i = 0; i < json_object_array_length(definitions); ++i) {
        struct json_object *def = json_object_array_get_idx(definitions, i),
                           *cases = dw_get(def, "cases");
        for (size_t j = 0; j < json_object_array_length(cases); ++j) {
            struct json_object *c = json_object_array_get_idx(cases, j);
            fprintf(f, "| %s | %s | %s | PASS |\n", dw_text(c, "requirement_id"),
                    dw_text(def, "id"), dw_text(c, "id"));
        }
    }
    fprintf(f, "\nDevelopment receipt: `%s`\n\nCheckpoint: `%s`\n",
            dw_text(a, "development_receipt"), dw_text(a, "checkpoint"));
    fputs("\n## Observed Source\n\n```json\n", f);
    fputs(json_object_to_json_string_ext(dw_get(a, "snapshot"), JSON_C_TO_STRING_PRETTY), f);
    fputs("\n```\n\n## Nonblocking Limitations (Agent Declared)\n\n", f);
    struct json_object *issues = dw_get(a, "unresolved_nonblocking_items");
    if (!json_object_array_length(issues))
        fputs("None declared; absence of undiscovered issues is not established.\n", f);
    for (size_t i = 0; i < json_object_array_length(issues); ++i) {
        struct json_object *v = json_object_array_get_idx(issues, i);
        fprintf(f, "- %s: ", dw_text(v, "id"));
        prose(f, dw_text(v, "description"));
        fprintf(f, " (evidence `%s`)\n", dw_text(v, "evidence_digest"));
    }
    fprintf(f,
            "\n## Recovery Boundary\n\nReentry decisions: %llu. Session sequence: %llu.\n\nNo "
            "unresolved recorded dispatch or active claim at issuance.\nNo external-effect "
            "exactly-once guarantee. Recovery never reruns commands.\n",
            (unsigned long long)dw_uint(a, "reentry_count"),
            (unsigned long long)dw_uint(dw_get(r, "boundary"), "session_sequence"));
    bool bad = ferror(f) != 0;
    if (fclose(f) != 0)
        bad = true;
    if (bad || n > GOLEM_DOCUMENT_MAX_BODY) {
        free(data);
        return bad ? GOLEM_ERR_IO : GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    *out = (golem_execution_reply){(uint8_t *)data, n};
    return GOLEM_OK;
}
