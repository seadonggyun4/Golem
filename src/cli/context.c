#include "work.h"
#include "golem/context.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_context(int argc, char **argv)
{
    if (argc < 5)
        return 2;
    bool render = argc == 5 && !strcmp(argv[2], "render");
    bool markdown = argc == 5 && !strcmp(argv[2], "markdown");
    bool publish = argc == 5 && !strcmp(argv[2], "publish");
    bool read = argc == 6 && !strcmp(argv[2], "read");
    if (!render && !markdown && !publish && !read)
        return 2;
    golem_digest digest, source;
    if (read &&
        (golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &digest) != GOLEM_OK ||
         golem_digest_parse((golem_string_view){argv[5], strlen(argv[5])}, &source) != GOLEM_OK))
        return 2;
    cli_blob request = {0};
    golem_status st = read ? GOLEM_OK : cli_read(argv[4], GOLEM_CONTEXT_REQUEST_MAX, &request);
    golem_document_store *s = NULL;
    if (st == GOLEM_OK)
        st = golem_document_store_open(argv[3], publish, NULL, &s, NULL);
    struct json_object *o = NULL;
    uint8_t *buffer = NULL;
    size_t n = 0, capacity = 0;
    if (st == GOLEM_OK && publish) {
        golem_receipt receipt;
        st = golem_context_publish(s, (golem_bytes){request.data, request.size}, NULL, &receipt,
                                   NULL);
        if (st == GOLEM_OK) {
            char hex[65];
            size_t ignored;
            st = golem_digest_format(&receipt.digest, hex, sizeof(hex), &ignored);
            o = json_object_new_object();
            if (st == GOLEM_OK && (!o || !cli_json_add(o, "digest", json_object_new_string(hex)) ||
                                   !cli_json_add(o, "bytes", cli_json_u64(receipt.size)) ||
                                   !cli_json_add(o, "derived_only", json_object_new_boolean(true))))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
    } else
        for (int pass = 0; st == GOLEM_OK && pass < 2; ++pass) {
            st = read ? golem_context_read(s, &digest, &source, NULL, buffer, capacity, &n, NULL)
                      : golem_context_render(s, (golem_bytes){request.data, request.size}, NULL,
                                             buffer, capacity, &n, NULL);
            if (pass == 0 && st == GOLEM_ERR_BUFFER_TOO_SMALL) {
                buffer = malloc(n);
                capacity = n;
                st = buffer ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
            }
        }
    if (st == GOLEM_OK && !publish)
        st = cli_json_parse((golem_bytes){buffer, n}, &o);
    golem_status closed = golem_document_store_close(s);
    if (st == GOLEM_OK)
        st = closed;
    free(request.data);
    free(buffer);
    if (st == GOLEM_OK && markdown) {
        struct json_object *value = NULL;
        if (!json_object_object_get_ex(o, "markdown", &value))
            st = GOLEM_ERR_PARSE;
        else {
            const char *bytes = json_object_get_string(value);
            size_t size = (size_t)json_object_get_string_len(value);
            if (fwrite(bytes, 1, size, stdout) != size || fflush(stdout))
                st = GOLEM_ERR_IO;
        }
        json_object_put(o);
        return st == GOLEM_OK ? 0 : 1;
    }
    return cli_emit(st, o);
}
