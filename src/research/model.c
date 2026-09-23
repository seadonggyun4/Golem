#include "internal.h"
#include <string.h>

#define KEYS(o, a) dw_keys(o, a, sizeof(a) / sizeof(*(a)))
static bool text(struct json_object *o, const char *key, size_t limit)
{
    const char *s = dw_text(o, key);
    size_t n = strlen(s), meaningful = 0;
    if (!n || n > limit) return false;
    for (size_t i = 0; i < n; ++i) {
        unsigned char c = (unsigned char)s[i];
        if ((c < 32 && c != '\n' && c != '\t') || c == 127) return false;
        if (c > 32) ++meaningful;
    }
    return meaningful > 0;
}
static bool choice(struct json_object *o, const char *key, const char *const *values, size_t n)
{
    for (size_t i = 0; i < n; ++i) if (!strcmp(dw_text(o, key), values[i])) return true;
    return false;
}
#define CHOICE(o, key, a) choice(o, key, a, sizeof(a) / sizeof(*(a)))
static bool optional_digest(struct json_object *o, const char *key)
{
    golem_digest d;
    return json_object_is_type(dw_get(o, key), json_type_string) &&
        (!*dw_text(o, key) || dw_digest(o, key, &d));
}
static bool array(struct json_object *a, size_t minimum, size_t maximum)
{
    return json_object_is_type(a, json_type_array) && json_object_array_length(a) >= minimum &&
        json_object_array_length(a) <= maximum;
}
static bool refs(struct json_object *a)
{
    const char *keys[] = {"role", "digest"};
    const char *roles[] = {"DOCUMENT", "SOURCE", "CONTEXT", "TOOL", "CONFIG", "EVIDENCE"};
    if (!array(a, 1, GOLEM_RESEARCH_MAX_REFS)) return false;
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *v = json_object_array_get_idx(a, i); golem_digest d;
        if (!KEYS(v, keys) || !CHOICE(v, "role", roles) || !dw_digest(v, "digest", &d)) return false;
        for (size_t j = 0; j < i; ++j)
            if (json_object_equal(v, json_object_array_get_idx(a, j))) return false;
    }
    return true;
}
static bool observations(struct json_object *a)
{
    const char *keys[] = {"digest", "summary", "counts"}, *ck[] = {"name", "value"};
    if (!array(a, 0, GOLEM_RESEARCH_MAX_REFS)) return false;
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *v = json_object_array_get_idx(a, i), *counts = dw_get(v, "counts");
        golem_digest d;
        if (!KEYS(v, keys) || !dw_digest(v, "digest", &d) || !text(v, "summary", 2048) ||
            !array(counts, 0, 16)) return false;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(dw_text(v, "digest"), dw_text(json_object_array_get_idx(a, j), "digest"))) return false;
        for (size_t j = 0; j < json_object_array_length(counts); ++j) {
            struct json_object *c = json_object_array_get_idx(counts, j);
            if (!KEYS(c, ck) || !dw_id(dw_text(c, "name")) || dw_uint(c, "value") > INT64_MAX) return false;
            for (size_t k = 0; k < j; ++k)
                if (!strcmp(dw_text(c, "name"), dw_text(json_object_array_get_idx(counts, k), "name"))) return false;
        }
    }
    return true;
}
static golem_status case_model(struct json_object *o)
{
    const char *keys[] = {"schema_version", "case_id", "work_id", "project_id", "case_type",
        "research_questions", "unit_of_analysis", "context", "privacy_level", "pre_registered_plan_digest"};
    const char *types[] = {"REAL_SERVICE", "BENCHMARK_TASK", "FAULT_INJECTION", "REGRESSION_CANARY"};
    const char *privacy[] = {"PRIVATE", "REDACTED_EXPORTABLE", "PUBLIC_SYNTHETIC"};
    const char *context_keys[] = {"product", "environment", "tool", "runner", "constraints"};
    const char *qkeys[] = {"id", "question"};
    struct json_object *questions = dw_get(o, "research_questions"), *context = dw_get(o, "context");
    if (!KEYS(o, keys) || !dw_id(dw_text(o, "project_id")) || !CHOICE(o, "case_type", types) ||
        !CHOICE(o, "privacy_level", privacy) || !text(o, "unit_of_analysis", 2048) ||
        !optional_digest(o, "pre_registered_plan_digest") || !KEYS(context, context_keys) ||
        !array(questions, 1, 16)) return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < sizeof(context_keys) / sizeof(*context_keys); ++i)
        if (!text(context, context_keys[i], 2048)) return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < json_object_array_length(questions); ++i) {
        struct json_object *q = json_object_array_get_idx(questions, i);
        if (!KEYS(q, qkeys) || !dw_id(dw_text(q, "id")) || !text(q, "question", 2048)) return GOLEM_ERR_PARSE;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(dw_text(q, "id"), dw_text(json_object_array_get_idx(questions, j), "id"))) return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}
