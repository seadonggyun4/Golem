#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "test.h"
#include "golem/system_error.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <spawn.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static const char *mode;
static unsigned reads, spawn_calls;
static bool is(const char *s) { return !strcmp(mode, s); }
static int returned_error(void) { errno = ENOSPC; return EINVAL; }
static int failed(void) { errno = EACCES; return -1; }
static int fake_socketpair(int domain, int type, int protocol, int fds[2])
{
    (void)domain; (void)type; (void)protocol;
    return is("socketpair") ? failed() : pipe(fds);
}
static int fake_pipe(int fds[2]) { return is("pipe") ? failed() : pipe(fds); }
static int fake_close(int fd)
{
    int rc = close(fd);
    if (is("spawn-cleanup") || is("cleanup-success")) { errno = EIO; return -1; }
    return rc;
}
static int fake_fcntl(int fd, int command, int argument)
{
    if ((is("fcntl_cloexec") && command == F_SETFD) ||
        (is("fcntl_nonblock") && command == F_SETFL)) return failed();
    return fcntl(fd, command, argument);
}
static int fake_clock(clockid_t id, struct timespec *t)
{
    if (is("clock")) return failed();
    if (is("clock-value")) { *t = (struct timespec){.tv_sec = -1}; errno = EACCES; return 0; }
    return clock_gettime(id, t);
}
static int fake_spawn(pid_t *pid, const char *path, const posix_spawn_file_actions_t *a,
                      const posix_spawnattr_t *b, char *const args[], char *const env[])
{
    (void)path; (void)a; (void)b; (void)args; (void)env;
    ++spawn_calls;
    if (is("posix_spawn") || is("spawn-cleanup")) return returned_error();
    *pid = 12345;
    return 0;
}
static ssize_t fake_read(int fd, void *buffer, size_t size)
{
    (void)fd; (void)buffer; (void)size;
    if (is("read")) return failed();
    if (is("read-eintr") && reads++ == 0) { errno = EINTR; return -1; }
    return 0;
}
static ssize_t fake_send(int fd, const void *data, size_t size, int flags)
{
    (void)fd; (void)data; (void)flags;
    return is("send") ? failed() : (ssize_t)size;
}
static int fake_waitid(idtype_t kind, id_t pid, siginfo_t *info, int options)
{
    (void)kind; (void)options;
    if (is("waitid")) return failed();
    info->si_pid = is("poll") || is("poll-kill") ? 0 : (pid_t)pid;
    return 0;
}
static int fake_poll(struct pollfd *fds, nfds_t n, int timeout)
{
    (void)fds; (void)n; (void)timeout;
    return failed();
}
static int fake_kill(pid_t pid, int signal)
{
    (void)pid; (void)signal;
    errno = is("kill") || is("poll-kill") ? EACCES : ESRCH;
    return -1;
}
static pid_t fake_waitpid(pid_t pid, int *status, int flags)
{
    (void)flags;
    if (is("waitpid")) { errno = ECHILD; return -1; }
    *status = 0;
    return pid;
}
static int fake_actions_destroy(posix_spawn_file_actions_t *a)
{
    int rc = posix_spawn_file_actions_destroy(a);
    return is("actions_destroy") ? returned_error() : rc;
}
static int fake_attributes_destroy(posix_spawnattr_t *a)
{
    int rc = posix_spawnattr_destroy(a);
    return is("attributes_destroy") ? returned_error() : rc;
}
/* No real process is created or signalled. Only this translation unit replaces
 * operations; production keeps its normal direct calls and ownership rules. */
