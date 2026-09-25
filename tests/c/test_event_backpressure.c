#include "../../tools/event_bridge_limits.h"
#include "test.h"
#include <stdint.h>
int main(void)
{
    CHECK(gb_output_room(0, GB_OUTPUT_LIMIT - GB_FRAME_RESERVE));
    CHECK(!gb_output_room(1, GB_OUTPUT_LIMIT - GB_FRAME_RESERVE));
    CHECK(!gb_output_room(SIZE_MAX, 1));
    CHECK(!gb_output_room(0, SIZE_MAX));
    CHECK(!gb_output_room(GB_OUTPUT_LIMIT, 0));
    unsigned slow = 0, fast = 0;
    for (unsigned i = 1; i <= GB_BLOCK_LIMIT; ++i) {
        CHECK(gb_overloaded(&slow, false) == (i == GB_BLOCK_LIMIT));
        CHECK(!gb_overloaded(&fast, true) && fast == 0);
    }
    CHECK(gb_overloaded(&slow, false) && slow == GB_BLOCK_LIMIT);
    CHECK(!gb_overloaded(&slow, true) && slow == 0);
    CHECK(!gb_overloaded(&slow, false) && slow == 1);
    return 0;
}
