#ifndef GOLEM_COST_H
#define GOLEM_COST_H

#include "golem/core.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_COST_VERSION 1
#define GOLEM_COST_TEXT_CAPACITY 96
typedef struct golem_cost_ledger golem_cost_ledger;
/* Disjoint billing buckets: input excludes cache reads; output excludes
 * reasoning. Adapters normalize provider totals before calling this API.
 * Cache writes belong to input unless priced externally in the billed amount. */
typedef struct golem_token_usage {
    uint64_t input_tokens, cached_input_tokens, output_tokens, reasoning_tokens, tool_calls;
} golem_token_usage;
/* Unsigned nano currency units (1 unit = 10^-9 of currency), never floating
 * point. One currency per ledger; no FX or hard-coded live provider prices. */
typedef struct golem_cost_amount {
    golem_token_usage usage;
    uint64_t nano_cost;
    bool usage_known, cost_known;
} golem_cost_amount;
typedef struct golem_cost_rates {
    golem_token_usage nano_per_unit;
} golem_cost_rates;
enum {
    GOLEM_BUDGET_INPUT = 1u, GOLEM_BUDGET_CACHED_INPUT = 2u,
    GOLEM_BUDGET_OUTPUT = 4u, GOLEM_BUDGET_REASONING = 8u,
    GOLEM_BUDGET_TOOLS = 16u, GOLEM_BUDGET_COST = 32u,
    GOLEM_BUDGET_ALL = 63u
};
typedef struct golem_budget {
    uint32_t enabled;
    golem_token_usage limits;
    uint64_t nano_cost_limit;
} golem_budget;
typedef struct golem_cost_options {
    uint32_t version;
    char currency[4]; /* Exactly three uppercase ASCII letters and NUL. */
    size_t entry_capacity, report_capacity;
    golem_budget run_budget;
    /* Cumulative per stage across retries, not reset per attempt. */
    golem_budget stage_budgets[GOLEM_STAGE_COUNT];
} golem_cost_options;
typedef struct golem_provider_usage {
    /* Strings inline, nonempty, NUL terminated; no truncation. request_id
     * identifies one incremental billable call within an entry, not a stream
     * snapshot. Distinct calls, including fallback, need distinct IDs. */
    char request_id[GOLEM_COST_TEXT_CAPACITY];
    char provider[GOLEM_COST_TEXT_CAPACITY];
    char model[GOLEM_COST_TEXT_CAPACITY];
    char price_revision[GOLEM_COST_TEXT_CAPACITY];
    char currency[4];
    golem_cost_amount actual;
} golem_provider_usage;
typedef struct golem_cost_entry {
    golem_stage_snapshot stage;
    golem_cost_amount expected, actual;
    size_t report_count;
    bool settled;
} golem_cost_entry;
typedef struct golem_cost_totals {
    golem_cost_amount expected, actual;
    size_t entries, reports, unsettled;
} golem_cost_totals;

/* Inputs borrowed for call; outputs are independent caller-owned copies.
 * No aliasing of inputs/outputs/owner storage. Errors preserve state and outputs.
 * Unknown input amount fields must be zero; known zero differs from unreported.
 * Checked uint64 arithmetic; no allocation/I/O/clock in value functions. */
golem_status golem_token_usage_add(const golem_token_usage *a,
    const golem_token_usage *b, golem_token_usage *out);
golem_status golem_cost_calculate(const golem_token_usage *usage,
    const golem_cost_rates *rates, uint64_t *nano_cost);
/* Unknown required dimensions return COST_INCOMPLETE; equality is allowed.
 * Disabled dimensions ignored. Enabled zero is a hard zero limit.
 * Accepts aggregate amounts with known partial sums and known=false. */
golem_status golem_budget_check(const golem_budget *budget, const golem_cost_amount *amount);

/* Opt-in accounting for a pristine READY WorkRun (sequence=0). Copies options,
 * preallocates bounded storage using the run allocator, owned/freed by WorkRun.
 * Cannot disable/reconfigure. Legacy unconfigured runs retain bounded replay
 * behavior; journal v1 has no billing and never implies free work.
 * No allocations after enable. Every successful begin path creates an entry;
 * capacity, missing required estimate or budget failures leave READY unchanged.
 * Run and ledger access must be serialized by caller. Not a provider sandbox. */
golem_status golem_work_run_cost_enable(golem_work_run *run, const golem_cost_options *options);
/* Immutable borrowed ledger, valid until run free; NULL if not enabled. */
const golem_cost_ledger *golem_work_run_cost_borrow(const golem_work_run *run);
/* Plan for next sequence, READY only. May replace it before execution, e.g. to
 * choose a cheaper route. Failed begin retains plan; success freezes/consumes it.
 * Without a plan, expected remains unknown (not free). */
golem_status golem_work_run_cost_plan(golem_work_run *run, uint64_t sequence,
    const golem_cost_amount *expected);
/* Append-only call reports, during/after execution until settlement.
 * Same entry/request_id + identical values is idempotent, even after settlement;
 * conflicting duplicate rejected. Actual over-budget charges are STILL stored.
 * Never use estimated cost as actual. Strings copied into preallocated storage. */
golem_status golem_work_run_cost_report(golem_work_run *run, uint64_t sequence,
    const golem_provider_usage *report);
/* Terminal attempts with >=1 report only; explicit known-zero report represents
 * free/no-op work. Idempotent. Prevents new reports, not duplicate delivery.
 * Unknown amounts may settle but remain incomplete for budget enforcement. */
golem_status golem_work_run_cost_settle(golem_work_run *run, uint64_t sequence);
/* Entries indexed by StageRun sequence (1-based); reports by entry-local index
 * (0-based). Totals retain known partial sums; known=false means incomplete,
 * including unsettled entries. No different currencies combined. */
golem_status golem_cost_ledger_entry_get(const golem_cost_ledger *ledger,
    uint64_t sequence, golem_cost_entry *out);
golem_status golem_cost_ledger_report_get(const golem_cost_ledger *ledger,
    uint64_t sequence, size_t index, golem_provider_usage *out);
golem_status golem_cost_ledger_totals_get(const golem_cost_ledger *ledger, golem_cost_totals *out);
/* Cumulative stage totals including failed/cancelled/reentered attempts. */
golem_status golem_cost_ledger_stage_totals_get(const golem_cost_ledger *ledger,
    golem_stage stage, golem_cost_totals *out);
golem_status golem_cost_ledger_options_get(const golem_cost_ledger *ledger, golem_cost_options *out);
#ifdef __cplusplus
}
#endif

#endif
