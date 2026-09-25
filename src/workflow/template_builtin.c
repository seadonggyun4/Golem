#include "template_internal.h"
#include "role_internal.h"
#include <string.h>

golem_status golem_workflow_template_builtin(const char *name, golem_execution_reply *out)
{
    if (!name || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    bool dev = !strcmp(name, "feature") || !strcmp(name, "bugfix");
    if (!dev && strcmp(name, "review") && strcmp(name, "research"))
        return GOLEM_ERR_NOT_FOUND;
    struct json_object *o = json_object_new_object(), *stages = json_object_new_array(),
                       *contract = json_object_new_object(), *rules = json_object_new_array(),
                       *budget = json_object_new_object();
    golem_status st = GOLEM_OK;
    const char *reason[] = {
        "Record scope, sources, assumptions and uncertainty before proceeding.",
        "The assessed scope requires user-experience evidence.",
        "The assessed scope requires publishing evidence.",
        dev ? "Plan and implement the scoped change with traceable evidence."
            : "Record recommendations only; this template grants no code execution.",
        dev ? (!strcmp(name, "bugfix")
                   ? "Execute reproduction and regression cases, preserving results."
                   : "Execute the approved QA contract and preserve results.")
            : "Document source checks, limitations and unresolved findings; do not claim code QA "
              "PASS.",
        "Review the exact current documents and evidence before completion."};
    for (size_t i = 0; st == GOLEM_OK && i < 6; ++i) {
        struct json_object *r = json_object_new_object();
        if (!ex_text(r, "stage", wf_stages[i]) ||
            !ex_text(r, "when",
                     i == 1   ? "SCOPE_UX"
                     : i == 2 ? "SCOPE_PUBLISHING"
                              : "ALWAYS") ||
            !ex_text(r, "reason", reason[i]) || !ex_text(r, "after", i ? wf_stages[i - 1] : "")) {
            json_object_put(r);
            st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (!wf_append(stages, r))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    const char *kinds[] = {"planning", "development-result", "qa-result", "completion"};
    for (size_t i = 0; st == GOLEM_OK && i < 4; ++i) {
        if (!dev && i == 1)
            continue;
        struct json_object *r = json_object_new_object();
        const char *role = i == 0   ? "researcher"
                           : i == 1 ? "implementer"
                           : i == 2 ? (dev ? "qa" : "doc-only")
                                    : "reviewer";
        const char *predicate = i == 0   ? "MARKDOWN"
                                : i == 1 ? "DEVELOPMENT"
                                : i == 2 ? (dev ? "QA_PASS" : "MARKDOWN")
                                         : "REVIEW";
        if (!ex_text(r, "role", role) ||
            !ex_text(r, "stage", wf_stages[wf_stage(wf_kind(kinds[i]))]) ||
            !ex_text(r, "kind", kinds[i]) || !ex_text(r, "predicate", predicate) ||
            !dw_add(r, "independent_review", json_object_new_boolean(false))) {
            json_object_put(r);
            st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (!wf_append(rules, r))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK &&
        (!ex_uint(contract, "schema_version", 1) || !ex_text(contract, "id", name) ||
         !ex_text(contract, "mode", dev ? "development" : "documents") ||
         !ex_text(contract, "allowed_effects", "NONE") ||
         !ex_uint(contract, "max_assessments", 16) ||
         !dw_add(contract, "rules", json_object_get(rules)) ||
         !ex_uint(budget, "context_bytes", 1048576) || !ex_uint(budget, "max_reentries", 4) ||
         !ex_uint(o, "schema_version", 1) || !ex_text(o, "id", name) || !ex_uint(o, "version", 1) ||
         !ex_text(o, "kind", name) || !ex_text(o, "mode", dev ? "development" : "documents") ||
         !dw_add(o, "stages", json_object_get(stages)) ||
         !dw_add(o, "role_contract", json_object_get(contract)) ||
         !dw_add(o, "budget", json_object_get(budget))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = wt_model(o);
    if (st == GOLEM_OK)
        st = ex_emit(o, out);
    json_object_put(o);
    json_object_put(stages);
    json_object_put(contract);
    json_object_put(rules);
    json_object_put(budget);
    return st;
}
