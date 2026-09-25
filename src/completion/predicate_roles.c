#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include "../workflow/role_internal.h"
#include "../reentry/internal.h"
#include "../research/internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

golem_status rc_completion(golem_document_store *s, struct json_object *r, bool live,
                           struct json_object **out)
{
    golem_status validated = co_validate(r);
    if (validated != GOLEM_OK || strcmp(dw_text(r, "operation"), "finalize"))
        return validated != GOLEM_OK ? validated : GOLEM_ERR_PARSE;
    struct json_object *enrolled = rc_enrollment(s, dw_text(r, "selection_id")),
                       *last = rc_latest(s, dw_text(r, "selection_id"));
    if (!enrolled || !last || dw_uint(r, "schema_version") != 2 ||
        dw_uint(r, "expected_generation") != s->count + 1)
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *roles = NULL, *a = NULL, *legacy = NULL;
    golem_status st = rc_assess(s, dw_get(last, "request"), live, NULL, &roles);
    if (st == GOLEM_OK && (strcmp(dw_text(roles, "state"), "SATISFIED") ||
                           !json_object_equal(roles, dw_get(last, "assessment"))))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    bool development =
        !strcmp(dw_text(dw_get(dw_get(enrolled, "request"), "contract"), "mode"), "development");
    if (st == GOLEM_OK && development) {
        if (json_object_deep_copy(r, &legacy, NULL) || !ex_uint(legacy, "schema_version", 1))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK)
            st = co_evaluate_v1(s, legacy, live, &a);
    } else if (st == GOLEM_OK) {
        const char *action = NULL, *kind = NULL, *reason = NULL;
        st = re_next(s, &action, &kind, &reason);
        if (st == GOLEM_OK && action)
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
        struct json_object *docs = NULL, *outcomes = NULL;
        const golem_digest no_qa = {{0}};
        /* A documents-mode selection must not bypass a Work-level enrolled
         * research/QA obligation from another selection or an older revision. */
        if (st == GOLEM_OK)
            st = rs_outcome_completion(s, dw_text(r, "selection_id"), &no_qa, &outcomes);
        if (st == GOLEM_OK)
            st = wf_completed_documents(s, dw_text(r, "selection_id"), &docs);
        /* Document-only completion does not claim tests or code execution. */
        if (st == GOLEM_OK && json_object_array_length(dw_get(r, "issues")))
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
        a = json_object_new_object();
        if (st == GOLEM_OK &&
            (!a || !ex_text(a, "work_id", dw_text(s->spec, "work_id")) ||
             !ex_uint(a, "generation", s->count + 1) ||
             !dw_add(a, "documents", json_object_get(docs)) ||
             !ex_text(a, "assurance", "DOCUMENT_CONTRACT_ONLY_NO_EXECUTION_CLAIM") ||
             !dw_add(a, "independent_review", json_object_new_boolean(false))))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(docs);
        json_object_put(outcomes);
    }
    struct json_object *policy = json_object_new_object();
    golem_digest digest, receipt;
    if (st == GOLEM_OK)
        st = ex_hash(last, &receipt);
    if (st == GOLEM_OK &&
        (!policy || !ex_uint(policy, "schema_version", 1) ||
         !ex_text(policy, "predicate", RC_PREDICATE) ||
         !dw_add(policy, "contract_digest", json_object_get(dw_get(roles, "contract_digest"))) ||
         !dw_add(policy, "work_acceptance", json_object_get(dw_get(s->spec, "acceptance")))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ex_hash(policy, &digest);
    if (st == GOLEM_OK && (!dw_add(a, "policy", json_object_get(policy)) ||
                           !dw_add_digest(a, "policy_digest", &digest) ||
                           !dw_add(a, "deliverables", json_object_get(roles)) ||
                           !dw_add_digest(a, "deliverable_receipt", &receipt)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        *out = a;
    else
        json_object_put(a);
    json_object_put(roles);
    json_object_put(policy);
    json_object_put(legacy);
    return st;
}

golem_status rc_markdown(struct json_object *record, golem_execution_reply *out)
{
    /* Separate versioned renderer: historical v1 bytes never change. JSON is
     * indented code, not executable Markdown supplied by an agent. */
    const char *json = json_object_to_json_string_ext(record, JSON_C_TO_STRING_PRETTY);
    if (!json)
        return GOLEM_ERR_OUT_OF_MEMORY;
    char *data = NULL;
    size_t size = 0;
    FILE *f = open_memstream(&data, &size);
    if (!f)
        return GOLEM_ERR_IO;
    fputs("# Role-contract completion\n\nDeclared contracts satisfied at issuance.\n"
          "Independent review is not established. No claim of bug absence.\n"
          "Live completion requires fresh revalidation.\n\n",
          f);
    /* Prefix every line so content cannot terminate a fenced code block. */
    fputs("    ", f);
    for (const char *p = json; *p; ++p) {
        fputc(*p, f);
        if (*p == '\n')
            fputs("    ", f);
    }
    fputc('\n', f);
    bool failed = ferror(f) != 0;
    if (fclose(f))
        failed = true;
    if (failed || size > GOLEM_DOCUMENT_MAX_BODY) {
        free(data);
        return failed ? GOLEM_ERR_IO : GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    *out = (golem_execution_reply){(uint8_t *)data, size};
    return GOLEM_OK;
}
