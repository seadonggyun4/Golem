#include "golem/context.h"
#include "golem/agent_session.h"
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
    CHECK(golem_document_store_open(argv[1], true, NULL, &store, NULL) == GOLEM_OK);
    const char *start = "{\"schema_version\":1,\"operation\":\"start\",\"work_id\":\"example-work\","
                        "\"key\":\"c-start\",\"expected_sequence\":0,\"selection_id\":\"selection\"}";
    const char *resume = "{\"schema_version\":1,\"operation\":\"resume\",\"work_id\":\"example-work\","
                         "\"key\":\"c-resume\",\"expected_sequence\":1,\"session_id\":\"c-agent\",\"ttl_ms\":60000}";
    golem_agent_reply reply = {0};
    CHECK(golem_agent_session_call(store, (golem_bytes){(const uint8_t *)start, strlen(start)},
                                   NULL, &reply, NULL) == GOLEM_OK);
    golem_agent_reply_free(&reply);
    reply = (golem_agent_reply){(uint8_t *)(uintptr_t)1, 17};
    CHECK(golem_agent_session_resume_context(store,
        (golem_bytes){(const uint8_t *)resume, strlen(resume)}, input, &tokenizer, NULL, &reply, NULL) ==
        GOLEM_ERR_BUDGET_EXHAUSTED);
    CHECK(reply.data == (uint8_t *)(uintptr_t)1 && reply.size == 17);
    tokenizer.count = count;
    reply = (golem_agent_reply){0};
    CHECK(golem_agent_session_resume_context(store,
        (golem_bytes){(const uint8_t *)resume, strlen(resume)}, input, &tokenizer, NULL, &reply, NULL) == GOLEM_OK);
    CHECK(reply.data != NULL && reply.size > 0);
    golem_agent_reply_free(&reply);
    CHECK(golem_document_store_close(store) == GOLEM_OK);
    return 0;
}
