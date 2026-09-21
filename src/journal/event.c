#include "internal.h"
#include <string.h>

/* Wire values are deliberately pinned; enum edits require a schema decision. */
_Static_assert(GOLEM_STAGE_PLANNING == 0 && GOLEM_STAGE_UX == 1 &&
    GOLEM_STAGE_PUBLISHING == 2 && GOLEM_STAGE_DEVELOPMENT == 3 &&
    GOLEM_STAGE_QA == 4 && GOLEM_STAGE_AUDIT == 5 && GOLEM_STAGE_NONE == 6, "stage v1");
_Static_assert(GOLEM_STAGE_PENDING == 0 && GOLEM_STAGE_RUNNING == 1 &&
    GOLEM_STAGE_PASSED == 2 && GOLEM_STAGE_FAILED == 3, "outcome v1");
_Static_assert(GOLEM_FAILURE_NONE == 0 && GOLEM_FAILURE_PLANNING_GAP == 1 &&
    GOLEM_FAILURE_UX_MISMATCH == 2 && GOLEM_FAILURE_PUBLISHING_GAP == 3 &&
    GOLEM_FAILURE_IMPLEMENTATION_DEFECT == 4 && GOLEM_FAILURE_QA_FLAKE == 5 &&
    GOLEM_FAILURE_AUDIT_GAP == 6 && GOLEM_FAILURE_POLICY_DENIED == 7 &&
    GOLEM_FAILURE_STALE_LEASE == 8 && GOLEM_FAILURE_BUDGET_EXHAUSTED == 9 &&
    GOLEM_FAILURE_TIMEOUT == 10 && GOLEM_FAILURE_UNKNOWN == 11 &&
    GOLEM_FAILURE_COUNT == 12, "failure v1");
_Static_assert(GOLEM_AUTONOMY_DENY == 0 && GOLEM_AUTONOMY_AUTO_LOCAL == 1 &&
    GOLEM_AUTONOMY_ASK_ON_EXTERNAL_EFFECT == 2 && GOLEM_AUTONOMY_ASK_ALWAYS == 3, "permission v1");

static bool event_valid(const golem_journal_event *e)
{
    if (e == NULL) return false;
    bool stage_valid = e->stage >= GOLEM_STAGE_PLANNING && e->stage < GOLEM_STAGE_COUNT;
    if (e->type == GOLEM_JOURNAL_STARTED)
        return stage_valid && e->attempt > 0 && e->attempt_sequence > 0 &&
            e->outcome == GOLEM_STAGE_RUNNING && e->failure == GOLEM_FAILURE_NONE && !e->requirements_met;
    if (e->type == GOLEM_JOURNAL_FINISHED)
        return stage_valid && e->attempt > 0 && e->attempt_sequence > 0 && !e->external_effect && !e->authorized &&
            ((e->outcome == GOLEM_STAGE_PASSED && e->failure == GOLEM_FAILURE_NONE && e->requirements_met) ||
             (e->outcome == GOLEM_STAGE_FAILED && e->failure > GOLEM_FAILURE_NONE &&
              e->failure < GOLEM_FAILURE_COUNT && !e->requirements_met));
    return ((e->type == GOLEM_JOURNAL_REENTERED && stage_valid) ||
            (e->type == GOLEM_JOURNAL_CANCELLED && e->stage == GOLEM_STAGE_NONE)) &&
        e->attempt == 0 && e->attempt_sequence == 0 && e->outcome == GOLEM_STAGE_PENDING &&
        e->failure == GOLEM_FAILURE_NONE && !e->external_effect && !e->authorized && !e->requirements_met;
}
golem_status golem_journal_event_encode(const golem_journal_event *event,
    void *destination, size_t capacity, size_t *required, golem_diagnostic *d)
{
    if (!event_valid(event) || required == NULL || (destination == NULL && capacity != 0))
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, "invalid event");
    if (capacity < GOLEM_JOURNAL_EVENT_SIZE) {
        *required = GOLEM_JOURNAL_EVENT_SIZE;
        return golem_journal_report(d, GOLEM_ERR_BUFFER_TOO_SMALL, 0, NULL);
    }
    uint8_t *p = destination;
    memset(p, 0, GOLEM_JOURNAL_EVENT_SIZE);
    golem_journal_put32(p, (uint32_t)event->stage);
    golem_journal_put32(p + 4, event->attempt);
    golem_journal_put64(p + 8, event->attempt_sequence);
    golem_journal_put32(p + 16, (uint32_t)event->outcome);
    golem_journal_put32(p + 20, (uint32_t)event->failure);
    golem_journal_put32(p + 24, (event->external_effect ? 1u : 0u) |
        (event->authorized ? 2u : 0u) | (event->requirements_met ? 4u : 0u));
    *required = GOLEM_JOURNAL_EVENT_SIZE;
    return golem_journal_report(d, GOLEM_OK, 0, NULL);
}
golem_status golem_journal_event_decode(const golem_journal_record *record,
    golem_journal_event *out, golem_diagnostic *d)
{
    if (record == NULL || out == NULL || (record->payload.data == NULL && record->payload.size != 0))
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, NULL);
    if (record->payload.size != GOLEM_JOURNAL_EVENT_SIZE)
        return golem_journal_report(d, GOLEM_ERR_CORRUPT_JOURNAL, 0, "invalid event size");
    const uint8_t *p = record->payload.data;
    uint32_t stage = golem_journal_u32(p), outcome = golem_journal_u32(p + 16);
    uint32_t failure = golem_journal_u32(p + 20), flags = golem_journal_u32(p + 24);
    if (stage > 6 || outcome > 3 || failure >= 12 || flags > 7 || golem_journal_u32(p + 28) != 0)
        return golem_journal_report(d, GOLEM_ERR_CORRUPT_JOURNAL, 0, "invalid event fields");
    golem_journal_event event = {record->type, (golem_stage)stage,
        golem_journal_u32(p + 4), golem_journal_u64(p + 8),
        (golem_stage_status)outcome, (golem_failure)failure,
        (flags & 1) != 0, (flags & 2) != 0, (flags & 4) != 0};
    if (!event_valid(&event))
        return golem_journal_report(d, GOLEM_ERR_CORRUPT_JOURNAL, 0, "noncanonical event");
    *out = event;
    return golem_journal_report(d, GOLEM_OK, 0, NULL);
}
