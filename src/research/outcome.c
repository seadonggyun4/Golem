#include "internal.h"
#include <string.h>

/* Enrollment is immutable. Assessments are derived from a bounded declaration
 * plus a runtime-issued QA receipt, never from a caller-supplied eligible flag. */
static struct json_object *record(golem_document_store *s, size_t i)
{ return dw_get(dw_get(s->research[i], "request"), "record"); }
static size_t latest(golem_document_store *s, const char *op, const char *id)
{
    for (size_t i = s->research_count; i > 0; --i)
        if (!strcmp(dw_text(dw_get(s->research[i-1], "request"), "operation"), op) &&
            !strcmp(dw_text(record(s, i-1), "case_id"), id)) return i-1;
    return SIZE_MAX;
}
static bool matches(struct json_object *o, const char *key, const golem_digest *d)
{ golem_digest actual; return dw_digest(o, key, &actual) && dw_equal(&actual, d); }
static struct json_object *by_id(struct json_object *a, const char *field, const char *id)
{
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *v = json_object_array_get_idx(a, i);
        if (!strcmp(dw_text(v, field), id)) return v;
    }
    return NULL;
}
bool rs_is_outcome(struct json_object *r)
{
    const char *op = dw_text(r, "operation");
    return !strcmp(op, "outcome-enroll") || !strcmp(op, "adjudicate");
}
golem_status rs_outcome_check(golem_document_store *s, struct json_object *r, struct json_object **out)
{
    struct json_object *o = dw_get(r, "record");
    const char *id = dw_text(o, "case_id");
    size_t p = latest(s, "outcome-enroll", id);
    if (!strcmp(dw_text(r, "operation"), "outcome-enroll")) {
        if (p != SIZE_MAX) return GOLEM_ERR_IDENTITY_MISMATCH;
        dw_entry *plan = dw_find(s, dw_text(o, "selection_id"), 0);
        if (!plan || dw_uint(plan->meta, "schema_version") != 3 ||
            strcmp(dw_text(dw_get(plan->meta, "selection"), "mode"), "development"))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        struct json_object *cases = dw_get(o, "required_cases"), *ids = dw_get(plan->meta, "requirement_ids");
        for (size_t i = 0; i < json_object_array_length(cases); ++i) {
            const char *req = dw_text(json_object_array_get_idx(cases, i), "requirement_id");
            bool found = false;
            for (size_t j = 0; j < json_object_array_length(ids); ++j)
                if (!strcmp(req, json_object_get_string(json_object_array_get_idx(ids, j)))) found = true;
            if (!found) return GOLEM_ERR_REQUIREMENTS_UNMET;
        }
        return GOLEM_OK;
    }
    if (p == SIZE_MAX) return GOLEM_ERR_NOT_FOUND;
    if (!matches(o, "policy_digest", &s->research_digests[p])) return GOLEM_ERR_IDENTITY_MISMATCH;
    size_t prev = latest(s, "adjudicate", id);
    if (prev == SIZE_MAX ? *dw_text(o, "supersedes") != '\0' :
        !matches(o, "supersedes", &s->research_digests[prev])) return GOLEM_ERR_STALE_RESULT;
    struct json_object *policy = record(s, p), *qa = NULL, *cp = NULL, *a = NULL;
    golem_digest q, c;
    if (!dw_digest(o, "qa_receipt", &q)) return GOLEM_ERR_PARSE;
    golem_status st = ex_load(s, &q, "qa", &qa);
    if (st == GOLEM_OK && !dw_digest(qa, "checkpoint", &c)) st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK) st = ex_load(s, &c, "checkpoint", &cp);
    if (st == GOLEM_OK && strcmp(dw_text(dw_get(cp, "contract"), "selection_id"),
        dw_text(policy, "selection_id"))) st = GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *gate = by_id(dw_get(qa, "gates"), "gate_id", dw_text(policy, "gate_id"));
    if (st == GOLEM_OK && !gate) st = GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *required = dw_get(policy, "required_cases"), *observed = dw_get(o, "observations");
    uint64_t pass = 0, fail = 0, error = 0, skipped = 0, missing = 0, unknown = 0;
    uint64_t product = 0, harness = 0, environment = 0;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(observed); ++i) {
        struct json_object *v = json_object_array_get_idx(observed, i); golem_digest d; uint64_t n;
        if (!by_id(required, "id", dw_text(v, "id"))) { st = GOLEM_ERR_REQUIREMENTS_UNMET; break; }
        if (!dw_digest(v, "evidence_digest", &d)) { st = GOLEM_ERR_PARSE; break; }
        st = golem_evidence_verify(s->cas, &d, &n, NULL);
    }
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(required); ++i) {
        struct json_object *v = by_id(observed, "id", dw_text(json_object_array_get_idx(required, i), "id"));
        const char *status = v ? dw_text(v, "status") : "NOT_EXECUTED", *domain = dw_text(v, "failure_domain");
        if (!strcmp(status, "PASS")) ++pass;
        else if (!strcmp(status, "FAIL")) ++fail;
        else if (!strcmp(status, "ERROR")) ++error;
        else if (!strcmp(status, "SKIPPED")) ++skipped;
        else if (!strcmp(status, "NOT_EXECUTED")) ++missing;
        else ++unknown;
        if (!strcmp(domain, "PRODUCT")) ++product;
        if (!strcmp(domain, "HARNESS")) ++harness;
        if (!strcmp(domain, "ENVIRONMENT")) ++environment;
    }
    bool native_pass = !strcmp(dw_text(qa, "status"), "PASS") && !strcmp(dw_text(gate, "status"), "PASS");
    bool eligible = native_pass && pass == json_object_array_length(required) &&
        json_object_array_length(dw_get(o, "open_blockers")) == 0;
    const char *status = fail ? "FAIL" : error ? "ERROR" : unknown ? "UNKNOWN" :
        missing ? "NOT_EXECUTED" : skipped ? "SKIPPED" : "PASS";
    if (st == GOLEM_OK) {
        a = json_object_new_object();
        if (!ex_uint(a, "schema_version", 1) || !ex_text(a, "rule", "golem.required-cases.v1") ||
            !ex_text(a, "source_kind", "DECLARED_OBSERVATIONS") || !ex_text(a, "normalized_status", status) ||
            !ex_text(a, "work_outcome", eligible ? "PASS" : "NOT_DONE") ||
            !dw_add(a, "completion_eligible", json_object_new_boolean(eligible)) ||
            !dw_add(a, "required_case_complete", json_object_new_boolean(pass + fail == json_object_array_length(required))) ||
            !dw_add(a, "native_qa_pass", json_object_new_boolean(native_pass)) ||
            !dw_add(a, "independent_review", json_object_new_boolean(false)) ||
            !dw_add_digest(a, "policy_digest", &s->research_digests[p]) || !dw_add_digest(a, "qa_receipt", &q) ||
            !ex_text(a, "selection_id", dw_text(policy, "selection_id")) ||
            !ex_uint(a, "pass_count", pass) || !ex_uint(a, "fail_count", fail) || !ex_uint(a, "error_count", error) ||
            !ex_uint(a, "skipped_count", skipped) || !ex_uint(a, "not_executed_count", missing) ||
            !ex_uint(a, "unknown_count", unknown) || !ex_uint(a, "product_failure_count", product) ||
            !ex_uint(a, "harness_failure_count", harness) || !ex_uint(a, "environment_failure_count", environment))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK && out) *out = a; else json_object_put(a);
    json_object_put(qa); json_object_put(cp);
    return st;
}
golem_status rs_outcome_completion(golem_document_store *s, const char *selection,
    const golem_digest *qa, struct json_object **out)
{
    struct json_object *items = json_object_new_array();
    golem_status st = items ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    /* All enrollments are Work obligations, not an optional selection filter. */
    for (size_t i = 0; st == GOLEM_OK && i < s->research_count; ++i) {
        if (strcmp(dw_text(dw_get(s->research[i], "request"), "operation"), "outcome-enroll")) continue;
        struct json_object *p = record(s, i);
        size_t j = latest(s, "adjudicate", dw_text(p, "case_id"));
        if (strcmp(dw_text(p, "selection_id"), selection) || j == SIZE_MAX) { st = GOLEM_ERR_REQUIREMENTS_UNMET; break; }
        struct json_object *a = dw_get(s->research[j], "assessment");
        if (!matches(a, "qa_receipt", qa) || !json_object_get_boolean(dw_get(a, "completion_eligible"))) {
            st = GOLEM_ERR_REQUIREMENTS_UNMET; break;
        }
        struct json_object *v = json_object_new_object();
        if (!dw_add_digest(v, "policy_digest", &s->research_digests[i]) ||
            !dw_add_digest(v, "adjudication_digest", &s->research_digests[j]) ||
            !ex_text(v, "case_id", dw_text(p, "case_id"))) { json_object_put(v); st = GOLEM_ERR_OUT_OF_MEMORY; }
        else if (json_object_array_add(items, v) != 0) { json_object_put(v); st = GOLEM_ERR_OUT_OF_MEMORY; }
    }
    if (st == GOLEM_OK) *out = items; else json_object_put(items);
    return st;
}
