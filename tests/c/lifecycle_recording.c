#define _POSIX_C_SOURCE 200809L
#define main existing_runtime_main
#include "test_runtime.c"
#undef main
#include "golem/record.h"
#include "golem/replay.h"
#include <errno.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    CHECK(argc == 2);
    CHECK(unsetenv("GOLEM_RECORD_ROOT") == 0);
    fixture f = {0};
    CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL, NULL, 2, 16, 0) == 0);
    char path[4096];
    CHECK(snprintf(path, sizeof(path), "%s/journal", argv[1]) > 0);
    golem_journal *journal = NULL;
    CHECK(golem_journal_open(path, NULL, &journal, NULL) == GOLEM_OK);
    CHECK(snprintf(path, sizeof(path), "%s/missing", argv[1]) > 0);
    CHECK(setenv("GOLEM_RECORD_ROOT", path, 1) == 0);
    CHECK(golem_runtime_step(f.runtime) != GOLEM_OK && f.calls == 0 && f.records == 0);
    CHECK(golem_runtime_cancel(f.runtime) == GOLEM_OK);
    golem_runtime_report report;
    CHECK(golem_runtime_report_get(f.runtime, &report) == GOLEM_OK);
    CHECK(report.work.status == GOLEM_WORK_CANCELLED && f.calls == 0);
    CHECK(replay(&f, GOLEM_WORK_CANCELLED) == 0);
    golem_work_capsule *c = NULL;
    CHECK(capsule(GOLEM_AUTONOMY_AUTO_LOCAL, NULL, &c) == 0);
    uint8_t bytes[16384]; size_t size; uint64_t sequence;
    CHECK(golem_journal_created_encode("lifecycle", c, 2, bytes, sizeof(bytes), &size, NULL) == GOLEM_OK);
    CHECK(golem_journal_append(journal, GOLEM_JOURNAL_CREATED, (golem_bytes){bytes, size}, &sequence, NULL) == GOLEM_OK);
    CHECK(sequence == 1);
    golem_journal_checkpoint checkpoint;
    CHECK(golem_journal_checkpoint_get(journal, &checkpoint) == GOLEM_OK);
    CHECK(golem_journal_close(journal, NULL) == GOLEM_OK);
    golem_work_capsule_free(c);
    errno = EDOM;
    golem_runtime_free(f.runtime);
    CHECK(errno == EDOM);
    golem_record_api_outcome result = {.struct_size = sizeof(result), .version = 1};
    CHECK(golem_record_last_api_outcome(&result));
    CHECK(result.dispatched && result.operation_status == GOLEM_OK && result.recording_status != GOLEM_OK);
    CHECK(!strcmp(result.operation, "golem_runtime_free"));
    CHECK(unsetenv("GOLEM_RECORD_ROOT") == 0);
    CHECK(snprintf(path, sizeof(path), "%s/journal", argv[1]) > 0);
    CHECK(golem_journal_open(path, NULL, &journal, NULL) == GOLEM_OK);
    golem_work_run *run = NULL;
    CHECK(golem_journal_recover(journal, NULL, &run, NULL, NULL) == GOLEM_OK);
    golem_work_run_free(run);
    CHECK(golem_journal_close(journal, NULL) == GOLEM_OK);
    CHECK(unlink(path) == 0);
    return 0;
}
