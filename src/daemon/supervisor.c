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
#include "golem/system_error.h"
#include "../common/record_internal.h"
#include "golem/record.h"
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

/* POSIX spawn APIs return an error number, unlike errno-based syscalls. */
static bool spawn_ok(int error, const char *operation)
{
    if (error)
        (void)golem_system_error_note(GOLEM_ERR_IO, "supervisor.spawn", operation, error);
    return error == 0;
}
static bool io_ok(int result, const char *operation)
{
    if (result < 0)
        (void)golem_system_error_note(GOLEM_ERR_IO, "supervisor", operation, errno);
    return result >= 0;
}
static void close_observed(int fd)
{
    /* Preserve ownership and the existing no-retry cleanup policy. */
    if (close(fd) < 0)
        (void)golem_system_error_note(GOLEM_ERR_IO, "supervisor.cleanup", "close", errno);
}
static golem_status clock_ns(uint64_t *out)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) < 0)
        return golem_system_error_note(GOLEM_ERR_IO, "supervisor", "clock_gettime", errno);
    if (t.tv_sec < 0 || t.tv_nsec < 0 || t.tv_nsec >= 1000000000)
        return golem_system_error_note(GOLEM_ERR_IO, "supervisor", "clock_value", 0);
    if ((uint64_t)t.tv_sec > (UINT64_MAX - (uint64_t)t.tv_nsec) / 1000000000u)
        return GOLEM_ERR_OVERFLOW;
    *out = (uint64_t)t.tv_sec * 1000000000u + (uint64_t)t.tv_nsec;
    return GOLEM_OK;
}
static bool fd_prepare(int *fd)
{
    if (*fd < 3) {
        int copy = fcntl(*fd, F_DUPFD_CLOEXEC, 3);
        (void)io_ok(copy, "fcntl_duplicate");
        close_observed(*fd);
        *fd = copy;
    }
    return *fd >= 0 && io_ok(fcntl(*fd, F_SETFD, FD_CLOEXEC), "fcntl_cloexec");
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
            return golem_system_error_note(GOLEM_ERR_IO, "supervisor", stream ? "read_stderr" : "read_stdout", errno);
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
static golem_status run_process(const char *executable, char *const argv[], const char *cwd,
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
    if (!io_ok(socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, in), "socketpair") ||
        !io_ok(pipe2(output, O_CLOEXEC), "pipe_stdout") ||
        !io_ok(pipe2(error, O_CLOEXEC), "pipe_stderr"))
#else
    if (!io_ok(socketpair(AF_UNIX, SOCK_STREAM, 0, in), "socketpair") ||
        !io_ok(pipe(output), "pipe_stdout") || !io_ok(pipe(error), "pipe_stderr"))
#endif
        goto cleanup;
    for (size_t i = 0; i < 2; ++i)
        if (!fd_prepare(&in[i]) || !fd_prepare(&output[i]) || !fd_prepare(&error[i]))
            goto cleanup;
#ifdef SO_NOSIGPIPE
    int one = 1;
    if (!io_ok(setsockopt(in[0], SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof(one)), "setsockopt"))
        goto cleanup;
#endif
    if (!spawn_ok(posix_spawn_file_actions_init(&actions), "actions_init"))
        goto cleanup;
    actions_init = true;
    if (!spawn_ok(posix_spawnattr_init(&attributes), "attributes_init"))
        goto cleanup;
    attrs_init = true;
    /* Keep compatibility with pre-macOS-26 deployment targets. The new POSIX
     * spelling is not available there; only this compatibility call is exempt. */
#ifdef __APPLE__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
#endif
    if (cwd && !spawn_ok(posix_spawn_file_actions_addchdir_np(&actions, cwd), "addchdir"))
        goto cleanup;
#ifdef __APPLE__
#pragma clang diagnostic pop
#endif
    if (!spawn_ok(posix_spawn_file_actions_adddup2(&actions, in[1], STDIN_FILENO), "dup_stdin") ||
        !spawn_ok(posix_spawn_file_actions_adddup2(&actions, output[1], STDOUT_FILENO), "dup_stdout") ||
        !spawn_ok(posix_spawn_file_actions_adddup2(&actions, error[1], STDERR_FILENO), "dup_stderr"))
        goto cleanup;
    for (size_t i = 0; i < 2; ++i)
        if (!spawn_ok(posix_spawn_file_actions_addclose(&actions, in[i]), "close_stdin") ||
            !spawn_ok(posix_spawn_file_actions_addclose(&actions, output[i]), "close_stdout") ||
            !spawn_ok(posix_spawn_file_actions_addclose(&actions, error[i]), "close_stderr"))
            goto cleanup;
    sigset_t mask;
    if (inherited >= 0 && !spawn_ok(posix_spawn_file_actions_adddup2(&actions, inherited, 3), "dup_inherited"))
        goto cleanup;
    if (!io_ok(sigemptyset(&mask), "sigemptyset"))
        goto cleanup;
    short spawn_flags = POSIX_SPAWN_SETPGROUP | POSIX_SPAWN_SETSIGMASK;
#ifdef __APPLE__
    /* Darwin lacks pipe2; close every descriptor not explicitly mapped by actions. */
    spawn_flags |= POSIX_SPAWN_CLOEXEC_DEFAULT;
#endif
    if (!spawn_ok(posix_spawnattr_setsigmask(&attributes, &mask), "setsigmask") ||
        !spawn_ok(posix_spawnattr_setpgroup(&attributes, 0), "setpgroup") ||
        !spawn_ok(posix_spawnattr_setflags(&attributes, spawn_flags), "setflags"))
        goto cleanup;
    uint64_t start;
    s = clock_ns(&start);
    if (s != GOLEM_OK)
        goto cleanup;
    if (timeout > UINT64_MAX - start) {
        s = GOLEM_ERR_OVERFLOW;
        goto cleanup;
    }
    if (!spawn_ok(posix_spawn(&pid, executable, &actions, &attributes, argv, envp), "posix_spawn")) {
        pid = -1;
        s = GOLEM_ERR_IO;
        goto cleanup;
    }
    if (observation)
        observation->spawned = true;
    if (capture)
        capture->spawned = true;
    close_observed(in[1]);
    in[1] = -1;
    close_observed(output[1]);
    output[1] = -1;
    close_observed(error[1]);
    error[1] = -1;
    golem_supervisor_result result = {.exit_code = -1};
    size_t sent = 0;
    bool stdout_eof = false, stderr_eof = false;
#ifdef __APPLE__
    bool exited = false, group_permission_pending = false;
#endif
    if (!io_ok(fcntl(in[0], F_SETFL, O_NONBLOCK), "nonblock_stdin") ||
        !io_ok(fcntl(output[0], F_SETFL, O_NONBLOCK), "nonblock_stdout") ||
        !io_ok(fcntl(error[0], F_SETFL, O_NONBLOCK), "nonblock_stderr"))
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
                (void)golem_system_error_note(GOLEM_ERR_INCOMPLETE_WORK, "supervisor", "send_input_closed", errno);
                close_observed(in[0]);
                in[0] = -1;
            } else if (n < 0 && errno != EINTR && errno != EAGAIN && errno != EWOULDBLOCK) {
                s = golem_system_error_note(GOLEM_ERR_IO, "supervisor", "send", errno);
                break;
            }
        }
        if (in[0] >= 0 && sent == input.size) {
            close_observed(in[0]);
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
            s = golem_system_error_note(GOLEM_ERR_IO, "supervisor", "waitid", errno);
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
            s = golem_system_error_note(GOLEM_ERR_IO, "supervisor", "poll", errno);
            break;
        }
    }
    /* Leader remains unreaped, so its process-group ID cannot be reused here. */
    if (kill(-pid, SIGKILL) < 0 && errno != ESRCH) {
        int saved = errno;
        (void)golem_system_error_note(GOLEM_ERR_IO, "supervisor.cleanup", "kill_group", saved);
        /* Darwin can report EPERM for an exited group leader before pipe EOF
         * becomes visible. Decide only after reaping and the final drain. */
#ifdef __APPLE__
        if (saved == EPERM && exited && s == GOLEM_OK)
            group_permission_pending = true;
        else if (s == GOLEM_OK)
            s = GOLEM_ERR_IO;
#else
        if (s == GOLEM_OK) s = GOLEM_ERR_IO;
#endif
    }
    int status = 0;
    pid_t waited;
    do {
        waited = waitpid(pid, &status, 0);
    } while (waited < 0 && errno == EINTR);
    if (waited != pid)
        (void)golem_system_error_note(GOLEM_ERR_IO, "supervisor.cleanup", "waitpid", waited < 0 ? errno : 0);
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
            s = golem_system_error_note(GOLEM_ERR_IO, "supervisor", "poll_drain", errno);
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
        (void)spawn_ok(posix_spawn_file_actions_destroy(&actions), "actions_destroy");
    if (attrs_init)
        (void)spawn_ok(posix_spawnattr_destroy(&attributes), "attributes_destroy");
    for (size_t i = 0; i < 2; ++i) {
        if (in[i] >= 0)
            close_observed(in[i]);
        if (output[i] >= 0)
            close_observed(output[i]);
        if (error[i] >= 0)
            close_observed(error[i]);
    }
    return s;
}
typedef struct recorded_stream {
    golem_record *record;
    const golem_supervisor_stream *downstream;
} recorded_stream;
static golem_status record_chunk(void *context, unsigned stream, golem_bytes bytes)
{
    recorded_stream *r = context;
    golem_status st = golem_record_write(r->record, stream, bytes);
    if (st == GOLEM_OK && r->downstream)
        st = r->downstream->write(r->downstream->context, stream, bytes);
    return st;
}
static golem_status run(const char *executable, char *const argv[], const char *cwd,
    char *const envp[], golem_bytes input, uint64_t timeout,
    golem_status (*pulse)(void *), void *context, golem_supervisor_result *out,
    golem_supervisor_observation *observation, const golem_supervisor_stream *sink,
    golem_supervisor_capture *capture, const uint64_t *limits, int inherited)
{
    golem_record_options options = {.struct_size = sizeof(options), .version = 1,
        .kind = "process", .operation = "supervisor", .executable = executable,
        .argv = argv, .cwd = cwd};
    golem_record *record = NULL;
    golem_status st = golem_record_begin(&options, &record);
    if (st != GOLEM_OK) return st;
    if (!record) return run_process(executable, argv, cwd, envp, input, timeout,
        pulse, context, out, observation, sink, capture, limits, inherited);
    recorded_stream tee = {record, sink};
    golem_supervisor_stream stream = {sizeof(stream), 1, record_chunk, &tee};
    golem_supervisor_capture local_capture = {0};
    golem_supervisor_capture *observed = capture ? capture : &local_capture;
    golem_supervisor_result result = {.exit_code = -1};
    /* Preserve legacy output-on-pre-spawn-failure and all existing stream limits. */
    st = run_process(executable, argv, cwd, envp, input, timeout, pulse, context,
        out ? &result : NULL, observation, &stream, observed, limits, inherited);
    if (observed->spawned && out) *out = result;
    golem_record_result finish = {.struct_size = sizeof(finish), .version = 1,
        .operation_status = st, .exit_code = result.exit_code,
        .signal_number = result.signal_number, .timed_out = result.timed_out,
        .spawned = observed->spawned, .reaped = observed->reaped,
        .eof = {observed->eof[0], observed->eof[1]}};
    golem_status recorded = golem_record_finish(record, &finish);
    return st == GOLEM_OK ? recorded : st;
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
        return gr_api_rejected("golem_supervisor_run_at");
    return run(executable, argv, cwd, envp, input, timeout, pulse, context, out, NULL, NULL, NULL, NULL, -1);
}
golem_status golem_supervisor_run_observed(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout,
    golem_status (*pulse)(void *), void *context, golem_supervisor_result *out,
    golem_supervisor_observation *observation)
{
    if (!observation)
        return gr_api_rejected("golem_supervisor_run_observed");
    *observation = (golem_supervisor_observation){0};
    if (!cwd || cwd[0] != '/' || !envp)
        return gr_api_rejected("golem_supervisor_run_observed");
    return run(executable, argv, cwd, envp, input, timeout, pulse, context, out, observation, NULL, NULL, NULL, -1);
}
golem_status golem_supervisor_run_streamed(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout,
    golem_status (*pulse)(void *), void *context, golem_supervisor_result *out,
    const golem_supervisor_stream *stream, golem_supervisor_capture *capture)
{
    if (!capture)
        return gr_api_rejected("golem_supervisor_run_streamed");
    *capture = (golem_supervisor_capture){0};
    if (!cwd || cwd[0] != '/' || !envp || !stream ||
        stream->struct_size != sizeof(*stream) || stream->version != 1 || !stream->write)
        return gr_api_rejected("golem_supervisor_run_streamed");
    return run(executable, argv, cwd, envp, input, timeout, pulse, context, out, NULL, stream, capture, NULL, -1);
}

