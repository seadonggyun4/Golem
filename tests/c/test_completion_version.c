#include "../../src/completion/internal.h"
#include "../../src/agent_session/internal.h"
#include "test.h"
#include <string.h>

typedef struct allocation_counter {
    size_t allocated, freed;
    bool fail;
    size_t calls, fail_at;
} allocation_counter;
static void *allocate(void *context, size_t size)
{
    allocation_counter *counter = context;
    ++counter->calls;
    if (counter->fail || (counter->fail_at && counter->calls == counter->fail_at))
        return NULL;
    void *memory = malloc(size);
    if (memory != NULL)
        ++counter->allocated;
    return memory;
}
static void deallocate(void *context, void *memory)
{
    allocation_counter *counter = context;
    ++counter->freed;
    free(memory);
}

int main(int argc, char **argv)
{
    if (argc == 2) {
        allocation_counter counter = {0};
        golem_allocator allocator = {&counter, allocate, deallocate};
        golem_document_store *store = NULL;
        CHECK(golem_document_store_open(argv[1], false, &allocator, &store, NULL) == GOLEM_OK);
        size_t baseline = counter.allocated - counter.freed;
        counter.calls = 0;
        as_log log;
        CHECK(as_load(store, NULL, NULL, &log) == GOLEM_OK);
        size_t calls = counter.calls;
        as_close(&log);
        CHECK(calls > 1 && counter.allocated - counter.freed == baseline);
        for (size_t i = 1; i <= calls; ++i) {
            counter.calls = 0;
            counter.fail_at = i;
            CHECK(as_load(store, NULL, NULL, &log) == GOLEM_ERR_OUT_OF_MEMORY);
            as_close(&log);
            CHECK(counter.allocated - counter.freed == baseline);
        }
        counter.fail_at = 0;
        CHECK(golem_document_store_close(store) == GOLEM_OK);
        CHECK(counter.allocated == counter.freed);
        return 0;
    }
    struct json_object *record =
        json_tokener_parse("{\"assessment\":{\"policy\":{\"schema_version\":1,"
                           "\"predicate\":\"golem.completion.development.v999\"}}}");
    CHECK(record != NULL);
    struct json_object *out = record;
    CHECK(co_evaluate_record(NULL, NULL, record, &out) == GOLEM_ERR_UNSUPPORTED_VERSION);
    CHECK(out == record);
    golem_execution_reply report = {(uint8_t *)record, 42};
    CHECK(co_markdown(record, &report) == GOLEM_ERR_UNSUPPORTED_VERSION);
    CHECK(report.data == (uint8_t *)record && report.size == 42);
    struct json_object *policy = dw_get(dw_get(record, "assessment"), "policy");
    json_object_object_del(policy, "predicate");
    CHECK(co_evaluate_record(NULL, NULL, record, &out) == GOLEM_ERR_CORRUPT_JOURNAL);
    CHECK(out == record);
    json_object_put(record);

    allocation_counter counter = {0};
    golem_document_store store = {.allocator = {&counter, allocate, deallocate}};
    uint8_t *bytes = NULL;
    CHECK(dw_scratch(&store, 32, &bytes) == GOLEM_OK);
    CHECK(bytes != NULL && counter.allocated == 1);
    dw_scratch_free(&store, bytes);
    CHECK(counter.freed == 1);
    counter.fail = true;
    bytes = (uint8_t *)&counter;
    CHECK(dw_scratch(&store, 32, &bytes) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(bytes == (uint8_t *)&counter);
    CHECK(dw_scratch(&store, 0, &bytes) == GOLEM_ERR_INVALID_ARGUMENT);
    dw_scratch_free(&store, NULL);
    CHECK(counter.freed == 1);
    return 0;
}
