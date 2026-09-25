#include "work.h"
#include "golem/role_contract.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_role(int argc, char **argv)
{
    bool sample = argc == 4 && !strcmp(argv[2], "template");
    bool validate = argc == 4 && !strcmp(argv[2], "validate");
    bool call = (argc == 5 || (argc == 7 && !strcmp(argv[5], "--approve-contract"))) &&
                !strcmp(argv[2], "call");
    if (!sample && !validate && !call)
        return 2;
    cli_blob b = {0};
    golem_execution_reply out = {0};
    golem_document_store *s = NULL;
    struct json_object *request = NULL;
    golem_digest digest, approval;
    golem_status st = GOLEM_OK;
    if (sample)
        st = golem_role_template(argv[3], &out);
    else
        st = cli_read(argv[validate ? 3 : 4], GOLEM_ROLE_MAX_JSON, &b);
    if (st == GOLEM_OK && validate) {
        st = golem_role_validate((golem_bytes){b.data, b.size}, &digest, NULL);
        char hex[GOLEM_DIGEST_HEX_CAPACITY];
        size_t required;
        if (st == GOLEM_OK)
            st = golem_digest_format(&digest, hex, sizeof(hex), &required);
        if (st == GOLEM_OK && printf("{\"contract_digest\":\"%s\"}", hex) < 0)
            st = GOLEM_ERR_IO;
    }
    if (st == GOLEM_OK && call && argc == 7)
        st = golem_digest_parse((golem_string_view){argv[6], strlen(argv[6])}, &approval);
    if (st == GOLEM_OK && call)
        st = cli_json_parse((golem_bytes){b.data, b.size}, &request);
    if (st == GOLEM_OK && call) {
        const char *op = cli_json_text(json_object_object_get(request, "operation"));
        bool writable = strcmp(op, "evaluate") && strcmp(op, "status");
        st = golem_document_store_open(argv[3], writable, NULL, &s, NULL);
    }
    if (st == GOLEM_OK && call)
        st = golem_role_call(s, (golem_bytes){b.data, b.size}, argc == 7 ? &approval : NULL, &out,
                             NULL);
    if (st == GOLEM_OK && out.size && fwrite(out.data, 1, out.size, stdout) != out.size)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && (fputc('\n', stdout) == EOF || fflush(stdout)))
        st = GOLEM_ERR_IO;
    free(b.data);
    json_object_put(request);
    golem_execution_reply_free(&out);
    golem_status closed = golem_document_store_close(s);
    if (st == GOLEM_OK)
        st = closed;
    if (st != GOLEM_OK)
        fprintf(stderr, "role: %s\n", golem_status_string(st));
    return st == GOLEM_OK ? 0 : 1;
}
