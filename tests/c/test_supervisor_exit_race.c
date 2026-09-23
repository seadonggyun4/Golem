#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "test.h"
#include <errno.h>
#include <signal.h>
#include <stdbool.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

/* Deterministically delay pipe EOF until the leader has been reaped. Only the
 * test translation unit substitutes syscalls; production has no test hooks. */
static bool reaped, keep_open;
static unsigned post_reap_reads;
static int cleanup_errno = EPERM;
static ssize_t delayed_read(int fd, void *buffer, size_t size)
{
    if (!reaped || keep_open) {
        errno = EAGAIN;
        return -1;
    }
    if (post_reap_reads != 0) {
        --post_reap_reads;
        errno = EAGAIN;
        return -1;
    }
    return read(fd, buffer, size);
}
static int denied_kill(pid_t pid, int sig)
{
    (void)kill(pid, sig);
    errno = cleanup_errno;
    return -1;
}
static pid_t observed_waitpid(pid_t pid, int *status, int options)
{
    pid_t result = waitpid(pid, status, options);
    if (result == pid)
        reaped = true;
    return result;
}
#define read delayed_read
#define kill denied_kill
#define waitpid observed_waitpid
#define golem_supervisor_run race_supervisor_run
#define golem_supervisor_run_at race_supervisor_run_at
#include "../../src/daemon/supervisor.c"
#undef read
#undef kill
#undef waitpid

int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "--child"))
        return 0;
    CHECK(argc == 2);
    keep_open = !strcmp(argv[1], "held-pipe");
    if (!strcmp(argv[1], "late-reap-eof"))
        post_reap_reads = 4;
    if (!strcmp(argv[1], "denied"))
        cleanup_errno = EACCES;
    char executable[4096];
    CHECK(realpath(argv[0], executable) != NULL);
    char *args[] = {executable, "--child", NULL};
    golem_supervisor_result result = {0};
    golem_status status = race_supervisor_run(executable, args, (golem_bytes){NULL, 0},
                                              UINT64_C(2000000000), NULL, NULL, &result);
#ifdef __APPLE__
    bool acceptable = !keep_open && cleanup_errno == EPERM;
#else
    bool acceptable = false;
#endif
    CHECK(status == (acceptable ? GOLEM_OK : GOLEM_ERR_IO));
    CHECK(reaped && result.exit_code == 0);
    CHECK(waitpid(-1, NULL, WNOHANG) == -1 && errno == ECHILD);
    return 0;
}
