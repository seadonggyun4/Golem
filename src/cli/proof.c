#include "work.h"
#include "golem/proof.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_proof(int argc, char **argv)
{
    bool render = argc == 5 && !strcmp(argv[2], "render");
    bool verify = argc == 6 && !strcmp(argv[2], "verify");
    bool publish = argc == 5 && !strcmp(argv[2], "publish");
    bool directory = argc == 5 && !strcmp(argv[2], "verify-dir");
    bool integrity = (argc == 4 || argc == 5) && !strcmp(argv[2], "integrity");
    if (!render && !verify && !publish && !directory && !integrity) {
        fputs("usage: golem proof render WORK REQUEST.json\n"
              "       golem proof verify WORK REQUEST.json PACK.json\n"
              "       golem proof publish PACK.json EXISTING_PRIVATE_ROOT\n"
              "       golem proof integrity PACK.json [EXPECTED_MANIFEST_SHA256]\n"
              "       golem proof verify-dir EXISTING_PRIVATE_ROOT MANIFEST_SHA256\n",
              stderr);
        return 2;
    }
    cli_blob input = {0}, pack = {0};
    golem_execution_reply reply = {0};
    golem_document_store *store = NULL;
    golem_digest digest;
    golem_status st = GOLEM_OK;
    if (directory || (integrity && argc == 5))
        st = golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &digest);
    if (st == GOLEM_OK && !directory)
        st = cli_read(argv[render || verify ? 4 : 3], GOLEM_DOCUMENT_MAX_JSON, &input);
    if (st == GOLEM_OK && verify)
        st = cli_read(argv[5], GOLEM_DOCUMENT_MAX_JSON, &pack);
    if (st == GOLEM_OK && (render || verify))
        st = golem_document_store_open(argv[3], false, NULL, &store, NULL);
    golem_bytes bytes = {input.data, input.size};
    if (st == GOLEM_OK) {
        if (render)
            st = golem_proof_render(store, bytes, &reply, NULL);
        else if (verify)
            st = golem_proof_verify(store, bytes, (golem_bytes){pack.data, pack.size}, NULL);
        else if (publish)
            st = golem_proof_publish(bytes, argv[4], &digest, NULL);
        else if (directory)
            st = golem_proof_verify_directory(argv[3], &digest, NULL);
        else
            st = golem_proof_integrity(bytes, argc == 5 ? &digest : NULL, NULL);
    }
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK && render &&
        (fwrite(reply.data, 1, reply.size, stdout) != reply.size || fputc('\n', stdout) == EOF))
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && publish) {
        char hex[65];
        size_t needed;
        st = golem_digest_format(&digest, hex, sizeof(hex), &needed);
        if (st == GOLEM_OK &&
            printf("{\"manifest_sha256\":\"%s\",\"acceptance_verified\":false}\n", hex) < 0)
            st = GOLEM_ERR_IO;
    } else if (st == GOLEM_OK && !render &&
               printf("{\"integrity_verified\":true,\"source_projection_verified\":%s,\"acceptance_"
                      "verified\":false}\n",
                      verify ? "true" : "false") < 0)
        st = GOLEM_ERR_IO;
    free(input.data);
    free(pack.data);
    golem_execution_reply_free(&reply);
    return st == GOLEM_OK ? 0 : cli_emit(st, NULL);
}
