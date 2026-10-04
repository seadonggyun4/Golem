#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "internal.h"
#include "golem/system_error.h"
#include <errno.h>
#include <time.h>
#include <string.h>
#ifdef __APPLE__
#include <sys/sysctl.h>
#else
#include <fcntl.h>
#include <unistd.h>
#endif
golem_status as_clock_read(const golem_agent_clock *clock, uint64_t *now, golem_digest *boot)
{
    if (clock)
        return clock->read ? clock->read(clock->context, now, boot) : GOLEM_ERR_INVALID_ARGUMENT;
    char id[128];
    size_t n = sizeof(id);
#ifdef __APPLE__
    if (sysctlbyname("kern.bootsessionuuid", id, &n, NULL, 0) != 0)
        return golem_system_error_note(GOLEM_ERR_IO, "session.clock", "sysctlbyname", errno);
    if (!n || n > sizeof(id))
        return golem_system_error_note(GOLEM_ERR_IO, "session.clock", "boot_identity_size", 0);
#else
    int fd = open("/proc/sys/kernel/random/boot_id", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0)
        return golem_system_error_note(GOLEM_ERR_IO, "session.clock", "open", errno);
    ssize_t got = read(fd, id, sizeof(id));
    int read_error = got < 0 ? errno : 0;
    if (got <= 0 || got >= (ssize_t)sizeof(id))
        (void)golem_system_error_note(GOLEM_ERR_IO, "session.clock", got < 0 ? "read" : "boot_identity_size", read_error);
    int closed = close(fd);
    if (closed < 0)
        (void)golem_system_error_note(GOLEM_ERR_IO, "session.clock", "close", errno);
    if (got <= 0 || got >= (ssize_t)sizeof(id) || closed < 0)
        return GOLEM_ERR_IO;
    n = (size_t)got;
#endif
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0)
        return golem_system_error_note(GOLEM_ERR_IO, "session.clock", "clock_gettime", errno);
    if (t.tv_sec < 0 || t.tv_nsec < 0 ||
        t.tv_nsec >= 1000000000L ||
        (uint64_t)t.tv_sec > (UINT64_MAX - (uint64_t)t.tv_nsec / 1000000) / 1000)
        return golem_system_error_note(GOLEM_ERR_IO, "session.clock", "clock_range", 0);
    golem_status st = golem_digest_bytes((golem_bytes){(const uint8_t *)id, n}, boot);
    if (st == GOLEM_OK)
        *now = (uint64_t)t.tv_sec * 1000 + (uint64_t)t.tv_nsec / 1000000;
    return st;
}
