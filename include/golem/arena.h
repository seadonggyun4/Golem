#ifndef GOLEM_ARENA_H
#define GOLEM_ARENA_H
#include <stddef.h>
#include "golem/error.h"
#ifdef __cplusplus
extern "C" {
#endif

/* Caller-owned arena and backing storage. Treat fields as read-only after
 * init; do not copy a live arena or overlap metadata with backing storage.
 * All returned allocations borrow backing memory; never individually free.
 * No heap use, internal synchronization, growth, or zero initialization.
 * Output arguments must not overlap arena metadata or backing storage.
 * Storage size describes a real live buffer, not just a numeric limit. */
typedef struct golem_arena {
    unsigned char *data;
    size_t capacity;
    size_t used;
} golem_arena;

/* NULL backing is valid only for capacity=0. Caller keeps storage alive.
 * Reinitialization/reset invalidates ALL prior allocation views. */
golem_status golem_arena_init(golem_arena *arena, void *storage, size_t capacity);
/* size > 0; alignment is a power of two <= _Alignof(max_align_t).
 * Supports unaligned backing storage; padding counts against capacity.
 * Error preserves arena and *out. Exhaustion returns OUT_OF_MEMORY. */
golem_status golem_arena_alloc(golem_arena *arena, size_t size,
                                      size_t alignment, void **out);
/* Reset reuses storage without erasing it or releasing caller ownership. */
golem_status golem_arena_reset(golem_arena *arena);
/* Outputs include alignment padding; unchanged on error. */
golem_status golem_arena_used_get(const golem_arena *arena, size_t *out);
#ifdef __cplusplus
}
#endif
#endif
