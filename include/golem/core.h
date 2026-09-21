#ifndef GOLEM_CORE_H
#define GOLEM_CORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "golem/error.h"
#include "golem/allocator.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct golem_work_capsule golem_work_capsule;
typedef struct golem_work_run golem_work_run;
typedef struct golem_stage_run golem_stage_run;
typedef struct golem_stage_graph golem_stage_graph;

typedef enum golem_stage {
    GOLEM_STAGE_PLANNING = 0, GOLEM_STAGE_UX,
    GOLEM_STAGE_PUBLISHING, GOLEM_STAGE_DEVELOPMENT,
    GOLEM_STAGE_QA, GOLEM_STAGE_AUDIT,
    GOLEM_STAGE_COUNT, GOLEM_STAGE_NONE = GOLEM_STAGE_COUNT
} golem_stage;
typedef enum golem_failure {
    GOLEM_FAILURE_NONE = 0, GOLEM_FAILURE_PLANNING_GAP,
    GOLEM_FAILURE_UX_MISMATCH, GOLEM_FAILURE_PUBLISHING_GAP,
    GOLEM_FAILURE_IMPLEMENTATION_DEFECT, GOLEM_FAILURE_QA_FLAKE,
    GOLEM_FAILURE_AUDIT_GAP, GOLEM_FAILURE_POLICY_DENIED,
    GOLEM_FAILURE_STALE_LEASE, GOLEM_FAILURE_BUDGET_EXHAUSTED,
    GOLEM_FAILURE_TIMEOUT, GOLEM_FAILURE_UNKNOWN, GOLEM_FAILURE_COUNT
} golem_failure;
typedef enum golem_autonomy {
    /* Zero-initialized permissions deny execution. */
    GOLEM_AUTONOMY_DENY = 0, GOLEM_AUTONOMY_AUTO_LOCAL,
    GOLEM_AUTONOMY_ASK_ON_EXTERNAL_EFFECT, GOLEM_AUTONOMY_ASK_ALWAYS
} golem_autonomy;
typedef enum golem_stage_status {
    GOLEM_STAGE_PENDING = 0, GOLEM_STAGE_RUNNING,
    GOLEM_STAGE_PASSED, GOLEM_STAGE_FAILED,
    GOLEM_STAGE_BLOCKED, GOLEM_STAGE_CANCELLED
} golem_stage_status;
typedef enum golem_work_status {
    GOLEM_WORK_READY = 0, GOLEM_WORK_RUNNING,
    GOLEM_WORK_FAILED, GOLEM_WORK_BLOCKED,
    GOLEM_WORK_SUCCEEDED, GOLEM_WORK_CANCELLED
} golem_work_status;
typedef struct golem_string_list {
    const char *const *items;
    size_t count;
} golem_string_list;

/* Sequential MVP, not a branching DAG. Stages are unique; subsets/reordering
 * are supported. Missing/forward reentry targets reject recovery.
 * NONE disables recovery. TIMEOUT always retries the current stage.
 * Policy/lease/budget failures always block regardless of this table. */
typedef struct golem_graph_spec {
    golem_stage order[GOLEM_STAGE_COUNT];
    size_t count;
    golem_stage reentry[GOLEM_FAILURE_COUNT];
} golem_graph_spec;
typedef struct golem_capsule_spec {
    const char *id;
    const char *goal;
    golem_string_list scope;
    golem_string_list acceptance;
    golem_string_list expected_artifacts;
    golem_string_list required_gates;
    golem_autonomy permissions[GOLEM_STAGE_COUNT];
    const golem_stage_graph *graph;
} golem_capsule_spec;
/* Value snapshot. sequence is scoped to one run, not a lease or global ID. */
typedef struct golem_stage_snapshot {
    golem_stage stage;
    golem_stage_status status;
    golem_failure failure;
    uint32_t attempt;
    uint64_t sequence;
} golem_stage_snapshot;
typedef struct golem_work_snapshot {
    golem_work_status status;
    golem_stage current_stage;
    size_t passed_count;
    size_t stage_count;
} golem_work_snapshot;

/* On errors, state and outputs remain unchanged except optional diagnostics.
 * _create deep-copies inputs;
 * caller owns result and calls matching _free (NULL allowed).
 * Borrowed views last until owner is freed unless stated otherwise.
 * Standalone Core has no I/O/clocks/global mutable state/locks. A WorkRun owned
 * by a lease-bound runtime additionally invokes its ownership guard before
 * admission/finish/reentry/cancel; the guard may read the host clock and reject
 * stale ownership. Read snapshots remain available. Serialize each WorkRun.
 * Independent runs may be operated independently.
 * All input pointers are borrowed for the call; output value structs are
 * caller-owned. Output/diagnostic storage must not alias input/owner storage.
 * _create uses the default allocator. _create_with_allocator accepts NULL for
 * default and copies callbacks/context into the owner; allocator context must
 * outlive that owner. Matching _free always uses its stored allocator.
 * Optional diagnostics are cleared on success, filled on failure.
 * Borrowed owner pointers must never be passed to _free.
 * No API transfers ownership of an input. */
