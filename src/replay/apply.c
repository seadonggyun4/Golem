#include "internal.h"
#include "../core/internal.h"

golem_status golem_replay_apply(golem_work_run *run, const golem_journal_event *event)
{
    golem_stage_snapshot stage;
    golem_work_snapshot work;
    golem_status status;
    switch (event->type) {
    case GOLEM_JOURNAL_STARTED:
        status = golem_work_run_begin(run, event->external_effect, event->authorized, &stage);
        if (status != GOLEM_OK) {
            return status;
        }
        /* Journal v1 cannot prove whether a provider invocation already occurred. */
        run->latest.adapter_dispatched = true;
        return stage.stage == event->stage && stage.attempt == event->attempt &&
            stage.sequence == event->attempt_sequence ? GOLEM_OK : GOLEM_ERR_INVALID_STATE;
    case GOLEM_JOURNAL_FINISHED: {
        const golem_stage_run *latest = golem_work_run_stage_borrow(run);
        if (latest == NULL) {
            return GOLEM_ERR_INVALID_STATE;
        }
        (void)golem_stage_run_snapshot_get(latest, &stage);
        if (stage.stage != event->stage || stage.attempt != event->attempt ||
            stage.sequence != event->attempt_sequence) {
            return GOLEM_ERR_STALE_RESULT;
        }
        return golem_work_run_finish(run, event->attempt_sequence, event->outcome,
                                         event->failure, event->requirements_met);
    }
    case GOLEM_JOURNAL_REENTERED:
        status = golem_work_run_reenter(run);
        if (status != GOLEM_OK) {
            return status;
        }
        (void)golem_work_run_snapshot_get(run, &work);
        return work.current_stage == event->stage ? GOLEM_OK : GOLEM_ERR_INVALID_STATE;
    case GOLEM_JOURNAL_CANCELLED:
        return golem_work_run_cancel(run);
    default:
        return GOLEM_ERR_CORRUPT_JOURNAL;
    }
}

void golem_replay_report_fill(const golem_work_run *run,
    uint64_t records, uint64_t bytes, golem_replay_report *out)
{
    golem_replay_report report = {0};
    report.verified_records = records;
    report.verified_bytes = bytes;
    report.next_record_sequence = records == UINT64_MAX ? 0 : records + 1;
    report.latest_attempt.stage = GOLEM_STAGE_NONE;
    (void)golem_work_run_snapshot_get(run, &report.work);
    const golem_stage_run *latest = golem_work_run_stage_borrow(run);
    if (latest != NULL) {
        report.has_latest_attempt = true;
        (void)golem_stage_run_snapshot_get(latest, &report.latest_attempt);
    }
    switch (report.work.status) {
    case GOLEM_WORK_READY:
        report.action = GOLEM_RECOVERY_CHECK_POLICY;
        break;
    case GOLEM_WORK_RUNNING:
        report.action = GOLEM_RECOVERY_RECONCILE_ATTEMPT;
        break;
    case GOLEM_WORK_FAILED:
        report.action = GOLEM_RECOVERY_EVALUATE_REENTRY;
        break;
    case GOLEM_WORK_BLOCKED:
        report.action = GOLEM_RECOVERY_RESOLVE_BLOCK;
        break;
    case GOLEM_WORK_SUCCEEDED:
    case GOLEM_WORK_CANCELLED:
        report.action = GOLEM_RECOVERY_NONE;
        break;
    }
    *out = report;
}
