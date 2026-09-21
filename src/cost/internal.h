#ifndef GOLEM_COST_INTERNAL_H
#define GOLEM_COST_INTERNAL_H
#include "golem/cost.h"
typedef struct golem_cost_report_record {
    uint64_t sequence;
    size_t next;
    golem_provider_usage value;
} golem_cost_report_record;
typedef struct golem_cost_entry_record {
    golem_cost_entry value;
    size_t first_report, last_report;
} golem_cost_entry_record;
struct golem_cost_ledger {
    golem_allocator allocator;
    golem_cost_options options;
    golem_cost_entry_record *entries;
    golem_cost_report_record *reports;
    size_t entry_count, report_count;
    size_t unreported;
    /* actual known flags describe reports alone; unsettled entries mask those
     * flags at query/admission time. This keeps settlement and totals O(1). */
    golem_cost_totals totals;
    golem_cost_totals stage_totals[GOLEM_STAGE_COUNT];
    bool has_plan;
    golem_cost_amount plan;
};
bool golem_cost_amount_valid(const golem_cost_amount *amount);
bool golem_cost_budget_valid(const golem_budget *budget);
golem_status golem_cost_budget_admit(const golem_budget *budget,
    const golem_cost_amount *prior, const golem_cost_amount *planned);
golem_status golem_cost_amount_add(const golem_cost_amount *a,
    const golem_cost_amount *b, golem_cost_amount *out);
golem_status golem_cost_ledger_create(const golem_cost_options *options,
    const golem_allocator *allocator, golem_cost_ledger **out);
void golem_cost_ledger_free(golem_cost_ledger *ledger);
golem_status golem_cost_begin(golem_cost_ledger *ledger, const golem_stage_snapshot *stage,
    const golem_cost_amount *estimate);
void golem_cost_finish(golem_cost_ledger *ledger, const golem_stage_snapshot *stage);
#endif