golem_status golem_supervisor_run_bulk(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout,
    golem_status (*pulse)(void *), void *context, golem_supervisor_result *out,
    const golem_supervisor_stream *stream, const uint64_t limits[2],
    golem_supervisor_capture *capture)
{
    if (!capture)
        return gr_api_rejected("golem_supervisor_run_bulk");
    *capture = (golem_supervisor_capture){0};
    if (!cwd || cwd[0] != '/' || !envp || !stream ||
        stream->struct_size != sizeof(*stream) || stream->version != 1 || !stream->write ||
        !limits || !limits[0] || !limits[1] || limits[0] > UINT64_C(67108864) ||
        limits[1] > UINT64_C(67108864))
        return gr_api_rejected("golem_supervisor_run_bulk");
    return run(executable, argv, cwd, envp, input, timeout, pulse, context, out,
               NULL, stream, capture, limits, -1);
}

golem_status golem_supervisor_run_joined(const char *exe, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout,
    golem_status (*pulse)(void *), void *context, golem_supervisor_result *out, int inherited)
{
    if (!cwd || cwd[0] != '/' || !envp || inherited < 3)
        return gr_api_rejected("golem_supervisor_run_joined");
    return run(exe, argv, cwd, envp, input, timeout, pulse, context, out,
               NULL, NULL, NULL, NULL, inherited);
}
