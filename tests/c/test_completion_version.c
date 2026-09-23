#include "../../src/completion/internal.h"
#include "test.h"
#include <string.h>

typedef struct allocation_counter {
    size_t allocated, freed;
    bool fail;
} allocation_counter;
static void *allocate(void *context, size_t size)
{
    allocation_counter *counter = context;
    if (counter->fail)
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

int main(void)
{
    struct json_object *record =
        json_tokener_parse("{\"assessment\":{\"policy\":{\"schema_version\":1,"
                           "\"predicate\":\"golem.completion.development.v999\"}}}");
    CHECK(record != NULL);
    struct json_object *out = record;
    CHECK(co_evaluate_record(NULL, NULL, record, &out) == GOLEM_ERR_UNSUPPORTED_VERSION);
    CHECK(out == record);
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
