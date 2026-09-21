#ifndef GOLEM_OPTIMIZATION_H
#define GOLEM_OPTIMIZATION_H
#include "golem/cost.h"
#include "golem/policy.h"
#include "golem/evidence.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_OPTIMIZATION_VERSION 1
typedef enum golem_optimization_kind {
    GOLEM_OPTIMIZATION_NOOP = 0, GOLEM_OPTIMIZATION_ROUTE = 1,
    GOLEM_OPTIMIZATION_CACHE = 2, GOLEM_OPTIMIZATION_FALLBACK = 3
} golem_optimization_kind;
enum {
    GOLEM_OPTIMIZE_ROUTE = 1u, GOLEM_OPTIMIZE_CACHE = 2u,
    GOLEM_OPTIMIZE_FALLBACK = 4u, GOLEM_OPTIMIZE_ALL = 7u
};
typedef enum golem_fallback_trigger {
    GOLEM_FALLBACK_NONE = 0, GOLEM_FALLBACK_UNAVAILABLE,
    GOLEM_FALLBACK_RATE_LIMIT, GOLEM_FALLBACK_TIMEOUT,
    GOLEM_FALLBACK_BUDGET_PRESSURE,
    /* These two are never eligible for optimizer fallback. */
    GOLEM_FALLBACK_POLICY_DENIED, GOLEM_FALLBACK_QUALITY_FAILURE
} golem_fallback_trigger;
enum {
    GOLEM_FALLBACK_ON_UNAVAILABLE = 1u,
    GOLEM_FALLBACK_ON_RATE_LIMIT = 2u,
    GOLEM_FALLBACK_ON_TIMEOUT = 4u,
    GOLEM_FALLBACK_ON_BUDGET_PRESSURE = 8u,
    GOLEM_FALLBACK_ON_ALL = 15u
};
typedef struct golem_fallback_policy {
    uint32_t triggers;
    uint32_t max_per_stage; /* Cumulative across successful starts and reentry. */
    bool local_only;
} golem_fallback_policy;
typedef struct golem_optimization_policy {
    uint32_t version;
    uint32_t allowed[GOLEM_STAGE_COUNT];
    uint64_t minimum_savings_nano;
    golem_fallback_policy fallback;
} golem_optimization_policy;

typedef struct golem_cache_model {
    uint64_t setup_nano, uncached_read_nano, cached_read_nano, expected_reads;
} golem_cache_model;
typedef struct golem_cache_result {
    uint64_t uncached_nano, cached_nano, savings_nano;
    /* Minimum reads for STRICT profit; zero means unreachable in uint64. */
    uint64_t break_even_reads;
    bool profitable;
} golem_cache_result;

/* Advisor-controlled data: no authorization, quality approval, permission table,
 * cost estimate or executable command. route_id selects a host-resolved offer.
 * Bindings must match the host's current stage/context/predecessor/requirements.
 * run_id borrows a NUL-terminated string for the call; inline IDs are nonempty,
 * bounded, NUL-terminated. NOOP ignores route_id, but still checks bindings. */
typedef struct golem_optimization_proposal {
    uint32_t version;
    const char *run_id;
    golem_stage stage;
    uint64_t sequence;
    uint32_t attempt;
    golem_digest context_digest, predecessor_digest, requirements_digest;
    golem_optimization_kind kind;
    char route_id[GOLEM_COST_TEXT_CAPACITY];
} golem_optimization_proposal;

/* HOST-TRUSTED data, never populate directly from an advisor response. A route
 * ID is an opaque allowlisted adapter reference, not a shell command. verified
 * attests host capability/quality checks against requirements_digest; it is not
 * a substitute for actual acceptance/evidence gates at stage completion. */
