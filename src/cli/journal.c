#include "work.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define JOURNAL_INSPECT_LIMIT (64u * 1024u * 1024u)

static golem_status read_component(const char *root, const char *name, size_t limit, cli_blob *out)
{
    char path[CLI_PATH_MAX];
    golem_status status = cli_path(root, name, path);
    return status == GOLEM_OK ? cli_read(path, limit, out) : status;
}

static bool matches(struct json_object *object, const char *key, const char *expected)
{
    struct json_object *value = NULL;
    if (!json_object_object_get_ex(object, key, &value))
        return false;
    const char *text = cli_json_text(value);
    return text && !strcmp(text, expected);
}

static bool receipt_boundary(struct json_object *object, size_t retained)
{
    const char *keys[] = {
        "schema_version", "source_digest", "chain_head",          "chain_algorithm",
        "source_bytes",   "valid_bytes",   "discarded_bytes",     "records",
        "stream_status",  "authenticated", "execution_authorized"};
    if (!cli_json_keys(object, keys, sizeof(keys) / sizeof(keys[0])) ||
        json_object_object_length(object) != 11)
        return false;
    struct json_object *value = NULL;
    if (!json_object_object_get_ex(object, "schema_version", &value) ||
        !json_object_is_type(value, json_type_int) || json_object_get_int64(value) != 1)
        return false;
    const char *flags[] = {"authenticated", "execution_authorized"};
    for (size_t i = 0; i < 2; ++i)
        if (!json_object_object_get_ex(object, flags[i], &value) ||
            !json_object_is_type(value, json_type_boolean) || json_object_get_boolean(value))
            return false;
    if (!json_object_object_get_ex(object, "source_digest", &value))
        return false;
    const char *digest = cli_json_text(value);
    golem_digest parsed;
    if (!digest ||
        golem_digest_parse((golem_string_view){digest, strlen(digest)}, &parsed) != GOLEM_OK)
        return false;
    size_t sizes[2] = {0};
    const char *names[] = {"source_bytes", "discarded_bytes"};
    for (size_t i = 0; i < 2; ++i) {
        if (!json_object_object_get_ex(object, names[i], &value))
            return false;
        const char *text = cli_json_text(value);
        if (!text || !*text || (text[0] == '0' && text[1]))
            return false;
        for (; *text; ++text) {
            unsigned digit = (unsigned)(*text - '0');
            if (digit > 9 || sizes[i] > (JOURNAL_INSPECT_LIMIT - digit) / 10)
                return false;
            sizes[i] = sizes[i] * 10 + digit;
        }
    }
    return retained > 0 && sizes[0] > retained && sizes[0] - retained == sizes[1];
}

static int verify_salvage(const char *root, const char *anchor)
{
    golem_digest expected, actual;
    golem_status status =
        golem_digest_parse((golem_string_view){anchor, strlen(anchor)}, &expected);
    cli_blob receipt = {0}, commit = {0}, journal = {0};
    if (status == GOLEM_OK)
        status = read_component(root, "salvage.commit", 64, &commit);
    if (status == GOLEM_OK && (commit.size != 64 || memcmp(commit.data, anchor, 64)))
        status = GOLEM_ERR_DIGEST_MISMATCH;
    if (status == GOLEM_OK)
        status = read_component(root, "salvage.json", CLI_BUNDLE_MAX, &receipt);
    if (status == GOLEM_OK)
        status = golem_digest_bytes((golem_bytes){receipt.data, receipt.size}, &actual);
    if (status == GOLEM_OK && memcmp(actual.bytes, expected.bytes, GOLEM_DIGEST_SIZE))
        status = GOLEM_ERR_DIGEST_MISMATCH;
    struct json_object *object = NULL;
    if (status == GOLEM_OK)
        status = cli_json_parse((golem_bytes){receipt.data, receipt.size}, &object);
    if (status == GOLEM_OK)
        status = read_component(root, "journal.bin", JOURNAL_INSPECT_LIMIT, &journal);
    golem_journal_inspection inspection;
    if (status == GOLEM_OK)
        status = golem_journal_inspect((golem_bytes){journal.data, journal.size}, &inspection);
    if (status == GOLEM_OK)
        status = inspection.stream_status;
    if (status == GOLEM_OK && !receipt_boundary(object, inspection.valid_bytes))
        status = GOLEM_ERR_PARSE;
    if (status == GOLEM_OK) {
        char head[GOLEM_DIGEST_HEX_CAPACITY];
        size_t required;
        (void)golem_digest_format(&inspection.chain_head, head, sizeof(head), &required);
        struct json_object *count = cli_json_u64(inspection.records);
        struct json_object *size = cli_json_u64(inspection.valid_bytes);
        if (!count || !size)
            status = GOLEM_ERR_OUT_OF_MEMORY;
        else if (!matches(object, "chain_head", head) ||
                 !matches(object, "valid_bytes", cli_json_text(size)) ||
                 !matches(object, "records", cli_json_text(count)) ||
                 !matches(object, "chain_algorithm", "golem.journal.chain.v1") ||
                 !matches(object, "stream_status",
                          golem_status_string(GOLEM_ERR_TRUNCATED_JOURNAL)))
            status = GOLEM_ERR_REPLAY_MISMATCH;
        json_object_put(count);
        json_object_put(size);
    }
    golem_work_run *run = NULL;
    if (status == GOLEM_OK)
        status = golem_journal_replay((golem_bytes){journal.data, journal.size}, NULL, &run, NULL);
    golem_work_run_free(run);
    free(receipt.data);
    free(commit.data);
    free(journal.data);
    return cli_emit(status, object);
}

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
    if (argc == 6 && !strcmp(argv[2], "verify-salvage") && !strcmp(argv[4], "--expect-receipt"))
        return verify_salvage(argv[3], argv[5]);
    bool inspect = argc >= 3 && !strcmp(argv[2], "inspect");
    bool salvage = argc >= 3 && !strcmp(argv[2], "salvage");
    bool anchored = inspect && argc == 6 && !strcmp(argv[4], "--expect-chain");
    if ((!inspect && !salvage) || (inspect && argc != 4 && !anchored) ||
        (salvage && (argc != 8 || strcmp(argv[5], "--expect-source") ||
                     strcmp(argv[7], "--accept-truncated-tail")))) {
        fputs("Usage: golem journal inspect FILE [--expect-chain SHA256]\n"
              "       golem journal verify-salvage DIRECTORY --expect-receipt SHA256\n"
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
        /* Publish the receipt commitment last. Partial exports have no valid
         * commit marker and cannot pass verify-salvage. No source is modified. */
        if (status == GOLEM_OK) {
            const char *encoded = json_object_to_json_string_ext(object, JSON_C_TO_STRING_PLAIN);
            golem_digest digest;
            char hex[GOLEM_DIGEST_HEX_CAPACITY];
            size_t required;
            status = encoded
                         ? golem_digest_bytes(
                               (golem_bytes){(const uint8_t *)encoded, strlen(encoded)}, &digest)
                         : GOLEM_ERR_OUT_OF_MEMORY;
            if (status == GOLEM_OK)
                status = golem_digest_format(&digest, hex, sizeof(hex), &required);
            if (status == GOLEM_OK)
                status = cli_write_new(directory, "salvage.commit",
                                       (golem_bytes){(const uint8_t *)hex, 64});
        }
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
