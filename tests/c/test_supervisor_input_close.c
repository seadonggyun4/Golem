#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "test.h"
#include <errno.h>
#include <signal.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <unistd.h>

/* Inject only the send outcome, leaving process exit, drain and reap real. */
static int send_error;
static unsigned sends;
static ssize_t closed_send(int fd, const void *buffer, size_t size, int flags)
{
    (void)fd;
    (void)buffer;
    (void)size;
    (void)flags;
    ++sends;
    errno = send_error;
    return -1;
}
#define send closed_send
#define golem_supervisor_run input_supervisor_run
#define golem_supervisor_run_at input_supervisor_run_at
#include "../../src/daemon/supervisor.c"
#undef send

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "--child")) {
        (void)close(STDIN_FILENO);
        if (!strcmp(argv[2], "signal")) {
            raise(SIGTERM);
            return 1;
        }
        if (!strcmp(argv[2], "hang")) {
            for (;;)
                pause();
        }
        return !strcmp(argv[2], "success") ? 0 : 17;
    }
    CHECK(argc == 3);
    send_error = !strcmp(argv[1], "reset") ? ECONNRESET : !strcmp(argv[1], "io") ? EIO : EPIPE;
    char executable[4096];
    CHECK(realpath(argv[0], executable) != NULL);
    char *args[] = {executable, "--child", argv[2], NULL};
    golem_supervisor_result result = {0};
    bool hang = !strcmp(argv[2], "hang");
    golem_status status = input_supervisor_run(
        executable, args, (golem_bytes){(const uint8_t *)"input", 5},
        hang ? UINT64_C(100000000) : UINT64_C(2000000000), NULL, NULL, &result);
    CHECK(sends == 1);
    CHECK(status == (send_error == EIO ? GOLEM_ERR_IO : GOLEM_ERR_INCOMPLETE_WORK));
    if (send_error != EIO) {
        if (hang)
            CHECK(result.timed_out && result.signal_number == SIGKILL);
        else if (!strcmp(argv[2], "signal"))
            CHECK(result.signal_number == SIGTERM);
        else
            CHECK(result.exit_code == (!strcmp(argv[2], "success") ? 0 : 17));
    }
    CHECK(waitpid(-1, NULL, WNOHANG) == -1 && errno == ECHILD);
    return 0;
}
