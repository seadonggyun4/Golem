#include "internal.h"
#include "../journal/internal.h"
#include <string.h>

struct golem_replay {
    golem_allocator allocator;
    golem_replay_options options;
    char *expected_id;
    golem_work_run *run;
    golem_replay_state state;
    uint64_t records;
    size_t verified_bytes;
    size_t received_bytes;
    uint8_t header[GOLEM_JOURNAL_HEADER_SIZE];
    uint8_t *frame;
    size_t capacity;
    size_t filled;
    size_t frame_size;
    golem_digest chain_head;
    golem_journal_checkpoint checkpoint;
    bool has_checkpoint;
};

golem_status golem_replay_expect_checkpoint(golem_replay *engine,
                                            const golem_journal_checkpoint *checkpoint)
{
    if (engine == NULL || checkpoint == NULL)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (engine->state != GOLEM_REPLAY_ACTIVE || engine->received_bytes || engine->has_checkpoint)
        return GOLEM_ERR_INVALID_STATE;
    if (checkpoint->records > checkpoint->bytes / GOLEM_JOURNAL_HEADER_SIZE)
        return GOLEM_ERR_INVALID_ARGUMENT;
    engine->checkpoint = *checkpoint;
    engine->has_checkpoint = true;
    return GOLEM_OK;
}

static golem_status fail(golem_replay *engine, golem_status status, size_t offset,
                         const char *message, golem_diagnostic *d)
{
    engine->state = GOLEM_REPLAY_FAILED;
    golem_work_run_free(engine->run);
    engine->run = NULL;
    return golem_journal_report(d, status, offset, message);
}

golem_status golem_replay_create(const golem_replay_options *options,
                                 const golem_allocator *allocator, golem_replay **out,
                                 golem_diagnostic *d)
{
    golem_replay_options selected = options == NULL ? (golem_replay_options){0} : *options;
    if (out == NULL || golem_allocator_validate(allocator) != GOLEM_OK ||
        (selected.expected_run_id != NULL && selected.expected_run_id[0] == '\0') ||
        (selected.has_expected_boundary &&
         (selected.expected_records == 0 || selected.expected_bytes < GOLEM_JOURNAL_HEADER_SIZE ||
          selected.expected_records > selected.expected_bytes / GOLEM_JOURNAL_HEADER_SIZE)) ||
        (!selected.has_expected_boundary &&
         (selected.expected_records != 0 || selected.expected_bytes != 0))) {
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, "invalid replay options");
    }
    void *memory;
    golem_status status = golem_allocator_alloc(allocator, sizeof(golem_replay), &memory);
    if (status != GOLEM_OK) {
        return golem_journal_report(d, status, 0, NULL);
    }
    golem_replay *engine = memory;
    *engine = (golem_replay){0};
    engine->allocator = allocator == NULL ? golem_allocator_default() : *allocator;
    engine->options = selected;
    if (selected.expected_run_id != NULL) {
        golem_string_view id = {selected.expected_run_id, strlen(selected.expected_run_id)};
        status = golem_string_clone(id, &engine->allocator, &engine->expected_id);
        if (status != GOLEM_OK) {
            golem_replay_free(engine);
            return golem_journal_report(d, status, 0, NULL);
        }
    }
    engine->options.expected_run_id = engine->expected_id;
    *out = engine;
    return golem_journal_report(d, GOLEM_OK, 0, NULL);
}

