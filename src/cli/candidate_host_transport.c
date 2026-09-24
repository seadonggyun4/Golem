#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "candidate_host.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopping;
static void stop_signal(int signal_number)
{
    (void)signal_number;
    stopping = 1;
}
static uint64_t milliseconds(void)
{
    struct timespec now;
    return clock_gettime(CLOCK_MONOTONIC, &now)
               ? 0
               : (uint64_t)now.tv_sec * 1000 + (uint64_t)now.tv_nsec / 1000000;
}

static golem_status transfer(int fd, void *data, size_t size, bool writing, uint64_t deadline)
{
    size_t offset = 0;
    while (offset < size) {
        uint64_t now = milliseconds();
        if (!now || now >= deadline || stopping)
            return GOLEM_ERR_IO;
        struct pollfd p = {.fd = fd, .events = writing ? POLLOUT : POLLIN};
        int ready = poll(&p, 1, (int)(deadline - now));
        if (ready < 0 && errno == EINTR)
            continue;
        if (ready <= 0)
            return GOLEM_ERR_IO;
        ssize_t n = writing ? send(fd, (uint8_t *)data + offset, size - offset, 0)
                            : recv(fd, (uint8_t *)data + offset, size - offset, 0);
        if (n < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK))
            continue;
        if (n <= 0)
            return GOLEM_ERR_IO;
        offset += (size_t)n;
    }
    return GOLEM_OK;
}

static golem_status send_json(int fd, struct json_object *o, unsigned timeout_ms)
{
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (!text)
        return GOLEM_ERR_OUT_OF_MEMORY;
    size_t n = strlen(text);
    if (!n || n > CH_WIRE_MAX)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    uint8_t header[4] = {(uint8_t)(n >> 24), (uint8_t)(n >> 16), (uint8_t)(n >> 8), (uint8_t)n};
    uint64_t deadline = milliseconds() + timeout_ms;
    golem_status st = transfer(fd, header, sizeof(header), true, deadline);
    if (st == GOLEM_OK)
        st = transfer(fd, (void *)text, n, true, deadline);
    return st;
}

static golem_status receive_json(int fd, unsigned timeout_ms, struct json_object **out)
{
    uint8_t header[4];
    uint64_t deadline = milliseconds() + timeout_ms;
    golem_status st = transfer(fd, header, sizeof(header), false, deadline);
    if (st != GOLEM_OK)
        return st;
    size_t n = ((size_t)header[0] << 24) | ((size_t)header[1] << 16) | ((size_t)header[2] << 8) |
               header[3];
    if (!n || n > CH_WIRE_MAX)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    uint8_t *bytes = malloc(n);
    if (!bytes)
        return GOLEM_ERR_OUT_OF_MEMORY;
    st = transfer(fd, bytes, n, false, deadline);
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){bytes, n}, CH_WIRE_MAX, out);
    free(bytes);
    return st;
}

/* Private canonical parent + same-uid peer, not a remote authentication service.
 * Never replace a preexisting endpoint, including a stale socket after a crash. */
static golem_status address(const char *path, struct sockaddr_un *out)
{
    if (!path || path[0] != '/' || strlen(path) >= sizeof(out->sun_path))
        return GOLEM_ERR_INVALID_ARGUMENT;
    char parent[sizeof(out->sun_path)];
    strcpy(parent, path);
    char *slash = strrchr(parent, '/');
    if (!slash || slash == parent || !slash[1] || !strcmp(slash + 1, ".") ||
        !strcmp(slash + 1, ".."))
        return GOLEM_ERR_INVALID_ARGUMENT;
    *slash = 0;
    int directory = -1;
    golem_status st = ws_directory(parent, &directory);
    struct stat s;
    if (st == GOLEM_OK && fstat(directory, &s))
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && (s.st_uid != geteuid() || (s.st_mode & 0077)))
        st = GOLEM_ERR_POLICY_DENIED;
    if (directory >= 0)
        close(directory);
    if (st == GOLEM_OK) {
        *out = (struct sockaddr_un){.sun_family = AF_UNIX};
        strcpy(out->sun_path, path);
    }
    return st;
}

static golem_status peer(int fd)
{
#if defined(__APPLE__)
    uid_t uid;
    gid_t gid;
    return getpeereid(fd, &uid, &gid) == 0 && uid == geteuid() ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED;
#elif defined(__linux__)
    struct ucred credentials;
    socklen_t size = sizeof(credentials);
    return getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &credentials, &size) == 0 &&
                   size == sizeof(credentials) && credentials.uid == geteuid()
               ? GOLEM_OK
               : GOLEM_ERR_POLICY_DENIED;
