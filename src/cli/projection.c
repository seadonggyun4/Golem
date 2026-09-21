#include "work.h"

static struct json_object *amount(const golem_cost_amount *a)
{
    struct json_object *o = json_object_new_object();
    if (!cli_json_add(o, "nano_cost", cli_json_u64(a->nano_cost)) ||
        !cli_json_add(o, "cost_known", json_object_new_boolean(a->cost_known)) ||
        !cli_json_add(o, "usage_known", json_object_new_boolean(a->usage_known)) ||
        !cli_json_add(o, "input_tokens", cli_json_u64(a->usage.input_tokens)) ||
        !cli_json_add(o, "cached_input_tokens", cli_json_u64(a->usage.cached_input_tokens)) ||
        !cli_json_add(o, "output_tokens", cli_json_u64(a->usage.output_tokens)) ||
        !cli_json_add(o, "reasoning_tokens", cli_json_u64(a->usage.reasoning_tokens)) ||
        !cli_json_add(o, "tool_calls", cli_json_u64(a->usage.tool_calls))) { json_object_put(o); return NULL; }
    return o;
}
struct json_object *cli_cost_projection(const golem_work_run *run)
{
    const golem_cost_ledger *ledger = golem_work_run_cost_borrow(run);
    golem_cost_totals totals; golem_cost_options options;
    if (golem_cost_ledger_totals_get(ledger, &totals) != GOLEM_OK ||
        golem_cost_ledger_options_get(ledger, &options) != GOLEM_OK) return NULL;
    struct json_object *o = json_object_new_object(), *entries = json_object_new_array();
    if (o == NULL || entries == NULL) { json_object_put(o); json_object_put(entries); return NULL; }
    if (!cli_json_add(o, "entries", entries)) { json_object_put(o); return NULL; }
    if (!cli_json_add(o, "schema_version", json_object_new_int(1)) ||
        !cli_json_add(o, "run_id", json_object_new_string(golem_work_run_id_borrow(run))) ||
        !cli_json_add(o, "simulation", json_object_new_boolean(true)) ||
        !cli_json_add(o, "currency", json_object_new_string(options.currency)) ||
        !cli_json_add(o, "expected", amount(&totals.expected)) || !cli_json_add(o, "actual", amount(&totals.actual)) ||
        !cli_json_add(o, "unsettled", cli_json_u64(totals.unsettled))) { json_object_put(o); return NULL; }
    for (size_t i = 0; i < totals.entries; ++i) {
        golem_cost_entry e;
        if (golem_cost_ledger_entry_get(ledger, i + 1, &e) != GOLEM_OK) { json_object_put(o); return NULL; }
        struct json_object *row = json_object_new_object();
        if (!cli_json_add(row, "stage", json_object_new_string(golem_stage_name(e.stage.stage))) ||
            !cli_json_add(row, "sequence", cli_json_u64(e.stage.sequence)) ||
            !cli_json_add(row, "attempt", json_object_new_int64(e.stage.attempt)) ||
            !cli_json_add(row, "provider", json_object_new_string("local")) ||
            !cli_json_add(row, "model", json_object_new_string("noop")) ||
            !cli_json_add(row, "expected", amount(&e.expected)) || !cli_json_add(row, "actual", amount(&e.actual)) ||
            !cli_json_add(row, "settled", json_object_new_boolean(e.settled))) { json_object_put(row); json_object_put(o); return NULL; }
        if (!cli_json_append(entries, row)) { json_object_put(o); return NULL; }
    }
    return o;
}
struct json_object *cli_run_projection(const golem_work_run *run, const golem_replay_report *r, bool complete)
{
    static const char *const states[] = {"READY", "RUNNING", "FAILED", "BLOCKED", "SUCCEEDED", "CANCELLED"};
    static const char *const actions[] = {"NONE", "CHECK_POLICY", "RECONCILE_ATTEMPT", "EVALUATE_REENTRY", "RESOLVE_BLOCK"};
    golem_work_snapshot work; (void)golem_work_run_snapshot_get(run, &work);
    struct json_object *o = json_object_new_object();
    if (!cli_json_add(o, "schema_version", json_object_new_int(1)) ||
        !cli_json_add(o, "run_id", json_object_new_string(golem_work_run_id_borrow(run))) ||
        !cli_json_add(o, "state", json_object_new_string(states[work.status])) ||
        !cli_json_add(o, "passed_stages", cli_json_u64(work.passed_count)) ||
        !cli_json_add(o, "stage_count", cli_json_u64(work.stage_count)) ||
        !cli_json_add(o, "bundle_verified", json_object_new_boolean(complete)) ||
        !cli_json_add(o, "simulation", json_object_new_string(complete ? "verified_noop" : "unknown")) ||
        !cli_json_add(o, "acceptance_verified", json_object_new_boolean(false)) ||
        !cli_json_add(o, "recovery_action", json_object_new_string(r == NULL ? "NONE" : actions[r->action])) ||
        (r != NULL && (!cli_json_add(o, "journal_records", cli_json_u64(r->verified_records)) ||
        !cli_json_add(o, "journal_bytes", cli_json_u64(r->verified_bytes))))) { json_object_put(o); return NULL; }
    return o;
}
