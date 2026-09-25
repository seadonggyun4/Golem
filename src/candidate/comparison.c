#include "internal.h"
#include <string.h>

static uint64_t sum(uint64_t a, uint64_t b, bool *overflow)
{
    if (b > UINT64_MAX - a) {
        *overflow = true;
        return UINT64_MAX;
    }
    return a + b;
}
/* Pure decision rule after evidence collection. No confidence, model identity,
 * test count or cheapest-route heuristic is a proxy for correctness. */
const char *cf_decision_v1(bool comparable, size_t passes)
{
    return !comparable   ? "INCOMPARABLE"
           : passes == 0 ? "NO_ELIGIBLE"
           : passes == 1 ? "SOLE_PASS"
                         : "TIE";
}
golem_status cf_report(cf_context *c, bool compare, struct json_object **out)
{
    struct json_object *report = json_object_new_object(), *rows = json_object_new_array();
    size_t count = json_object_array_length(dw_get(c->manifest, "candidates")), passes = 0,
           intents = 0, cancelled = 0;
    uint64_t cost = 0, tokens = 0;
    bool cost_known = true, tokens_known = true, comparable = compare, overflow = false,
         over_budget = false;
    const char *winner = "";
    golem_status st = GOLEM_OK;
    for (size_t i = 0; st == GOLEM_OK && i < count; ++i) {
        struct json_object *row = json_object_new_object(), *record = c->members[i];
        struct json_object *result = dw_get(record, "result"),
                           *resource = dw_get(cf_spec(c, i), "resources");
        const char *eligibility = "NOT_EVALUATED";
        if (json_object_get_boolean(dw_get(record, "dispatch_intent")))
            ++intents;
        bool ck = result && json_object_get_boolean(dw_get(result, "cost_known"));
        bool tk = result && json_object_get_boolean(dw_get(result, "tokens_known"));
        cost_known = cost_known && ck;
        tokens_known = tokens_known && tk;
        if (ck) {
            cost = sum(cost, dw_uint(result, "nano_cost"), &overflow);
            over_budget =
                over_budget || dw_uint(result, "nano_cost") > dw_uint(resource, "nano_cost");
        }
        if (tk) {
            tokens = sum(tokens, dw_uint(result, "tokens"), &overflow);
            over_budget = over_budget || dw_uint(result, "tokens") > dw_uint(resource, "tokens");
        }
        bool was_cancelled = result && json_object_get_boolean(dw_get(result, "cancelled"));
        if (was_cancelled)
            ++cancelled;
        golem_status observed = GOLEM_OK;
        if (compare) {
            golem_digest qa_key, gates, expected;
            golem_candidate_member member;
            struct json_object *qa = NULL;
            if (strcmp(cf_state(c, i), "FINISHED"))
                eligibility = "NOT_FINISHED";
            else if (was_cancelled)
                eligibility = "CANCELLED";
            else if (!dw_digest(result, "qa", &qa_key))
                eligibility = "MISSING_QA";
            else {
                observed = cf_member(c, i, &member);
                if (observed == GOLEM_OK)
                    observed = cf_qa(member.work, &qa_key, member.tree_root,
                                     dw_text(c->manifest, "base_commit"), &gates, &qa);
                if (observed == GOLEM_OK && (!dw_digest(c->manifest, "gates_digest", &expected) ||
                                             !dw_equal(&gates, &expected)))
                    observed = GOLEM_ERR_IDENTITY_MISMATCH;
                eligibility = observed == GOLEM_OK
                                  ? (!strcmp(dw_text(qa, "status"), "PASS")   ? "PASS"
                                     : !strcmp(dw_text(qa, "status"), "FAIL") ? "FAIL"
                                                                              : "QA_ERROR")
                                  : "INVALID_OR_STALE_QA";
            }
            if (strcmp(dw_text(cf_spec(c, 0), "environment_digest"),
                       dw_text(cf_spec(c, i), "environment_digest")))
                eligibility = "ENVIRONMENT_MISMATCH";
            if (!strcmp(eligibility, "PASS") && cf_review_check(c, i) != GOLEM_OK)
                eligibility = "MISSING_OR_STALE_REVIEW";
            if (!strcmp(eligibility, "PASS")) {
                ++passes;
                winner = dw_text(cf_spec(c, i), "id");
            } else if (strcmp(eligibility, "FAIL"))
                comparable = false;
            json_object_put(qa);
        }
        if (!ex_text(row, "candidate", dw_text(cf_spec(c, i), "id")) ||
            !ex_text(row, "state", cf_state(c, i)) || !ex_text(row, "eligibility", eligibility) ||
            !ex_uint(row, "verification_status", observed) ||
            !dw_add(row, "record", record ? json_object_get(record) : json_object_new_object()) ||
            !dw_add(row, "reservation_limit", json_object_get(resource)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) {
            if (!wf_append(rows, row))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        } else
            json_object_put(row);
    }
    struct json_object *limits = dw_get(c->manifest, "limits");
    over_budget = over_budget || overflow || cost > dw_uint(limits, "nano_cost") ||
                  tokens > dw_uint(limits, "tokens");
    comparable = comparable && cost_known && tokens_known && !over_budget;
    golem_digest manifest;
    if (st == GOLEM_OK)
        st = ex_hash(c->manifest, &manifest);
    if (st == GOLEM_OK &&
        (!ex_uint(report, "schema_version", 1) ||
         !ex_text(report, "type", "CandidateComparisonV1") ||
         !dw_add_digest(report, "manifest", &manifest) ||
         !dw_add_digest(report, "journal_head", &c->last) ||
         !ex_text(report, "decision", cf_decision_v1(comparable, passes)) ||
         !ex_text(report, "winner", comparable && passes == 1 ? winner : "") ||
         !ex_uint(report, "task_denominator", 1) ||
         !ex_uint(report, "candidate_denominator", count) ||
         !ex_uint(report, "dispatch_intent_denominator", intents) ||
         !ex_uint(report, "cancelled", cancelled) ||
         !ex_uint(report, "fresh_pass_candidates", passes) ||
         !ex_uint(report, "known_nano_cost", cost) || !ex_uint(report, "known_tokens", tokens) ||
         !dw_add(report, "cost_complete", json_object_new_boolean(cost_known)) ||
         !dw_add(report, "tokens_complete", json_object_new_boolean(tokens_known)) ||
         !dw_add(report, "over_budget", json_object_new_boolean(over_budget)) ||
         !ex_text(report, "sampling",
                  count > 1 ? "BEST_OF_N_NOT_SINGLE_RUN_SUCCESS_RATE" : "SINGLE_CANDIDATE") ||
         !dw_add(report, "wall_time_available", json_object_new_boolean(false)) ||
         !dw_add(report, "actual_cpu_available", json_object_new_boolean(false)) ||
         !dw_add(report, "merge_authorized", json_object_new_boolean(false)) ||
         !dw_add(report, "push_authorized", json_object_new_boolean(false)) ||
         !dw_add(report, "candidates", json_object_get(rows)) ||
         !dw_add(report, "selection",
                 c->selection ? json_object_get(c->selection) : json_object_new_object())))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(rows);
    if (st == GOLEM_OK)
        *out = report;
    else
        json_object_put(report);
    return st;
}

golem_status cf_target(cf_context *c, size_t i, struct json_object **out)
{
    if (!c->selection || dw_uint(c->selection, "candidate") != i)
        return GOLEM_ERR_APPROVAL_REQUIRED;
    struct json_object *report = NULL, *qa = NULL, *selected_qa = NULL;
    golem_status st = cf_report(c, true, &report);
    if (st == GOLEM_OK &&
        (!strcmp(dw_text(report, "decision"), "INCOMPARABLE") ||
         strcmp(dw_text(json_object_array_get_idx(dw_get(report, "candidates"), i), "eligibility"),
                "PASS")))
        st = GOLEM_ERR_STALE_RESULT;
    golem_candidate_member target = {0};
    if (st == GOLEM_OK)
        st = c->host->resolve(c->host->context, "$target", &target);
    if (st == GOLEM_OK && (!target.work || !target.tree_root))
        st = GOLEM_ERR_INVALID_ARGUMENT;
    for (size_t j = 0;
         st == GOLEM_OK && j < json_object_array_length(dw_get(c->manifest, "candidates")); ++j)
        if (!strcmp(dw_text(target.work->spec, "work_id"), dw_text(cf_spec(c, j), "work_id")))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
    golem_digest key, gates, expected, environment;
    if (st == GOLEM_OK && (!dw_digest(c->request, "qa", &key) ||
                           !dw_digest(cf_spec(c, i), "environment_digest", &environment) ||
                           !dw_equal(&environment, &target.environment)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        st = cf_qa(target.work, &key, target.tree_root, dw_text(c->manifest, "base_commit"), &gates,
                   &qa);
    if (st == GOLEM_OK && (!dw_digest(c->manifest, "gates_digest", &expected) ||
                           !dw_equal(&gates, &expected) || strcmp(dw_text(qa, "status"), "PASS")))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    golem_candidate_member selected;
    golem_digest selected_key, patch;
    if (st == GOLEM_OK && !dw_digest(dw_get(c->members[i], "result"), "qa", &selected_key))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK)
        st = cf_member(c, i, &selected);
    if (st == GOLEM_OK)
        st = cf_qa(selected.work, &selected_key, selected.tree_root,
                   dw_text(c->manifest, "base_commit"), &gates, &selected_qa);
    if (st == GOLEM_OK &&
        (!dw_equal(&gates, &expected) || strcmp(dw_text(selected_qa, "status"), "PASS")))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK)
        st = cf_patch_identity(selected.work, selected_qa, target.work, qa, &patch);
    if (st == GOLEM_OK && dw_get(c->members[i], "diff") &&
        strcmp(dw_text(c->request, "operation"), "review") &&
        strcmp(dw_text(dw_get(c->members[i], "review"), "qa"), dw_text(c->request, "qa")))
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    struct json_object *result = json_object_new_object();
    if (st == GOLEM_OK &&
        (!dw_add_digest(result, "target_qa", &key) ||
         !dw_add(result, "target_qa_passed", json_object_new_boolean(true)) ||
         !dw_add_digest(result, "selected_qa", &selected_key) ||
         !dw_add_digest(result, "scoped_patch_identity", &patch) ||
         !ex_text(result, "patch_scope", "EXACT_POLICY_SCOPED_HEAD_INDEX_WORKTREE_V1") ||
         !dw_add(result, "selected_patch_verified", json_object_new_boolean(true)) ||
         !dw_add(result, "merge_authorized", json_object_new_boolean(false)) ||
         !dw_add(result, "push_authorized", json_object_new_boolean(false))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(report);
    json_object_put(qa);
    json_object_put(selected_qa);
    if (st == GOLEM_OK)
        *out = result;
    else
        json_object_put(result);
    return st;
}
