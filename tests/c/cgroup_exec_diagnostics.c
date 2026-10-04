#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include <stdbool.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include "test.h"
static int mode, closed, executed, writes;
static char diagnostics[2048];
static size_t used;
static int mock_open(int fd, const char *path, int flags, ...)
{
    (void)fd; (void)path; (void)flags;
    if (mode == 1) { errno = EACCES; return -1; }
    return 7;
}
static ssize_t mock_write(int fd, const void *data, size_t size)
{
    if (fd == STDERR_FILENO) {
        if (size > sizeof(diagnostics) - used - 1) return -1;
        memcpy(diagnostics + used, data, size); used += size; diagnostics[used] = 0;
        return (ssize_t)size;
    }
    ++writes;
    if (mode == 2) { errno = ENOSPC; return -1; }
    if (mode == 3) { errno = EDOM; return 0; }
    if (mode == 6 && writes == 1) { errno = EINTR; return -1; }
    return (ssize_t)size;
}
static int mock_close(int fd)
{
    ++closed;
    if (mode == 4 || (mode == 2 && fd == 3)) { errno = EIO; return -1; }
    return 0;
}
static int mock_exec(const char *path, char *const argv[], char *const env[])
{
    (void)path; (void)argv; (void)env; ++executed; errno = ENOENT; return -1;
}
#define openat mock_open
#define write mock_write
#define close mock_close
#define execve mock_exec
#include "../../src/daemon/cgroup_exec_internal.h"
#undef openat
#undef write
#undef close
#undef execve
static int verify(int fd) { (void)fd; return 0; }
int main(void)
{
    char *args[] = {"trampoline", "/private-target", "private-argv", NULL}, *env[] = {NULL};
    for (mode = 0; mode <= 6; ++mode) {
        used = 0; diagnostics[0] = 0; closed = executed = writes = 0;
        int code = gc_exec_run(3, args, env, verify);
        CHECK(code == ((mode == 0 || mode >= 5) ? 127 : 126));
        CHECK(executed == (code == 127));
        CHECK(closed == (mode == 1 ? 0 : 2));
        CHECK(strstr(diagnostics, "golem.child-system-error.v1"));
        CHECK(!strstr(diagnostics, "private-target") && !strstr(diagnostics, "private-argv"));
        if (mode == 2) CHECK(strstr(diagnostics, "write_membership") && strstr(diagnostics, "close_scope"));
        if (mode == 3) CHECK(strstr(diagnostics, "\"errno\":0"));
        if (mode == 6) CHECK(writes == 2 && !strstr(diagnostics, "write_membership"));
    }
    return 0;
}