typedef struct golem_optimization_route {
    char id[GOLEM_COST_TEXT_CAPACITY];
    golem_effect effect;
    golem_cost_amount estimate;
    golem_digest requirements_digest;
    bool verified;
} golem_optimization_route;
typedef struct golem_optimization_context {
    const char *run_id;
    golem_stage stage;
    uint64_t sequence;
    uint32_t attempt;
    char currency[4];
    golem_digest context_digest, predecessor_digest, requirements_digest;
    golem_optimization_route baseline, candidate;
    /* Sunk/projected advisor cost and effects also apply to NOOP. Authorize an
     * external advisor BEFORE contacting it; this API itself never calls one. */
    golem_cost_amount overhead;
    golem_effect advisor_effect;
    bool baseline_available;
    bool cache_verified; /* Host verified freshness, scope and artifact digest. */
    /* CACHE model covers this attempt only, not speculative future executions.
     * Its totals must equal baseline/candidate cost estimates, respectively. */
    golem_cache_model cache;
    golem_fallback_trigger fallback_trigger; /* Host-observed failure. */
} golem_optimization_context;
typedef enum golem_optimization_verdict {
    GOLEM_OPTIMIZATION_REJECT = 0,
    GOLEM_OPTIMIZATION_KEEP_BASELINE,
    GOLEM_OPTIMIZATION_APPLY
} golem_optimization_verdict;
typedef enum golem_optimization_reason {
    GOLEM_OPTIMIZATION_DISABLED = 0,
    GOLEM_OPTIMIZATION_NO_PROPOSAL,
    GOLEM_OPTIMIZATION_EXPLICIT_NOOP,
    GOLEM_OPTIMIZATION_QUALITY_UNVERIFIED,
    GOLEM_OPTIMIZATION_CACHE_UNVERIFIED,
    GOLEM_OPTIMIZATION_FALLBACK_FORBIDDEN,
    GOLEM_OPTIMIZATION_NO_SAVINGS,
    GOLEM_OPTIMIZATION_BASELINE_UNAVAILABLE,
    GOLEM_OPTIMIZATION_ACCEPTED
} golem_optimization_reason;
typedef struct golem_optimization_decision {
    golem_optimization_verdict verdict;
    golem_optimization_reason reason;
    golem_optimization_kind selected_kind;
    char route_id[GOLEM_COST_TEXT_CAPACITY];
    golem_effect effect;
    golem_cost_amount expected; /* Selected estimate + ALL overhead. */
    uint64_t savings_nano; /* Strict net savings vs baseline without overhead. */
} golem_optimization_decision;
typedef struct golem_optimization_approval {
    golem_authorization authorization;
    /* GRANTED must name the final selected route, never the original route.
     * Host must reauthorize changed context/effects/estimates even with same ID.
     * Trusted attestation, not a signed or replay-proof capability. */
    char route_id[GOLEM_COST_TEXT_CAPACITY];
} golem_optimization_approval;

/* All inputs borrowed for call; value outputs are independent copies. No aliasing
 * of inputs/outputs/owners. Errors preserve state/outputs except optional diag
 * and begin's explicit decision-output exceptions. No I/O, callbacks, network,
 * process launch, locks, clocks or optimizer dependency. Caller serializes runs. */
golem_status golem_optimization_policy_init(golem_optimization_policy *out);
golem_status golem_cache_break_even(const golem_cache_model *model, golem_cache_result *out);
/* Pure fallback eligibility; false is not permission to run the baseline. */
golem_status golem_fallback_check(const golem_fallback_policy *policy,
    golem_fallback_trigger trigger, uint32_t used, golem_effect candidate_effect, bool *out);
/* Copies policy into run-owned storage. Pristine READY run and enabled cost
 * ledger required. Default policy enables no optimization. Cannot reconfigure.
 * One run-allocator allocation, freed with WorkRun; all later calls allocation-free. */
golem_status golem_work_run_optimization_enable(golem_work_run *run,
    const golem_optimization_policy *policy);
golem_status golem_work_run_optimization_policy_get(const golem_work_run *run,
    golem_optimization_policy *out);
/* Pure selection for current READY attempt; NULL proposal means absent advisor.
 * No grant is carried in a decision. Malformed/stale bindings are errors; semantic
 * rejection is OK + REJECT. Missing known cost/usage returns COST_INCOMPLETE.
 * Equal cost, zero/negative savings, or savings below the configured minimum
 * keeps baseline if available. CACHE/FALLBACK still require host verification.
 * Host-observed POLICY_DENIED/QUALITY_FAILURE reject every selection path,
 * including absent proposals, disabled transformations and explicit NOOP. */
golem_status golem_work_run_optimization_evaluate(const golem_work_run *run,
    const golem_optimization_context *context, const golem_optimization_proposal *proposal,
    golem_optimization_decision *out);
/* Re-evaluates selection, then enters the SAME authoritative Capsule permission
 * and cost gate as begin_authorized. A decision is never accepted as an input.
 * NOOP still executes baseline through that gate, with overhead included.
 * Effects are conservative union of baseline, selected route and advisor.
 * Success records the selected estimate atomically and increments fallback count
 * only for accepted fallback starts. Failed admission preserves pending cost plan.
 * OPTIONAL decision is written on OK, OPTIMIZATION_REJECTED, APPROVAL_REQUIRED
 * and POLICY_DENIED. Other errors preserve it; stage output changes on OK only.
 * No acceptance changes, retry/reentry, actual billing or auto-dispatch occurs. */
golem_status golem_work_run_begin_optimized(golem_work_run *run,
    const golem_optimization_context *context, const golem_optimization_proposal *proposal,
    const golem_optimization_approval *approval, golem_stage_snapshot *stage,
    golem_optimization_decision *decision, golem_diagnostic *diagnostic);

#ifdef __cplusplus
}
#endif
#endif
