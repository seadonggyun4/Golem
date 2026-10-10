#ifndef GOLEM_CLI_CONTEXT_TOKENIZER_H
#define GOLEM_CLI_CONTEXT_TOKENIZER_H
#include "work.h"
#include "golem/context.h"
typedef struct cli_context_count {
    struct json_object *proof;
    golem_digest digest;
    uint64_t tokens;
    golem_context_tokenizer tokenizer;
} cli_context_count;
golem_status cli_context_count_load(const char *path, cli_context_count *count);
void cli_context_count_clear(cli_context_count *count);
#endif
