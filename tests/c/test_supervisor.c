#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/supervisor.h"
#include "test.h"
#include <errno.h>
#include <signal.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static int child(const char *mode)
{
    if (strcmp(mode, "exit") == 0) return 17;
    if (strcmp(mode, "signal") == 0) { raise(SIGTERM); return 1; }
    if (strcmp(mode, "hang") == 0) { for (;;) pause(); }
    if (strcmp(mode, "overflow") == 0 || strcmp(mode, "stderr") == 0) {
        char data[4096] = {0}; int fd = strcmp(mode, "stderr") == 0 ? 2 : 1;
        for (int i = 0; i < 8; ++i) if (write(fd, data, sizeof(data)) < 0) return 1;
        return 0;
    }
    char bytes[1024]; ssize_t n;
    while ((n = read(0, bytes, sizeof(bytes))) > 0) if (write(1, bytes, (size_t)n) != n) return 1;
    return n < 0 ? 1 : 0;
}
static golem_status cancel(void *context) { unsigned *calls = context; return ++*calls >= 2 ? GOLEM_ERR_STALE_LEASE : GOLEM_OK; }
int main(int argc, char **argv)
{
    if (argc == 3 && strcmp(argv[1], "--child") == 0) return child(argv[2]);
    CHECK(argc == 2);
    char executable[4096]; CHECK(realpath(argv[0], executable) != NULL);
    char *args[] = {executable, "--child", argv[1], NULL};
    golem_supervisor_result r = {0}; golem_status s;
    if (strcmp(argv[1], "cancel") == 0) {
        args[2] = "hang"; unsigned calls = 0;
        s = golem_supervisor_run(executable, args, (golem_bytes){NULL, 0}, UINT64_C(2000000000), cancel, &calls, &r);
        CHECK(s == GOLEM_ERR_STALE_LEASE && calls == 2 && r.signal_number == SIGKILL);
    } else {
        s = golem_supervisor_run(executable, args, (golem_bytes){(const uint8_t *)"echo", 4},
            strcmp(argv[1], "hang") == 0 ? UINT64_C(100000000) : UINT64_C(2000000000), NULL, NULL, &r);
        fprintf(stderr, "supervisor %s: %s exit=%d signal=%d stdout=%zu stderr=%zu timeout=%d\n",
            argv[1], golem_status_string(s), r.exit_code, r.signal_number, r.output_size, r.error_size, (int)r.timed_out);
        if (strcmp(argv[1], "echo") == 0) CHECK(s == GOLEM_OK && r.output_size == 4 && memcmp(r.output, "echo", 4) == 0 && r.exit_code == 0);
        else if (strcmp(argv[1], "hang") == 0) CHECK(s == GOLEM_ERR_INCOMPLETE_WORK && r.timed_out && r.signal_number == SIGKILL);
        else if (strcmp(argv[1], "overflow") == 0 || strcmp(argv[1], "stderr") == 0) CHECK(s == GOLEM_ERR_OVERFLOW);
        else if (strcmp(argv[1], "exit") == 0) CHECK(s == GOLEM_ERR_INCOMPLETE_WORK && r.exit_code == 17);
        else if (strcmp(argv[1], "signal") == 0) CHECK(s == GOLEM_ERR_INCOMPLETE_WORK && r.signal_number == SIGTERM);
        else return 1;
    }
    CHECK(waitpid(-1, NULL, WNOHANG) == -1 && errno == ECHILD);
    CHECK(golem_supervisor_run("relative", args, (golem_bytes){NULL, 0}, 1, NULL, NULL, &r) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_supervisor_run(executable, args, (golem_bytes){NULL, 0}, 0, NULL, NULL, &r) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
