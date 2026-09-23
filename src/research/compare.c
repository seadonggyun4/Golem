#include "internal.h"
#include <string.h>

static struct json_object *req(golem_document_store *s, size_t i)
{ return dw_get(s->research[i], "request"); }
static struct json_object *rec(golem_document_store *s, size_t i)
{ return dw_get(req(s, i), "record"); }
static bool flag(struct json_object *o, const char *key, bool value)
{ return dw_add(o, key, json_object_new_boolean(value)); }

golem_status golem_research_compare(golem_document_store *s, const char *id,
    golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out || !id || !dw_id(id)) return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (s->poisoned) return dw_report(d, GOLEM_ERR_INVALID_STATE, NULL);
    size_t cohort = SIZE_MAX;
    for (size_t i = 0; i < s->research_count; ++i)
        if (!strcmp(dw_text(req(s, i), "operation"), "cohort-create") &&
            !strcmp(dw_text(rec(s, i), "cohort_id"), id)) cohort = i;
    if (cohort == SIZE_MAX) return dw_report(d, GOLEM_ERR_NOT_FOUND, NULL);
    struct json_object *definition = rec(s, cohort), *members = dw_get(definition, "members");
    struct json_object *o = json_object_new_object(), *rows = json_object_new_array();
    struct json_object *groups = json_object_new_array(), *sources = json_object_new_array();
    golem_status st = o && rows && groups && sources ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    const char *arms[] = {"NON_USE", "PARTIAL_USE", "FULL_USE"};
    const char *statuses[] = {"PASS", "FAIL", "SKIPPED", "NOT_DONE", "UNKNOWN", "NOT_RECORDED"};
    uint64_t counts[3][6] = {{0}}, revisions[3] = {0}, deviations[3] = {0};
    for (size_t j = 0; st == GOLEM_OK && j < json_object_array_length(members); ++j) {
        struct json_object *m = json_object_array_get_idx(members, j);
        size_t last = SIZE_MAX, total = 0; bool historical_deviation = false;
        unsigned group = 0;
        while (group < 2 && strcmp(arms[group], dw_text(m, "arm"))) ++group;
        for (size_t i = cohort + 1; i < s->research_count; ++i) {
            struct json_object *r = rec(s, i);
            if (strcmp(dw_text(req(s, i), "operation"), "cohort-observe") ||
                strcmp(dw_text(r, "cohort_id"), id) || strcmp(dw_text(r, "case_id"), dw_text(m, "case_id"))) continue;
            last = i; ++total;
            historical_deviation |= json_object_get_boolean(dw_get(r, "leakage")) ||
                strcmp(dw_text(r, "observed_arm"), dw_text(m, "arm")) != 0 ||
                strcmp(dw_text(r, "environment_digest"), dw_text(definition, "environment_digest")) != 0;
        }
        struct json_object *latest = last == SIZE_MAX ? NULL : rec(s, last);
        const char *status = latest ? dw_text(latest, "status") : "NOT_RECORDED";
        unsigned state = 0;
        while (state < 5 && strcmp(statuses[state], status)) ++state;
        ++counts[group][state]; revisions[group] += total;
        if (historical_deviation) ++deviations[group];
        struct json_object *row = json_object_new_object();
        if (!ex_text(row, "case_id", dw_text(m, "case_id")) || !ex_text(row, "assigned_arm", arms[group]) ||
            !ex_text(row, "block_id", dw_text(m, "block_id")) || !ex_text(row, "declared_status", status) ||
            !ex_text(row, "observed_arm", latest ? dw_text(latest, "observed_arm") : "UNKNOWN") ||
            !ex_uint(row, "observation_revision_count", total) || !flag(row, "ever_declared_deviation", historical_deviation) ||
            !ex_text(row, "case_digest", dw_text(m, "case_digest"))) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && last != SIZE_MAX &&
            (!dw_add_digest(row, "latest_observation_digest", &s->research_digests[last]) ||
             !ex_text(row, "evidence_digest", dw_text(latest, "evidence_digest")))) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && json_object_array_add(rows, row) == 0) row = NULL;
        else st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(row);
    }
    for (unsigned g = 0; st == GOLEM_OK && g < 3; ++g) {
        struct json_object *row = json_object_new_object(), *hist = json_object_new_object(); uint64_t assigned = 0;
        for (unsigned k = 0; k < 6; ++k) {
            assigned += counts[g][k];
            if (!ex_uint(hist, statuses[k], counts[g][k])) st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        if (!ex_text(row, "arm", arms[g]) || !ex_uint(row, "assigned", assigned) ||
            !ex_uint(row, "observations", assigned - counts[g][5]) ||
            !ex_uint(row, "observation_revision_count", revisions[g]) ||
            !ex_uint(row, "ever_declared_deviation_count", deviations[g]) ||
            !dw_add(row, "declared_status_counts", json_object_get(hist))) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && json_object_array_add(groups, row) == 0) row = NULL;
        else st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(row); json_object_put(hist);
    }
    for (size_t i = cohort; st == GOLEM_OK && i < s->research_count; ++i) {
        if (!rs_is_cohort(req(s, i)) || strcmp(dw_text(rec(s, i), "cohort_id"), id)) continue;
        struct json_object *v = json_object_new_object();
        if (!ex_uint(v, "sequence", i+1) || !dw_add_digest(v, "record_digest", &s->research_digests[i]) ||
            !dw_add_digest(v, "event_digest", &s->research_frames[i])) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && json_object_array_add(sources, v) == 0) v = NULL;
        else st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(v);
    }
    if (st == GOLEM_OK && (!ex_uint(o, "schema_version", 1) || !ex_text(o, "rule", "golem.comparison-cohort.v1") ||
        !ex_text(o, "work_id", dw_text(s->spec, "work_id")) || !ex_text(o, "cohort_id", id) ||
        !ex_text(o, "design", dw_text(definition, "design")) || !ex_text(o, "trust", "DECLARED_OUTCOMES") ||
        !flag(o, "causal_effect_verified", false) || !flag(o, "acceptance_verified", false) ||
        !flag(o, "external_preregistration_verified", false) || !flag(o, "execution_authorized", false) ||
        !dw_add_digest(o, "cohort_digest", &s->research_digests[cohort]) ||
        !dw_add_digest(o, "work_head", &s->last) || !ex_uint(o, "event_count", s->event_count) ||
        !dw_add(o, "arms", json_object_get(groups)) || !dw_add(o, "members", json_object_get(rows)) ||
        !dw_add(o, "source_records", json_object_get(sources)))) st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_digest digest;
    if (st == GOLEM_OK) st = ex_hash(o, &digest);
    if (st == GOLEM_OK && !dw_add_digest(o, "projection_digest", &digest)) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) st = ex_emit(o, out);
    json_object_put(o); json_object_put(rows); json_object_put(groups); json_object_put(sources);
    return dw_report(d, st, NULL);
}
