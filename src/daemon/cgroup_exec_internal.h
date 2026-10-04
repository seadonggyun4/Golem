#ifndef GOLEM_CGROUP_EXEC_INTERNAL_H
#define GOLEM_CGROUP_EXEC_INTERNAL_H
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdbool.h>
#include <unistd.h>

/* Runs after exec of the trusted trampoline, not in a post-fork child. Fixed
 * labels only: do not print argv, environment, paths or control-file values. */
static void gc_exec_error(const char *operation, int error_number)
{
    int saved = errno;
    char line[256];
    int n = snprintf(line, sizeof(line),
        "{\"schema\":\"golem.child-system-error.v1\",\"phase\":\"cgroup.enter\","
        "\"operation\":\"%s\",\"errno\":%d}\n", operation, error_number);
    if (n > 0 && (size_t)n < sizeof(line)) {
        size_t done = 0;
        while (done < (size_t)n) {
            ssize_t written = write(STDERR_FILENO, line + done, (size_t)n - done);
            if (written < 0 && errno == EINTR) continue;
            if (written <= 0) break; /* A broken diagnostic sink is not retried. */
            done += (size_t)written;
        }
    }
    errno = saved;
}

static int gc_exec_run(int argc, char **argv, char **environment,
                       int (*verify)(int))
{
    if (argc < 3 || argv[1][0] != '/') {
        gc_exec_error("arguments", 0);
        return 126;
    }
    if (verify(3) != 0) return 126;
    int fd = openat(3, "cgroup.procs", O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) {
        gc_exec_error("open_membership", errno);
        return 126;
    }
    ssize_t n;
    do { n = write(fd, "0", 1); } while (n < 0 && errno == EINTR);
    bool failed = n != 1;
    if (failed) gc_exec_error(n < 0 ? "write_membership" : "short_write_membership", n < 0 ? errno : 0);
    if (close(fd) != 0) { gc_exec_error("close_membership", errno); failed = true; }
    if (close(3) != 0) { gc_exec_error("close_scope", errno); failed = true; }
    if (failed) return 126;
    execve(argv[1], argv + 2, environment);
    gc_exec_error("execve", errno);
    return 127;
}
#endif
