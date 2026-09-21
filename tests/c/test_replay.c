#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/replay.h"
#include "journal_fixture.h"
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>

static golem_status replay_bytes(golem_bytes bytes, const golem_replay_options *options,
    const golem_allocator *allocator, golem_work_run **out, golem_replay_report *report)
{
    golem_replay *engine = NULL;
    golem_status status = golem_replay_create(options, allocator, &engine, NULL);
    if (status == GOLEM_OK) status = golem_replay_feed(engine, bytes, NULL);
    if (status == GOLEM_OK) status = golem_replay_finish(engine, out, report, NULL);
    golem_replay_free(engine);
    return status;
}
static int boundaries(golem_bytes bytes, size_t *offsets, size_t *count)
{
    golem_journal_reader reader;
    CHECK(golem_journal_reader_init(&reader, bytes) == GOLEM_OK);
    size_t n = 0;
    offsets[0] = 0;
    while (reader.offset < bytes.size) {
        golem_journal_record record;
        bool has;
        CHECK(n < 63);
        CHECK(golem_journal_reader_next(&reader, &record, &has, NULL) == GOLEM_OK && has);
        offsets[++n] = reader.offset;
    }
    *count = n;
    return EXIT_SUCCESS;
}
static int test_chunks(void)
{
    uint8_t bytes[FIXTURE_CAPACITY];
    size_t size;
    CHECK(load_fixture("default", bytes, &size) == EXIT_SUCCESS);
    /* Exercise every possible two-chunk split, including empty chunks. */
    for (size_t split = 0; split <= size; ++split) {
        golem_replay *engine = NULL;
        CHECK(golem_replay_create(NULL, NULL, &engine, NULL) == GOLEM_OK);
        CHECK(golem_replay_feed(engine, (golem_bytes){bytes, split}, NULL) == GOLEM_OK);
        CHECK(golem_replay_feed(engine, (golem_bytes){bytes + split, size - split}, NULL) == GOLEM_OK);
        golem_work_run *run = NULL;
        golem_replay_report report;
        CHECK(golem_replay_finish(engine, &run, &report, NULL) == GOLEM_OK);
        CHECK(report.verified_records == 13 && report.verified_bytes == size);
        CHECK(report.next_record_sequence == 14 && report.work.status == GOLEM_WORK_SUCCEEDED);
        CHECK(report.action == GOLEM_RECOVERY_NONE && report.latest_attempt.stage == GOLEM_STAGE_AUDIT);
        golem_replay_free(engine);
        CHECK(strcmp(golem_work_run_id_borrow(run), "run-golden") == 0);
        golem_work_run_free(run);
    }
    const size_t steps[] = {1, 2, 7, 31, 32, 33, 64, 16384};
    CHECK(load_fixture("reentry", bytes, &size) == EXIT_SUCCESS);
    for (size_t i = 0; i < sizeof(steps) / sizeof(steps[0]); ++i) {
        char identity[] = "run-golden";
        golem_replay_options options = {identity, true, 22, size, true};
        golem_replay *engine = NULL;
        CHECK(golem_replay_create(&options, NULL, &engine, NULL) == GOLEM_OK);
        identity[0] = 'X';
        options.expected_records = 999;
        for (size_t offset = 0; offset < size;) {
            size_t amount = size - offset < steps[i] ? size - offset : steps[i];
            uint8_t chunk[FIXTURE_CAPACITY];
            memcpy(chunk, bytes + offset, amount);
            CHECK(golem_replay_feed(engine, (golem_bytes){chunk, amount}, NULL) == GOLEM_OK);
            memset(chunk, 0, amount);
            offset += amount;
        }
        golem_work_run *run = NULL;
        golem_replay_report report;
        CHECK(golem_replay_finish(engine, &run, &report, NULL) == GOLEM_OK);
        CHECK(report.work.status == GOLEM_WORK_SUCCEEDED && report.verified_records == 22);
        uint32_t attempts;
        CHECK(golem_work_run_attempts_get(run, GOLEM_STAGE_UX, &attempts) == GOLEM_OK && attempts == 2);
        golem_replay_free(engine);
        golem_work_run_free(run);
    }
    return EXIT_SUCCESS;
}
static int test_missing(void)
{
    uint8_t bytes[FIXTURE_CAPACITY], changed[FIXTURE_CAPACITY];
    size_t size, count, offsets[64];
    CHECK(load_fixture("default", bytes, &size) == EXIT_SUCCESS);
    CHECK(boundaries((golem_bytes){bytes, size}, offsets, &count) == EXIT_SUCCESS);
    golem_replay_options options = {"run-golden", true, count, size, false};
    golem_work_run *anchor = NULL;
    CHECK(replay_bytes((golem_bytes){bytes, size}, &options, NULL, &anchor, NULL) == GOLEM_OK);
    for (size_t i = 0; i < count; ++i) {
        size_t removed = offsets[i + 1] - offsets[i];
        memcpy(changed, bytes, offsets[i]);
        memcpy(changed + offsets[i], bytes + offsets[i + 1], size - offsets[i + 1]);
        golem_work_run *out = anchor;
        golem_replay_report report = {0};
        report.verified_records = UINT64_MAX;
        CHECK(replay_bytes((golem_bytes){changed, size - removed}, &options, NULL, &out, &report) == GOLEM_ERR_MISSING_RECORD);
        CHECK(out == anchor && report.verified_records == UINT64_MAX);
    }
    golem_work_run *run = NULL;
    size_t prefix = offsets[count - 1];
    CHECK(replay_bytes((golem_bytes){bytes, prefix}, NULL, NULL, &run, NULL) == GOLEM_OK);
    golem_work_run_free(run);
    run = NULL;
    golem_replay_options terminal = {0};
    terminal.require_terminal = true;
    CHECK(replay_bytes((golem_bytes){bytes, prefix}, &terminal, NULL, &run, NULL) == GOLEM_ERR_INCOMPLETE_WORK);
    options.expected_records = count - 1;
    options.expected_bytes = prefix;
    CHECK(replay_bytes((golem_bytes){bytes, size}, &options, NULL, &run, NULL) == GOLEM_ERR_REPLAY_MISMATCH);
    options.expected_records = count;
    options.expected_bytes = size + 1;
    CHECK(replay_bytes((golem_bytes){bytes, size}, &options, NULL, &run, NULL) == GOLEM_ERR_REPLAY_MISMATCH);
    options.expected_bytes = size;
    options.expected_run_id = "different-run";
    CHECK(replay_bytes((golem_bytes){bytes, size}, &options, NULL, &run, NULL) == GOLEM_ERR_REPLAY_MISMATCH);
    CHECK(replay_bytes((golem_bytes){NULL, 0}, NULL, NULL, &run, NULL) == GOLEM_ERR_MISSING_RECORD);
    /* Removal plus renumbering cannot hide a FINISHED without STARTED. */
    size_t position = 0;
    uint64_t sequence = 1;
    for (size_t i = 0; i < count; ++i) {
        if (i == 1) continue;
        golem_journal_record record;
        size_t used, written;
        CHECK(golem_journal_record_decode((golem_bytes){bytes + offsets[i], offsets[i + 1] - offsets[i]},
            &record, &used, NULL) == GOLEM_OK);
        CHECK(golem_journal_record_encode(record.type, sequence++, record.payload,
            changed + position, sizeof(changed) - position, &written, NULL) == GOLEM_OK);
        position += written;
    }
    CHECK(replay_bytes((golem_bytes){changed, position}, NULL, NULL, &run, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(run == NULL);
    golem_work_run_free(anchor);
    golem_journal_record first_event;
    size_t used, written;
    CHECK(golem_journal_record_decode((golem_bytes){bytes + offsets[1], offsets[2] - offsets[1]},
        &first_event, &used, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_encode(first_event.type, 1, first_event.payload,
        changed, sizeof(changed), &written, NULL) == GOLEM_OK);
    CHECK(replay_bytes((golem_bytes){changed, written}, NULL, NULL, &run, NULL) == GOLEM_ERR_MISSING_RECORD);
    CHECK(golem_journal_replay((golem_bytes){changed, written}, NULL, &run, NULL) == GOLEM_ERR_INVALID_STATE);
    return EXIT_SUCCESS;
}
static int test_failure_state(void)
{
    uint8_t bytes[FIXTURE_CAPACITY];
    size_t size, offsets[64], count;
    CHECK(load_fixture("default", bytes, &size) == EXIT_SUCCESS);
    CHECK(boundaries((golem_bytes){bytes, size}, offsets, &count) == EXIT_SUCCESS);
    golem_replay *engine = NULL;
    CHECK(golem_replay_create(NULL, NULL, &engine, NULL) == GOLEM_OK);
    CHECK(golem_replay_feed(engine, (golem_bytes){bytes, offsets[1]}, NULL) == GOLEM_OK);
    bytes[offsets[1] + 24] ^= 1;
    golem_diagnostic diagnostic;
    CHECK(golem_replay_feed(engine, (golem_bytes){bytes + offsets[1], offsets[2] - offsets[1]}, &diagnostic)
        == GOLEM_ERR_CORRUPT_JOURNAL);
    CHECK(diagnostic.offset == offsets[1] + 24);
    golem_replay_progress progress;
    CHECK(golem_replay_progress_get(engine, &progress) == GOLEM_OK);
    CHECK(progress.state == GOLEM_REPLAY_FAILED && progress.verified_records == 1 &&
        progress.verified_bytes == offsets[1]);
    golem_work_run *out = NULL;
    golem_replay_report report = {0};
    report.verified_bytes = UINT64_MAX;
    CHECK(golem_replay_finish(engine, &out, &report, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(out == NULL && report.verified_bytes == UINT64_MAX);
    CHECK(golem_replay_feed(engine, (golem_bytes){NULL, 0}, NULL) == GOLEM_ERR_INVALID_STATE);
    golem_replay_free(engine);
    CHECK(golem_replay_create(NULL, NULL, &engine, NULL) == GOLEM_OK);
    CHECK(golem_replay_feed(engine, (golem_bytes){bytes, 17}, NULL) == GOLEM_OK);
    CHECK(golem_replay_progress_get(engine, &progress) == GOLEM_OK && progress.buffered_bytes == 17);
    CHECK(golem_replay_finish(engine, &out, &report, &diagnostic) == GOLEM_ERR_TRUNCATED_JOURNAL);
    CHECK(diagnostic.offset == 17 && out == NULL);
    golem_replay_free(engine);
    CHECK(load_fixture("invalid_transition", bytes, &size) == EXIT_SUCCESS);
    CHECK(replay_bytes((golem_bytes){bytes, size}, NULL, NULL, &out, &report) == GOLEM_ERR_INVALID_STATE);
    CHECK(out == NULL && report.verified_bytes == UINT64_MAX);
    CHECK(golem_replay_create(NULL, NULL, &engine, NULL) == GOLEM_OK);
    CHECK(golem_replay_feed(engine, (golem_bytes){NULL, 1}, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_replay_progress_get(engine, &progress) == GOLEM_OK && progress.state == GOLEM_REPLAY_FAILED);
    golem_replay_free(engine);
    golem_replay_options invalid = {NULL, false, 1, 0, false};
    engine = NULL;
    CHECK(golem_replay_create(&invalid, NULL, &engine, NULL) == GOLEM_ERR_INVALID_ARGUMENT && engine == NULL);
    CHECK(golem_replay_create(NULL, NULL, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_replay_feed(NULL, (golem_bytes){NULL, 0}, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_replay_finish(NULL, &out, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_replay_progress_get(NULL, &progress) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_replay_free(NULL);
    return EXIT_SUCCESS;
}
static int test_reports(void)
{
    const struct { const char *fixture; size_t records; golem_work_status state; golem_recovery_action action; } cases[] = {
        {"default", 1, GOLEM_WORK_READY, GOLEM_RECOVERY_CHECK_POLICY},
        {"default", 2, GOLEM_WORK_RUNNING, GOLEM_RECOVERY_RECONCILE_ATTEMPT},
        {"default", 13, GOLEM_WORK_SUCCEEDED, GOLEM_RECOVERY_NONE},
        {"reentry", 11, GOLEM_WORK_FAILED, GOLEM_RECOVERY_EVALUATE_REENTRY},
        {"reentry", 12, GOLEM_WORK_READY, GOLEM_RECOVERY_CHECK_POLICY},
        {"cancelled", 3, GOLEM_WORK_CANCELLED, GOLEM_RECOVERY_NONE}
    };
    uint8_t bytes[FIXTURE_CAPACITY];
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        size_t size, offsets[64], count;
        CHECK(load_fixture(cases[i].fixture, bytes, &size) == EXIT_SUCCESS);
        CHECK(boundaries((golem_bytes){bytes, size}, offsets, &count) == EXIT_SUCCESS);
        golem_replay *engine = NULL;
        CHECK(golem_replay_create(NULL, NULL, &engine, NULL) == GOLEM_OK);
        size_t end = offsets[cases[i].records];
        CHECK(golem_replay_feed(engine, (golem_bytes){bytes, end}, NULL) == GOLEM_OK);
        golem_replay_report report;
        golem_work_run *run = NULL;
        CHECK(golem_replay_finish(engine, &run, &report, NULL) == GOLEM_OK);
        CHECK(report.work.status == cases[i].state && report.action == cases[i].action);
        CHECK(report.verified_bytes == end && report.verified_records == cases[i].records);
        CHECK(report.has_latest_attempt == (cases[i].records > 1));
        CHECK(golem_replay_finish(engine, &run, NULL, NULL) == GOLEM_ERR_INVALID_STATE);
        CHECK(golem_replay_feed(engine, (golem_bytes){NULL, 0}, NULL) == GOLEM_ERR_INVALID_STATE);
        golem_replay_free(engine);
        golem_work_run_free(run);
    }
    size_t size, offsets[64], count;
    CHECK(load_fixture("default", bytes, &size) == EXIT_SUCCESS);
    CHECK(boundaries((golem_bytes){bytes, size}, offsets, &count) == EXIT_SUCCESS);
    golem_journal_event event = {0};
    event.type = GOLEM_JOURNAL_FINISHED;
    event.stage = GOLEM_STAGE_PLANNING;
    event.attempt = 1;
    event.attempt_sequence = 1;
    event.outcome = GOLEM_STAGE_FAILED;
    event.failure = GOLEM_FAILURE_STALE_LEASE;
    uint8_t payload[32];
    size_t written;
    CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &written, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_encode(event.type, 3, (golem_bytes){payload, written},
        bytes + offsets[2], sizeof(bytes) - offsets[2], &written, NULL) == GOLEM_OK);
    golem_work_run *run = NULL;
    golem_replay_report report;
    CHECK(replay_bytes((golem_bytes){bytes, offsets[2] + written}, NULL, NULL, &run, &report) == GOLEM_OK);
    CHECK(report.work.status == GOLEM_WORK_BLOCKED && report.action == GOLEM_RECOVERY_RESOLVE_BLOCK);
    CHECK(report.latest_attempt.failure == GOLEM_FAILURE_STALE_LEASE);
    golem_work_run_free(run);
    return EXIT_SUCCESS;
}

typedef struct tracker { size_t calls, fail_at, live; } tracker;
static void *tracked_alloc(void *context, size_t size)
{
    tracker *t = context;
    ++t->calls;
    if (t->fail_at != 0 && t->calls >= t->fail_at) return NULL;
    void *memory = malloc(size);
    if (memory != NULL) ++t->live;
    return memory;
}
static void tracked_free(void *context, void *memory)
{
    tracker *t = context;
    if (memory != NULL) { --t->live; free(memory); }
}
static int test_oom(void)
{
    uint8_t bytes[FIXTURE_CAPACITY];
    size_t size;
    CHECK(load_fixture("default", bytes, &size) == EXIT_SUCCESS);
    tracker t = {0};
    golem_allocator allocator = {&t, tracked_alloc, tracked_free};
    golem_replay_options options = {"run-golden", true, 13, size, true};
    golem_work_run *anchor = NULL, *run = NULL;
    CHECK(replay_bytes((golem_bytes){bytes, size}, NULL, NULL, &anchor, NULL) == GOLEM_OK);
    CHECK(replay_bytes((golem_bytes){bytes, size}, &options, &allocator, &run, NULL) == GOLEM_OK);
    size_t allocations = t.calls;
    golem_work_run_free(run);
    CHECK(t.live == 0);
    for (size_t i = 1; i <= allocations; ++i) {
        t = (tracker){0, i, 0};
        run = anchor;
        golem_replay_report report = {0};
        report.verified_records = UINT64_MAX;
        CHECK(replay_bytes((golem_bytes){bytes, size}, &options, &allocator, &run, &report) == GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(run == anchor && report.verified_records == UINT64_MAX && t.live == 0);
    }
    t = (tracker){0};
    golem_replay *engine = NULL;
    CHECK(golem_replay_create(&options, &allocator, &engine, NULL) == GOLEM_OK);
    CHECK(golem_replay_feed(engine, (golem_bytes){bytes, 35}, NULL) == GOLEM_OK);
    golem_replay_free(engine);
    CHECK(t.live == 0);
    golem_work_run_free(anchor);
    return EXIT_SUCCESS;
}
static int append_prefix(const char *path, golem_bytes bytes)
{
    golem_journal *j = NULL;
    CHECK(golem_journal_open(path, NULL, &j, NULL) == GOLEM_OK);
    golem_journal_reader reader;
    CHECK(golem_journal_reader_init(&reader, bytes) == GOLEM_OK);
    while (reader.offset < bytes.size) {
        golem_journal_record record;
        bool has;
        uint64_t sequence;
        CHECK(golem_journal_reader_next(&reader, &record, &has, NULL) == GOLEM_OK && has);
        CHECK(golem_journal_append(j, record.type, record.payload, &sequence, NULL) == GOLEM_OK);
    }
    /* Process-exit test intentionally does not close the owned descriptor. */
    return EXIT_SUCCESS;
}
static int test_crash(void)
{
    uint8_t bytes[FIXTURE_CAPACITY];
    size_t size, offsets[64], count;
    CHECK(load_fixture("default", bytes, &size) == EXIT_SUCCESS);
    CHECK(boundaries((golem_bytes){bytes, size}, offsets, &count) == EXIT_SUCCESS);
    char path[] = "/tmp/golem-recovery-XXXXXX";
    int fd = mkstemp(path);
    CHECK(fd >= 0 && close(fd) == 0);
    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0) {
        _exit(append_prefix(path, (golem_bytes){bytes, offsets[2]}));
    }
    int result;
    CHECK(waitpid(child, &result, 0) == child && WIFEXITED(result) && WEXITSTATUS(result) == 0);
    golem_journal *j = NULL, *other = NULL;
    CHECK(golem_journal_open(path, NULL, &j, NULL) == GOLEM_OK);
    golem_replay_options options = {"run-golden", true, 2, offsets[2], false};
    golem_work_run *run = NULL;
    golem_replay_report report;
    CHECK(golem_journal_recover(j, &options, &run, &report, NULL) == GOLEM_OK);
    CHECK(report.action == GOLEM_RECOVERY_RECONCILE_ATTEMPT);
    CHECK(report.latest_attempt.attempt == 1 && report.latest_attempt.sequence == 1);
    CHECK(report.work.status == GOLEM_WORK_RUNNING && report.next_record_sequence == 3);
    CHECK(golem_journal_open(path, NULL, &other, NULL) == GOLEM_ERR_JOURNAL_BUSY);
    /* Recovery must not write or automatically retry an ambiguous active stage. */
    FILE *file = fopen(path, "rb");
    CHECK(file != NULL);
    uint8_t actual[FIXTURE_CAPACITY];
    size_t actual_size = fread(actual, 1, sizeof(actual), file);
    CHECK(fclose(file) == 0 && actual_size == offsets[2] && memcmp(actual, bytes, actual_size) == 0);
    /* Simulate externally reconciled result: append the known completion. */
    golem_journal_record record;
    size_t used;
    CHECK(golem_journal_record_decode((golem_bytes){bytes + offsets[2], offsets[3] - offsets[2]},
        &record, &used, NULL) == GOLEM_OK);
    uint64_t sequence;
    CHECK(golem_journal_append(j, record.type, record.payload, &sequence, NULL) == GOLEM_OK && sequence == 3);
    golem_work_run *after = NULL;
    CHECK(golem_journal_recover(j, NULL, &after, &report, NULL) == GOLEM_OK);
    CHECK(report.work.current_stage == GOLEM_STAGE_UX && report.action == GOLEM_RECOVERY_CHECK_POLICY);
    golem_work_run_free(run);
    CHECK(golem_journal_close(j, NULL) == GOLEM_OK);
    golem_work_run_free(after);
    CHECK(unlink(path) == 0);

    CHECK(load_fixture("invalid_transition", bytes, &size) == EXIT_SUCCESS);
    file = fopen(path, "wb");
    CHECK(file != NULL && fwrite(bytes, 1, size, file) == size && fclose(file) == 0);
    CHECK(golem_journal_open(path, NULL, &j, NULL) == GOLEM_OK);
    run = NULL;
    report.verified_records = UINT64_MAX;
    CHECK(golem_journal_recover(j, NULL, &run, &report, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(run == NULL && report.verified_records == UINT64_MAX);
    CHECK(golem_journal_append(j, GOLEM_JOURNAL_CANCELLED,
        (golem_bytes){NULL, 0}, &sequence, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_journal_close(j, NULL) == GOLEM_OK);
    CHECK(unlink(path) == 0);
    return EXIT_SUCCESS;
}
static int test_recover_failure(void)
{
    uint8_t bytes[FIXTURE_CAPACITY];
    size_t size;
    CHECK(load_fixture("default", bytes, &size) == EXIT_SUCCESS);
    char path[] = "/tmp/golem-recovery-failure-XXXXXX";
    int fd = mkstemp(path);
    CHECK(fd >= 0);
    FILE *file = fdopen(fd, "wb");
    CHECK(file != NULL && fwrite(bytes, 1, size, file) == size && fclose(file) == 0);
    tracker t = {0};
    golem_allocator allocator = {&t, tracked_alloc, tracked_free};
    golem_journal *j = NULL;
    CHECK(golem_journal_open(path, &allocator, &j, NULL) == GOLEM_OK);
    CHECK(t.live == 1);
    golem_work_run *run = NULL;
    golem_replay_report report = {0};
    report.verified_records = UINT64_MAX;
    t.fail_at = t.calls + 1;
    CHECK(golem_journal_recover(j, NULL, &run, &report, NULL) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(run == NULL && t.live == 1 && report.verified_records == UINT64_MAX);
    t.fail_at = 0;
    CHECK(golem_journal_recover(j, NULL, &run, &report, NULL) == GOLEM_OK);
    golem_work_run_free(run);
    run = NULL;
    CHECK(t.live == 1);
    t.fail_at = t.calls + 2; /* Engine created, first frame allocation fails. */
    CHECK(golem_journal_recover(j, NULL, &run, NULL, NULL) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(run == NULL && t.live == 1);
    uint64_t sequence = 999;
    CHECK(golem_journal_append(j, GOLEM_JOURNAL_CANCELLED,
        (golem_bytes){NULL, 0}, &sequence, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(sequence == 999);
    CHECK(golem_journal_close(j, NULL) == GOLEM_OK && t.live == 0);
    CHECK(golem_journal_open(path, NULL, &j, NULL) == GOLEM_OK);
    golem_replay_options options = {"wrong-run", false, 0, 0, false};
    CHECK(golem_journal_recover(j, &options, &run, NULL, NULL) == GOLEM_ERR_REPLAY_MISMATCH);
    CHECK(golem_journal_recover(j, NULL, &run, NULL, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_journal_close(j, NULL) == GOLEM_OK);
    CHECK(golem_journal_open(path, NULL, &j, NULL) == GOLEM_OK);
    file = fopen(path, "ab");
    CHECK(file != NULL && fputc(1, file) == 1 && fclose(file) == 0);
    CHECK(golem_journal_recover(j, NULL, &run, NULL, NULL) == GOLEM_ERR_IO);
    CHECK(run == NULL && golem_journal_close(j, NULL) == GOLEM_OK);
    CHECK(unlink(path) == 0);
    return EXIT_SUCCESS;
}

static int test_bounded(void)
{
    uint8_t bytes[FIXTURE_CAPACITY], payload[2048], frame[2048];
    size_t size, used, written;
    CHECK(load_fixture("default", bytes, &size) == EXIT_SUCCESS);
    golem_journal_record created;
    CHECK(golem_journal_record_decode((golem_bytes){bytes, size}, &created, &used, NULL) == GOLEM_OK);
    memcpy(payload, created.payload.data, created.payload.size);
    payload[0] = 255;
    payload[1] = 255; /* max_attempts = 65535 */
    CHECK(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1,
        (golem_bytes){payload, created.payload.size}, frame, sizeof(frame), &written, NULL) == GOLEM_OK);
    tracker t = {0};
    golem_allocator allocator = {&t, tracked_alloc, tracked_free};
    golem_replay *engine = NULL;
    CHECK(golem_replay_create(NULL, &allocator, &engine, NULL) == GOLEM_OK);
    CHECK(golem_replay_feed(engine, (golem_bytes){frame, written}, NULL) == GOLEM_OK);
    size_t calls = t.calls;
    t.fail_at = calls + 1;
    char path[] = "/tmp/golem-recovery-stream-XXXXXX";
    int fd = mkstemp(path);
    CHECK(fd >= 0);
    FILE *file = fdopen(fd, "wb");
    CHECK(file != NULL && fwrite(frame, 1, written, file) == written);
    uint64_t sequence = 2;
    for (uint32_t attempt = 1; attempt <= 1000; ++attempt) {
        golem_journal_event events[3] = {{0}};
        events[0].type = GOLEM_JOURNAL_STARTED;
        events[0].stage = GOLEM_STAGE_PLANNING;
        events[0].attempt = attempt;
        events[0].attempt_sequence = attempt;
        events[0].outcome = GOLEM_STAGE_RUNNING;
        events[1] = events[0];
        events[1].type = GOLEM_JOURNAL_FINISHED;
        events[1].outcome = GOLEM_STAGE_FAILED;
        events[1].failure = GOLEM_FAILURE_TIMEOUT;
        events[2].type = GOLEM_JOURNAL_REENTERED;
        events[2].stage = GOLEM_STAGE_PLANNING;
        for (size_t i = 0; i < 3; ++i) {
            size_t payload_size;
            CHECK(golem_journal_event_encode(&events[i], payload, sizeof(payload), &payload_size, NULL) == GOLEM_OK);
            CHECK(golem_journal_record_encode(events[i].type, sequence++, (golem_bytes){payload, payload_size},
                frame, sizeof(frame), &written, NULL) == GOLEM_OK);
            CHECK(golem_replay_feed(engine, (golem_bytes){frame, written}, NULL) == GOLEM_OK);
            CHECK(fwrite(frame, 1, written, file) == written);
        }
    }
    CHECK(fclose(file) == 0);
    golem_replay_report report;
    golem_work_run *run = NULL;
    CHECK(golem_replay_finish(engine, &run, &report, NULL) == GOLEM_OK);
    CHECK(t.calls == calls && report.verified_records == 3001);
    CHECK(report.verified_bytes > 16384 && report.action == GOLEM_RECOVERY_CHECK_POLICY);
    golem_replay_free(engine);
    golem_work_run_free(run);
    CHECK(t.live == 0);
    golem_journal *j = NULL;
    CHECK(golem_journal_open(path, NULL, &j, NULL) == GOLEM_OK);
    golem_replay_options options = {"run-golden", true, report.verified_records, report.verified_bytes, false};
    CHECK(golem_journal_recover(j, &options, &run, &report, NULL) == GOLEM_OK);
    uint32_t attempts;
    CHECK(golem_work_run_attempts_get(run, GOLEM_STAGE_PLANNING, &attempts) == GOLEM_OK && attempts == 1000);
    CHECK(golem_journal_close(j, NULL) == GOLEM_OK);
    golem_work_run_free(run);
    CHECK(unlink(path) == 0);
    return EXIT_SUCCESS;
}
int main(int argc, char **argv)
{
    const struct { const char *name; int (*run)(void); } cases[] = {
        {"chunks", test_chunks}, {"missing", test_missing}, {"failure_state", test_failure_state},
        {"reports", test_reports}, {"oom", test_oom}, {"crash", test_crash},
        {"recover_failure", test_recover_failure}, {"bounded", test_bounded}
    };
    if (argc != 2) return EXIT_FAILURE;
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        if (strcmp(argv[1], cases[i].name) == 0) return cases[i].run();
    }
    return EXIT_FAILURE;
}