#define SPAWN_CALL(name, call) (is(name) ? returned_error() : (call))
#define socketpair fake_socketpair
#define pipe fake_pipe
#define pipe2(fds, flags) fake_pipe(fds)
#define setsockopt(fd, level, opt, value, size) ((void)(value), is("setsockopt") ? failed() : 0)
#define close fake_close
#define fcntl fake_fcntl
#define clock_gettime fake_clock
#define posix_spawn fake_spawn
#define posix_spawn_file_actions_destroy fake_actions_destroy
#define posix_spawnattr_destroy fake_attributes_destroy
#define posix_spawn_file_actions_init(p) SPAWN_CALL("actions_init", posix_spawn_file_actions_init(p))
#define posix_spawnattr_init(p) SPAWN_CALL("attributes_init", posix_spawnattr_init(p))
#define posix_spawn_file_actions_addchdir_np(p, dir) SPAWN_CALL("addchdir", posix_spawn_file_actions_addchdir_np(p, dir))
#define posix_spawn_file_actions_adddup2(p, a, b) SPAWN_CALL("dup_stdin", posix_spawn_file_actions_adddup2(p, a, b))
#define posix_spawn_file_actions_addclose(p, fd) SPAWN_CALL("close_stdin", posix_spawn_file_actions_addclose(p, fd))
#define posix_spawnattr_setsigmask(p, mask) SPAWN_CALL("setsigmask", posix_spawnattr_setsigmask(p, mask))
#define posix_spawnattr_setpgroup(p, group) SPAWN_CALL("setpgroup", posix_spawnattr_setpgroup(p, group))
#define posix_spawnattr_setflags(p, flags) SPAWN_CALL("setflags", posix_spawnattr_setflags(p, flags))
#define read fake_read
#define send fake_send
#define waitid fake_waitid
#define poll fake_poll
#define kill fake_kill
#define waitpid fake_waitpid
#include "../../src/daemon/supervisor.c"

int main(int argc, char **argv)
{
    CHECK(argc == 4);
    mode = argv[1];
    golem_system_error_scope scope;
    CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
    /* Recording hashes the executable before reaching the mocked spawn. Use
     * this real fixture binary so recording-enabled suites reach each fault. */
    char *args[] = {argv[0], NULL}, *env[] = {NULL};
    golem_supervisor_result result = {.exit_code = 73};
    golem_supervisor_observation observed = {0};
    golem_status st = golem_supervisor_run_observed(args[0], args, "/", env,
        (golem_bytes){(const uint8_t *)"x", 1}, 1000000000, NULL, NULL, &result, &observed);
    CHECK(golem_system_error_end(&scope) == GOLEM_OK);
    bool success = is("success") || is("read-eintr") || is("cleanup-success") ||
                   is("actions_destroy") || is("attributes_destroy");
    CHECK(st == (success ? GOLEM_OK : GOLEM_ERR_IO));
    if (!observed.spawned) CHECK(result.exit_code == 73);
    else if (!is("waitpid")) CHECK(observed.reaped && result.exit_code == 0);
    if (!strcmp(argv[2], "none")) CHECK(scope.count == 0);
    else {
        CHECK(scope.count > 0);
        if (strcmp(scope.entries[0].operation, argv[2]))
            fprintf(stderr, "mode=%s expected=%s observed=%s errno=%d\n", mode, argv[2],
                    scope.entries[0].operation, scope.entries[0].error_number);
        CHECK(!strcmp(scope.entries[0].operation, argv[2]));
        int wanted = !strcmp(argv[3], "EINVAL") ? EINVAL :
                     !strcmp(argv[3], "ECHILD") ? ECHILD :
                     !strcmp(argv[3], "EIO") ? EIO :
                     !strcmp(argv[3], "zero") ? 0 : EACCES;
        CHECK(scope.entries[0].error_number == wanted);
        for (size_t i = 0; i < scope.count; ++i) {
            CHECK(!strchr(scope.entries[i].component, '/'));
            CHECK(!strchr(scope.entries[i].operation, '/'));
        }
    }
    if (is("spawn-cleanup")) CHECK(scope.count == 7 && spawn_calls == 1);
    if (is("poll-kill")) CHECK(scope.count == 2 && !strcmp(scope.entries[1].operation, "kill_group"));
    return 0;
}
