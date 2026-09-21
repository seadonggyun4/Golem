#ifndef GOLEM_TYPES_H
#define GOLEM_TYPES_H
#include <stddef.h>
#include <stdint.h>
#include "golem/error.h"
#include "golem/allocator.h"
#ifdef __cplusplus
extern "C" {
#endif

/* Borrowed bytes. The caller keeps the backing storage alive.
 * NULL is valid only when size is zero. No NUL termination is implied. */
typedef struct golem_bytes {
    const uint8_t *data;
    size_t size;
} golem_bytes;

/* On failure, out is unchanged. No allocation or ownership transfer.
 * All view metadata/output arguments must be distinct from backing storage. */
golem_status golem_bytes_init(golem_bytes *out, const void *data, size_t size);

/* Borrowed text bytes, not necessarily NUL terminated; no UTF-8 validation.
 * Embedded NUL bytes are preserved. NULL is valid only with size zero. */
typedef struct golem_string_view {
    const char *data;
    size_t size;
} golem_string_view;
/* Borrowed slices retain the backing owner's lifetime. On error outputs stay
 * unchanged. Bounds use subtraction to avoid offset+size overflow. */
golem_status golem_bytes_slice(golem_bytes source, size_t offset,
                                       size_t size, golem_bytes *out);
golem_status golem_string_view_init(golem_string_view *out, const char *data, size_t size);
/* text must be a valid NUL-terminated string; the result borrows it. */
golem_status golem_string_view_from_cstr(const char *text, golem_string_view *out);
golem_status golem_string_view_slice(golem_string_view source, size_t offset,
                                             size_t size, golem_string_view *out);

/* Caller-owned writes. Source/destination may overlap (memmove semantics).
 * required must not overlap source/destination/metadata. NULL destination
 * with capacity=0 is a size query. No writes on BUFFER_TOO_SMALL; *required is
 * updated on OK or BUFFER_TOO_SMALL only, unchanged on other failures.
 * Byte writes add no terminator; text writes append NUL, included in required.
 * All pointers must describe valid accessible storage for their stated sizes. */
golem_status golem_bytes_write(golem_bytes source, void *destination,
                                       size_t capacity, size_t *required);
golem_status golem_string_view_write(golem_string_view source, char *destination,
                                             size_t capacity, size_t *required);
/* Deep copy plus trailing NUL. Caller owns *out; release with
 * golem_allocator_free using the SAME allocator/context (NULL=default).
 * Even an empty view allocates one byte. On error *out remains unchanged. */
golem_status golem_string_clone(golem_string_view source,
                                        const golem_allocator *allocator, char **out);

#ifdef __cplusplus
}
#endif
#endif