static golem_status apply_frame(golem_replay *engine, golem_diagnostic *d)
{
    const uint8_t *data =
        engine->frame_size == GOLEM_JOURNAL_HEADER_SIZE ? engine->header : engine->frame;
    golem_journal_record record;
    size_t consumed;
    golem_diagnostic detail;
    golem_status status = golem_journal_record_decode((golem_bytes){data, engine->frame_size},
                                                      &record, &consumed, &detail);
    if (status != GOLEM_OK) {
        return fail(engine, status, engine->verified_bytes + detail.offset, detail.message, d);
    }
    if (engine->records == UINT64_MAX || record.sequence <= engine->records) {
        return fail(engine, GOLEM_ERR_CORRUPT_JOURNAL, engine->verified_bytes + 16,
                    "duplicate or reordered record", d);
    }
    if (record.sequence != engine->records + 1) {
        return fail(engine, GOLEM_ERR_MISSING_RECORD, engine->verified_bytes + 16,
                    "journal sequence gap", d);
    }
    if (record.type == GOLEM_JOURNAL_CREATED) {
        if (engine->run != NULL) {
            return fail(engine, GOLEM_ERR_INVALID_STATE, engine->verified_bytes,
                        "duplicate created record", d);
        }
        status =
            golem_journal_created_decode(record.payload, &engine->allocator, &engine->run, &detail);
        if (status != GOLEM_OK) {
            return fail(engine, status,
                        engine->verified_bytes + GOLEM_JOURNAL_HEADER_SIZE + detail.offset,
                        detail.message, d);
        }
        if (engine->expected_id != NULL &&
            strcmp(engine->expected_id, golem_work_run_id_borrow(engine->run)) != 0) {
            return fail(engine, GOLEM_ERR_REPLAY_MISMATCH, engine->verified_bytes,
                        "unexpected work run identity", d);
        }
    } else {
        if (engine->run == NULL) {
            return fail(engine, GOLEM_ERR_MISSING_RECORD, engine->verified_bytes,
                        "missing created record", d);
        }
        golem_journal_event event;
        status = golem_journal_event_decode(&record, &event, &detail);
        if (status != GOLEM_OK) {
            return fail(engine, status,
                        engine->verified_bytes + GOLEM_JOURNAL_HEADER_SIZE + detail.offset,
                        detail.message, d);
        }
        status = golem_replay_apply(engine->run, &event);
        if (status != GOLEM_OK) {
            return fail(engine, status, engine->verified_bytes, "event violates core lifecycle", d);
        }
    }
    status = golem_journal_chain_extend(&engine->chain_head, (golem_bytes){data, consumed},
                                        &engine->chain_head);
    if (status != GOLEM_OK)
        return fail(engine, status, engine->verified_bytes, "chain digest failed", d);
    ++engine->records;
    engine->verified_bytes += consumed;
    engine->filled = 0;
    engine->frame_size = 0;
    return GOLEM_OK;
}

golem_status golem_replay_feed(golem_replay *engine, golem_bytes chunk, golem_diagnostic *d)
{
    if (engine == NULL) {
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, NULL);
    }
    if (engine->state != GOLEM_REPLAY_ACTIVE) {
        return golem_journal_report(d, GOLEM_ERR_INVALID_STATE, engine->received_bytes,
                                    "replay is sealed");
    }
    if (chunk.data == NULL && chunk.size != 0) {
        return fail(engine, GOLEM_ERR_INVALID_ARGUMENT, engine->received_bytes,
                    "invalid input span", d);
    }
    if (chunk.size > SIZE_MAX - engine->received_bytes) {
        return fail(engine, GOLEM_ERR_OVERFLOW, engine->received_bytes, "stream size overflow", d);
    }
    size_t position = 0;
    while (position < chunk.size) {
        if (engine->filled < GOLEM_JOURNAL_HEADER_SIZE) {
            size_t amount = GOLEM_JOURNAL_HEADER_SIZE - engine->filled;
            if (amount > chunk.size - position) {
                amount = chunk.size - position;
            }
            memcpy(engine->header + engine->filled, chunk.data + position, amount);
            engine->filled += amount;
            engine->received_bytes += amount;
            position += amount;
            if (engine->filled < GOLEM_JOURNAL_HEADER_SIZE) {
                continue;
            }
            golem_diagnostic detail;
            golem_status status =
                golem_journal_header_check(engine->header, &engine->frame_size, &detail);
            if (status != GOLEM_OK) {
                return fail(engine, status, engine->verified_bytes + detail.offset, detail.message,
                            d);
            }
            if (engine->frame_size > GOLEM_JOURNAL_HEADER_SIZE) {
                if (engine->frame_size > engine->capacity) {
                    void *memory;
                    status = golem_allocator_alloc(&engine->allocator, engine->frame_size, &memory);
                    if (status != GOLEM_OK) {
                        return fail(engine, status, engine->verified_bytes,
                                    "cannot allocate frame buffer", d);
                    }
                    (void)golem_allocator_free(&engine->allocator, engine->frame);
                    engine->frame = memory;
                    engine->capacity = engine->frame_size;
                }
                memcpy(engine->frame, engine->header, GOLEM_JOURNAL_HEADER_SIZE);
            }
        }
        size_t amount = engine->frame_size - engine->filled;
        if (amount > chunk.size - position) {
            amount = chunk.size - position;
        }
        if (amount != 0) {
            memcpy(engine->frame + engine->filled, chunk.data + position, amount);
            engine->filled += amount;
            engine->received_bytes += amount;
            position += amount;
        }
        if (engine->filled == engine->frame_size) {
            golem_status status = apply_frame(engine, d);
            if (status != GOLEM_OK) {
                return status;
            }
        }
    }
    return golem_journal_report(d, GOLEM_OK, 0, NULL);
}

