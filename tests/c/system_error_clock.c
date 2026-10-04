#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "golem/system_error.h"
#include "test.h"
#include <errno.h>
#include <string.h>
#include <time.h>
#ifdef __APPLE__
#include <sys/sysctl.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif
static int mode;
static int clock_fault(clockid_t id, struct timespec *t)
{
    (void)id;
    if (mode == 2) { errno = EIO; return -1; }
    *t = (struct timespec){.tv_sec = 10};
    return 0;
}
#ifdef __APPLE__
static int boot_fault(const char *name, void *out, size_t *size, void *in, size_t n)
{
    (void)name; (void)in; (void)n;
    if (mode == 1) { errno = EPERM; return -1; }
    *size = mode == 3 ? 0 : 4;
    memcpy(out, "boot", 4);
    errno = EACCES;
    return 0;
}
#define sysctlbyname boot_fault
#else
static int boot_open(const char *name, int flags, ...)
{ (void)name; (void)flags; return 77; }
static ssize_t boot_read(int fd, void *out, size_t n)
{
    (void)fd; (void)n;
    if (mode == 1) { errno = EPERM; return -1; }
    memcpy(out, "boot", 4); errno = EACCES;
    return mode == 3 ? 0 : 4;
}
static int boot_close(int fd) { (void)fd; errno = EBADF; return 0; }
#define open boot_open
#define read boot_read
#define close boot_close
#endif
#define clock_gettime clock_fault
#define as_clock_read tested_clock
#include "../../src/agent_session/clock.c"

int main(void)
{
    for (mode = 1; mode <= 4; ++mode) {
        golem_system_error_scope scope;
        CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
        uint64_t now = 99;
        golem_digest boot = {{0}};
        golem_status st = tested_clock(NULL, &now, &boot);
        CHECK(golem_system_error_end(&scope) == GOLEM_OK);
        if (mode == 4) CHECK(st == GOLEM_OK && now == 10000 && scope.count == 0);
        else {
            CHECK(st == GOLEM_ERR_IO && now == 99 && scope.count == 1);
            CHECK(scope.entries[0].error_number == (mode == 1 ? EPERM : mode == 2 ? EIO : 0));
            CHECK(!strcmp(scope.entries[0].component, "session.clock"));
        }
    }
    return 0;
}
