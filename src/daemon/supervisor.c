#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#ifndef _DARWIN_C_SOURCE
#define _DARWIN_C_SOURCE
#endif
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "golem/supervisor.h"
#include "cgroup_internal.h"
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
extern char **environ;

static golem_status clock_ns(uint64_t *out)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) < 0 || t.tv_sec < 0)
        return GOLEM_ERR_IO;
    if ((uint64_t)t.tv_sec > (UINT64_MAX - (uint64_t)t.tv_nsec) / 1000000000u)
        return GOLEM_ERR_OVERFLOW;
    *out = (uint64_t)t.tv_sec * 1000000000u + (uint64_t)t.tv_nsec;
    return GOLEM_OK;
}
static bool fd_prepare(int *fd)
{
    if (*fd < 3) {
        int copy = fcntl(*fd, F_DUPFD_CLOEXEC, 3);
        (void)close(*fd);
        *fd = copy;
    }
    return *fd >= 0 && fcntl(*fd, F_SETFD, FD_CLOEXEC) == 0;
}
static golem_status drain(int fd, uint8_t *buffer, size_t *size, bool *eof,
                          const golem_supervisor_stream *sink,
                          golem_supervisor_capture *capture, unsigned stream,
                          const uint64_t *limits)
{
    uint8_t chunk[4096];
    /* Return to heartbeat/deadline and the other pipe even for a hot writer. */
    for (unsigned batch = 0; batch < 16; ++batch) {
        ssize_t n = read(fd, chunk, sizeof(chunk));
        if (n < 0 && errno == EINTR)
            continue;
        if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK))
            return GOLEM_OK;
        if (n < 0)
            return GOLEM_ERR_IO;
        if (n == 0) {
            *eof = true;
            if (capture)
                capture->eof[stream] = true;
            return GOLEM_OK;
        }
        if (capture) {
            if ((uint64_t)n > UINT64_MAX - capture->observed_bytes[stream])
                return GOLEM_ERR_OVERFLOW;
            capture->observed_bytes[stream] += (uint64_t)n;
            if (limits && capture->observed_bytes[stream] > limits[stream])
                return GOLEM_ERR_BUDGET_EXHAUSTED;
        }
        if (sink) {
            golem_status st = sink->write(sink->context, stream,
                                          (golem_bytes){chunk, (size_t)n});
            if (st != GOLEM_OK)
                return st;
        }
        if (limits)
            continue;
        if ((size_t)n > GOLEM_SUPERVISOR_OUTPUT_MAX - *size)
            return GOLEM_ERR_OVERFLOW;
        memcpy(buffer + *size, chunk, (size_t)n);
        *size += (size_t)n;
    }
    return GOLEM_OK;
}
static golem_status run(const char *executable, char *const argv[], const char *cwd,
                        char *const envp[], golem_bytes input, uint64_t timeout,
                        golem_status (*pulse)(void *), void *context, golem_supervisor_result *out,
                        golem_supervisor_observation *observation,
                        const golem_supervisor_stream *sink, golem_supervisor_capture *capture,
                        const uint64_t *limits, int inherited)
{
    if (executable == NULL || executable[0] != '/' || argv == NULL || argv[0] == NULL ||
        out == NULL || timeout == 0 || timeout > UINT64_C(3600000000000) || input.size > 16384 ||
        (input.size != 0 && input.data == NULL))
        return GOLEM_ERR_INVALID_ARGUMENT;
    int in[2] = {-1, -1}, output[2] = {-1, -1}, error[2] = {-1, -1};
    golem_status s = GOLEM_ERR_IO;
    pid_t pid = -1;
    posix_spawn_file_actions_t actions;
    posix_spawnattr_t attributes;
    bool actions_init = false, attrs_init = false;
#ifdef __linux__
    /* Atomic CLOEXEC matters when independent supervisor threads spawn together. */
    if (socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, in) < 0 ||
        pipe2(output, O_CLOEXEC) < 0 || pipe2(error, O_CLOEXEC) < 0)
#else
    if (socketpair(AF_UNIX, SOCK_STREAM, 0, in) < 0 || pipe(output) < 0 || pipe(error) < 0)
#endif
        goto cleanup;
    for (size_t i = 0; i < 2; ++i)
        if (!fd_prepare(&in[i]) || !fd_prepare(&output[i]) || !fd_prepare(&error[i]))
            goto cleanup;
#ifdef SO_NOSIGPIPE
    int one = 1;
    if (setsockopt(in[0], SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof(one)) < 0)
        goto cleanup;
