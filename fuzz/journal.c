#include "golem/replay.h"
#include "check.h"

static void replay(golem_bytes bytes)
{
    golem_replay *whole = NULL, *chunks = NULL;
    REQUIRE(golem_replay_create(NULL, NULL, &whole, NULL) == GOLEM_OK);
    REQUIRE(golem_replay_create(NULL, NULL, &chunks, NULL) == GOLEM_OK);
    golem_status a = golem_replay_feed(whole, bytes, NULL), b = GOLEM_OK;
    for (size_t pos = 0; b == GOLEM_OK && pos < bytes.size;) {
        size_t n = 1 + bytes.data[pos] % 97;
        if (n > bytes.size - pos) n = bytes.size - pos;
        b = golem_replay_feed(chunks, (golem_bytes){bytes.data + pos, n}, NULL);
        pos += n;
    }
    golem_work_run *x = NULL, *y = NULL;
    golem_replay_report rx, ry;
    if (a == GOLEM_OK) a = golem_replay_finish(whole, &x, &rx, NULL);
    if (b == GOLEM_OK) b = golem_replay_finish(chunks, &y, &ry, NULL);
    REQUIRE(a == b);
    if (a == GOLEM_OK) {
        REQUIRE(rx.verified_records == ry.verified_records && rx.verified_bytes == ry.verified_bytes);
        REQUIRE(rx.work.status == ry.work.status && rx.work.current_stage == ry.work.current_stage);
        REQUIRE(rx.work.passed_count == ry.work.passed_count && rx.action == ry.action);
        REQUIRE(rx.work.stage_count == ry.work.stage_count && rx.next_record_sequence == ry.next_record_sequence);
        REQUIRE(rx.has_latest_attempt == ry.has_latest_attempt);
        if (rx.has_latest_attempt) {
            REQUIRE(rx.latest_attempt.stage == ry.latest_attempt.stage && rx.latest_attempt.status == ry.latest_attempt.status);
            REQUIRE(rx.latest_attempt.failure == ry.latest_attempt.failure && rx.latest_attempt.attempt == ry.latest_attempt.attempt);
            REQUIRE(rx.latest_attempt.sequence == ry.latest_attempt.sequence);
        }
        for (int stage = 0; stage < GOLEM_STAGE_COUNT; ++stage) {
            uint32_t nx = UINT32_MAX, ny = UINT32_MAX;
            golem_status sx = golem_work_run_attempts_get(x, (golem_stage)stage, &nx);
            golem_status sy = golem_work_run_attempts_get(y, (golem_stage)stage, &ny);
            REQUIRE(sx == sy && nx == ny);
        }
        REQUIRE(strcmp(golem_work_run_id_borrow(x), golem_work_run_id_borrow(y)) == 0);
    } else REQUIRE(x == NULL && y == NULL);
    golem_work_run_free(x); golem_work_run_free(y);
    golem_replay_free(whole); golem_replay_free(chunks);
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    if (size > GOLEM_JOURNAL_MAX_PAYLOAD + GOLEM_JOURNAL_HEADER_SIZE) return 0;
    golem_journal_record record;
    memset(&record, 0xa5, sizeof(record));
    unsigned char saved[sizeof(record)]; memcpy(saved, &record, sizeof(record));
    size_t consumed = SIZE_MAX;
    golem_status s = golem_journal_record_decode((golem_bytes){data, size}, &record, &consumed, NULL);
    if (s == GOLEM_OK) {
        REQUIRE(consumed <= size && consumed >= GOLEM_JOURNAL_HEADER_SIZE);
        uint8_t *wire = malloc(consumed); REQUIRE(wire != NULL); size_t n;
        REQUIRE(golem_journal_record_encode(record.type, record.sequence, record.payload, wire, consumed, &n, NULL) == GOLEM_OK);
        REQUIRE(n == consumed && memcmp(wire, data, n) == 0);
        free(wire);
    } else REQUIRE(consumed == SIZE_MAX && memcmp(saved, &record, sizeof(record)) == 0);
    golem_journal_reader reader;
    REQUIRE(golem_journal_reader_init(&reader, (golem_bytes){data, size}) == GOLEM_OK);
    for (;;) {
        size_t offset = reader.offset; uint64_t sequence = reader.next_sequence;
        bool has = false;
        memset(&record, 0xa5, sizeof(record)); memcpy(saved, &record, sizeof(record));
        s = golem_journal_reader_next(&reader, &record, &has, NULL);
        if (s != GOLEM_OK) {
            REQUIRE(reader.offset == offset && reader.next_sequence == sequence && !has);
            REQUIRE(memcmp(saved, &record, sizeof(record)) == 0);
            break;
        }
        if (!has) { REQUIRE(memcmp(saved, &record, sizeof(record)) == 0); break; }
        REQUIRE(reader.offset > offset && reader.offset <= size && record.sequence == sequence);
    }
    replay((golem_bytes){data, size});
    golem_journal_inspection inspection;
    REQUIRE(golem_journal_inspect((golem_bytes){data, size}, &inspection) == GOLEM_OK);
    REQUIRE(inspection.valid_bytes == reader.offset);
    REQUIRE(inspection.stream_status == s);
    REQUIRE(inspection.valid_bytes <= size);
    /* Reframe arbitrary payloads so CRC is not a coverage barrier to CREATED
     * capsule parsing. Raw framing above remains independently fuzzed. */
    if (size <= GOLEM_JOURNAL_MAX_PAYLOAD) {
        size_t cap = size + GOLEM_JOURNAL_HEADER_SIZE, n;
        uint8_t *wire = malloc(cap); REQUIRE(wire != NULL);
        REQUIRE(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){data, size}, wire, cap, &n, NULL) == GOLEM_OK);
        replay((golem_bytes){wire, n}); free(wire);
    }
    for (int type = GOLEM_JOURNAL_STARTED; type <= GOLEM_JOURNAL_CANCELLED; ++type) {
        golem_journal_record r = {(golem_journal_type)type, 1, {data, size}};
        golem_journal_event e;
        memset(&e, 0xa5, sizeof(e));
        unsigned char event_saved[sizeof(e)]; memcpy(event_saved, &e, sizeof(e));
        if (golem_journal_event_decode(&r, &e, NULL) == GOLEM_OK) {
            uint8_t wire[GOLEM_JOURNAL_EVENT_SIZE]; size_t n;
            REQUIRE(golem_journal_event_encode(&e, wire, sizeof(wire), &n, NULL) == GOLEM_OK);
            REQUIRE(n == size && memcmp(wire, data, n) == 0);
        } else REQUIRE(memcmp(event_saved, &e, sizeof(e)) == 0);
    }
    return 0;
}
