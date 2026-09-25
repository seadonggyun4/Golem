#ifndef GOLEM_EVENT_BRIDGE_LIMITS_H
#define GOLEM_EVENT_BRIDGE_LIMITS_H
#include <stdbool.h>
#include <stddef.h>
#define GB_SUBSCRIBERS 32u
#define GB_OUTPUT_LIMIT 65536u
#define GB_FRAME_RESERVE 32u
#define GB_BLOCK_LIMIT 4u
/* Reserve HTTP chunk framing before enqueue; avoid size_t subtraction wrap. */
static inline bool gb_output_room(size_t queued, size_t frame)
{
    return frame <= GB_OUTPUT_LIMIT - GB_FRAME_RESERVE &&
           queued <= GB_OUTPUT_LIMIT - GB_FRAME_RESERVE - frame;
}
/* Consecutive failed enqueues, not lifetime failures. Saturation is terminal. */
static inline bool gb_overloaded(unsigned *blocked, bool accepted)
{
    if (accepted)
        *blocked = 0;
    else if (*blocked < GB_BLOCK_LIMIT)
        ++*blocked;
    return *blocked >= GB_BLOCK_LIMIT;
}
#endif
