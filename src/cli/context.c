#include "work.h"
#include "golem/context.h"
#include "context_tokenizer.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static golem_status candidate_count(void *context, golem_bytes bytes, uint64_t *tokens)
{
    (void)context; (void)bytes;
    *tokens = 0;
    return GOLEM_OK;
}
int golem_cli_context(int argc, char **argv)
{
    cli_context_count count = {0};
    bool proof = argc >= 7 && !strcmp(argv[argc - 2], "--token-count");
    const char *proof_path = proof ? argv[argc - 1] : NULL;
    if (proof)
        argc -= 2;
    if (argc < 5)
        return 2;
    bool render = argc == 5 && !strcmp(argv[2], "render");
    bool markdown = argc == 5 && !strcmp(argv[2], "markdown");
    bool publish = argc == 5 && !strcmp(argv[2], "publish");
    bool candidate = argc == 5 && !strcmp(argv[2], "candidate") && !proof;
    bool read = argc == 6 && !strcmp(argv[2], "read");
    if (!render && !markdown && !publish && !read && !candidate)
        return 2;
    golem_digest digest, source;
    if (read &&
        (golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &digest) != GOLEM_OK ||
         golem_digest_parse((golem_string_view){argv[5], strlen(argv[5])}, &source) != GOLEM_OK))
        return 2;
    cli_blob request = {0};
    golem_status st = read ? GOLEM_OK : cli_read(argv[4], GOLEM_CONTEXT_REQUEST_MAX, &request);
    if (st == GOLEM_OK && proof)
        st = cli_context_count_load(proof_path, &count);
    struct json_object *parsed = NULL;
    golem_context_tokenizer unchecked = {0};
    if (st == GOLEM_OK && candidate) {
        st = cli_json_parse((golem_bytes){request.data, request.size}, &parsed);
        unchecked = (golem_context_tokenizer){cli_json_text(json_object_object_get(parsed, "tokenizer_id")), NULL, candidate_count};
    }
    const golem_context_tokenizer *tokenizer = proof ? &count.tokenizer : candidate ? &unchecked : NULL;
    golem_document_store *s = NULL;
    if (st == GOLEM_OK)
        st = golem_document_store_open(argv[3], publish, NULL, &s, NULL);
    struct json_object *o = NULL;
    uint8_t *buffer = NULL;
    size_t n = 0, capacity = 0;
    if (st == GOLEM_OK && publish) {
        golem_receipt receipt;
        st = golem_context_publish(s, (golem_bytes){request.data, request.size}, tokenizer, &receipt,
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
            st = read ? golem_context_read(s, &digest, &source, tokenizer, buffer, capacity, &n, NULL)
                      : golem_context_render(s, (golem_bytes){request.data, request.size}, tokenizer,
                                             buffer, capacity, &n, NULL);
            if (pass == 0 && st == GOLEM_ERR_BUFFER_TOO_SMALL) {
                buffer = malloc(n);
                capacity = n;
                st = buffer ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
            }
        }
    if (st == GOLEM_OK && !publish)
        st = cli_json_parse((golem_bytes){buffer, n}, &o);
    if (st == GOLEM_OK && candidate) {
        golem_digest hash;
        char hex[65]; size_t ignored;
        st = golem_digest_bytes((golem_bytes){buffer, n}, &hash);
        if (st == GOLEM_OK)
            st = golem_digest_format(&hash, hex, sizeof(hex), &ignored);
        struct json_object *envelope = json_object_new_object();
        if (st == GOLEM_OK && (!envelope ||
            !cli_json_add(envelope, "candidate", json_object_get(o)) ||
            !cli_json_add(envelope, "candidate_json", json_object_new_string_len((const char *)buffer, (int)n)) ||
            !cli_json_add(envelope, "projection_digest", json_object_new_string(hex)) ||
            !cli_json_add(envelope, "budget_verified", json_object_new_boolean(false))))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(o); o = envelope;
    }
    golem_status closed = golem_document_store_close(s);
    if (st == GOLEM_OK)
        st = closed;
    free(request.data);
    free(buffer);
    json_object_put(parsed);
    cli_context_count_clear(&count);
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
