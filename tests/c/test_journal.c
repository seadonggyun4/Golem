#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/journal.h"
#include "test.h"
#include <string.h>
#include <unistd.h>
#include <fcntl.h>

#include "journal_fixture.h"
static int make_capsule(golem_work_capsule **out)
{
    golem_graph_spec graph_spec;
    golem_stage_graph *graph = NULL;
    CHECK(golem_stage_graph_default_spec(&graph_spec) == GOLEM_OK);
    CHECK(golem_stage_graph_create(&graph_spec, &graph) == GOLEM_OK);
    const char *scope[] = {"src"}, *acceptance[] = {"tests pass"};
    const char *artifacts[] = {"patch"}, *gates[] = {"review"};
    golem_capsule_spec spec = {0};
    spec.id = "capsule-golden";
    spec.goal = "Golden work";
    spec.scope = (golem_string_list){scope, 1};
    spec.acceptance = (golem_string_list){acceptance, 1};
    spec.expected_artifacts = (golem_string_list){artifacts, 1};
    spec.required_gates = (golem_string_list){gates, 1};
    spec.graph = graph;
    for (size_t i = 0; i < 6; ++i) spec.permissions[i] = GOLEM_AUTONOMY_AUTO_LOCAL;
    CHECK(golem_work_capsule_create(&spec, out) == GOLEM_OK);
    golem_stage_graph_free(graph);
    return EXIT_SUCCESS;
}
static int test_codec(void)
{
    uint32_t crc = 99;
    CHECK(golem_journal_crc32((golem_bytes){(const uint8_t *)"123456789", 9}, &crc) == GOLEM_OK);
    CHECK(crc == 0xcbf43926u);
    CHECK(golem_journal_crc32((golem_bytes){NULL, 0}, &crc) == GOLEM_OK && crc == 0);
    CHECK(golem_journal_crc32((golem_bytes){NULL, 1}, &crc) == GOLEM_ERR_INVALID_ARGUMENT);
    uint8_t golden[FIXTURE_CAPACITY], encoded[FIXTURE_CAPACITY], payload[2048];
    size_t size, needed = 99;
    CHECK(load_fixture("default", golden, &size) == EXIT_SUCCESS);
    golem_work_capsule *capsule = NULL;
    CHECK(make_capsule(&capsule) == EXIT_SUCCESS);
    CHECK(golem_journal_created_encode("run-golden", capsule, 3, NULL, 0, &needed, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    memset(payload, 0xaa, sizeof(payload));
    CHECK(golem_journal_created_encode("run-golden", capsule, 3, payload, needed - 1, &needed, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(payload[0] == 0xaa);
    CHECK(golem_journal_created_encode("run-golden", capsule, 3, payload, sizeof(payload), &needed, NULL) == GOLEM_OK);
    golem_work_capsule_free(capsule);
    size_t framed;
    CHECK(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){payload, needed},
        encoded, sizeof(encoded), &framed, NULL) == GOLEM_OK);
    CHECK(memcmp(encoded, golden, framed) == 0);
    golem_journal_reader reader;
    CHECK(golem_journal_reader_init(&reader, (golem_bytes){golden, size}) == GOLEM_OK);
    size_t count = 0;
    while (true) {
        golem_journal_record record;
        bool has_record;
        size_t offset = reader.offset;
        CHECK(golem_journal_reader_next(&reader, &record, &has_record, NULL) == GOLEM_OK);
        if (!has_record) break;
        CHECK(record.sequence == ++count);
        if (record.type != GOLEM_JOURNAL_CREATED) {
            golem_journal_event event;
            CHECK(golem_journal_event_decode(&record, &event, NULL) == GOLEM_OK);
            CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &needed, NULL) == GOLEM_OK);
            CHECK(needed == record.payload.size && memcmp(payload, record.payload.data, needed) == 0);
        }
        CHECK(golem_journal_record_encode(record.type, record.sequence, record.payload,
            encoded, sizeof(encoded), &framed, NULL) == GOLEM_OK);
        CHECK(framed == reader.offset - offset && memcmp(encoded, golden + offset, framed) == 0);
    }
    CHECK(count == 13);
    memset(encoded, 0xaa, sizeof(encoded));
    CHECK(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){NULL, 0},
        encoded, 31, &needed, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(needed == 32 && encoded[0] == 0xaa);
    needed = 123;
    CHECK(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 0, (golem_bytes){NULL, 0},
        encoded, sizeof(encoded), &needed, NULL) == GOLEM_ERR_INVALID_ARGUMENT && needed == 123);
    CHECK(golem_journal_record_encode((golem_journal_type)99, 1, (golem_bytes){NULL, 0},
        encoded, sizeof(encoded), &needed, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){encoded, SIZE_MAX},
        NULL, 0, &needed, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return EXIT_SUCCESS;
}
static int test_replay(void)
{
    const char *names[] = {"default", "reentry", "cancelled", "invalid_transition"};
    for (size_t i = 0; i < 4; ++i) {
        uint8_t golden[FIXTURE_CAPACITY];
        size_t size;
        CHECK(load_fixture(names[i], golden, &size) == EXIT_SUCCESS);
        golem_work_run *run = NULL;
        golem_diagnostic diagnostic;
        golem_status status = golem_journal_replay((golem_bytes){golden, size}, NULL, &run, &diagnostic);
        if (i == 3) {
            CHECK(status == GOLEM_ERR_INVALID_STATE && run == NULL && diagnostic.offset > 0);
            continue;
        }
        CHECK(status == GOLEM_OK && diagnostic.status == GOLEM_OK);
        /* Returned run is independent of encoded input lifetime. */
        memset(golden, 0, size);
        CHECK(strcmp(golem_work_run_id_borrow(run), "run-golden") == 0);
        golem_work_snapshot work;
        CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
        CHECK(work.status == (i == 2 ? GOLEM_WORK_CANCELLED : GOLEM_WORK_SUCCEEDED));
        CHECK(work.passed_count == (i == 2 ? 0u : 6u));
        for (int stage = 0; stage < 6; ++stage) {
            uint32_t attempts;
            CHECK(golem_work_run_attempts_get(run, (golem_stage)stage, &attempts) == GOLEM_OK);
            uint32_t expected = i == 2 ? (stage == 0 ? 1u : 0u) : (i == 1 && stage > 0 && stage < 5 ? 2u : 1u);
            CHECK(attempts == expected);
        }
        golem_work_run_free(run);
    }
    return EXIT_SUCCESS;
}
static int test_corruption(void)
{
    uint8_t golden[FIXTURE_CAPACITY], changed[FIXTURE_CAPACITY];
    size_t size;
    CHECK(load_fixture("default", golden, &size) == EXIT_SUCCESS);
    golem_work_run *anchor = NULL;
    CHECK(golem_journal_replay((golem_bytes){golden, size}, NULL, &anchor, NULL) == GOLEM_OK);
    /* Every single-byte bit flip must fail, including CRC/header/payload. */
    for (size_t i = 0; i < size; ++i) {
        memcpy(changed, golden, size);
        changed[i] ^= 1;
        golem_work_run *out = anchor;
        CHECK(golem_journal_replay((golem_bytes){changed, size}, NULL, &out, NULL) != GOLEM_OK);
        CHECK(out == anchor);
    }
    bool boundary[FIXTURE_CAPACITY] = {false};
    golem_journal_reader reader;
    CHECK(golem_journal_reader_init(&reader, (golem_bytes){golden, size}) == GOLEM_OK);
    while (reader.offset < size) {
        golem_journal_record record;
        bool has;
        CHECK(golem_journal_reader_next(&reader, &record, &has, NULL) == GOLEM_OK && has);
        boundary[reader.offset] = true;
    }
    /* Every possible torn write, including partial headers, is rejected.
     * Prefixes ending exactly on record boundaries retain a valid unfinished run. */
    for (size_t cut = 0; cut < size; ++cut) {
        golem_work_run *out = anchor;
        golem_diagnostic diagnostic;
        golem_status status = golem_journal_replay((golem_bytes){golden, cut}, NULL, &out, &diagnostic);
        if (boundary[cut]) {
            CHECK(status == GOLEM_OK && out != anchor);
            golem_work_run_free(out);
        } else {
            CHECK(status == (cut == 0 ? GOLEM_ERR_CORRUPT_JOURNAL : GOLEM_ERR_TRUNCATED_JOURNAL));
            CHECK(out == anchor);
            if (cut != 0) CHECK(diagnostic.offset == cut);
        }
    }
    memcpy(changed, golden, size);
    changed[4] = 2;
    golem_work_run *out = anchor;
    CHECK(golem_journal_replay((golem_bytes){changed, size}, NULL, &out, NULL) == GOLEM_ERR_UNSUPPORTED_VERSION);
    memcpy(changed, golden, size);
    memset(changed + 12, 255, 4);
    CHECK(golem_journal_replay((golem_bytes){changed, size}, NULL, &out, NULL) == GOLEM_ERR_CORRUPT_JOURNAL);
    /* Failures do not advance reader cursor or overwrite outputs. */
    CHECK(golem_journal_reader_init(&reader, (golem_bytes){golden, 31}) == GOLEM_OK);
    golem_journal_record record = {GOLEM_JOURNAL_CANCELLED, 99, {NULL, 0}};
    bool has = true;
    CHECK(golem_journal_reader_next(&reader, &record, &has, NULL) == GOLEM_ERR_TRUNCATED_JOURNAL);
    CHECK(reader.offset == 0 && record.sequence == 99 && has);
    golem_work_run_free(anchor);
    return EXIT_SUCCESS;
}
static int test_semantics(void)
{
    uint8_t golden[FIXTURE_CAPACITY], changed[FIXTURE_CAPACITY], payload[2048];
    size_t size, first, next_size;
    CHECK(load_fixture("default", golden, &size) == EXIT_SUCCESS);
    golem_journal_record created, started;
    CHECK(golem_journal_record_decode((golem_bytes){golden, size}, &created, &first, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_decode((golem_bytes){golden + first, size - first}, &started, &next_size, NULL) == GOLEM_OK);
    memcpy(changed, golden, first);
    golem_work_run *out = NULL;
    size_t written;
    /* Valid checksums cannot hide replay gaps, duplicates or invalid event data. */
    CHECK(golem_journal_record_encode(started.type, 3, started.payload, changed + first,
        sizeof(changed) - first, &written, NULL) == GOLEM_OK);
    CHECK(golem_journal_replay((golem_bytes){changed, first + written}, NULL, &out, NULL) == GOLEM_ERR_CORRUPT_JOURNAL);
    CHECK(golem_journal_record_encode(created.type, 2, created.payload, changed + first,
        sizeof(changed) - first, &written, NULL) == GOLEM_OK);
    CHECK(golem_journal_replay((golem_bytes){changed, first + written}, NULL, &out, NULL) == GOLEM_ERR_INVALID_STATE);
    memcpy(payload, created.payload.data, created.payload.size);
    memset(payload, 0, 4); /* max_attempts=0 */
    CHECK(golem_journal_record_encode(created.type, 1, (golem_bytes){payload, created.payload.size},
        changed, sizeof(changed), &written, NULL) == GOLEM_OK);
    CHECK(golem_journal_replay((golem_bytes){changed, written}, NULL, &out, NULL) == GOLEM_ERR_CORRUPT_JOURNAL);
    /* Each shortened creation payload is a framed but invalid capsule. */
    for (size_t cut = 0; cut < created.payload.size; ++cut) {
        CHECK(golem_journal_record_encode(created.type, 1, (golem_bytes){created.payload.data, cut},
            changed, sizeof(changed), &written, NULL) == GOLEM_OK);
        CHECK(golem_journal_replay((golem_bytes){changed, written}, NULL, &out, NULL) == GOLEM_ERR_CORRUPT_JOURNAL);
    }
    /* Unknown enum, reserved byte, flags, stale attempt token. */
    for (size_t offset = 0; offset < 32; offset += 4) {
        memcpy(changed, golden, first);
        memcpy(payload, started.payload.data, started.payload.size);
        payload[offset] = 255;
        CHECK(golem_journal_record_encode(started.type, 2, (golem_bytes){payload, started.payload.size},
            changed + first, sizeof(changed) - first, &written, NULL) == GOLEM_OK);
        CHECK(golem_journal_replay((golem_bytes){changed, first + written}, NULL, &out, NULL) != GOLEM_OK);
        CHECK(out == NULL);
    }
    return EXIT_SUCCESS;
}
static int test_lifecycle(void)
{
    uint8_t golden[FIXTURE_CAPACITY], stream[FIXTURE_CAPACITY], payload[2048];
    size_t size, first, written;
    CHECK(load_fixture("reentry", golden, &size) == EXIT_SUCCESS);
    golem_journal_record created;
    CHECK(golem_journal_record_decode((golem_bytes){golden, size}, &created, &first, NULL) == GOLEM_OK);
    memcpy(payload, created.payload.data, created.payload.size);
    payload[0] = 1; /* Per-stage max_attempts. Reentry would need a second attempt. */
    CHECK(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){payload, created.payload.size},
        stream, sizeof(stream), &written, NULL) == GOLEM_OK && written == first);
    memcpy(stream + first, golden + first, size - first);
    golem_work_run *run = NULL;
    CHECK(golem_journal_replay((golem_bytes){stream, size}, NULL, &run, NULL) == GOLEM_ERR_ATTEMPT_LIMIT);
    CHECK(run == NULL);

    memcpy(payload, created.payload.data, created.payload.size);
    payload[80] = 3; /* planning permission: ASK_ALWAYS */
    CHECK(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){payload, created.payload.size},
        stream, sizeof(stream), &written, NULL) == GOLEM_OK);
    golem_journal_event event = {0};
    event.type = GOLEM_JOURNAL_STARTED;
    event.stage = GOLEM_STAGE_PLANNING;
    event.attempt = 1;
    event.attempt_sequence = 1;
    event.outcome = GOLEM_STAGE_RUNNING;
    size_t payload_size;
    CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &payload_size, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_encode(event.type, 2, (golem_bytes){payload, payload_size},
        stream + first, sizeof(stream) - first, &written, NULL) == GOLEM_OK);
    size_t prefix = first + written;
    CHECK(golem_journal_replay((golem_bytes){stream, prefix}, NULL, &run, NULL) == GOLEM_ERR_POLICY_DENIED);
    event.authorized = true;
    CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &payload_size, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_encode(event.type, 2, (golem_bytes){payload, payload_size},
        stream + first, sizeof(stream) - first, &written, NULL) == GOLEM_OK);
    CHECK(golem_journal_replay((golem_bytes){stream, prefix}, NULL, &run, NULL) == GOLEM_OK);
    golem_work_snapshot work;
    CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK && work.status == GOLEM_WORK_RUNNING);
    golem_work_run_free(run);
    run = NULL;

    event.type = GOLEM_JOURNAL_FINISHED;
    event.authorized = false;
    event.outcome = GOLEM_STAGE_PASSED;
    event.requirements_met = true;
    event.attempt_sequence = 2; /* checksum-valid stale completion */
    CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &payload_size, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_encode(event.type, 3, (golem_bytes){payload, payload_size},
        stream + prefix, sizeof(stream) - prefix, &written, NULL) == GOLEM_OK);
    CHECK(golem_journal_replay((golem_bytes){stream, prefix + written}, NULL, &run, NULL) == GOLEM_ERR_STALE_RESULT);
    event.attempt_sequence = 1;
    event.outcome = GOLEM_STAGE_FAILED;
    event.failure = GOLEM_FAILURE_STALE_LEASE;
    event.requirements_met = false;
    CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &payload_size, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_encode(event.type, 3, (golem_bytes){payload, payload_size},
        stream + prefix, sizeof(stream) - prefix, &written, NULL) == GOLEM_OK);
    prefix += written;
    CHECK(golem_journal_replay((golem_bytes){stream, prefix}, NULL, &run, NULL) == GOLEM_OK);
    CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK && work.status == GOLEM_WORK_BLOCKED);
    golem_work_run_free(run);
    run = NULL;
    event = (golem_journal_event){0};
    event.type = GOLEM_JOURNAL_REENTERED;
    event.stage = GOLEM_STAGE_PLANNING;
    CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &payload_size, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_encode(event.type, 4, (golem_bytes){payload, payload_size},
        stream + prefix, sizeof(stream) - prefix, &written, NULL) == GOLEM_OK);
    CHECK(golem_journal_replay((golem_bytes){stream, prefix + written}, NULL, &run, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(run == NULL);
    return EXIT_SUCCESS;
}

static int read_file(const char *path, uint8_t *data, size_t *size)
{
    FILE *file = fopen(path, "rb");
    CHECK(file != NULL);
    *size = fread(data, 1, FIXTURE_CAPACITY, file);
    CHECK(!ferror(file) && feof(file));
    CHECK(fclose(file) == 0);
    return EXIT_SUCCESS;
}
static int test_file(void)
{
    char path[] = "/tmp/golem-journal-XXXXXX";
    int fd = mkstemp(path);
    CHECK(fd >= 0 && close(fd) == 0);
    uint8_t golden[FIXTURE_CAPACITY], actual[FIXTURE_CAPACITY];
    size_t size;
    CHECK(load_fixture("default", golden, &size) == EXIT_SUCCESS);
    golem_journal *writer = NULL, *other = NULL;
    CHECK(golem_journal_open(path, NULL, &writer, NULL) == GOLEM_OK);
    CHECK(golem_journal_open(path, NULL, &other, NULL) == GOLEM_ERR_JOURNAL_BUSY && other == NULL);
    golem_journal_reader reader;
    CHECK(golem_journal_reader_init(&reader, (golem_bytes){golden, size}) == GOLEM_OK);
    size_t count = 0;
    while (reader.offset < size) {
        golem_journal_record record;
        bool has;
        CHECK(golem_journal_reader_next(&reader, &record, &has, NULL) == GOLEM_OK && has);
        uint64_t sequence;
        CHECK(golem_journal_append(writer, record.type, record.payload, &sequence, NULL) == GOLEM_OK);
        CHECK(sequence == record.sequence);
        if (++count == 5) {
            CHECK(golem_journal_close(writer, NULL) == GOLEM_OK);
            CHECK(golem_journal_open(path, NULL, &writer, NULL) == GOLEM_OK);
        }
    }
    CHECK(golem_journal_close(writer, NULL) == GOLEM_OK);
    size_t actual_size;
    CHECK(read_file(path, actual, &actual_size) == EXIT_SUCCESS);
    CHECK(actual_size == size && memcmp(actual, golden, size) == 0);
    CHECK(golem_journal_open(path, NULL, &writer, NULL) == GOLEM_OK);
    /* Noncooperating writes poison the handle, never silently append over them. */
    FILE *file = fopen(path, "ab");
    CHECK(file != NULL && fputc(0xaa, file) == 0xaa && fclose(file) == 0);
    uint64_t sequence = 999;
    CHECK(golem_journal_append(writer, GOLEM_JOURNAL_CANCELLED,
        (golem_bytes){NULL, 0}, &sequence, NULL) == GOLEM_ERR_IO);
    CHECK(sequence == 999);
    CHECK(golem_journal_append(writer, GOLEM_JOURNAL_CANCELLED,
        (golem_bytes){NULL, 0}, &sequence, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_journal_close(writer, NULL) == GOLEM_OK);
    writer = NULL;
    CHECK(golem_journal_open(path, NULL, &writer, NULL) == GOLEM_ERR_TRUNCATED_JOURNAL);
    CHECK(writer == NULL);
    CHECK(read_file(path, actual, &actual_size) == EXIT_SUCCESS);
    CHECK(actual_size == size + 1 && memcmp(actual, golden, size) == 0);
    CHECK(unlink(path) == 0);
    /* Refused opens preserve checksum-corrupt, future-version, and oversized files. */
    const size_t corrupt_offsets[] = {24, 4, 6, 12};
    for (size_t i = 0; i < 4; ++i) {
        memcpy(actual, golden, size);
        actual[corrupt_offsets[i]] = 255;
        file = fopen(path, "wb");
        CHECK(file != NULL && fwrite(actual, 1, size, file) == size && fclose(file) == 0);
        writer = NULL;
        golem_diagnostic diagnostic;
        golem_status expected = i == 1 ? GOLEM_ERR_UNSUPPORTED_VERSION : GOLEM_ERR_CORRUPT_JOURNAL;
        if (i == 3) {
            /* Set every length byte to exceed the payload limit. */
            file = fopen(path, "r+b");
            CHECK(file != NULL && fseek(file, 12, SEEK_SET) == 0);
            const uint8_t huge[] = {255, 255, 255, 255};
            CHECK(fwrite(huge, 1, sizeof(huge), file) == sizeof(huge) && fclose(file) == 0);
            memcpy(actual + 12, huge, sizeof(huge));
        }
        CHECK(golem_journal_open(path, NULL, &writer, &diagnostic) == expected);
        CHECK(writer == NULL && diagnostic.status == expected);
        uint8_t unchanged[FIXTURE_CAPACITY];
        size_t unchanged_size;
        CHECK(read_file(path, unchanged, &unchanged_size) == EXIT_SUCCESS);
        CHECK(unchanged_size == size && memcmp(unchanged, actual, size) == 0);
        CHECK(unlink(path) == 0);
    }
    /* Creation of absent file and final-path symlink rejection. */
    CHECK(golem_journal_open(path, NULL, &writer, NULL) == GOLEM_OK);
    CHECK(golem_journal_close(writer, NULL) == GOLEM_OK);
    CHECK(unlink(path) == 0);
    CHECK(symlink("/dev/null", path) == 0);
    writer = NULL;
    CHECK(golem_journal_open(path, NULL, &writer, NULL) == GOLEM_ERR_IO);
    CHECK(unlink(path) == 0);
    CHECK(golem_journal_open("/tmp", NULL, &writer, NULL) == GOLEM_ERR_IO);
    CHECK(golem_journal_close(NULL, NULL) == GOLEM_OK);
    return EXIT_SUCCESS;
}

typedef struct tracker { size_t calls, fail_at, live; } tracker;
static void *test_alloc(void *context, size_t size)
{
    tracker *t = context;
    ++t->calls;
    if (t->fail_at != 0 && t->calls >= t->fail_at) return NULL;
    void *memory = malloc(size);
    if (memory != NULL) ++t->live;
    return memory;
}
static void test_free(void *context, void *memory)
{
    tracker *t = context;
    if (memory != NULL) { --t->live; free(memory); }
}
static int test_oom(void)
{
    uint8_t golden[FIXTURE_CAPACITY];
    size_t size;
    CHECK(load_fixture("default", golden, &size) == EXIT_SUCCESS);
    tracker t = {0};
    golem_allocator allocator = {&t, test_alloc, test_free};
    golem_work_run *anchor = NULL, *out = NULL;
    CHECK(golem_journal_replay((golem_bytes){golden, size}, NULL, &anchor, NULL) == GOLEM_OK);
    CHECK(golem_journal_replay((golem_bytes){golden, size}, &allocator, &out, NULL) == GOLEM_OK);
    size_t allocations = t.calls;
    golem_work_run_free(out);
    CHECK(t.live == 0 && allocations > 20);
    for (size_t failure = 1; failure <= allocations; ++failure) {
        t = (tracker){0, failure, 0};
        out = anchor;
        golem_diagnostic d;
        CHECK(golem_journal_replay((golem_bytes){golden, size}, &allocator, &out, &d) == GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(out == anchor && t.live == 0 && d.status == GOLEM_ERR_OUT_OF_MEMORY);
    }
    golem_work_run_free(anchor);
    char path[] = "/tmp/golem-journal-oom-XXXXXX";
    int fd = mkstemp(path);
    CHECK(fd >= 0 && close(fd) == 0);
    t = (tracker){0, 1, 0};
    golem_journal *writer = NULL;
    CHECK(golem_journal_open(path, &allocator, &writer, NULL) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(t.live == 0 && writer == NULL);
    t = (tracker){0};
    CHECK(golem_journal_open(path, &allocator, &writer, NULL) == GOLEM_OK);
    t.fail_at = t.calls + 1;
    golem_journal_record record;
    size_t consumed;
    CHECK(golem_journal_record_decode((golem_bytes){golden, size}, &record, &consumed, NULL) == GOLEM_OK);
    uint64_t sequence = 99;
    CHECK(golem_journal_append(writer, record.type, record.payload, &sequence, NULL) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(sequence == 99);
    t.fail_at = 0;
    CHECK(golem_journal_append(writer, record.type, record.payload, &sequence, NULL) == GOLEM_OK && sequence == 1);
    CHECK(golem_journal_close(writer, NULL) == GOLEM_OK && t.live == 0);
    /* Open validation allocation failure releases both descriptor and lock. */
    t = (tracker){0, 2, 0};
    writer = NULL;
    CHECK(golem_journal_open(path, &allocator, &writer, NULL) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(writer == NULL && t.live == 0);
    CHECK(golem_journal_open(path, NULL, &writer, NULL) == GOLEM_OK);
    CHECK(golem_journal_close(writer, NULL) == GOLEM_OK);
    CHECK(unlink(path) == 0);
    return EXIT_SUCCESS;
}
int main(int argc, char **argv)
{
    const struct { const char *name; int (*run)(void); } cases[] = {
        {"codec", test_codec}, {"replay", test_replay}, {"corruption", test_corruption},
        {"semantics", test_semantics}, {"lifecycle", test_lifecycle},
        {"file", test_file}, {"oom", test_oom}
    };
    if (argc != 2) return EXIT_FAILURE;
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i)
        if (strcmp(argv[1], cases[i].name) == 0) return cases[i].run();
    return EXIT_FAILURE;
}
