#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "cgroup_internal.h"
#include "golem/system_error.h"
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

bool golem_cgroup_write_value(int scope, const char *name, const char *value)
{
    int fd = openat(scope, name, O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) {
        (void)golem_system_error_note(GOLEM_ERR_IO, name, "open_control", errno);
        return false;
    }
    size_t size = strlen(value);
    ssize_t written;
    do {
        written = write(fd, value, size);
    } while (written < 0 && errno == EINTR);
    if (written < 0)
        (void)golem_system_error_note(GOLEM_ERR_IO, name, "write_control", errno);
    else if (written != (ssize_t)size)
        (void)golem_system_error_note(GOLEM_ERR_IO, name, "short_write_control", 0);
    int closed = close(fd);
    if (closed < 0)
        (void)golem_system_error_note(GOLEM_ERR_IO, name, "close_control", errno);
    return written == (ssize_t)size && !closed;
}

bool golem_cgroup_is_empty(int scope, bool *empty)
{
    int fd = openat(scope, "cgroup.events", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) {
        (void)golem_system_error_note(GOLEM_ERR_IO, "cgroup.events", "open_control", errno);
        return false;
    }
    char text[1024];
    ssize_t n;
    do {
        n = read(fd, text, sizeof(text) - 1);
    } while (n < 0 && errno == EINTR);
    bool valid = n > 0 && n < (ssize_t)sizeof(text) - 1;
    if (n < 0)
        (void)golem_system_error_note(GOLEM_ERR_IO, "cgroup.events", "read_control", errno);
    else if (!valid)
        (void)golem_system_error_note(GOLEM_ERR_IO, "cgroup.events", "read_shape", 0);
    int closed = close(fd);
    if (closed < 0)
        (void)golem_system_error_note(GOLEM_ERR_IO, "cgroup.events", "close_control", errno);
    if (!valid || closed) return false;
    text[n] = 0;
    if (!strncmp(text, "populated 0\n", 12) || strstr(text, "\npopulated 0\n")) {
        *empty = true;
        return true;
    }
    if (!strncmp(text, "populated 1\n", 12) || strstr(text, "\npopulated 1\n")) {
        *empty = false;
        return true;
    }
    (void)golem_system_error_note(GOLEM_ERR_IO, "cgroup.events", "populated_field", 0);
    return false;
}