#else
    (void)fd;
    return GOLEM_ERR_POLICY_DENIED;
#endif
}

static golem_status nonblocking(int fd)
{
    int flags = fcntl(fd, F_GETFL);
    return flags >= 0 && fcntl(fd, F_SETFL, flags | O_NONBLOCK) == 0 &&
                   fcntl(fd, F_SETFD, FD_CLOEXEC) == 0
               ? GOLEM_OK
               : GOLEM_ERR_IO;
}

golem_status ch_client(const char *path, struct json_object *envelope, struct json_object **out)
{
    struct sockaddr_un addr;
    golem_status st = address(path, &addr);
    struct stat endpoint;
    if (st == GOLEM_OK && (lstat(path, &endpoint) || !S_ISSOCK(endpoint.st_mode) ||
                           endpoint.st_uid != geteuid() || (endpoint.st_mode & 0077)))
        st = GOLEM_ERR_POLICY_DENIED;
    int fd = st == GOLEM_OK ? socket(AF_UNIX, SOCK_STREAM, 0) : -1;
    if (st == GOLEM_OK && fd < 0)
        st = GOLEM_ERR_IO;
    (void)signal(SIGPIPE, SIG_IGN);
    if (st == GOLEM_OK)
        st = nonblocking(fd);
    if (st == GOLEM_OK && connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK)
        st = peer(fd);
    if (st == GOLEM_OK)
        st = send_json(fd, envelope, 5000);
    if (st == GOLEM_OK)
        st = receive_json(fd, 120000, out);
    if (fd >= 0)
        close(fd);
    return st;
}

golem_status ch_serve(struct json_object *config, const char *path)
{
    struct sockaddr_un addr;
    golem_status st = address(path, &addr);
    struct stat existing, owned = {0};
    if (st == GOLEM_OK && (lstat(path, &existing) == 0 || errno != ENOENT))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    ch_host host = {0};
    if (st == GOLEM_OK)
        st = ch_open(&host, config);
    int fd = st == GOLEM_OK ? socket(AF_UNIX, SOCK_STREAM, 0) : -1;
    if (st == GOLEM_OK && fd < 0)
        st = GOLEM_ERR_IO;
    bool bound = false;
    if (st == GOLEM_OK) {
        if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)))
            st = GOLEM_ERR_IO;
        else if (lstat(path, &owned))
            st = GOLEM_ERR_IO;
        else
            bound = true;
    }
    if (st == GOLEM_OK && (chmod(path, 0600) || listen(fd, 8)))
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK)
        st = nonblocking(fd);
    stopping = 0;
    (void)signal(SIGPIPE, SIG_IGN);
    (void)signal(SIGTERM, stop_signal);
    (void)signal(SIGINT, stop_signal);
    while (st == GOLEM_OK && !stopping && !host.stop) {
        struct pollfd wait = {.fd = fd, .events = POLLIN};
        int ready = poll(&wait, 1, 100);
        if (ready < 0 && errno == EINTR)
            continue;
        if (ready < 0) {
            st = GOLEM_ERR_IO;
            break;
        }
        if (!ready)
            continue;
        int client = accept(fd, NULL, NULL);
        if (client < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK))
            continue;
        if (client < 0) {
            st = GOLEM_ERR_IO;
            break;
        }
        struct json_object *request = NULL, *result = NULL, *response = json_object_new_object();
        golem_status call = nonblocking(client);
        if (call == GOLEM_OK)
            call = peer(client);
        if (call == GOLEM_OK)
            call = receive_json(client, 5000, &request);
        if (call == GOLEM_OK)
            call = ch_call(&host, request, &result);
        if (response && ex_uint(response, "status", call) &&
            dw_add(response, "result", result ? json_object_get(result) : json_object_new_object()))
            (void)send_json(client, response, 5000);
        /* A lost response is an uncertain outcome, never permission to retry a
         * start. Admission and candidate ledgers remain the source of truth. */
        json_object_put(request);
        json_object_put(result);
        json_object_put(response);
        close(client);
    }
    if (fd >= 0)
        close(fd);
    if (bound && lstat(path, &existing) == 0 && existing.st_dev == owned.st_dev &&
        existing.st_ino == owned.st_ino && S_ISSOCK(existing.st_mode))
        (void)unlink(path);
    golem_status closed = ch_close(&host);
    return st == GOLEM_OK ? closed : st;
}
