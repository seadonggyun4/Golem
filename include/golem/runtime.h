#ifndef GOLEM_RUNTIME_H
#define GOLEM_RUNTIME_H
#include "golem/journal.h"
#include "golem/lease.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_RUNTIME_VERSION 1u
typedef struct golem_runtime golem_runtime;
typedef struct golem_runtime_options {
    uint32_t version;
    uint32_t max_attempts; /* Core per-stage limit, including invalidated passes. */
    uint64_t max_stage_runs; /* Positive total callback limit, including retries. */
    uint64_t timeout_ns; /* Zero disables; elapsed >= timeout is expired. */
} golem_runtime_options;
typedef struct golem_runtime_result {
    uint64_t sequence; /* Must match the executing attempt. */
    golem_stage_status outcome;
    golem_failure failure;
    bool requirements_met; /* Trusted acceptance/evidence attestation, not inferred. */
} golem_runtime_result;
typedef struct golem_runtime_ops {
    /* Required append-only durable sink. Borrowed payload valid only for call.
     * Called for CREATED, STARTED, FINISHED, REENTERED and CANCELLED. Host may
     * directly call journal_append. OK must mean durable commit, not queued I/O.
     * Any error is ambiguous: runtime stops permanently, never retries append. */
    golem_status (*record)(void *context, golem_journal_type type, golem_bytes payload);
    /* Required synchronous local executor. run is borrowed exclusively for
     * adapter_dispatch / usage reporting; NEVER finish, reenter, cancel, free,
     * retain or otherwise mutate its lifecycle. Result/evidence must be durable
     * before OK. Non-OK may have caused effects: runtime stops with RUNNING
     * unreconciled. Return OK + FAILED for a classified, safely retryable failure.
     * Deadline is absolute monotonic ns; zero means disabled. Returning implies
     * all work is quiescent: NEVER leave a child/task running into a retry.
     * No implicit acceptance, provider execution, CAS verification or sandbox. */
    golem_status (*execute)(void *context, golem_work_run *run,
        const golem_stage_snapshot *stage, uint64_t deadline_ns, golem_runtime_result *out);
    /* Optional clock; NULL uses CLOCK_MONOTONIC. Required only when timeout is
     * enabled or a lease is bound. Errors/backward clocks stop the runtime.
     * Must not mutate run or call heartbeat/checkpoint recursively. */
    golem_status (*now)(void *context, uint64_t *nanoseconds);
} golem_runtime_ops;
typedef struct golem_runtime_report {
    golem_work_snapshot work;
    uint64_t dispatched;
    uint64_t reentries;
    bool stopped; /* Includes successful/cancelled terminal state. */
    golem_status stop_reason;
} golem_runtime_report;

/* Single-threaded local runtime, no background threads or global state. Create
 * deep-copies capsule/id/options/ops/allocator, BORROWS callback context until
 * free. Owns its WorkRun. Allocator context must outlive free. No I/O at create.
 * Inputs borrowed only for call, outputs unchanged on error. No aliasing.
 * record is mandatory so no execution silently escapes the journal contract.
 * Serialize calls; callbacks cannot reenter step/drive/cancel/free. Reentry is
 * rejected, not queued. Free is only valid outside callbacks. NULL free is safe.
 * Recovery accepts only safe journal boundaries; RUNNING needs reconciliation.
 * No authorization grants; every attempt is LOCAL with NONE authorization. */
golem_status golem_runtime_create(const char *id, const golem_work_capsule *capsule,
    const golem_runtime_options *options, const golem_runtime_ops *ops, void *context,
    const golem_allocator *allocator, golem_runtime **out);
void golem_runtime_free(golem_runtime *runtime);
/* Recover from a caller-held locked journal, retaining history/attempt limits.
 * Only READY/FAILED accepted; RUNNING, BLOCKED and terminal runs are rejected.
 * max_attempts must match CREATED; dispatch/reentry counts are reconstructed.
 * Host MUST verify its persisted evidence and supervision state before calling.
 * No old lease is restored. Bind a newly acquired lease before executing.
 * Borrows journal only during call; ops/context/allocator ownership as create.
 * Output unchanged on error; journal recovery errors may poison its handle. */
golem_status golem_runtime_recover(golem_journal *journal, const golem_runtime_options *options,
    const golem_runtime_ops *ops, void *context, const golem_allocator *allocator, golem_runtime **out);
/* One step executes at most one callback, including optional classified-failure
 * reentry. drive repeats steps until completion or stop. All infrastructure,
 * policy, limit and validation errors latch permanently; inspecting remains safe.
 * Errors can leave changed Core/durable records, never imply rollback. Successful
 * domain FAILED is recorded then reentered on the next step using StageGraph.
 * Unknown/no target and policy/lease/budget blocks never retry. Timeout is
 * cooperative: cannot interrupt a hung callback. Late valid local results become
 * FAILED/TIMEOUT, except blocking failures remain blocked. Callback errors never
 * become retryable timeout. Deadline includes STARTED persistence + execution.
 * Repeated drive/step on terminal/stopped runtime return its same stop reason. */
golem_status golem_runtime_step(golem_runtime *runtime);
golem_status golem_runtime_drive(golem_runtime *runtime);
/* Between steps only. Does not interrupt callbacks or reconcile uncertain work.
 * Idempotent after successful cancellation; rejects any other stopped runtime. */
golem_status golem_runtime_cancel(golem_runtime *runtime);
golem_status golem_runtime_report_get(const golem_runtime *runtime, golem_runtime_report *out);
/* Immutable borrowed owner, valid until runtime free; NULL runtime -> NULL.
 * State changes on step/cancel; no ownership transfer or mutation allowed. */
const golem_work_run *golem_runtime_run_borrow(const golem_runtime *runtime);
/* Opt-in ownership for compatibility with unleased Phase 13 callers. Bind ONCE,
 * before first step/cancel; resource must equal WorkRun ID. Copies token, BORROWS
 * authority until runtime_free. All authority/runtime calls serialized, same
 * monotonic clock domain. Cannot detach/rebind/revive after losing ownership.
 * Runtime free never implicitly releases the host's lease. No grants inferred.
 * Legacy unbound instances are intentionally not ownership-protected. */
golem_status golem_runtime_lease_bind(golem_runtime *runtime, golem_lease *lease,
    const golem_lease_token *token);
/* Cooperative continuation check, callable between steps and inside execute.
 * Also enforced by bound Core admission/finish/reentry/cancel and adapter dispatch
 * before/after callbacks. Failure permanently stops runtime; late results never
 * finish Core. Host must call before each custom tool/side effect. Cannot interrupt
 * a hung callback, undo effects or fence an external system that ignores tokens.
 * Journal v1 does not restore ownership; replay is never a renewed lease. */
golem_status golem_runtime_checkpoint(golem_runtime *runtime);
/* Explicit heartbeat, including inside synchronous execute. No background timer.
 * Uses bound token/clock and durable authority sink. Failure latches stop (except
 * invalid NULL output/zero TTL). No renewal after expiry/release/takeover. */
golem_status golem_runtime_heartbeat(golem_runtime *runtime, uint64_t ttl_ns,
    golem_lease_snapshot *out);
#ifdef __cplusplus
}
#endif
#endif
