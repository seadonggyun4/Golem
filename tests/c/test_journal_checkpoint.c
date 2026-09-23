#define _POSIX_C_SOURCE 200809L
#include "golem/replay.h"
#include "test.h"
#include "journal_fixture.h"
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

int main(void)
{
    uint8_t bytes[FIXTURE_CAPACITY], changed[FIXTURE_CAPACITY];
    size_t size;
    CHECK(load_fixture("default", bytes, &size) == EXIT_SUCCESS);
    golem_journal_inspection inspection;
    CHECK(golem_journal_inspect((golem_bytes){bytes, size}, &inspection) == GOLEM_OK);
    golem_journal_checkpoint expected = {inspection.records, size, inspection.chain_head};
    for (unsigned mode = 0; mode < 4; ++mode) {
        golem_journal_checkpoint wanted = expected;
        if (mode == 1)
            wanted.chain_head.bytes[0] ^= 1;
        if (mode == 2)
            --wanted.records;
        if (mode == 3)
            ++wanted.bytes;
        golem_replay *engine = NULL;
        CHECK(golem_replay_create(NULL, NULL, &engine, NULL) == GOLEM_OK);
        CHECK(golem_replay_expect_checkpoint(engine, &wanted) == GOLEM_OK);
        CHECK(golem_replay_expect_checkpoint(engine, &wanted) == GOLEM_ERR_INVALID_STATE);
        for (size_t i = 0; i < size; ++i)
            CHECK(golem_replay_feed(engine, (golem_bytes){bytes + i, 1}, NULL) == GOLEM_OK);
        golem_work_run *run = NULL;
        CHECK(golem_replay_finish(engine, &run, NULL, NULL) ==
              (mode ? GOLEM_ERR_DIGEST_MISMATCH : GOLEM_OK));
        if (mode)
            CHECK(run == NULL);
        golem_work_run_free(run);
        golem_replay_free(engine);
    }
    char path[] = "/tmp/golem-checkpoint-XXXXXX";
    int fd = mkstemp(path);
    CHECK(fd >= 0);
    golem_journal *writer = NULL;
    CHECK(golem_journal_open(path, NULL, &writer, NULL) == GOLEM_OK);
    golem_journal_reader reader;
    CHECK(golem_journal_reader_init(&reader, (golem_bytes){bytes, size}) == GOLEM_OK);
    while (reader.offset < size) {
        golem_journal_record record;
        bool present;
        uint64_t sequence;
        CHECK(golem_journal_reader_next(&reader, &record, &present, NULL) == GOLEM_OK && present);
        CHECK(golem_journal_append(writer, record.type, record.payload, &sequence, NULL) ==
              GOLEM_OK);
    }
    golem_journal_checkpoint actual;
    CHECK(golem_journal_checkpoint_get(writer, &actual) == GOLEM_OK);
    CHECK(actual.records == expected.records && actual.bytes == expected.bytes);
    CHECK(!memcmp(actual.chain_head.bytes, expected.chain_head.bytes, GOLEM_DIGEST_SIZE));
    golem_work_run *run = NULL;
    CHECK(golem_journal_recover(writer, NULL, &run, NULL, NULL) == GOLEM_OK);
    golem_work_run_free(run);
    run = NULL;
    /* A same-length, CRC-correct rewrite remains structurally/semantically
     * valid but must not replace the writer's previously verified snapshot. */
    memcpy(changed, bytes, size);
    size_t goal = 0;
    for (size_t i = 0; i + 11 <= size; ++i)
        if (!memcmp(bytes + i, "Golden work", 11)) {
            goal = i;
            break;
        }
    CHECK(goal != 0);
    bytes[goal] = 'Z';
    golem_journal_record first;
    size_t consumed, encoded;
    /* The modified payload is borrowed without decoding its old CRC. */
    CHECK(golem_journal_record_decode((golem_bytes){changed, size}, &first, &consumed, NULL) ==
          GOLEM_OK);
    CHECK(golem_journal_record_encode(
              first.type, first.sequence,
              (golem_bytes){bytes + GOLEM_JOURNAL_HEADER_SIZE, first.payload.size}, changed,
              sizeof(changed), &encoded, NULL) == GOLEM_OK);
    CHECK(golem_journal_replay((golem_bytes){changed, size}, NULL, &run, NULL) == GOLEM_OK);
    golem_work_run_free(run);
    run = NULL;
    CHECK(pwrite(fd, changed, size, 0) == (ssize_t)size && fsync(fd) == 0);
    CHECK(golem_journal_recover(writer, NULL, &run, NULL, NULL) == GOLEM_ERR_DIGEST_MISMATCH);
    CHECK(run == NULL);
    CHECK(golem_journal_checkpoint_get(writer, &actual) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_journal_close(writer, NULL) == GOLEM_OK);
    CHECK(close(fd) == 0 && unlink(path) == 0);
    return EXIT_SUCCESS;
}
