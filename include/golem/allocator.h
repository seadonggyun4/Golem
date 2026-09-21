#ifndef GOLEM_ALLOCATOR_H
#define GOLEM_ALLOCATOR_H
#include <stddef.h>
#include "golem/error.h"
#ifdef __cplusplus
extern "C" {
#endif

/* allocate returns NULL or at least size bytes aligned for max_align_t.
 * deallocate receives exactly a live pointer from that allocator. Callbacks
 * must not longjmp. The context must outlive all allocations/owners.
 * No realloc dependency; no process-global allocator configuration.
 * Callback/context thread safety is the caller's responsibility.
 * Output storage must not alias allocator descriptors or allocation contents. */
typedef struct golem_allocator {
    void *context;
    void *(*allocate)(void *context, size_t size);
    void (*deallocate)(void *context, void *pointer);
} golem_allocator;

/* Value copy of the C heap allocator. No ownership to release. */
golem_allocator golem_allocator_default(void);
/* NULL selects the default. Non-NULL requires both callbacks. */
golem_status golem_allocator_validate(const golem_allocator *allocator);
/* Positive sizes only. Caller owns *out and frees it with the same allocator.
 * Failure leaves *out unchanged. alloc_zero checks count*size and zeroes bytes;
 * byte-zero is not a portable replacement for typed pointer initialization. */
golem_status golem_allocator_alloc(const golem_allocator *allocator,
                                           size_t size, void **out);
golem_status golem_allocator_alloc_zero(const golem_allocator *allocator,
                                                size_t count, size_t size, void **out);
/* NULL pointer is a no-op after allocator validation. No ownership is taken
 * on error. Foreign/double frees violate the API contract. */
golem_status golem_allocator_free(const golem_allocator *allocator, void *pointer);
#ifdef __cplusplus
}
#endif
#endif