static golem_status attempt_model(struct json_object *o, bool plan)
{
    const char *keys[] = {"schema_version", "case_id", "work_id", "attempt_id", "case_digest",
        "previous_attempt_digest", "started_at", "actor_kind", "hypothesis", "intervention", "input_refs",
        "ended_at", "observations", "classification", "next_action", "decision_rule", "confidence", "plan_digest"};
    const char *actors[] = {"CURRENT_AGENT", "HUMAN_OPERATOR", "RUNTIME", "EXTERNAL_TOOL"};
    const char *classes[] = {"PRODUCT_PASS_OBSERVED", "PRODUCT_FAILURE_OBSERVED", "TEST_HARNESS_LIMITATION",
        "ENVIRONMENT_LIMITATION", "UNCERTAIN_EXTERNAL_EFFECT", "STALE_EVIDENCE_REJECTED",
        "FALSE_COMPLETION_PREVENTED", "DUPLICATE_EXECUTION_PREVENTED", "INSUFFICIENT_EVIDENCE", "OPERATOR_ABORTED"};
    const char *actions[] = {"CONTINUE", "REVISE_DOCUMENT", "RERUN_ALLOWED", "RECONCILE", "BLOCKED",
        "STOP_NOT_DONE", "FINALIZE_CANDIDATE"};
    const char *confidence[] = {"LOW", "MEDIUM", "HIGH"};
    golem_digest d;
    if (!dw_keys(o, keys, plan ? 11 : 18) || !dw_id(dw_text(o, "attempt_id")) ||
        !dw_digest(o, "case_digest", &d) || !optional_digest(o, "previous_attempt_digest") ||
        dw_uint(o, "started_at") > UINT64_C(253402300799999) || !CHOICE(o, "actor_kind", actors) ||
        !text(o, "hypothesis", 4096) || !text(o, "intervention", 4096) || !refs(dw_get(o, "input_refs")))
        return GOLEM_ERR_PARSE;
    if (plan) return GOLEM_OK;
    if (dw_uint(o, "ended_at") > UINT64_C(253402300799999) || dw_uint(o, "ended_at") < dw_uint(o, "started_at") ||
        !observations(dw_get(o, "observations")) || !CHOICE(o, "classification", classes) ||
        !CHOICE(o, "next_action", actions) || !dw_id(dw_text(o, "decision_rule")) ||
        !CHOICE(o, "confidence", confidence) || !optional_digest(o, "plan_digest")) return GOLEM_ERR_PARSE;
    const char *classification = dw_text(o, "classification"), *action = dw_text(o, "next_action");
    if (!strcmp(classification, "UNCERTAIN_EXTERNAL_EFFECT") &&
        strcmp(action, "RECONCILE") && strcmp(action, "BLOCKED") && strcmp(action, "STOP_NOT_DONE"))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    if (!strcmp(action, "FINALIZE_CANDIDATE") && strcmp(classification, "PRODUCT_PASS_OBSERVED"))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    if (!json_object_array_length(dw_get(o, "observations")) &&
        strcmp(classification, "INSUFFICIENT_EVIDENCE") && strcmp(classification, "OPERATOR_ABORTED"))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    return GOLEM_OK;
}
static golem_status outcome_model(struct json_object *o, bool enroll)
{
    const char *pk[] = {"schema_version", "work_id", "case_id", "case_digest", "selection_id",
        "gate_id", "adjudication_rule", "required_cases"};
    const char *ak[] = {"schema_version", "work_id", "case_id", "case_digest", "policy_digest",
        "qa_receipt", "supersedes", "raw_status", "observations", "open_blockers", "rationale"};
    golem_digest d;
    if (!dw_digest(o, "case_digest", &d)) return GOLEM_ERR_PARSE;
    struct json_object *items = dw_get(o, enroll ? "required_cases" : "observations");
    if (!array(items, enroll ? 1 : 0, 64)) return GOLEM_ERR_PARSE;
    if (enroll) {
        if (!KEYS(o, pk) || !dw_id(dw_text(o, "selection_id")) || !dw_id(dw_text(o, "gate_id")))
            return GOLEM_ERR_PARSE;
        if (strcmp(dw_text(o, "adjudication_rule"), "golem.required-cases.v1")) return GOLEM_ERR_UNSUPPORTED_VERSION;
    } else {
        if (!KEYS(o, ak) || !dw_digest(o, "policy_digest", &d) || !dw_digest(o, "qa_receipt", &d) ||
            !optional_digest(o, "supersedes") || !text(o, "raw_status", 256) || !text(o, "rationale", 4096) ||
            !array(dw_get(o, "open_blockers"), 0, 32)) return GOLEM_ERR_PARSE;
        struct json_object *blockers = dw_get(o, "open_blockers");
        for (size_t i = 0; i < json_object_array_length(blockers); ++i) {
            struct json_object *v = json_object_array_get_idx(blockers, i);
            if (!json_object_is_type(v, json_type_string) || !dw_id(json_object_get_string(v))) return GOLEM_ERR_PARSE;
            for (size_t j = 0; j < i; ++j)
                if (json_object_equal(v, json_object_array_get_idx(blockers, j))) return GOLEM_ERR_PARSE;
        }
    }
    for (size_t i = 0; i < json_object_array_length(items); ++i) {
        struct json_object *v = json_object_array_get_idx(items, i);
        const char *ck[] = {"id", "requirement_id"};
        const char *ok[] = {"id", "status", "failure_domain", "evidence_digest"};
        const char *statuses[] = {"PASS", "FAIL", "ERROR", "SKIPPED", "NOT_EXECUTED", "UNKNOWN"};
        const char *domains[] = {"NONE", "PRODUCT", "HARNESS", "ENVIRONMENT", "UNKNOWN"};
        if (!dw_id(dw_text(v, "id"))) return GOLEM_ERR_PARSE;
        if (enroll) {
            if (!KEYS(v, ck) || !dw_id(dw_text(v, "requirement_id"))) return GOLEM_ERR_PARSE;
        } else {
            if (!KEYS(v, ok) || !CHOICE(v, "status", statuses) || !CHOICE(v, "failure_domain", domains) ||
                !dw_digest(v, "evidence_digest", &d)) return GOLEM_ERR_PARSE;
            bool pass = !strcmp(dw_text(v, "status"), "PASS");
            if (pass != !strcmp(dw_text(v, "failure_domain"), "NONE")) return GOLEM_ERR_PARSE;
            if (!strcmp(dw_text(v, "failure_domain"), "PRODUCT") && strcmp(dw_text(v, "status"), "FAIL"))
                return GOLEM_ERR_PARSE;
        }
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(dw_text(v, "id"), dw_text(json_object_array_get_idx(items, j), "id"))) return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}
golem_status rs_validate(struct json_object *r)
{
    const char *keys[] = {"schema_version", "operation", "key", "record"};
    struct json_object *o = dw_get(r, "record");
    if (!KEYS(r, keys) || !dw_id(dw_text(r, "key")) ||
        !dw_id(dw_text(o, "work_id"))) return GOLEM_ERR_PARSE;
    if (dw_uint(r, "schema_version") != 1 || dw_uint(o, "schema_version") != 1) return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (rs_is_cohort(r)) return rs_cohort_model(r);
    if (!dw_id(dw_text(o, "case_id"))) return GOLEM_ERR_PARSE;
    const char *op = dw_text(r, "operation");
    if (!strcmp(op, "case-create")) return case_model(o);
    if (!strcmp(op, "attempt-plan")) return attempt_model(o, true);
    if (!strcmp(op, "attempt-record")) return attempt_model(o, false);
    if (rs_is_outcome(r)) return outcome_model(o, !strcmp(op, "outcome-enroll"));
    return GOLEM_ERR_PARSE;
}
golem_status golem_research_validate(golem_bytes b, golem_diagnostic *d)
{
    struct json_object *r = NULL;
    golem_status st = golem_json_parse(b, GOLEM_RESEARCH_MAX_JSON, &r);
    if (st == GOLEM_OK) st = rs_validate(r);
    json_object_put(r);
    return dw_report(d, st, st == GOLEM_OK ? "structural research validation; not adjudication" : NULL);
}
