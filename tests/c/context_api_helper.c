#include "golem/context.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x)                                                                                   \
    do {                                                                                           \
        if (!(x))                                                                                  \
            return __LINE__;                                                                       \
    } while (0)
static golem_status count(void *context, golem_bytes bytes, uint64_t *tokens)
{
    unsigned *calls = context;
    ++*calls;
    *tokens = bytes.size;
    return GOLEM_OK;
}
static golem_status over_budget(void *context, golem_bytes bytes, uint64_t *tokens)
{
    (void)context;
    (void)bytes;
    *tokens = UINT64_MAX;
    return GOLEM_OK;
}
int main(int argc, char **argv)
{
    CHECK(argc == 3);
    FILE *f = fopen(argv[2], "rb");
    CHECK(f != NULL);
    uint8_t request[GOLEM_CONTEXT_REQUEST_MAX];
    size_t n = fread(request, 1, sizeof(request), f);
    CHECK(!ferror(f));
    CHECK(fclose(f) == 0);
    golem_bytes input = {request, n};
    CHECK(golem_context_request_validate(input, NULL) == GOLEM_OK);
    golem_document_store *store = NULL;
    CHECK(golem_document_store_open(argv[1], false, NULL, &store, NULL) == GOLEM_OK);
    unsigned calls = 0;
    golem_context_tokenizer tokenizer = {"test-byte-v1", &calls, count};
    size_t required = 0;
    CHECK(golem_context_render(store, input, &tokenizer, NULL, 0, &required, NULL) ==
          GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(calls == 1 && required > 1);
    uint8_t small[1] = {0xa5};
    CHECK(golem_context_render(store, input, &tokenizer, small, 1, &required, NULL) ==
          GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(small[0] == 0xa5);
    uint8_t *output = malloc(required);
    CHECK(output != NULL);
    CHECK(golem_context_render(store, input, &tokenizer, output, required, &required, NULL) ==
          GOLEM_OK);
    free(output);
    tokenizer.count = over_budget;
    required = 123;
    CHECK(golem_context_render(store, input, &tokenizer, small, 1, &required, NULL) ==
          GOLEM_ERR_BUDGET_EXHAUSTED);
    CHECK(required == 123 && small[0] == 0xa5);
    golem_receipt receipt;
    CHECK(golem_context_publish(store, input, &tokenizer, &receipt, NULL) ==
          GOLEM_ERR_POLICY_DENIED);
    CHECK(golem_document_store_close(store) == GOLEM_OK);
    return 0;
}
