#include "work.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define JOURNAL_INSPECT_LIMIT (64u * 1024u * 1024u)

static struct json_object *inspection_json(const golem_journal_inspection *report, size_t size)
{
    char source[GOLEM_DIGEST_HEX_CAPACITY], head[GOLEM_DIGEST_HEX_CAPACITY];
    size_t required;
    (void)golem_digest_format(&report->source_digest, source, sizeof(source), &required);
    (void)golem_digest_format(&report->chain_head, head, sizeof(head), &required);
    struct json_object *object = json_object_new_object();
    if (!cli_json_add(object, "schema_version", json_object_new_int(1)) ||
        !cli_json_add(object, "source_digest", json_object_new_string(source)) ||
        !cli_json_add(object, "chain_head", json_object_new_string(head)) ||
        !cli_json_add(object, "chain_algorithm",
                      json_object_new_string("golem.journal.chain.v1")) ||
        !cli_json_add(object, "source_bytes", cli_json_u64(size)) ||
        !cli_json_add(object, "valid_bytes", cli_json_u64(report->valid_bytes)) ||
        !cli_json_add(object, "discarded_bytes", cli_json_u64(size - report->valid_bytes)) ||
        !cli_json_add(object, "records", cli_json_u64(report->records)) ||
        !cli_json_add(object, "stream_status",
                      json_object_new_string(golem_status_string(report->stream_status))) ||
        !cli_json_add(object, "authenticated", json_object_new_boolean(false)) ||
        !cli_json_add(object, "execution_authorized", json_object_new_boolean(false))) {
        json_object_put(object);
        return NULL;
    }
    return object;
}

int golem_cli_journal(int argc, char **argv)
{
    bool inspect = argc >= 3 && !strcmp(argv[2], "inspect");
    bool salvage = argc >= 3 && !strcmp(argv[2], "salvage");
    bool anchored = inspect && argc == 6 && !strcmp(argv[4], "--expect-chain");
    if ((!inspect && !salvage) || (inspect && argc != 4 && !anchored) ||
        (salvage && (argc != 8 || strcmp(argv[5], "--expect-source") ||
                     strcmp(argv[7], "--accept-truncated-tail")))) {
        fputs("Usage: golem journal inspect FILE [--expect-chain SHA256]\n"
              "       golem journal salvage FILE NEW_DIRECTORY --expect-source SHA256 "
              "--accept-truncated-tail\n",
              stderr);
        return 2;
    }
    golem_digest expected;
    golem_status status = GOLEM_OK;
    if (anchored || salvage) {
        const char *hex = argv[salvage ? 6 : 5];
        status = golem_digest_parse((golem_string_view){hex, strlen(hex)}, &expected);
    }
    cli_blob source = {0};
    if (status == GOLEM_OK)
        status = cli_read(argv[3], JOURNAL_INSPECT_LIMIT, &source);
    golem_journal_inspection report = {0};
    if (status == GOLEM_OK)
        status = golem_journal_inspect((golem_bytes){source.data, source.size}, &report);
    if (status == GOLEM_OK && (anchored || salvage)) {
        const golem_digest *observed = salvage ? &report.source_digest : &report.chain_head;
        if (memcmp(expected.bytes, observed->bytes, GOLEM_DIGEST_SIZE) != 0)
            status = GOLEM_ERR_DIGEST_MISMATCH;
    }
    struct json_object *object = status == GOLEM_OK ? inspection_json(&report, source.size) : NULL;
    if (status == GOLEM_OK && object == NULL)
        status = GOLEM_ERR_OUT_OF_MEMORY;
    if (status == GOLEM_OK && salvage) {
        /* Only a torn final frame is eligible. Never skip CRC errors, gaps or
         * semantic corruption. A new directory prevents source replacement. */
        if (report.stream_status != GOLEM_ERR_TRUNCATED_JOURNAL || report.valid_bytes == 0)
            status = GOLEM_ERR_INVALID_STATE;
        golem_work_run *run = NULL;
        if (status == GOLEM_OK)
            status = golem_journal_replay((golem_bytes){source.data, report.valid_bytes}, NULL,
                                          &run, NULL);
        golem_work_run_free(run);
        int directory = -1;
        if (status == GOLEM_OK)
            status = cli_mkdir_new(argv[4], &directory);
        if (status == GOLEM_OK)
            status = cli_write_new(directory, "journal.bin",
                                   (golem_bytes){source.data, report.valid_bytes});
        if (status == GOLEM_OK)
            status = cli_json_write(directory, "salvage.json", object);
        if (directory >= 0 && close(directory) < 0 && status == GOLEM_OK)
            status = GOLEM_ERR_IO;
    }
    free(source.data);
    /* Inspection reports malformed streams on stdout but exits unsuccessfully. */
    int result = cli_emit(status, object);
    if (!salvage && result == 0 && report.stream_status != GOLEM_OK)
        result = 1;
    return result;
}
