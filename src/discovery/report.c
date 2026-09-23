#include "internal.h"
#include <stdlib.h>
#include <stdio.h>
#include <inttypes.h>
#include <string.h>
typedef struct report {
    char *data;
    size_t size;
    bool overflow;
} report;
static void raw(report *r, const char *s)
{
    size_t n = strlen(s);
    if (n > GOLEM_DOCUMENT_MAX_BODY - r->size) {
        r->overflow = true;
        return;
    }
    memcpy(r->data + r->size, s, n);
    r->size += n;
}
/* All agent/source text remains inert prose, never raw Markdown directives. */
static void text(report *r, const char *s)
{
    for (; *s; ++s) {
        char c[2] = {*s, 0};
        if ((unsigned char)*s < 32 || *s == 127) {
            raw(r, " ");
            continue;
        }
        if (strchr("\\`*_[]<>#", *s))
            raw(r, "\\");
        raw(r, c);
    }
}
static void field(report *r, const char *label, struct json_object *o, const char *key)
{
    raw(r, label);
    text(r, dw_text(o, key));
    raw(r, "\n\n");
}
static void number(report *r, const char *label, struct json_object *o, const char *key)
{
    char n[32];
    (void)snprintf(n, sizeof(n), "%" PRIu64, dw_uint(o, key));
    raw(r, label);
    raw(r, n);
    raw(r, "\n\n");
}
golem_status golem_discovery_report(golem_bytes b, const char *kind, void *buffer, size_t capacity,
                                    size_t *required, golem_diagnostic *d)
{
    if (!kind || !required || (!buffer && capacity) ||
        (strcmp(kind, "discovery") != 0 && strcmp(kind, "research") != 0 &&
         strcmp(kind, "scope") != 0))
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *o = NULL;
    golem_discovery_result result;
    golem_status st = golem_json_parse(b, GOLEM_DOCUMENT_MAX_JSON, &o);
    if (st == GOLEM_OK)
        st = ds_validate(o, &result);
    report r = {NULL, 0, false};
    if (st == GOLEM_OK) {
        r.data = malloc(GOLEM_DOCUMENT_MAX_BODY);
        if (!r.data)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK) {
        raw(&r, "# Project ");
        text(&r, kind);
        raw(&r, "\n\n## Purpose\n\nRecorded exploration and scope assessment for Work ");
        text(&r, dw_text(o, "work_id"));
        raw(&r, ". Agent claims are not independent execution verification.\n\n## Scope\n\n");
        field(&r, "Non-goals: ", o, "non_goals");
        raw(&r, "## Parents\n\nThis draft has no registered parent bindings. Add exact parent "
                "links when registering a handoff.\n\n## Evidence\n\n");
        char digest[65];
        size_t n;
        (void)golem_digest_format(&result.snapshot_digest, digest, sizeof(digest), &n);
        raw(&r, "Allowlisted snapshot digest: ");
        raw(&r, digest);
        raw(&r, ". This is not a complete repository snapshot or authenticated attestation.\n\n");
        struct json_object *repos = dw_get(dw_get(o, "snapshot"), "repositories");
        for (size_t i = 0; i < json_object_array_length(repos); ++i) {
            struct json_object *v = json_object_array_get_idx(repos, i);
            field(&r, "Repository: ", v, "id");
            field(&r, "HEAD: ", v, "head");
            field(&r, "Declared toolchain: ", v, "toolchain");
            field(&r, "Declared tests: ", v, "test_configuration");
            struct json_object *files = dw_get(v, "files");
            for (size_t j = 0; j < json_object_array_length(files); ++j) {
                struct json_object *f = json_object_array_get_idx(files, j);
                field(&r, "Observed path: ", f, "path");
                field(&r, "Content digest: ", f, "digest");
                number(&r, "Bytes: ", f, "size");
                raw(&r, json_object_get_boolean(dw_get(f, "tracked")) ? "Tracked: true. "
                                                                      : "Tracked: false. ");
                raw(&r, json_object_get_boolean(dw_get(f, "dirty")) ? "Raw-byte dirty: true.\n\n"
                                                                    : "Raw-byte dirty: false.\n\n");
            }
        }
        raw(&r, "## Decisions\n\nSelection is a recorded proposal, not permission to execute.\n\n");
        field(&r, "Permission assessment: ", o, "permission");
        struct json_object *ss = dw_get(o, "selections");
        for (size_t i = 0; i < json_object_array_length(ss); ++i) {
            struct json_object *v = json_object_array_get_idx(ss, i);
            field(&r, "Candidate: ", v, "finding_id");
            field(&r, "Decision: ", v, "decision");
            field(&r, "Reason: ", v, "reason");
            field(&r, "Estimated size: ", v, "size");
            field(&r, "Acceptance criterion: ", v, "acceptance");
            raw(&r, json_object_get_boolean(dw_get(v, "needs_ux")) ? "UX requested: true. "
                                                                   : "UX requested: false. ");
            raw(&r, json_object_get_boolean(dw_get(v, "needs_publishing"))
                        ? "Publishing requested: true.\n\n"
                        : "Publishing requested: false.\n\n");
        }
        raw(&r, "## Requirements\n\nRequirements linked by this assessment:\n\n");
        const char *lists[] = {"questions", "findings"};
        for (size_t k = 0; k < 2; ++k) {
            struct json_object *a = dw_get(o, lists[k]);
            for (size_t i = 0; i < json_object_array_length(a); ++i)
                field(&r, "Requirement: ", json_object_array_get_idx(a, i), "requirement_id");
        }
        raw(&r,
            "## Work\n\nExploration observations are separated from proposed explanations.\n\n");
        struct json_object *fs = dw_get(o, "findings");
        for (size_t i = 0; i < json_object_array_length(fs); ++i) {
            struct json_object *f = json_object_array_get_idx(fs, i),
                               *p = dw_get(f, "reproduction");
            field(&r, "Finding: ", f, "id");
            field(&r, "Classification: ", f, "status");
            field(&r, "Location: ", f, "path");
            field(&r, "Observation: ", f, "observation");
            field(&r, "Hypothesis: ", f, "hypothesis");
            field(&r, "Uncertainty: ", f, "uncertainty");
            field(&r, "Recorded command (not executed here): ", p, "command");
            field(&r, "Expected: ", p, "expected");
            field(&r, "Actual: ", p, "actual");
            field(&r, "Reproduction classification: ", p, "result");
            field(&r, "Evidence digest: ", p, "evidence_digest");
        }
        raw(&r, "## Validation\n\nStructural relationships passed validation. Semantic acceptance "
                "and execution authority are not verified. Scope proposal ready: ");
        raw(&r, result.scope_ready ? "true.\n\n" : "false.\n\n");
        raw(&r, "## Risks\n\nSource applicability, declared reading scope and agent observations "
                "require review.\n\n");
        struct json_object *qs = dw_get(o, "questions");
        for (size_t i = 0; i < json_object_array_length(qs); ++i) {
            struct json_object *q = json_object_array_get_idx(qs, i);
            field(&r, "Question: ", q, "question");
            field(&r, "Research status: ", q, "status");
            field(&r, "Search protocol: ", q, "search_strategy");
            field(&r, "Conclusion: ", q, "conclusion");
            field(&r, "Eligibility criteria: ", q, "eligibility");
            number(&r, "Source budget: ", q, "source_budget");
            number(&r, "Time budget seconds: ", q, "seconds_budget");
            number(&r, "Declared elapsed seconds: ", q, "elapsed_seconds");
            field(&r, "Omissions and budget limits: ", q, "omissions");
        }
        raw(&r, strcmp(kind, "discovery") == 0  ? "## Observations\n\n"
                : strcmp(kind, "research") == 0 ? "## Sources\n\n"
                                                : "## Selection\n\n");
        raw(&r, "The structured sidecar retains all selection and evidence relationships. "
                "References do not independently prove local defects.\n\n");
        struct json_object *refs = dw_get(o, "references");
        if (!json_object_array_length(refs))
            raw(&r, "No references were recorded; research coverage is incomplete.\n\n");
        for (size_t i = 0; i < json_object_array_length(refs); ++i) {
            struct json_object *v = json_object_array_get_idx(refs, i);
            const char *keys[] = {
                "title",       "authors",         "url",      "version",     "published",
                "accessed",    "read_scope",      "locator",  "claim",       "applicability",
                "limitations", "counterevidence", "decision", "source_type", "decision_reason"};
            for (size_t k = 0; k < sizeof(keys) / sizeof(*keys); ++k) {
                raw(&r, keys[k]);
                field(&r, ": ", v, keys[k]);
            }
        }
        if (r.overflow)
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
        else {
            *required = r.size;
            if (capacity < r.size)
                st = GOLEM_ERR_BUFFER_TOO_SMALL;
            else
                memcpy(buffer, r.data, r.size);
        }
    }
    free(r.data);
    json_object_put(o);
    return dw_report(d, st, NULL);
}
