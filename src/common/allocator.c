#include "golem/allocator.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static void *heap_allocate(void *context, size_t size)
{
    (void)context;
    return malloc(size);
}
static void heap_deallocate(void *context, void *pointer)
{
    (void)context;
    free(pointer);
}
golem_allocator golem_allocator_default(void)
{
    return (golem_allocator){NULL, heap_allocate, heap_deallocate};
}
golem_status golem_allocator_validate(const golem_allocator *allocator)
{
    return allocator != NULL && (allocator->allocate == NULL || allocator->deallocate == NULL)
        ? GOLEM_ERR_INVALID_ARGUMENT : GOLEM_OK;
}
golem_status golem_allocator_alloc(const golem_allocator *allocator, size_t size, void **out)
{
    if (out == NULL || size == 0 || golem_allocator_validate(allocator) != GOLEM_OK) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    golem_allocator selected = allocator == NULL ? golem_allocator_default() : *allocator;
    void *memory = selected.allocate(selected.context, size);
    if (memory == NULL) {
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    *out = memory;
    return GOLEM_OK;
}
golem_status golem_allocator_alloc_zero(const golem_allocator *allocator,
                                                size_t count, size_t size, void **out)
{
    if (out == NULL || count == 0 || size == 0 ||
        golem_allocator_validate(allocator) != GOLEM_OK) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (count > SIZE_MAX / size) {
        return GOLEM_ERR_OVERFLOW;
    }
    void *memory;
    golem_status status = golem_allocator_alloc(allocator, count * size, &memory);
    if (status != GOLEM_OK) {
        return status;
    }
    memset(memory, 0, count * size);
    *out = memory;
    return GOLEM_OK;
}
golem_status golem_allocator_free(const golem_allocator *allocator, void *pointer)
{
    if (golem_allocator_validate(allocator) != GOLEM_OK) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (pointer != NULL) {
        golem_allocator selected = allocator == NULL ? golem_allocator_default() : *allocator;
        selected.deallocate(selected.context, pointer);
    }
    return GOLEM_OK;
}