#endif
    if (posix_spawn_file_actions_init(&actions) != 0)
        goto cleanup;
    actions_init = true;
    if (posix_spawnattr_init(&attributes) != 0)
        goto cleanup;
    attrs_init = true;
    /* Keep compatibility with pre-macOS-26 deployment targets. The new POSIX
     * spelling is not available there; only this compatibility call is exempt. */
#ifdef __APPLE__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
#endif
    if (cwd && posix_spawn_file_actions_addchdir_np(&actions, cwd) != 0)
        goto cleanup;
#ifdef __APPLE__
#pragma clang diagnostic pop
#endif
    if (posix_spawn_file_actions_adddup2(&actions, in[1], STDIN_FILENO) != 0 ||
        posix_spawn_file_actions_adddup2(&actions, output[1], STDOUT_FILENO) != 0 ||
        posix_spawn_file_actions_adddup2(&actions, error[1], STDERR_FILENO) != 0)
        goto cleanup;
    for (size_t i = 0; i < 2; ++i)
        if (posix_spawn_file_actions_addclose(&actions, in[i]) != 0 ||
            posix_spawn_file_actions_addclose(&actions, output[i]) != 0 ||
            posix_spawn_file_actions_addclose(&actions, error[i]) != 0)
            goto cleanup;
    sigset_t mask;
    if (inherited >= 0 && posix_spawn_file_actions_adddup2(&actions, inherited, 3) != 0)
        goto cleanup;
    sigemptyset(&mask);
    short spawn_flags = POSIX_SPAWN_SETPGROUP | POSIX_SPAWN_SETSIGMASK;
#ifdef __APPLE__
    /* Darwin lacks pipe2; close every descriptor not explicitly mapped by actions. */
    spawn_flags |= POSIX_SPAWN_CLOEXEC_DEFAULT;
#endif
    if (posix_spawnattr_setsigmask(&attributes, &mask) != 0 ||
        posix_spawnattr_setpgroup(&attributes, 0) != 0 ||
        posix_spawnattr_setflags(&attributes, spawn_flags) != 0)
        goto cleanup;
    uint64_t start;
    s = clock_ns(&start);
    if (s != GOLEM_OK)
        goto cleanup;
    if (timeout > UINT64_MAX - start) {
        s = GOLEM_ERR_OVERFLOW;
        goto cleanup;
    }
    if (posix_spawn(&pid, executable, &actions, &attributes, argv, envp) != 0) {
        pid = -1;
        s = GOLEM_ERR_IO;
        goto cleanup;
    }
    if (observation)
        observation->spawned = true;
    if (capture)
        capture->spawned = true;
    (void)close(in[1]);
    in[1] = -1;
    (void)close(output[1]);
    output[1] = -1;
    (void)close(error[1]);
    error[1] = -1;
    golem_supervisor_result result = {.exit_code = -1};
    size_t sent = 0;
    bool stdout_eof = false, stderr_eof = false;
#ifdef __APPLE__
    bool exited = false, group_permission_pending = false;
