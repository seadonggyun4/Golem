#include "work.h"
#include "golem/runtime_profile.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static bool number(const char *text, uint64_t *out)
{
    uint64_t value = 0;
    if (!text || !*text)
        return false;
    for (; *text; ++text) {
        if (*text < '0' || *text > '9' || value > (UINT64_MAX - (unsigned)(*text - '0')) / 10)
            return false;
        value = value * 10 + (unsigned)(*text - '0');
    }
    *out = value;
    return true;
}

static int link_run(char **argv)
{
    golem_digest binding, receipt;
    golem_journal_checkpoint checkpoint = {0};
    golem_status status =
        golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &binding);
    if (status == GOLEM_OK)
        status = golem_digest_parse((golem_string_view){argv[9], strlen(argv[9])},
                                    &checkpoint.chain_head);
    if (!number(argv[7], &checkpoint.records) || !number(argv[8], &checkpoint.bytes))
        status = GOLEM_ERR_INVALID_ARGUMENT;
    cli_blob journal = {0};
    golem_document_store *store = NULL;
    if (status == GOLEM_OK)
        status = cli_read(argv[5], 16u * 1024u * 1024u, &journal);
    if (status == GOLEM_OK)
        status = golem_document_store_open(argv[3], true, NULL, &store, NULL);
    if (status == GOLEM_OK)
        status = golem_runtime_link_run(store, &binding, (golem_bytes){journal.data, journal.size},
                                        argv[6], &checkpoint, &receipt, NULL);
    struct json_object *output = NULL;
    if (status == GOLEM_OK) {
        char hex[GOLEM_DIGEST_HEX_CAPACITY];
        size_t required;
        status = golem_digest_format(&receipt, hex, sizeof(hex), &required);
        output = json_object_new_object();
        if (status == GOLEM_OK &&
            (!cli_json_add(output, "link_receipt", json_object_new_string(hex)) ||
             !cli_json_add(output, "execution_authorized", json_object_new_boolean(false))))
            status = GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_status closed = golem_document_store_close(store);
    if (status == GOLEM_OK)
        status = closed;
    free(journal.data);
    return cli_emit(status, output);
}

int golem_cli_runtime_profile(int argc, char **argv)
{
    if (argc == 10 && !strcmp(argv[2], "link"))
        return link_run(argv);
    bool validate = argc == 4 && !strcmp(argv[2], "validate");
    bool current = argc == 4 && !strcmp(argv[2], "current");
    bool publish = argc == 6 && !strcmp(argv[2], "register");
    if (!validate && !current && !publish) {
        fputs("usage: golem profile validate PROFILE.json\n"
              "       golem profile register WORK PROFILE.json KEY\n"
              "       golem profile current WORK\n"
              "       golem profile link WORK BINDING JOURNAL RUN_ID RECORDS BYTES CHAIN_HEAD\n",
              stderr);
        return 2;
    }
    cli_blob input = {0};
    golem_runtime_profile *profile = NULL;
    golem_document_store *store = NULL;
    golem_status status = GOLEM_OK;
    struct json_object *output = NULL;
    if (!current) {
        status = cli_read(argv[publish ? 4 : 3], GOLEM_RUNTIME_PROFILE_MAX_BYTES, &input);
        if (status == GOLEM_OK)
            status = golem_runtime_profile_parse((golem_bytes){input.data, input.size}, NULL,
                                                 &profile, NULL);
    }
    if (status == GOLEM_OK && !validate)
        status = golem_document_store_open(argv[3], publish, NULL, &store, NULL);
    if (status == GOLEM_OK && current) {
        size_t size = 0;
        status = golem_runtime_profile_current(store, NULL, 0, &size);
        if (status == GOLEM_ERR_BUFFER_TOO_SMALL) {
            input.data = malloc(size);
            status = input.data
                         ? golem_runtime_profile_current(store, input.data, size, &input.size)
                         : GOLEM_ERR_OUT_OF_MEMORY;
        }
        if (status == GOLEM_ERR_NOT_FOUND) {
            output = json_object_new_object();
            status = cli_json_add(output, "runtime_identity", json_object_new_string("UNKNOWN"))
                         ? GOLEM_OK
                         : GOLEM_ERR_OUT_OF_MEMORY;
        } else if (status == GOLEM_OK)
            status = cli_json_parse((golem_bytes){input.data, input.size}, &output);
    } else if (status == GOLEM_OK) {
        golem_digest digest;
        status = publish ? golem_runtime_profile_register(store, profile, argv[5], &digest, NULL)
                         : golem_runtime_profile_digest(profile, &digest);
        char hex[GOLEM_DIGEST_HEX_CAPACITY];
        size_t size;
        if (status == GOLEM_OK)
            status = golem_digest_format(&digest, hex, sizeof(hex), &size);
        if (status == GOLEM_OK) {
            output = json_object_new_object();
            if (!cli_json_add(output, "profile_digest", json_object_new_string(hex)) ||
                !cli_json_add(output, "committed", json_object_new_boolean(publish)) ||
                !cli_json_add(output, "execution_authorized", json_object_new_boolean(false)))
                status = GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    golem_status closed = golem_document_store_close(store);
    if (status == GOLEM_OK)
        status = closed;
    golem_runtime_profile_free(profile);
    free(input.data);
    return cli_emit(status, output);
}
