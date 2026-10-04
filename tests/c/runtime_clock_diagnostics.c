#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <time.h>
static int mode;
static int test_clock(clockid_t clock, struct timespec *value)
{
    (void)clock;
    if (mode == 0) { errno = EPERM; return -1; }
    *value = (struct timespec){.tv_sec = 1, .tv_nsec = 1000000000L};
    return 0;
}
#define clock_gettime test_clock
#include "../../src/runtime/loop.c"
#undef clock_gettime
#include "test.h"
int main(void)
{
    for (mode = 0; mode < 2; ++mode) {
        golem_runtime runtime = {0};
        uint64_t value = 42;
        golem_system_error_scope scope;
        CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
        errno = EDOM;
        CHECK(clock_read(&runtime, &value) == GOLEM_ERR_IO && value == 42);
        CHECK(golem_system_error_end(&scope) == GOLEM_OK);
        CHECK(scope.count == 1 && scope.entries[0].error_number == (mode ? 0 : EPERM));
        CHECK(!strcmp(scope.entries[0].operation, mode ? "clock_value" : "clock_gettime"));
        CHECK(!runtime.clock_seen);
    }
    return 0;
}
