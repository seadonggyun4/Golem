#include "internal.h"
#include "golem/replay.h"

golem_status golem_journal_replay(golem_bytes bytes, const golem_allocator *allocator,
    golem_work_run **out, golem_diagnostic *d)
{
    if (out == NULL || (bytes.data == NULL && bytes.size != 0) ||
        golem_allocator_validate(allocator) != GOLEM_OK) {
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, NULL);
    }
    golem_replay *engine = NULL;
    golem_status status = golem_replay_create(NULL, allocator, &engine, d);
    if (status == GOLEM_OK) {
        status = golem_replay_feed(engine, bytes, d);
    }
    if (status == GOLEM_OK) {
        status = golem_replay_finish(engine, out, NULL, d);
    }
    golem_replay_free(engine);
    /* Keep v1 one-shot callers' corruption category for missing framing.
     * The new engine exposes the more specific MISSING_RECORD status. */
    if (status == GOLEM_ERR_MISSING_RECORD) {
        status = GOLEM_ERR_CORRUPT_JOURNAL;
        golem_journal_record first;
        size_t consumed;
        if (golem_journal_record_decode(bytes, &first, &consumed, NULL) == GOLEM_OK &&
            first.sequence == 1 && first.type != GOLEM_JOURNAL_CREATED) {
            status = GOLEM_ERR_INVALID_STATE;
        }
        if (d != NULL) {
            d->status = status;
        }
    }
    return status;
}
