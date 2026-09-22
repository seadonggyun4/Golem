#define _POSIX_C_SOURCE 200809L
#include "golem/runtime.h"
#include "golem/policy.h"
#include "golem/replay.h"
#include "../core/internal.h"
#include <string.h>
#include <time.h>

struct golem_runtime {
    golem_allocator allocator;
    golem_work_run *run;
    golem_runtime_options options;
    golem_runtime_ops ops;
    void *context;
    uint8_t *created;
    size_t created_size;
    uint64_t dispatched, reentries, last_clock;
    bool initialized, busy, stopped, clock_seen;
    golem_status reason;
    golem_lease *lease;
    golem_lease_token token;
    bool checking;
    bool stepped;
};

static golem_status clock_read(golem_runtime *r, uint64_t *out)
{
    uint64_t value;
    if (r->ops.now != NULL) {
        golem_status s = r->ops.now(r->context, &value);
        if (s != GOLEM_OK) return s;
    } else {
        struct timespec t;
        if (clock_gettime(CLOCK_MONOTONIC, &t) != 0 || t.tv_sec < 0 || t.tv_nsec < 0 || t.tv_nsec >= 1000000000L) return GOLEM_ERR_IO;
        if ((uint64_t)t.tv_sec > (UINT64_MAX - (uint64_t)t.tv_nsec) / 1000000000u) return GOLEM_ERR_OVERFLOW;
        value = (uint64_t)t.tv_sec * 1000000000u + (uint64_t)t.tv_nsec;
    }
    if (r->clock_seen && value < r->last_clock) return GOLEM_ERR_INVALID_STATE;
    r->clock_seen = true; r->last_clock = value; *out = value; return GOLEM_OK;
}
static golem_status initialize(golem_runtime *r)
{
    if (r->initialized) return GOLEM_OK;
    golem_status s = r->ops.record(r->context, GOLEM_JOURNAL_CREATED,
        (golem_bytes){r->created, r->created_size});
    if (s == GOLEM_OK) r->initialized = true;
    return s;
}
static golem_status emit(golem_runtime *r, const golem_journal_event *event)
{
    golem_status checked = golem_runtime_checkpoint(r);
    if (checked != GOLEM_OK) return checked;
    uint8_t bytes[GOLEM_JOURNAL_EVENT_SIZE]; size_t required;
    golem_status s = golem_journal_event_encode(event, bytes, sizeof(bytes), &required, NULL);
    if (s == GOLEM_OK) s = r->ops.record(r->context, event->type, (golem_bytes){bytes, required});
    return s == GOLEM_OK ? golem_runtime_checkpoint(r) : s;
}
static golem_status leave(golem_runtime *r, golem_status s)
{
    golem_work_snapshot work; (void)golem_work_run_snapshot_get(r->run, &work);
    if (s != GOLEM_OK || work.status == GOLEM_WORK_SUCCEEDED || work.status == GOLEM_WORK_CANCELLED) {
        r->stopped = true; r->reason = s;
    }
    r->busy = false; return s;
}
golem_status golem_runtime_create(const char *id, const golem_work_capsule *capsule,
    const golem_runtime_options *options, const golem_runtime_ops *ops, void *context,
    const golem_allocator *allocator, golem_runtime **out)
{
    if (options == NULL || ops == NULL || out == NULL || capsule == NULL || id == NULL ||
        options->max_attempts == 0 || options->max_stage_runs == 0 || ops->execute == NULL || ops->record == NULL)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (options->version != GOLEM_RUNTIME_VERSION) return GOLEM_ERR_UNSUPPORTED_VERSION;
    golem_status s = golem_allocator_validate(allocator);
    if (s != GOLEM_OK) return s;
    void *memory = NULL; s = golem_allocator_alloc(allocator, sizeof(golem_runtime), &memory);
    if (s != GOLEM_OK) return s;
    golem_runtime *r = memory; *r = (golem_runtime){0};
    r->allocator = allocator == NULL ? golem_allocator_default() : *allocator;
    r->options = *options; r->ops = *ops; r->context = context;
    s = golem_work_run_create_with_allocator(id, capsule, options->max_attempts, &r->allocator, &r->run, NULL);
    if (s == GOLEM_OK) {
        s = golem_journal_created_encode(id, capsule, options->max_attempts, NULL, 0, &r->created_size, NULL);
        if (s == GOLEM_ERR_BUFFER_TOO_SMALL) {
            void *buffer = NULL; s = golem_allocator_alloc(&r->allocator, r->created_size, &buffer); r->created = buffer;
            if (s == GOLEM_OK) s = golem_journal_created_encode(id, capsule, options->max_attempts, r->created, r->created_size, &r->created_size, NULL);
        }
    }
    if (s != GOLEM_OK) { golem_runtime_free(r); return s; }
    *out = r; return GOLEM_OK;
}
void golem_runtime_free(golem_runtime *r)
{
    if (r == NULL) return;
    golem_work_run_free(r->run);
    (void)golem_allocator_free(&r->allocator, r->created);
    golem_allocator a = r->allocator; (void)golem_allocator_free(&a, r);
}
golem_status golem_runtime_recover(golem_journal *journal, const golem_runtime_options *options,
    const golem_runtime_ops *ops, void *context, const golem_allocator *allocator, golem_runtime **out)
{
    if (journal == NULL || options == NULL || ops == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_work_run *run = NULL; golem_replay_report report;
    golem_status s = golem_journal_recover(journal, NULL, &run, &report, NULL);
    if (s != GOLEM_OK) return s;
    if ((run->status != GOLEM_WORK_READY && run->status != GOLEM_WORK_FAILED) || run->max_attempts != options->max_attempts) {
        golem_work_run_free(run); return GOLEM_ERR_INVALID_STATE;
    }
    golem_runtime *r = NULL;
    s = golem_runtime_create(run->id, run->capsule, options, ops, context, allocator, &r);
    if (s == GOLEM_OK) {
        /* Copy replayed state into the run allocated by the requested allocator. */
        r->run->status = run->status; r->run->position = run->position;
        memcpy(r->run->passed, run->passed, sizeof(run->passed));
        memcpy(r->run->attempts, run->attempts, sizeof(run->attempts));
        r->run->sequence = run->sequence; r->run->latest = run->latest;
        r->initialized = true; r->dispatched = run->sequence;
        r->reentries = report.verified_records - 1 - 2 * run->sequence;
        *out = r;
    }
    golem_work_run_free(run); return s;
}
golem_status golem_runtime_step(golem_runtime *r)
{
    if (r == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->busy || r->checking) return GOLEM_ERR_INVALID_STATE;
    if (r->stopped) return r->reason;
    r->stepped = true;
    r->busy = true;
    golem_status s = golem_runtime_checkpoint(r); if (s != GOLEM_OK) return leave(r, s);
    s = initialize(r); if (s != GOLEM_OK) return leave(r, s);
    s = golem_runtime_checkpoint(r); if (s != GOLEM_OK) return leave(r, s);
    golem_work_snapshot work; (void)golem_work_run_snapshot_get(r->run, &work);
    if (work.status == GOLEM_WORK_BLOCKED) return leave(r, GOLEM_ERR_POLICY_DENIED);
    if (r->dispatched >= r->options.max_stage_runs) return leave(r, GOLEM_ERR_ATTEMPT_LIMIT);
    if (work.status == GOLEM_WORK_FAILED) {
        s = golem_work_run_reenter(r->run); if (s != GOLEM_OK) return leave(r, s);
        (void)golem_work_run_snapshot_get(r->run, &work);
        golem_journal_event e = {.type = GOLEM_JOURNAL_REENTERED, .stage = work.current_stage};
        ++r->reentries;
        s = emit(r, &e); if (s != GOLEM_OK) return leave(r, s);
    }
    uint64_t start = 0, deadline = 0;
    if (r->options.timeout_ns != 0) {
        s = clock_read(r, &start); if (s != GOLEM_OK) return leave(r, s);
        if (r->options.timeout_ns > UINT64_MAX - start) return leave(r, GOLEM_ERR_OVERFLOW);
        deadline = start + r->options.timeout_ns;
    }
    golem_stage_permission_request permission;
    s = golem_work_run_permission_request(r->run, GOLEM_EFFECT_LOCAL, &permission, NULL);
    if (s != GOLEM_OK) return leave(r, s);
    golem_stage_snapshot stage;
    s = golem_work_run_begin_authorized(r->run, &permission, &stage, NULL, NULL);
    if (s != GOLEM_OK) return leave(r, s);
    golem_journal_event event = {.type = GOLEM_JOURNAL_STARTED, .stage = stage.stage,
        .attempt = stage.attempt, .attempt_sequence = stage.sequence, .outcome = GOLEM_STAGE_RUNNING};
    s = emit(r, &event); if (s != GOLEM_OK) return leave(r, s);
    golem_runtime_result result = {0};
    ++r->dispatched;
    s = r->ops.execute(r->context, r->run, &stage, deadline, &result);
    golem_status owned = golem_runtime_checkpoint(r);
    if (owned != GOLEM_OK) return leave(r, owned);
    if (s != GOLEM_OK) return leave(r, s);
    if (result.sequence != stage.sequence) return leave(r, GOLEM_ERR_STALE_RESULT);
    if ((result.outcome != GOLEM_STAGE_PASSED && result.outcome != GOLEM_STAGE_FAILED) ||
        (result.outcome == GOLEM_STAGE_PASSED && (result.failure != GOLEM_FAILURE_NONE || !result.requirements_met)) ||
        (result.outcome == GOLEM_STAGE_FAILED && (result.failure <= GOLEM_FAILURE_NONE || result.failure >= GOLEM_FAILURE_COUNT || result.requirements_met)))
        return leave(r, GOLEM_ERR_INVALID_ARGUMENT);
    if (deadline != 0) {
        uint64_t end; s = clock_read(r, &end); if (s != GOLEM_OK) return leave(r, s);
        if (end >= deadline && result.failure != GOLEM_FAILURE_POLICY_DENIED &&
            result.failure != GOLEM_FAILURE_STALE_LEASE && result.failure != GOLEM_FAILURE_BUDGET_EXHAUSTED)
            result = (golem_runtime_result){stage.sequence, GOLEM_STAGE_FAILED, GOLEM_FAILURE_TIMEOUT, false};
    }
    s = golem_work_run_finish(r->run, stage.sequence, result.outcome, result.failure, result.requirements_met);
    if (s != GOLEM_OK) return leave(r, s);
    event.type = GOLEM_JOURNAL_FINISHED; event.outcome = result.outcome; event.failure = result.failure; event.requirements_met = result.requirements_met;
    s = emit(r, &event); return leave(r, s);
}
golem_status golem_runtime_drive(golem_runtime *r)
{
    if (r == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->busy || r->checking) return GOLEM_ERR_INVALID_STATE;
    while (!r->stopped) {
        golem_status s = golem_runtime_step(r); if (s != GOLEM_OK) return s;
    }
    return r->reason;
}
golem_status golem_runtime_cancel(golem_runtime *r)
{
    if (r == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->busy || r->checking) return GOLEM_ERR_INVALID_STATE;
    golem_work_snapshot work; (void)golem_work_run_snapshot_get(r->run, &work);
    if (r->stopped) return work.status == GOLEM_WORK_CANCELLED && r->reason == GOLEM_OK ? GOLEM_OK : GOLEM_ERR_INVALID_STATE;
    r->busy = true;
    golem_status s = golem_runtime_checkpoint(r);
    if (s == GOLEM_OK) s = initialize(r);
    if (s == GOLEM_OK) s = golem_work_run_cancel(r->run);
    golem_journal_event event = {.type = GOLEM_JOURNAL_CANCELLED, .stage = GOLEM_STAGE_NONE};
    if (s == GOLEM_OK) s = emit(r, &event);
    return leave(r, s);
}
golem_status golem_runtime_report_get(const golem_runtime *r, golem_runtime_report *out)
{
    if (r == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_runtime_report report = {.dispatched = r->dispatched, .reentries = r->reentries, .stopped = r->stopped, .stop_reason = r->reason};
    (void)golem_work_run_snapshot_get(r->run, &report.work); *out = report; return GOLEM_OK;
}
const golem_work_run *golem_runtime_run_borrow(const golem_runtime *r) { return r == NULL ? NULL : r->run; }

static golem_status ownership_guard(void *context) { return golem_runtime_checkpoint(context); }
golem_status golem_runtime_lease_bind(golem_runtime *r, golem_lease *lease, const golem_lease_token *token)
{
    if (r == NULL || lease == NULL || token == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->busy || r->checking || r->stepped || r->stopped || r->lease != NULL) return GOLEM_ERR_INVALID_STATE;
    if (strcmp(golem_lease_resource_borrow(lease), golem_work_run_id_borrow(r->run)) != 0) return GOLEM_ERR_IDENTITY_MISMATCH;
    r->checking = true;
    uint64_t now; golem_status s = clock_read(r, &now);
    if (s == GOLEM_OK) s = golem_lease_validate(lease, token, now);
    r->checking = false;
    if (s != GOLEM_OK) return s;
    r->lease = lease; r->token = *token;
    r->run->ownership_check = ownership_guard; r->run->ownership_context = r;
    return GOLEM_OK;
}
golem_status golem_runtime_checkpoint(golem_runtime *r)
{
    if (r == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->checking) return GOLEM_ERR_INVALID_STATE;
    if (r->stopped) return r->reason == GOLEM_OK ? GOLEM_ERR_INVALID_STATE : r->reason;
    if (r->lease == NULL) return GOLEM_OK;
    r->checking = true;
    uint64_t now; golem_status s = clock_read(r, &now);
    if (s == GOLEM_OK) s = golem_lease_validate(r->lease, &r->token, now);
    r->checking = false;
    if (s != GOLEM_OK) { r->stopped = true; r->reason = s; }
    return s;
}
golem_status golem_runtime_heartbeat(golem_runtime *r, uint64_t ttl, golem_lease_snapshot *out)
{
    if (r == NULL || out == NULL || ttl == 0) return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->checking || r->lease == NULL || r->stopped) return GOLEM_ERR_INVALID_STATE;
    r->checking = true;
    uint64_t now; golem_status s = clock_read(r, &now);
    if (s == GOLEM_OK) s = golem_lease_heartbeat(r->lease, &r->token, now, ttl, out);
    r->checking = false;
    if (s != GOLEM_OK) { r->stopped = true; r->reason = s; }
    return s;
}
