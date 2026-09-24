#include "../../src/execution/internal.h"
#include "test.h"
#include <string.h>

typedef struct allocations { size_t calls, live, fail; } allocations;
static void *allocate(void *context, size_t n)
{
    allocations *a = context;
    if (++a->calls == a->fail)
        return NULL;
    void *p = malloc(n);
    if (p)
        ++a->live;
    return p;
}
static void release(void *context, void *p)
{
    allocations *a = context;
    --a->live;
    free(p);
}
int main(void)
{
    const char *text = "{\"mode\":\"REDACTED_CAPTURE\",\"max_bytes\":8,"
        "\"redactor\":\"mask-bytes-v1\",\"require_complete\":false}";
    struct json_object *policy = NULL;
    CHECK(golem_json_parse((golem_bytes){(const uint8_t *)text, strlen(text)}, 1024, &policy) == GOLEM_OK);
    allocations a = {0};
    golem_document_store store = {.allocator = {&a, allocate, release}};
    for (size_t fail = 1; fail <= 2; ++fail) {
        a = (allocations){.fail = fail};
        ex_log_capture capture = {.cap = 42};
        CHECK(ex_logs_open(&store, policy, &capture) == GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(capture.cap == 42 && a.live == 0);
    }
    a = (allocations){0};
    ex_log_capture capture = {0};
    CHECK(ex_logs_open(&store, policy, &capture) == GOLEM_OK);
    const uint8_t first[] = {0, 255, 0xe2};
    const uint8_t second[] = {0x82, 0xac, 's', 'e', 'c', 'r', 'e', 't'};
    CHECK(ex_logs_write(&capture, 0, (golem_bytes){first, sizeof(first)}) == GOLEM_OK);
    CHECK(ex_logs_write(&capture, 0, (golem_bytes){second, sizeof(second)}) == GOLEM_OK);
    CHECK(capture.observed[0] == 11 && capture.size[0] == 8);
    CHECK(memcmp(capture.retained[0], "********", 8) == 0);
    CHECK(capture.observed[1] == 0 && capture.size[1] == 0);
    CHECK(ex_logs_write(&capture, 2, (golem_bytes){first, 3}) == GOLEM_ERR_INVALID_ARGUMENT);
    capture.observed[1] = UINT64_MAX;
    CHECK(ex_logs_write(&capture, 1, (golem_bytes){first, 1}) == GOLEM_ERR_OVERFLOW);
    ex_logs_close(&capture);
    CHECK(a.live == 0);
    json_object_put(policy);
    golem_execution_reply out = {(uint8_t *)"sentinel", 8};
    CHECK(golem_execution_bundle_inspect(NULL, NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(out.size == 8 && !strcmp((char *)out.data, "sentinel"));
    CHECK(golem_execution_bundle_verify(NULL, (golem_bytes){NULL, 0}, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
