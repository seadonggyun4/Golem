#include "context_tokenizer.h"
#include <stdlib.h>
#include <string.h>

static golem_status count(void *context, golem_bytes bytes, uint64_t *tokens)
{
    cli_context_count *p = context;
    golem_digest digest;
    golem_status st = golem_digest_bytes(bytes, &digest);
    if (st == GOLEM_OK && memcmp(&digest, &p->digest, sizeof(digest)))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK)
        *tokens = p->tokens;
    return st;
}
golem_status cli_context_count_load(const char *path, cli_context_count *p)
{
    cli_blob bytes = {0};
    golem_status st = cli_read(path, GOLEM_CONTEXT_REQUEST_MAX, &bytes);
    if (st == GOLEM_OK)
        st = cli_json_parse((golem_bytes){bytes.data, bytes.size}, &p->proof);
    free(bytes.data);
    const char *keys[] = {"schema_version", "tokenizer_id", "projection_digest", "input_tokens"};
    struct json_object *version = p->proof ? json_object_object_get(p->proof, "schema_version") : NULL;
    struct json_object *n = p->proof ? json_object_object_get(p->proof, "input_tokens") : NULL;
    const char *id = cli_json_text(p->proof ? json_object_object_get(p->proof, "tokenizer_id") : NULL);
    const char *hex = cli_json_text(p->proof ? json_object_object_get(p->proof, "projection_digest") : NULL);
    if (st == GOLEM_OK && (!cli_json_keys(p->proof, keys, 4) ||
        !json_object_is_type(version, json_type_int) || json_object_get_int64(version) != 1 ||
        !json_object_is_type(n, json_type_int) || json_object_get_int64(n) <= 0 || json_object_get_uint64(n) > 1000000000 ||
        !id || !*id || strlen(id) > 128 || !hex ||
        golem_digest_parse((golem_string_view){hex, strlen(hex)}, &p->digest) != GOLEM_OK))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK) {
        p->tokens = json_object_get_uint64(n);
        p->tokenizer = (golem_context_tokenizer){id, p, count};
    }
    return st;
}
void cli_context_count_clear(cli_context_count *p)
{
    json_object_put(p->proof);
    *p = (cli_context_count){0};
}
