#include "golem/arena.h"
#include <stdint.h>
#include <stdbool.h>

static bool arena_valid(const golem_arena *arena)
{
    return arena != NULL && arena->used <= arena->capacity &&
        (arena->data != NULL || arena->capacity == 0);
}
golem_status golem_arena_init(golem_arena *arena, void *storage, size_t capacity)
{
    if (arena == NULL || (storage == NULL && capacity != 0)) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *arena = (golem_arena){storage, capacity, 0};
    return GOLEM_OK;
}
golem_status golem_arena_alloc(golem_arena *arena, size_t size,
                                      size_t alignment, void **out)
{
    if (!arena_valid(arena) || out == NULL || size == 0 || alignment == 0 ||
        alignment > _Alignof(max_align_t) || (alignment & (alignment - 1)) != 0) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    size_t remaining = arena->capacity - arena->used;
    if (size > remaining) {
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    /* size>0 and sufficient capacity imply non-NULL storage. */
    unsigned char *cursor = arena->data + arena->used;
    size_t remainder = (size_t)((uintptr_t)cursor % alignment);
    size_t padding = remainder == 0 ? 0 : alignment - remainder;
    if (padding > remaining || size > remaining - padding) {
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    *out = cursor + padding;
    arena->used += padding + size;
    return GOLEM_OK;
}
golem_status golem_arena_reset(golem_arena *arena)
{
    if (!arena_valid(arena)) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    arena->used = 0;
    return GOLEM_OK;
}
golem_status golem_arena_used_get(const golem_arena *arena, size_t *out)
{
    if (!arena_valid(arena) || out == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = arena->used;
    return GOLEM_OK;
}
