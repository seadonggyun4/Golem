#include "internal.h"
#include <string.h>

#define KEYS(o, k) dw_keys(o, k, sizeof(k)/sizeof(*(k)))
static const char *const arms[] = {"NON_USE", "PARTIAL_USE", "FULL_USE"};
static const char *const contracts[] = {"protocol_digest", "task_digest", "acceptance_digest",
    "environment_digest", "evaluation_digest"};
static int arm(struct json_object *o, const char *key)
{
    for (int i = 0; i < 3; ++i) if (!strcmp(dw_text(o, key), arms[i])) return i;
    return -1;
}
bool rs_is_cohort(struct json_object *r)
{
    const char *op = dw_text(r, "operation");
    return !strcmp(op, "cohort-create") || !strcmp(op, "cohort-observe");
}
static struct json_object *request(golem_document_store *s, size_t i)
{ return dw_get(s->research[i], "request"); }
static struct json_object *record(golem_document_store *s, size_t i)
{ return dw_get(request(s, i), "record"); }
static struct json_object *member(struct json_object *o, const char *id)
{
    struct json_object *a = dw_get(o, "members");
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *v = json_object_array_get_idx(a, i);
        if (!strcmp(dw_text(v, "case_id"), id)) return v;
    }
    return NULL;
}
golem_status rs_cohort_model(struct json_object *r)
{
    struct json_object *o = dw_get(r, "record"); golem_digest d;
    if (!dw_id(dw_text(o, "cohort_id"))) return GOLEM_ERR_PARSE;
    if (!strcmp(dw_text(r, "operation"), "cohort-create")) {
        const char *keys[] = {"schema_version", "work_id", "cohort_id", "design", "protocol_digest",
            "task_digest", "acceptance_digest", "environment_digest", "evaluation_digest", "members"};
        const char *mk[] = {"case_id", "case_digest", "arm", "block_id"};
        struct json_object *a = dw_get(o, "members");
        bool matched = !strcmp(dw_text(o, "design"), "MATCHED_BLOCKS");
        if (!KEYS(o, keys) || (!matched && strcmp(dw_text(o, "design"), "OBSERVATIONAL")) ||
            !json_object_is_type(a, json_type_array) || json_object_array_length(a) < 3 ||
            json_object_array_length(a) > 48) return GOLEM_ERR_PARSE;
        for (size_t i = 0; i < sizeof(contracts)/sizeof(*contracts); ++i)
            if (!dw_digest(o, contracts[i], &d)) return GOLEM_ERR_PARSE;
        unsigned seen = 0;
        for (size_t i = 0; i < json_object_array_length(a); ++i) {
            struct json_object *v = json_object_array_get_idx(a, i);
            int group = arm(v, "arm");
            if (!KEYS(v, mk) || !dw_id(dw_text(v, "case_id")) || !dw_id(dw_text(v, "block_id")) ||
                !dw_digest(v, "case_digest", &d) || group < 0) return GOLEM_ERR_PARSE;
            seen |= 1u << (unsigned)group;
            unsigned block = 0;
            for (size_t j = 0; j < json_object_array_length(a); ++j) {
                struct json_object *other = json_object_array_get_idx(a, j);
                if (j != i && !strcmp(dw_text(v, "case_id"), dw_text(other, "case_id"))) return GOLEM_ERR_PARSE;
                if (matched && !strcmp(dw_text(v, "block_id"), dw_text(other, "block_id"))) {
                    int g = arm(other, "arm");
                    if (g < 0 || (block & (1u << (unsigned)g))) return GOLEM_ERR_PARSE;
                    block |= 1u << (unsigned)g;
                }
            }
            if (matched && block != 7) return GOLEM_ERR_REQUIREMENTS_UNMET;
        }
        return seen == 7 ? GOLEM_OK : GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    const char *keys[] = {"schema_version", "work_id", "cohort_id", "cohort_digest", "case_id",
        "supersedes", "status", "observed_arm", "environment_digest", "evidence_digest", "leakage"};
    const char *statuses[] = {"PASS", "FAIL", "SKIPPED", "NOT_DONE", "UNKNOWN"};
    if (!KEYS(o, keys) || !dw_id(dw_text(o, "case_id")) || !dw_digest(o, "cohort_digest", &d) ||
        !dw_digest(o, "environment_digest", &d) || !dw_digest(o, "evidence_digest", &d) ||
        arm(o, "observed_arm") < 0 || !json_object_is_type(dw_get(o, "leakage"), json_type_boolean) ||
        !json_object_is_type(dw_get(o, "supersedes"), json_type_string) ||
        (*dw_text(o, "supersedes") && !dw_digest(o, "supersedes", &d))) return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < sizeof(statuses)/sizeof(*statuses); ++i)
        if (!strcmp(dw_text(o, "status"), statuses[i])) return GOLEM_OK;
    return GOLEM_ERR_PARSE;
}
static bool match(struct json_object *o, const char *key, const golem_digest *d)
{ golem_digest actual; return dw_digest(o, key, &actual) && dw_equal(&actual, d); }
static golem_status verify(golem_document_store *s, struct json_object *o, const char *key)
{
    golem_digest d; uint64_t size;
    if (!dw_digest(o, key, &d)) return GOLEM_ERR_PARSE;
    return golem_evidence_verify(s->cas, &d, &size, NULL);
}
golem_status rs_cohort_check(golem_document_store *s, struct json_object *r)
{
    struct json_object *o = dw_get(r, "record");
    bool create = !strcmp(dw_text(r, "operation"), "cohort-create");
    size_t cohort = SIZE_MAX, last = SIZE_MAX;
    for (size_t i = 0; i < s->research_count; ++i) {
        struct json_object *v = record(s, i);
        const char *op = dw_text(request(s, i), "operation");
        if (strcmp(dw_text(v, "cohort_id"), dw_text(o, "cohort_id"))) continue;
        if (!strcmp(op, "cohort-create")) cohort = i;
        if (!strcmp(op, "cohort-observe") && !strcmp(dw_text(v, "case_id"), dw_text(o, "case_id"))) last = i;
    }
    if (!create) {
        if (cohort == SIZE_MAX) return GOLEM_ERR_NOT_FOUND;
        if (!match(o, "cohort_digest", &s->research_digests[cohort])) return GOLEM_ERR_IDENTITY_MISMATCH;
        if (!member(record(s, cohort), dw_text(o, "case_id"))) return GOLEM_ERR_NOT_FOUND;
        if (last == SIZE_MAX ? *dw_text(o, "supersedes") != '\0' :
            !match(o, "supersedes", &s->research_digests[last])) return GOLEM_ERR_STALE_RESULT;
        golem_status st = verify(s, o, "environment_digest");
        return st == GOLEM_OK ? verify(s, o, "evidence_digest") : st;
    }
    if (cohort != SIZE_MAX) return GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *a = dw_get(o, "members");
    for (size_t j = 0; j < json_object_array_length(a); ++j) {
        struct json_object *v = json_object_array_get_idx(a, j); bool found = false;
        for (size_t i = 0; i < s->research_count; ++i) {
            struct json_object *old = record(s, i);
            const char *op = dw_text(request(s, i), "operation");
            if (!strcmp(op, "cohort-create") && member(old, dw_text(v, "case_id")))
                return GOLEM_ERR_IDENTITY_MISMATCH;
            if (strcmp(dw_text(old, "case_id"), dw_text(v, "case_id"))) continue;
            /* Journal order is enforceable; external execution time is not. */
            if (strcmp(op, "case-create")) return GOLEM_ERR_INVALID_STATE;
            if (!match(v, "case_digest", &s->research_digests[i])) return GOLEM_ERR_IDENTITY_MISMATCH;
            found = true;
        }
        if (!found) return GOLEM_ERR_NOT_FOUND;
    }
    for (size_t i = 0; i < sizeof(contracts)/sizeof(*contracts); ++i) {
        golem_status st = verify(s, o, contracts[i]);
        if (st != GOLEM_OK) return st;
    }
    return GOLEM_OK;
}