#endif
    if (fcntl(in[0], F_SETFL, O_NONBLOCK) < 0 || fcntl(output[0], F_SETFL, O_NONBLOCK) < 0 ||
        fcntl(error[0], F_SETFL, O_NONBLOCK) < 0)
        s = GOLEM_ERR_IO;
    while (s == GOLEM_OK) {
        uint64_t time;
        s = clock_ns(&time);
        if (s != GOLEM_OK)
            break;
        if (time < start) {
            s = GOLEM_ERR_INVALID_STATE;
            break;
        }
        if (time - start >= timeout) {
            result.timed_out = true;
            s = GOLEM_ERR_INCOMPLETE_WORK;
            break;
        }
        if (pulse != NULL) {
            s = pulse(context);
            if (s != GOLEM_OK)
                break;
        }
        if (in[0] >= 0 && sent < input.size) {
#ifdef MSG_NOSIGNAL
            ssize_t n = send(in[0], input.data + sent, input.size - sent, MSG_NOSIGNAL);
#else
            ssize_t n = send(in[0], input.data + sent, input.size - sent, 0);
#endif
            if (n > 0)
                sent += (size_t)n;
            else if (n < 0 && (errno == EPIPE || errno == ECONNRESET)) {
                /* The child declined input. Preserve its exit/signal and drain
                 * diagnostics; unsent input is classified below as incomplete. */
                (void)close(in[0]);
                in[0] = -1;
            } else if (n < 0 && errno != EINTR && errno != EAGAIN && errno != EWOULDBLOCK) {
                s = GOLEM_ERR_IO;
                break;
            }
        }
        if (in[0] >= 0 && sent == input.size) {
            (void)close(in[0]);
            in[0] = -1;
        }
        s = drain(output[0], result.output, &result.output_size, &stdout_eof, sink, capture, 0, limits);
        if (s != GOLEM_OK)
            break;
        s = drain(error[0], result.error, &result.error_size, &stderr_eof, sink, capture, 1, limits);
        if (s != GOLEM_OK)
            break;
        siginfo_t info;
        memset(&info, 0, sizeof(info));
        if (waitid(P_PID, (id_t)pid, &info, WEXITED | WNOHANG | WNOWAIT) < 0) {
            if (errno == EINTR)
                continue;
            s = GOLEM_ERR_IO;
            break;
        }
        if (info.si_pid == pid) {
#ifdef __APPLE__
            exited = true;
#endif
            s = drain(output[0], result.output, &result.output_size, &stdout_eof, sink, capture, 0, limits);
            if (s == GOLEM_OK)
                s = drain(error[0], result.error, &result.error_size, &stderr_eof, sink, capture, 1, limits);
            break;
        }
        struct pollfd fds[3] = {{stdout_eof ? -1 : output[0], POLLIN, 0},
                                {stderr_eof ? -1 : error[0], POLLIN, 0},
                                {in[0], POLLOUT, 0}};
        if (poll(fds, 3, 20) < 0 && errno != EINTR) {
            s = GOLEM_ERR_IO;
            break;
        }
    }
    /* Leader remains unreaped, so its process-group ID cannot be reused here. */
    if (kill(-pid, SIGKILL) < 0 && errno != ESRCH && s == GOLEM_OK) {
        /* Darwin can report EPERM for an exited group leader before pipe EOF
         * becomes visible. Decide only after reaping and the final drain. */
#ifdef __APPLE__
        if (errno == EPERM && exited)
            group_permission_pending = true;
        else
            s = GOLEM_ERR_IO;
#else
        s = GOLEM_ERR_IO;
#endif
    }
    int status = 0;
    pid_t waited;
    do {
        waited = waitpid(pid, &status, 0);
    } while (waited < 0 && errno == EINTR);
    if (observation)
        observation->reaped = waited == pid;
    if (capture)
        capture->reaped = waited == pid;
    if (waited != pid && s == GOLEM_OK)
        s = GOLEM_ERR_IO;
    if (waited == pid && WIFEXITED(status))
        result.exit_code = WEXITSTATUS(status);
    if (waited == pid && WIFSIGNALED(status))
        result.signal_number = WTERMSIG(status);
    golem_status drained = drain(output[0], result.output, &result.output_size, &stdout_eof, sink, capture, 0, limits);
    if (s == GOLEM_OK)
        s = drained;
    drained = drain(error[0], result.error, &result.error_size, &stderr_eof, sink, capture, 1, limits);
    if (s == GOLEM_OK)
        s = drained;
    /* Reaping the leader is not a readiness notification for nonblocking
     * pipes. Finish draining within the original deadline, without retrying
     * execution or signalling a process-group ID after it may be reused. */
    while (s == GOLEM_OK && (!stdout_eof || !stderr_eof)) {
        uint64_t time;
        s = clock_ns(&time);
        if (s != GOLEM_OK)
            break;
        if (time < start) {
            s = GOLEM_ERR_INVALID_STATE;
            break;
        }
        if (time - start >= timeout) {
            result.timed_out = true;
            s = GOLEM_ERR_INCOMPLETE_WORK;
            break;
        }
        if (pulse != NULL) {
            s = pulse(context);
            if (s != GOLEM_OK)
                break;
        }
        struct pollfd fds[2] = {{stdout_eof ? -1 : output[0], POLLIN, 0},
                                {stderr_eof ? -1 : error[0], POLLIN, 0}};
        if (poll(fds, 2, 20) < 0 && errno != EINTR) {
            s = GOLEM_ERR_IO;
            break;
        }
        s = drain(output[0], result.output, &result.output_size, &stdout_eof, sink, capture, 0, limits);
        if (s == GOLEM_OK)
            s = drain(error[0], result.error, &result.error_size, &stderr_eof, sink, capture, 1, limits);
    }
