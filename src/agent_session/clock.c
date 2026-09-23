#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "internal.h"
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
    if (sysctlbyname("kern.bootsessionuuid", id, &n, NULL, 0) != 0 || !n || n > sizeof(id))
        return GOLEM_ERR_IO;
#else
    int fd = open("/proc/sys/kernel/random/boot_id", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0)
        return GOLEM_ERR_IO;
    ssize_t got = read(fd, id, sizeof(id));
    int closed = close(fd);
    if (got <= 0 || got >= (ssize_t)sizeof(id) || closed < 0)
        return GOLEM_ERR_IO;
    n = (size_t)got;
#endif
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0 || t.tv_sec < 0 || t.tv_nsec < 0 ||
        t.tv_nsec >= 1000000000L ||
        (uint64_t)t.tv_sec > (UINT64_MAX - (uint64_t)t.tv_nsec / 1000000) / 1000)
        return GOLEM_ERR_IO;
    golem_status st = golem_digest_bytes((golem_bytes){(const uint8_t *)id, n}, boot);
    if (st == GOLEM_OK)
        *now = (uint64_t)t.tv_sec * 1000 + (uint64_t)t.tv_nsec / 1000000;
    return st;
}
