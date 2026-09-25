#include "work.h"
#include "golem/workflow_template.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_workflow_template(int argc, char **argv)
{
    if (argc == 4 && !strcmp(argv[3], "list")) {
        return puts("[\"feature\",\"bugfix\",\"review\",\"research\"]") < 0 ? 1 : 0;
    }
    bool show = argc == 5 && !strcmp(argv[3], "show");
    bool validate = argc == 5 && !strcmp(argv[3], "validate");
    bool instantiate = argc == 8 && !strcmp(argv[3], "instantiate");
    if (!show && !validate && !instantiate) {
        fputs("usage: golem workflow template list\n"
              "       golem workflow template show NAME\n"
              "       golem workflow template validate TEMPLATE.json\n"
              "       golem workflow template instantiate WORK SCOPE REVISION TEMPLATE.json\n",
              stderr);
        return 2;
    }
    cli_blob input = {0};
    golem_execution_reply reply = {0};
    golem_document_store *store = NULL;
    golem_status st = GOLEM_OK;
    if (show)
        st = golem_workflow_template_builtin(argv[4], &reply);
    else
        st = cli_read(argv[instantiate ? 7 : 4], 65536, &input);
    golem_digest digest;
    if (st == GOLEM_OK && validate)
        st = golem_workflow_template_validate((golem_bytes){input.data, input.size}, &digest);
    uint32_t revision = 0;
    if (st == GOLEM_OK && instantiate) {
        const char *p = argv[6];
        for (; *p; ++p) {
            if (*p < '0' || *p > '9' || revision > GOLEM_DOCUMENT_MAX_REVISIONS / 10) {
                st = GOLEM_ERR_PARSE;
                break;
            }
            revision = revision * 10 + (unsigned)(*p - '0');
        }
        if (!revision || revision > GOLEM_DOCUMENT_MAX_REVISIONS)
            st = GOLEM_ERR_PARSE;
        if (st == GOLEM_OK)
            st = golem_document_store_open(argv[4], false, NULL, &store, NULL);
        if (st == GOLEM_OK)
            st = golem_workflow_template_instantiate(store, argv[5], revision,
                                                     (golem_bytes){input.data, input.size}, &reply);
    }
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK && validate) {
        char hex[65];
        size_t needed;
        st = golem_digest_format(&digest, hex, sizeof(hex), &needed);
        if (st == GOLEM_OK && puts(hex) < 0)
            st = GOLEM_ERR_IO;
    } else if (st == GOLEM_OK && (fwrite(reply.data, 1, reply.size, stdout) != reply.size ||
                                  fputc('\n', stdout) == EOF))
        st = GOLEM_ERR_IO;
    free(input.data);
    golem_execution_reply_free(&reply);
    return st == GOLEM_OK ? 0 : cli_emit(st, NULL);
}
