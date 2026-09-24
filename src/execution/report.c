#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* All external prose is escaped; no log text or executable Markdown is copied. */
static void escaped(FILE *f, const char *p)
{
    for (; *p; ++p) {
        unsigned char c = (unsigned char)*p;
        if (c == '&' || c == '<' || c == '>' || c == '|' || c == '`' || c == '*' || c == '_' ||
            c == '[' || c == ']' || c == '\\')
            fprintf(f, "&#%u;", (unsigned)c);
        else if (c < 32)
            fputc(' ', f);
        else
            fputc(c, f);
    }
}
static struct json_object *by_path(struct json_object *a, const char *path)
{
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *v = json_object_array_get_idx(a, i);
        if (strcmp(dw_text(v, "path"), path) == 0)
            return v;
    }
    return NULL;
}
static void delta(FILE *f, struct json_object *cp, struct json_object *r)
{
    fputs("\n**Changes**\n\nAllowlisted byte-level delta, not authorship or a complete repository "
          "diff.\n\n"
          "| Repository / path | Baseline dirty | Before SHA256 | After SHA256 | Changed since "
          "baseline |\n"
          "| --- | --- | --- | --- | --- |\n",
          f);
    struct json_object *before = dw_get(dw_get(cp, "baseline"), "repositories"),
                       *after = dw_get(dw_get(r, "snapshot"), "repositories");
    for (size_t i = 0; i < json_object_array_length(after); ++i) {
        struct json_object *repo = json_object_array_get_idx(after, i),
                           *base = json_object_array_get_idx(before, i),
                           *files = dw_get(repo, "files");
        for (size_t j = 0; j < json_object_array_length(files); ++j) {
            struct json_object *v = json_object_array_get_idx(files, j),
                               *old = by_path(dw_get(base, "files"), dw_text(v, "path"));
            fputs("| ", f);
            escaped(f, dw_text(repo, "id"));
            fputs(" / ", f);
            escaped(f, dw_text(v, "path"));
            fprintf(f, " | %s | %s | %s | %s |\n",
                    json_object_get_boolean(dw_get(old, "dirty")) ? "yes" : "no",
                    dw_text(old, "digest"), dw_text(v, "digest"),
                    strcmp(dw_text(old, "digest"), dw_text(v, "digest")) ? "yes" : "no");
        }
    }
}
golem_status ex_markdown(golem_document_store *s, struct json_object *m, golem_execution_reply *out)
{
    golem_digest key, checkpoint;
    struct json_object *r = NULL, *cp = NULL;
    if (dw_uint(m, "schema_version") != 5 || !dw_digest(m, "execution_receipt", &key))
        return GOLEM_ERR_PARSE;
    bool qa = strcmp(dw_text(m, "kind"), "qa-result") == 0;
    golem_status st = ex_load(s, &key, qa ? "qa" : "development", &r);
    if (st == GOLEM_OK && (!dw_digest(r, "checkpoint", &checkpoint) ||
                           !json_object_equal(dw_get(m, "input_manifest"), dw_get(r, "manifest"))))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK)
        st = ex_load(s, &checkpoint, "checkpoint", &cp);
    char *text = NULL;
    size_t size = 0;
    FILE *f = NULL;
    if (st == GOLEM_OK) {
        f = open_memstream(&text, &size);
        if (!f)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK) {
        fprintf(f,
                "# %s\n\n## Purpose\n\nEngine-observed %s report.\n\n## Scope\n\nWork: %s. Scope "
                "revision: 1.\n\n## Parents\n\n",
                qa ? "QA Result" : "Development Result", qa ? "gate execution" : "source delta",
                dw_text(m, "work_id"));
        struct json_object *parents = dw_get(m, "parents");
        for (size_t i = 0; i < json_object_array_length(parents); ++i) {
            struct json_object *p = json_object_array_get_idx(parents, i);
            fprintf(f, "- [Input %s](golem-doc:%s:%llu:%s)\n", dw_text(p, "document_id"),
                    dw_text(p, "document_id"), (unsigned long long)dw_uint(p, "revision"),
                    dw_text(p, "digest"));
        }
        fprintf(
            f,
            "\n## Evidence\n\nExecution receipt: `%s`. Checkpoint: `%s`.\n\n"
            "## Decisions\n\nNo semantic product acceptance is asserted. Source changes require "
            "new verification.\n\n## Requirements\n\nDeclared requirement coverage:\n\n",
            dw_text(m, "execution_receipt"), dw_text(r, "checkpoint"));
        struct json_object *req = dw_get(m, "requirement_ids");
        struct json_object *acceptance = dw_get(s->spec, "acceptance");
        for (size_t i = 0; i < json_object_array_length(req); ++i) {
            const char *id = json_object_get_string(json_object_array_get_idx(req, i));
            fprintf(f, "- %s: ", id);
            for (size_t j = 0; j < json_object_array_length(acceptance); ++j) {
                struct json_object *criterion = json_object_array_get_idx(acceptance, j);
                if (strcmp(id, dw_text(criterion, "id")) == 0)
                    escaped(f, dw_text(criterion, "criterion"));
            }
            fputc('\n', f);
        }
        fputs("\n## Work\n\nCurrent agent authored the implementation; this engine observes "
              "declared files and gates.\n",
              f);
        delta(f, cp, r);
        fprintf(f, "\n## Results\n\nStatus: **%s**.\n", qa ? dw_text(r, "status") : "OBSERVED");
        if (qa) {
            fprintf(f, "\nReason: %s. Attempt: %s.\n\n", dw_text(r, "reason"),
                    dw_text(r, "attempt_id"));
            struct json_object *gates = dw_get(r, "gates"),
                               *definitions = dw_get(dw_get(cp, "contract"), "gates");
            for (size_t i = 0; i < json_object_array_length(gates); ++i) {
                struct json_object *g = json_object_array_get_idx(gates, i),
                                   *def = json_object_array_get_idx(definitions, i),
                                   *cases = dw_get(def, "cases"), *actual = dw_get(g, "cases");
                fprintf(f,
                        "**Gate %s**\n\n%s: %s. Exit: %d. Signal: %llu. Observation: `%s`.\n\n"
                        "| Requirement | Case | Expected | Observed |\n| --- | --- | --- | --- |\n",
                        dw_text(g, "gate_id"), dw_text(g, "status"), dw_text(g, "reason"),
                        json_object_get_int(dw_get(g, "exit_code")),
                        (unsigned long long)dw_uint(g, "signal"), dw_text(g, "observation_digest"));
                for (size_t j = 0; j < json_object_array_length(cases); ++j) {
                    struct json_object *c = json_object_array_get_idx(cases, j),
                                       *a = json_object_array_get_idx(actual, j);
                    fprintf(f, "| %s | %s | PASS | %s |\n", dw_text(c, "requirement_id"),
                            dw_text(c, "id"), a ? dw_text(a, "status") : "UNKNOWN");
                }
                if (dw_uint(r, "schema_version") >= 2) {
                    struct json_object *logs = dw_get(g, "logs");
                    fprintf(f, "\nLog retention: %s. Duration: %llu ms.\n\n",
                        dw_text(g, "log_policy"), (unsigned long long)dw_uint(g, "duration_ms"));
                    for (size_t j = 0; j < json_object_array_length(logs); ++j) {
                        struct json_object *log = json_object_array_get_idx(logs, j);
                        fprintf(f, "- %s: %s; observed %llu bytes; retained %llu bytes; "
                            "EOF %s; redactor %s; receipt %s.\n",
                            dw_text(log, "stream"), dw_text(log, "state"),
                            (unsigned long long)dw_uint(log, "observed_bytes"),
                            (unsigned long long)dw_uint(log, "retained_bytes"),
                            json_object_get_boolean(dw_get(log, "eof")) ? "yes" : "no",
                            dw_text(log, "redactor"), *dw_text(log, "retained_receipt")
                                ? dw_text(log, "retained_receipt") : "unavailable");
                    }
                }
            }
        }
        if (qa && dw_uint(r, "schema_version") >= 2) {
            struct json_object *bundle = NULL;
            golem_digest digest;
            st = ex_bundle_build(s, &key, r, &bundle);
            if (st == GOLEM_OK)
                st = ex_hash(bundle, &digest);
            char hex[65];
            size_t required;
            if (st == GOLEM_OK)
                st = golem_digest_format(&digest, hex, sizeof(hex), &required);
            if (st == GOLEM_OK)
                fprintf(f, "\nVerification bundle: `%s`. Redacted captures are lossy and "
                    "private; log completeness does not establish acceptance.\n", hex);
            json_object_put(bundle);
        }
        fputs("\n## Validation\n\nFacts are generated from immutable receipts. PASS covers only "
              "the declared cases, not semantic completeness.\n\n"
              "## Risks\n\nAllowlisted, non-atomic filesystem observations are not a sandbox. Raw "
              "logs are discarded for confidentiality. "
              "Baseline dirty changes remain unattributed. Review deviations and failure "
              "hypotheses in a separate referenced document; do not edit this projection.\n",
              f);
        if (ferror(f))
            st = GOLEM_ERR_IO;
        if (fclose(f) != 0)
            st = GOLEM_ERR_IO;
        if (size > GOLEM_DOCUMENT_MAX_BODY)
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    if (st == GOLEM_OK)
        *out = (golem_execution_reply){(uint8_t *)text, size};
    else
        free(text);
    json_object_put(r);
    json_object_put(cp);
    return st;
}
golem_status ex_document(golem_document_store *s, struct json_object *meta, golem_bytes body)
{
    if (dw_uint(meta, "schema_version") != 5)
        return GOLEM_OK;
    golem_execution_reply expected = {0};
    golem_status st = ex_markdown(s, meta, &expected);
    if (st == GOLEM_OK &&
        (expected.size != body.size || memcmp(expected.data, body.data, body.size)))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    golem_execution_reply_free(&expected);
    return st;
}
golem_status golem_execution_render(golem_document_store *s, golem_bytes metadata,
                                    golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *m = NULL;
    golem_status st = dw_meta(metadata, &m);
    if (st == GOLEM_OK)
        st = ex_markdown(s, m, out);
    json_object_put(m);
    return dw_report(d, st, NULL);
}
