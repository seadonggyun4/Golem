#include "work.h"
#include "golem/approval.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_approval(int argc, char **argv)
{
    bool describe = argc == 5 && !strcmp(argv[2], "describe");
    bool call = argc == 5 && !strcmp(argv[2], "call");
    if (!describe && !call) {
        fputs("usage: golem approval describe WORK EXECUTION.json\n"
              "       golem approval call WORK REQUEST.json\n",
              stderr);
        return 2;
    }
    cli_blob input = {0};
    struct json_object *r = NULL;
    golem_document_store *s = NULL;
    golem_execution_reply out = {0};
    golem_status st =
        cli_read(argv[4], describe ? GOLEM_DOCUMENT_MAX_JSON : GOLEM_APPROVAL_MAX_JSON, &input);
    if (st == GOLEM_OK)
        st = cli_json_parse((golem_bytes){input.data, input.size}, &r);
    const char *op = r ? cli_json_text(json_object_object_get(r, "operation")) : "";
    bool readonly = describe || !strcmp(op, "status") || !strcmp(op, "recover");
    if (st == GOLEM_OK)
        st = golem_document_store_open(argv[3], !readonly, NULL, &s, NULL);
    if (st == GOLEM_OK)
        st = describe
                 ? golem_approval_describe(s, (golem_bytes){input.data, input.size}, &out, NULL)
                 : golem_approval_call(s, (golem_bytes){input.data, input.size}, NULL, NULL, &out,
                                       NULL);
    golem_status closed = golem_document_store_close(s);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK && (fwrite(out.data, 1, out.size, stdout) != out.size ||
                           fputc('\n', stdout) == EOF || fflush(stdout)))
        st = GOLEM_ERR_IO;
    golem_execution_reply_free(&out);
    json_object_put(r);
    free(input.data);
    if (st != GOLEM_OK)
        fprintf(stderr, "approval: %s\n", golem_status_string(st));
    return st == GOLEM_OK ? 0 : 1;
}