#ifdef __APPLE__
    /* A live descendant retaining a pipe or a failed reap still fails closed. */
    if ((s == GOLEM_OK || s == GOLEM_ERR_INCOMPLETE_WORK) && group_permission_pending &&
        (waited != pid || !stdout_eof || !stderr_eof))
        s = GOLEM_ERR_IO;
#endif
    if (s == GOLEM_OK && (result.exit_code != 0 || result.signal_number != 0 ||
                          sent != input.size || !stdout_eof || !stderr_eof))
        s = GOLEM_ERR_INCOMPLETE_WORK;
    *out = result;
cleanup:
    if (actions_init)
        (void)posix_spawn_file_actions_destroy(&actions);
    if (attrs_init)
        (void)posix_spawnattr_destroy(&attributes);
    for (size_t i = 0; i < 2; ++i) {
        if (in[i] >= 0)
            (void)close(in[i]);
        if (output[i] >= 0)
            (void)close(output[i]);
        if (error[i] >= 0)
            (void)close(error[i]);
    }
    return s;
}
golem_status golem_supervisor_run(const char *executable, char *const argv[], golem_bytes input,
                                  uint64_t timeout, golem_status (*pulse)(void *), void *context,
                                  golem_supervisor_result *out)
{
    return run(executable, argv, NULL, environ, input, timeout, pulse, context, out, NULL, NULL, NULL, NULL, -1);
}
golem_status golem_supervisor_run_at(const char *executable, char *const argv[], const char *cwd,
                                     char *const envp[], golem_bytes input, uint64_t timeout,
                                     golem_status (*pulse)(void *), void *context,
                                     golem_supervisor_result *out)
{
    if (!cwd || cwd[0] != '/' || !envp)
        return GOLEM_ERR_INVALID_ARGUMENT;
    return run(executable, argv, cwd, envp, input, timeout, pulse, context, out, NULL, NULL, NULL, NULL, -1);
}
golem_status golem_supervisor_run_observed(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout,
    golem_status (*pulse)(void *), void *context, golem_supervisor_result *out,
    golem_supervisor_observation *observation)
{
    if (!observation)
        return GOLEM_ERR_INVALID_ARGUMENT;
    *observation = (golem_supervisor_observation){0};
    if (!cwd || cwd[0] != '/' || !envp)
        return GOLEM_ERR_INVALID_ARGUMENT;
    return run(executable, argv, cwd, envp, input, timeout, pulse, context, out, observation, NULL, NULL, NULL, -1);
}
golem_status golem_supervisor_run_streamed(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout,
    golem_status (*pulse)(void *), void *context, golem_supervisor_result *out,
    const golem_supervisor_stream *stream, golem_supervisor_capture *capture)
{
    if (!capture)
        return GOLEM_ERR_INVALID_ARGUMENT;
    *capture = (golem_supervisor_capture){0};
    if (!cwd || cwd[0] != '/' || !envp || !stream ||
        stream->struct_size != sizeof(*stream) || stream->version != 1 || !stream->write)
        return GOLEM_ERR_INVALID_ARGUMENT;
    return run(executable, argv, cwd, envp, input, timeout, pulse, context, out, NULL, stream, capture, NULL, -1);
}

golem_status golem_supervisor_run_bulk(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout,
    golem_status (*pulse)(void *), void *context, golem_supervisor_result *out,
    const golem_supervisor_stream *stream, const uint64_t limits[2],
    golem_supervisor_capture *capture)
{
    if (!capture)
        return GOLEM_ERR_INVALID_ARGUMENT;
    *capture = (golem_supervisor_capture){0};
    if (!cwd || cwd[0] != '/' || !envp || !stream ||
        stream->struct_size != sizeof(*stream) || stream->version != 1 || !stream->write ||
        !limits || !limits[0] || !limits[1] || limits[0] > UINT64_C(67108864) ||
        limits[1] > UINT64_C(67108864))
        return GOLEM_ERR_INVALID_ARGUMENT;
    return run(executable, argv, cwd, envp, input, timeout, pulse, context, out,
               NULL, stream, capture, limits, -1);
}

golem_status golem_supervisor_run_joined(const char *exe, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout,
    golem_status (*pulse)(void *), void *context, golem_supervisor_result *out, int inherited)
{
    if (!cwd || cwd[0] != '/' || !envp || inherited < 3)
        return GOLEM_ERR_INVALID_ARGUMENT;
    return run(exe, argv, cwd, envp, input, timeout, pulse, context, out,
               NULL, NULL, NULL, NULL, inherited);
}