/* Immutable process-lifetime name, including unknown. Never free. */
const char *golem_stage_name(golem_stage stage);
golem_status golem_stage_graph_default_spec(golem_graph_spec *out);
golem_status golem_stage_graph_create(const golem_graph_spec *spec, golem_stage_graph **out);
golem_status golem_stage_graph_create_with_allocator(const golem_graph_spec *spec,
    const golem_allocator *allocator, golem_stage_graph **out, golem_diagnostic *diagnostic);
void golem_stage_graph_free(golem_stage_graph *graph);
golem_status golem_stage_graph_spec_get(const golem_stage_graph *graph, golem_graph_spec *out);
/* End of graph returns OK and STAGE_NONE. */
golem_status golem_stage_graph_next(const golem_stage_graph *graph, golem_stage from, golem_stage *out);
golem_status golem_stage_graph_validate_transition(const golem_stage_graph *graph, golem_stage from, golem_stage to);
golem_status golem_stage_graph_reentry(const golem_stage_graph *graph, golem_stage from, golem_failure failure, golem_stage *out);
golem_status golem_stage_transition_validate(golem_stage_status from, golem_stage_status to);

/* Nonblank id/goal, nonempty scope/acceptance; optional artifacts/gates.
 * List entries must be nonblank and unique within their list. */
golem_status golem_work_capsule_create(const golem_capsule_spec *spec, golem_work_capsule **out);
golem_status golem_work_capsule_create_with_allocator(const golem_capsule_spec *spec,
    const golem_allocator *allocator, golem_work_capsule **out, golem_diagnostic *diagnostic);
void golem_work_capsule_free(golem_work_capsule *capsule);
/* Returned strings/lists/graph are immutable borrowed capsule storage. */
golem_status golem_work_capsule_spec_borrow(const golem_work_capsule *capsule, golem_capsule_spec *out);

/* Run owns a capsule copy. Positive max_attempts applies per stage across
 * the entire run, including successful attempts invalidated by recovery. */
golem_status golem_work_run_create(const char *id, const golem_work_capsule *capsule, uint32_t max_attempts, golem_work_run **out);
golem_status golem_work_run_create_with_allocator(const char *id, const golem_work_capsule *capsule,
    uint32_t max_attempts, const golem_allocator *allocator, golem_work_run **out,
    golem_diagnostic *diagnostic);
void golem_work_run_free(golem_work_run *run);
/* Immutable borrowed ID until run is freed; NULL run returns NULL. */
const char *golem_work_run_id_borrow(const golem_work_run *run);
golem_status golem_work_run_snapshot_get(const golem_work_run *run, golem_work_snapshot *out);
golem_status golem_work_run_attempts_get(const golem_work_run *run, golem_stage stage, uint32_t *out);
/* Latest attempt only. Pointer contents change on run mutation.
 * Append-only history belongs to the future journal subsystem. */
const golem_stage_run *golem_work_run_stage_borrow(const golem_work_run *run);
golem_status golem_stage_run_snapshot_get(const golem_stage_run *stage, golem_stage_snapshot *out);
/* Caller supplies authorization. DENY always rejects. ASK_ALWAYS requires
 * authorization; all modes require authorization for external effects.
 * Records lifecycle only; does not launch an agent or enforce a sandbox.
 * Compatibility wrapper over Policy Core: ASK and DENY both return POLICY_DENIED.
 * New integrations use policy.h for structured decisions and scoped requests. */
golem_status golem_work_run_begin(golem_work_run *run, bool external_effect, bool authorized, golem_stage_snapshot *out);
/* PASSED requires FAILURE_NONE and requirements_met=true.
 * requirements_met is caller attestation of acceptance/artifacts/gates/evidence,
 * not CAS verification. Final stage must also attest whole-work acceptance.
 * FAILED requires non-NONE failure and requirements_met=false. */
golem_status golem_work_run_finish(golem_work_run *run, uint64_t sequence, golem_stage_status outcome, golem_failure failure, bool requirements_met);
/* Failed work only. Clears downstream success, preserves attempt counts.
 * Rejects recovery if any stage in the rerun suffix has exhausted attempts.
 * Blocked work requires a future policy/recovery layer; no automatic resume. */
golem_status golem_work_run_reenter(golem_work_run *run);
golem_status golem_work_run_cancel(golem_work_run *run);
#ifdef __cplusplus
}
#endif
#endif
