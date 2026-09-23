#include "internal.h"
#include <string.h>

#define RM_RULE "golem.research-metrics.v1"
typedef struct rm_case {
    const char *id;
    size_t latest;
    uint64_t plans, attempts, linked, revisions, required, episodes, recovered;
    bool enrolled, pending;
} rm_case;

static bool increment(struct json_object *o, const char *key, uint64_t value)
{
    uint64_t prior = dw_get(o, key) ? dw_uint(o, key) : 0;
    return prior <= INT64_MAX && value <= (uint64_t)INT64_MAX - prior && ex_uint(o, key, prior + value);
}
static bool unavailable(struct json_object *o, const char *key, const char *reason)
{
    struct json_object *v = json_object_new_object();
    if (!v || json_object_object_add(v, "value", NULL) != 0 || !ex_text(v, "reason", reason)) {
        json_object_put(v); return false;
    }
    return dw_add(o, key, v);
}
static bool append(struct json_object *a, struct json_object *v)
{
    if (!v || json_object_array_add(a, v) != 0) { json_object_put(v); return false; }
    return true;
}
static golem_status source(struct json_object *items, golem_document_store *s, size_t i)
{
    struct json_object *v = json_object_new_object();
    if (!ex_uint(v, "research_sequence", i + 1) ||
        !dw_add_digest(v, "record_digest", &s->research_digests[i]) ||
        !dw_add_digest(v, "event_digest", &s->research_frames[i])) {
        json_object_put(v); return GOLEM_ERR_OUT_OF_MEMORY;
    }
    return append(items, v) ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
}
golem_status rs_metrics(golem_document_store *s, const char *filter, struct json_object **out)
{
    if (!s || !out || (filter && !dw_id(filter))) return GOLEM_ERR_INVALID_ARGUMENT;
    if (s->poisoned) return GOLEM_ERR_INVALID_STATE;
    rm_case cases[GOLEM_RESEARCH_MAX_EVENTS] = {0};
    size_t count = 0;
    uint64_t records = 0, plans = 0, attempts = 0, linked = 0, revisions = 0;
    uint64_t ineligible_revisions = 0, pass_but_ineligible = 0;
    uint64_t samples = 0, sum = 0, minimum = UINT64_MAX, maximum = 0;
    struct json_object *o = json_object_new_object(), *hist = json_object_new_object();
    struct json_object *actors = json_object_new_object(), *actions = json_object_new_object();
    struct json_object *sources = json_object_new_array(), *rows = json_object_new_array();
    struct json_object *totals = json_object_new_object(), *latest_status = json_object_new_object();
    struct json_object *coverage = json_object_new_object(), *recovery = json_object_new_object();
    struct json_object *duration = json_object_new_object(), *unknown = json_object_new_object();
    struct json_object *boundary = json_object_new_object(), *work = json_object_new_object();
    golem_status st = o && hist && actors && actions && sources && rows && totals && latest_status &&
        coverage && recovery && duration && unknown && boundary && work ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < s->research_count; ++i) {
        struct json_object *request = dw_get(s->research[i], "request"), *r = dw_get(request, "record");
        if (rs_is_cohort(request)) continue;
        const char *id = dw_text(r, "case_id"), *op = dw_text(request, "operation");
        if (filter && strcmp(id, filter)) continue;
        size_t c = 0;
        while (c < count && strcmp(cases[c].id, id)) ++c;
        if (!strcmp(op, "case-create")) {
            if (c != count || count >= GOLEM_RESEARCH_MAX_EVENTS) { st = GOLEM_ERR_CORRUPT_JOURNAL; break; }
            cases[count++] = (rm_case){.id = id, .latest = SIZE_MAX};
        } else if (c == count) { st = GOLEM_ERR_CORRUPT_JOURNAL; break; }
        rm_case *v = &cases[c];
        ++records;
        st = source(sources, s, i);
        if (st != GOLEM_OK) break;
        if (!strcmp(op, "attempt-plan")) { ++plans; ++v->plans; }
        else if (!strcmp(op, "attempt-record")) {
            ++attempts; ++v->attempts;
            if (*dw_text(r, "plan_digest")) { ++linked; ++v->linked; }
            if (!increment(hist, dw_text(r, "classification"), 1) ||
                !increment(actors, dw_text(r, "actor_kind"), 1) ||
                !increment(actions, dw_text(r, "next_action"), 1)) st = GOLEM_ERR_OUT_OF_MEMORY;
            uint64_t elapsed = dw_uint(r, "ended_at") - dw_uint(r, "started_at");
            /* Version-1 timestamp bounds and 256 records keep the sum < INT64_MAX. */
            ++samples; sum += elapsed;
            if (elapsed < minimum) minimum = elapsed;
            if (elapsed > maximum) maximum = elapsed;
        } else if (!strcmp(op, "outcome-enroll")) {
            v->enrolled = true; v->required = json_object_array_length(dw_get(r, "required_cases"));
        } else if (!strcmp(op, "adjudicate")) {
            struct json_object *assessment = dw_get(s->research[i], "assessment");
            bool eligible = json_object_get_boolean(dw_get(assessment, "completion_eligible"));
            ++revisions; ++v->revisions; v->latest = i;
            if (!eligible) {
                ++ineligible_revisions;
                if (!strcmp(dw_text(assessment, "normalized_status"), "PASS")) ++pass_but_ineligible;
            }
            if (!eligible && !v->pending) { ++v->episodes; v->pending = true; }
            else if (eligible && v->pending) { ++v->recovered; v->pending = false; }
        }
    }
    if (st == GOLEM_OK && filter && !count) st = GOLEM_ERR_NOT_FOUND;
    const char *fields[] = {"pass_count", "fail_count", "error_count", "skipped_count",
        "not_executed_count", "unknown_count", "product_failure_count", "harness_failure_count", "environment_failure_count"};
    for (size_t i = 0; st == GOLEM_OK && i < sizeof(fields)/sizeof(*fields); ++i)
        if (!ex_uint(coverage, fields[i], 0)) st = GOLEM_ERR_OUT_OF_MEMORY;
    uint64_t enrolled = 0, assessed = 0, eligible_count = 0, required = 0, unassessed = 0;
    uint64_t episodes = 0, recovered = 0, pending = 0;
    for (size_t i = 0; st == GOLEM_OK && i < count; ++i) {
        rm_case *v = &cases[i];
        bool has = v->latest != SIZE_MAX;
        struct json_object *a = has ? dw_get(s->research[v->latest], "assessment") : NULL;
        bool eligible = has && json_object_get_boolean(dw_get(a, "completion_eligible"));
        enrolled += v->enrolled; assessed += has; eligible_count += eligible; required += v->required;
        if (v->enrolled && !has) unassessed += v->required;
        episodes += v->episodes; recovered += v->recovered; pending += v->pending;
        if (has) {
            if (!increment(latest_status, dw_text(a, "normalized_status"), 1)) st = GOLEM_ERR_OUT_OF_MEMORY;
            for (size_t j = 0; st == GOLEM_OK && j < sizeof(fields)/sizeof(*fields); ++j)
                if (!increment(coverage, fields[j], dw_uint(a, fields[j]))) st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        struct json_object *row = json_object_new_object();
        if (!ex_text(row, "case_id", v->id) || !ex_text(row, "state", !v->enrolled ? "UNENROLLED" :
                !has ? "UNASSESSED" : eligible ? "ELIGIBLE" : "NOT_ELIGIBLE") ||
            !ex_uint(row, "attempt_count", v->attempts) || !ex_uint(row, "plan_count", v->plans) ||
            !ex_uint(row, "unobserved_plan_count", v->plans - v->linked) ||
            !ex_uint(row, "adjudication_revision_count", v->revisions) || !ex_uint(row, "required_case_count", v->required) ||
            !ex_uint(row, "not_eligible_episode_count", v->episodes) || !ex_uint(row, "recovered_episode_count", v->recovered) ||
            !dw_add(row, "open_episode", json_object_new_boolean(v->pending)) ||
            (has ? !dw_add_digest(row, "latest_adjudication_digest", &s->research_digests[v->latest]) :
                   json_object_object_add(row, "latest_adjudication_digest", NULL) != 0)) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) { if (!append(rows, row)) st = GOLEM_ERR_OUT_OF_MEMORY; }
        else json_object_put(row);
    }
    if (st == GOLEM_OK && (!ex_uint(totals, "research_record_count", records) || !ex_uint(totals, "case_count", count) ||
        !ex_uint(totals, "attempt_plan_count", plans) || !ex_uint(totals, "attempt_count_total", attempts) ||
        !ex_uint(totals, "linked_plan_attempt_count", linked) || !ex_uint(totals, "retrospective_attempt_count", attempts-linked) ||
        !ex_uint(totals, "unobserved_plan_count", plans-linked) || !ex_uint(totals, "outcome_enrollment_count", enrolled) ||
        !ex_uint(totals, "adjudication_revision_count", revisions) || !ex_uint(totals, "latest_assessed_case_count", assessed) ||
        !ex_uint(totals, "ineligible_adjudication_revision_count", ineligible_revisions) ||
        !ex_uint(totals, "pass_but_ineligible_revision_count", pass_but_ineligible) ||
        !ex_uint(totals, "latest_unassessed_enrollment_count", enrolled-assessed) ||
        !ex_uint(totals, "latest_eligible_case_count", eligible_count) ||
        !ex_uint(totals, "latest_not_eligible_case_count", assessed-eligible_count) ||
        !ex_uint(coverage, "required_case_count", required) || !ex_uint(coverage, "unassessed_required_case_count", unassessed) ||
        !ex_text(coverage, "basis", "LATEST_RECORDED_ADJUDICATION_PER_CASE") ||
        !ex_text(recovery, "unit", "ADJUDICATION_NOT_ELIGIBLE_EPISODE") ||
        !ex_uint(recovery, "episode_count", episodes) || !ex_uint(recovery, "recovered_episode_count", recovered) ||
        !ex_uint(recovery, "open_episode_count", pending) ||
        !ex_uint(recovery, "rate_numerator", recovered) || !ex_uint(recovery, "rate_denominator", episodes) ||
        !dw_add(recovery, "rate_defined", json_object_new_boolean(episodes != 0)) ||
        !ex_text(duration, "basis", "DECLARED_ATTEMPT_INTERVALS_NOT_WORK_ELAPSED_TIME") ||
        !ex_uint(duration, "sample_count", samples) || !ex_uint(duration, "sum_ms", sum))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        bool good = samples ? ex_uint(duration, "min_ms", minimum) && ex_uint(duration, "max_ms", maximum) :
            json_object_object_add(duration, "min_ms", NULL) == 0 && json_object_object_add(duration, "max_ms", NULL) == 0;
        if (!good) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    const char *unrecorded[] = {"false_completion_prevented_count", "stale_evidence_rejected_count",
        "duplicate_execution_prevented_count", "uncertain_effect_reconciled_count", "manual_intervention_count"};
    for (size_t i = 0; st == GOLEM_OK && i < sizeof(unrecorded)/sizeof(*unrecorded); ++i)
        if (!unavailable(unknown, unrecorded[i], "NO_COMPLETE_ENGINE_FACT_STREAM; CLASSIFICATIONS_ARE_DECLARATIONS")) st = GOLEM_ERR_OUT_OF_MEMORY;
    const char *times[] = {"time_to_first_failure", "time_to_classification", "time_to_completion_or_block"};
    for (size_t i = 0; st == GOLEM_OK && i < sizeof(times)/sizeof(*times); ++i)
        if (!unavailable(unknown, times[i], "NO_TRUSTED_MATCHED_START_AND_END_CLOCK")) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && (!unavailable(unknown, "cloud_cost_observed", "NO_RESEARCH_LINKED_COST_CONTRACT") ||
        !unavailable(unknown, "local_resource_cost_observed", "NO_RESEARCH_LINKED_COST_CONTRACT") ||
        !unavailable(unknown, "unknown_cost_count", "NO_DEFINED_COST_OBSERVATION_POPULATION") ||
        !unavailable(unknown, "evidence_completeness_score", "COMPOSITE_SCORE_NOT_VALIDATED; SEE_REQUIRED_CASE_COVERAGE") ||
        !unavailable(unknown, "current_task_completion", "HISTORICAL_REPLAY_ONLY; USE_COMPLETION_RESUME"))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && (!ex_uint(boundary, "work_event_count", s->event_count) ||
        !ex_uint(boundary, "research_event_count", s->research_count) || !ex_uint(boundary, "document_generation", s->count+1) ||
        !dw_add_digest(boundary, "work_head", &s->last) || !ex_uint(work, "work_count", 1) ||
        !ex_text(work, "scope", "WHOLE_WORK_NOT_CASE_FILTERED") ||
        !ex_uint(work, "recorded_completion_count", s->completion_count) ||
        !ex_uint(work, "ever_recorded_completed_work_count", s->completion_count ? 1 : 0) ||
        !ex_uint(work, "recorded_reentry_count", s->reentry_count))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && s->completion_count &&
        !dw_add_digest(work, "latest_completion_digest", &s->completion_digests[s->completion_count-1])) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && (!ex_uint(o, "schema_version", 1) || !ex_text(o, "rule", RM_RULE) ||
        !ex_text(o, "work_id", dw_text(s->spec, "work_id")) || !ex_text(o, "scope", filter ? "CASE" : "WORK") ||
        !ex_text(o, "case_id", filter ? filter : "") || !ex_text(o, "trust", "DECLARED_INPUTS_VERIFIED_REFERENCES") ||
        !dw_add(o, "acceptance_verified", json_object_new_boolean(false)) ||
        !dw_add(o, "execution_authorized", json_object_new_boolean(false)) ||
        !dw_add(o, "boundary", json_object_get(boundary)) || !dw_add(o, "work_history", json_object_get(work)) ||
        !dw_add(o, "counts", json_object_get(totals)) || !dw_add(o, "declared_classification_counts", json_object_get(hist)) ||
        !dw_add(o, "declared_actor_counts", json_object_get(actors)) || !dw_add(o, "declared_next_action_counts", json_object_get(actions)) ||
        !dw_add(o, "latest_normalized_status_counts", json_object_get(latest_status)) ||
        !dw_add(o, "required_case_coverage", json_object_get(coverage)) || !dw_add(o, "adjudication_recovery", json_object_get(recovery)) ||
        !dw_add(o, "declared_attempt_duration", json_object_get(duration)) || !dw_add(o, "unavailable", json_object_get(unknown)) ||
        !dw_add(o, "cases", json_object_get(rows)) || !dw_add(o, "source_records", json_object_get(sources)))) st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_digest digest;
    if (st == GOLEM_OK) st = ex_hash(o, &digest);
    if (st == GOLEM_OK && !dw_add_digest(o, "projection_digest", &digest)) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) *out = o; else json_object_put(o);
    json_object_put(hist); json_object_put(actors); json_object_put(actions); json_object_put(sources);
    json_object_put(rows); json_object_put(totals); json_object_put(latest_status); json_object_put(coverage);
    json_object_put(recovery); json_object_put(duration); json_object_put(unknown); json_object_put(boundary); json_object_put(work);
    return st;
}
golem_status golem_research_metrics(golem_document_store *s, const char *filter,
    golem_execution_reply *out, golem_diagnostic *d)
{
    if (!out) return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *o = NULL;
    golem_status st = rs_metrics(s, filter, &o);
    if (st == GOLEM_OK) st = ex_emit(o, out);
    json_object_put(o);
    return dw_report(d, st, NULL);
}