golem_status golem_replay_finish(golem_replay *engine, golem_work_run **out,
                                 golem_replay_report *report, golem_diagnostic *d)
{
    if (engine == NULL) {
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, NULL);
    }
    if (engine->state != GOLEM_REPLAY_ACTIVE) {
        return golem_journal_report(d, GOLEM_ERR_INVALID_STATE, engine->received_bytes,
                                    "replay is sealed");
    }
    if (out == NULL) {
        return fail(engine, GOLEM_ERR_INVALID_ARGUMENT, engine->received_bytes, "missing output",
                    d);
    }
    if (engine->filled != 0) {
        return fail(engine, GOLEM_ERR_TRUNCATED_JOURNAL, engine->received_bytes,
                    "incomplete trailing record", d);
    }
    if (engine->run == NULL) {
        return fail(engine, GOLEM_ERR_MISSING_RECORD, 0, "missing created record", d);
    }
    if (engine->options.has_expected_boundary) {
        if (engine->records < engine->options.expected_records) {
            return fail(engine, GOLEM_ERR_MISSING_RECORD, engine->verified_bytes,
                        "missing expected tail records", d);
        }
        if (engine->records != engine->options.expected_records ||
            (uint64_t)engine->verified_bytes != engine->options.expected_bytes) {
            return fail(engine, GOLEM_ERR_REPLAY_MISMATCH, engine->verified_bytes,
                        "unexpected replay endpoint", d);
        }
    }
    golem_replay_report result;
    if (engine->has_checkpoint && (engine->checkpoint.records != engine->records ||
                                   engine->checkpoint.bytes != engine->verified_bytes ||
                                   memcmp(engine->checkpoint.chain_head.bytes,
                                          engine->chain_head.bytes, GOLEM_DIGEST_SIZE) != 0))
        return fail(engine, GOLEM_ERR_DIGEST_MISMATCH, engine->verified_bytes,
                    "journal checkpoint mismatch", d);
    golem_replay_report_fill(engine->run, engine->records, engine->verified_bytes, &result);
    if (engine->options.require_terminal && result.work.status != GOLEM_WORK_SUCCEEDED &&
        result.work.status != GOLEM_WORK_CANCELLED) {
        return fail(engine, GOLEM_ERR_INCOMPLETE_WORK, engine->verified_bytes,
                    "terminal work state required", d);
    }
    *out = engine->run;
    engine->run = NULL;
    engine->state = GOLEM_REPLAY_FINISHED;
    if (report != NULL) {
        *report = result;
    }
    return golem_journal_report(d, GOLEM_OK, 0, NULL);
}

golem_status golem_replay_progress_get(const golem_replay *engine, golem_replay_progress *out)
{
    if (engine == NULL || out == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = (golem_replay_progress){engine->state, engine->records, engine->verified_bytes,
                                   engine->filled};
    return GOLEM_OK;
}

void golem_replay_free(golem_replay *engine)
{
    if (engine != NULL) {
        golem_work_run_free(engine->run);
        (void)golem_allocator_free(&engine->allocator, engine->expected_id);
        (void)golem_allocator_free(&engine->allocator, engine->frame);
        (void)golem_allocator_free(&engine->allocator, engine);
    }
}
