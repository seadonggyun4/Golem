#include "work.h"
#include "golem/candidate.h"
#include "candidate_host.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_candidate(int argc, char **argv)
{
    if (argc >= 3 && (!strcmp(argv[2], "host-validate") || !strcmp(argv[2], "request-digest") ||
                      !strcmp(argv[2], "serve") || !strcmp(argv[2], "call")))
        return golem_cli_candidate_host(argc, argv);
    bool validate = argc == 4 && !strcmp(argv[2], "validate");
    bool gates = argc == 5 && !strcmp(argv[2], "gates");
    bool status = argc == 5 && !strcmp(argv[2], "status");
    if (!validate && !gates && !status) {
        fputs("usage: golem candidate validate MANIFEST.json\n"
              "       golem candidate gates WORK CHECKPOINT_SHA256\n"
              "       golem candidate status PARENT_WORK GROUP_ID\n"
              "       golem candidate host-validate CONFIG.json\n"
              "       golem candidate serve CONFIG.json SOCKET --approve-config SHA256\n"
              "       golem candidate call SOCKET REQUEST.json [--approve-request SHA256]\n",
              stderr);
        return 2;
    }
    cli_blob bytes = {0};
    golem_document_store *work = NULL;
    golem_execution_reply reply = {0};
    golem_digest digest;
    golem_status st = GOLEM_OK;
    if (validate) {
        st = cli_read(argv[3], GOLEM_DOCUMENT_MAX_JSON, &bytes);
        if (st == GOLEM_OK)
            st = golem_candidate_validate((golem_bytes){bytes.data, bytes.size}, &digest, NULL);
    } else {
        st = golem_document_store_open(argv[3], false, NULL, &work, NULL);
        if (st == GOLEM_OK && gates)
            st = golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &digest);
        if (st == GOLEM_OK && gates)
            st = golem_candidate_gate_digest(work, &digest, &digest, NULL);
        if (st == GOLEM_OK && status) {
            size_t n = strlen(argv[4]);
            if (!n || n > 24)
                st = GOLEM_ERR_PARSE;
            for (size_t i = 0; st == GOLEM_OK && i < n; ++i)
                if (!((argv[4][i] >= 'a' && argv[4][i] <= 'z') ||
                      (argv[4][i] >= 'A' && argv[4][i] <= 'Z') ||
                      (argv[4][i] >= '0' && argv[4][i] <= '9') || argv[4][i] == '-' ||
                      argv[4][i] == '_'))
                    st = GOLEM_ERR_PARSE;
            char request[128];
            int size =
                snprintf(request, sizeof(request), "{\"operation\":\"status\",\"group_id\":\"%s\"}",
                         st == GOLEM_OK ? argv[4] : "");
            if (st == GOLEM_OK)
                st = golem_candidate_call(work, NULL, NULL,
                                          (golem_bytes){(const uint8_t *)request, (size_t)size},
                                          &reply, NULL);
        }
    }
    golem_status closed = golem_document_store_close(work);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK && status) {
        if (fwrite(reply.data, 1, reply.size, stdout) != reply.size || fputc('\n', stdout) == EOF)
            st = GOLEM_ERR_IO;
    } else if (st == GOLEM_OK) {
        char hex[65];
        size_t needed;
        st = golem_digest_format(&digest, hex, sizeof(hex), &needed);
        if (st == GOLEM_OK && puts(hex) < 0)
            st = GOLEM_ERR_IO;
    }
    free(bytes.data);
    golem_execution_reply_free(&reply);
    return st == GOLEM_OK ? 0 : cli_emit(st, NULL);
}
