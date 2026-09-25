#define _POSIX_C_SOURCE 200809L
#include "golem/event_reader.h"
#include "event_bridge_limits.h"
#include <event2/event.h>
#include <event2/http.h>
#include <event2/buffer.h>
#include <event2/bufferevent.h>
#include <event2/keyvalq_struct.h>
#include <openssl/crypto.h>
#include <sys/resource.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <netinet/in.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define SUBSCRIBERS GB_SUBSCRIBERS
typedef struct subscriber {
    struct evhttp_request *request;
    golem_runtime_cursor cursor;
    bool has_cursor;
    unsigned blocked;
} subscriber;
typedef struct bridge {
    golem_event_reader *reader;
    struct event_base *base;
    subscriber clients[SUBSCRIBERS];
    char authority[40], bearer[72];
    const char *credential_path;
    unsigned ticks;
    bool healthy;
} bridge;

/* Credentials never come from query strings, argv values or event payloads. */
static bool credential(const char *path, char out[72])
{
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0)
        return false;
    struct stat st;
    char bytes[66];
    bool ok = !fstat(fd, &st) && S_ISREG(st.st_mode) && st.st_uid == geteuid() &&
              !(st.st_mode & 077) && (st.st_size == 64 || st.st_size == 65);
    ssize_t n = ok ? read(fd, bytes, sizeof(bytes)) : -1;
    if (close(fd))
        ok = false;
    if (n != 64 && !(n == 65 && bytes[64] == '\n'))
        ok = false;
    for (size_t i = 0; ok && i < 64; ++i)
        if (!((bytes[i] >= '0' && bytes[i] <= '9') || (bytes[i] >= 'a' && bytes[i] <= 'f')))
            ok = false;
    if (ok) {
        memcpy(out, "Bearer ", 7);
        memcpy(out + 7, bytes, 64);
        out[71] = 0;
    }
    OPENSSL_cleanse(bytes, sizeof(bytes));
    return ok;
}
static void disconnected(struct evhttp_connection *connection, void *context)
{
    (void)connection;
    subscriber *s = context;
    /* EOF/timeout detaches an unfinished streaming reply before closecb.
     * Attached requests remain owned by connection_free; detached ones do not.
     */
    if (s->request && !evhttp_request_get_connection(s->request))
        evhttp_request_free(s->request);
    memset(s, 0, sizeof(*s));
}
static void drop(subscriber *s)
{
    struct evhttp_connection *c = evhttp_request_get_connection(s->request);
    /* Attached requests are released by libevent after disconnected. */
    if (c)
        evhttp_connection_free(c);
    else {
        evhttp_request_free(s->request);
        memset(s, 0, sizeof(*s));
    }
}
static bool send_bytes(subscriber *s, const char *data, size_t size)
{
    struct evhttp_connection *c = evhttp_request_get_connection(s->request);
    struct bufferevent *bev = c ? evhttp_connection_get_bufferevent(c) : NULL;
    if (!bev || !gb_output_room(evbuffer_get_length(bufferevent_get_output(bev)), size))
        return false;
    struct evbuffer *b = evbuffer_new();
    if (!b)
        return false;
    bool ok = evbuffer_add(b, data, size) == 0;
    if (ok)
        evhttp_send_reply_chunk(s->request, b);
    evbuffer_free(b);
    return ok;
}
static void terminal(subscriber *s, const char *reason)
{
    char msg[160];
    int n = snprintf(msg, sizeof(msg),
                     "event: gap\ndata: {\"reason\":\"%s\",\"restart_required\":true}\n\n", reason);
    if (!strcmp(reason, "slow_consumer") || n <= 0 || (size_t)n >= sizeof(msg) ||
        !send_bytes(s, msg, (size_t)n)) {
        drop(s);
        return;
    }
    struct evhttp_request *req = s->request;
    struct evhttp_connection *c = evhttp_request_get_connection(req);
    evhttp_connection_set_closecb(c, NULL, NULL);
    memset(s, 0, sizeof(*s));
    evhttp_connection_free_on_completion(c);
    evhttp_send_reply_end(req);
}
static void pump(bridge *b, subscriber *s)
{
    golem_runtime_event records[GOLEM_RUNTIME_EVENT_PAGE_MAX];
    golem_runtime_event_page page;
    golem_status st = golem_event_reader_read(b->reader, s->has_cursor ? &s->cursor : NULL, records,
                                              GOLEM_RUNTIME_EVENT_PAGE_MAX, &page);
    if (st != GOLEM_OK) {
        terminal(s, st == GOLEM_ERR_STALE_RESULT ? "retention" : "source_changed");
        return;
    }
    for (size_t i = 0; i < page.count; ++i) {
        char frame[1024];
        size_t size;
        st = golem_runtime_event_sse(&records[i], frame, sizeof(frame), &size);
        if (st != GOLEM_OK) {
            terminal(s, "encoding");
            return;
        }
        if (!send_bytes(s, frame, size)) {
            if (gb_overloaded(&s->blocked, false))
                terminal(s, "slow_consumer");
            return;
        }
        (void)gb_overloaded(&s->blocked, true);
        s->cursor = records[i].cursor;
        s->has_cursor = true;
    }
    if (!page.count && b->ticks % 20 == 0) {
        static const char heartbeat[] = ": heartbeat\n\n";
        if (gb_overloaded(&s->blocked, send_bytes(s, heartbeat, sizeof(heartbeat) - 1)))
            terminal(s, "slow_consumer");
    }
}
static void tick(evutil_socket_t fd, short events, void *context)
{
    (void)fd;
    (void)events;
    bridge *b = context;
    char current[72];
    bool auth = credential(b->credential_path, current) && !CRYPTO_memcmp(current, b->bearer, 71);
    OPENSSL_cleanse(current, sizeof(current));
    b->healthy = auth && golem_event_reader_refresh(b->reader) == GOLEM_OK;
    ++b->ticks;
    for (size_t i = 0; i < SUBSCRIBERS; ++i)
        if (b->clients[i].request) {
            if (!b->healthy)
                terminal(&b->clients[i], auth ? "source_unavailable" : "authorization_changed");
            else
                pump(b, &b->clients[i]);
        }
}
static const char *single_header(struct evkeyvalq *headers, const char *name)
{
    const char *value = NULL;
    for (struct evkeyval *p = headers->tqh_first; p; p = p->next.tqe_next)
        if (!evutil_ascii_strcasecmp(p->key, name)) {
            if (value)
                return NULL;
            value = p->value;
        }
    return value;
}
static void request(struct evhttp_request *req, void *context)
{
    bridge *b = context;
    struct evkeyvalq *h = evhttp_request_get_input_headers(req);
    const char *host = single_header(h, "Host"), *auth = single_header(h, "Authorization");
    if (!host || strcmp(host, b->authority) || evhttp_find_header(h, "Origin")) {
        evhttp_send_error(req, 403, "Forbidden");
        return;
    }
    if (!auth || strlen(auth) != 71 || CRYPTO_memcmp(auth, b->bearer, 71)) {
        evhttp_send_error(req, 401, "Unauthorized");
        return;
    }
    if (evhttp_request_get_command(req) != EVHTTP_REQ_GET ||
        strcmp(evhttp_request_get_uri(req), "/events") ||
        evbuffer_get_length(evhttp_request_get_input_buffer(req))) {
        evhttp_send_error(req, 400, "Invalid observation request");
        return;
    }
    if (!b->healthy) {
        evhttp_send_error(req, 503, "Source unavailable");
        return;
    }
    golem_runtime_cursor cursor, *after = NULL;
    const char *id = single_header(h, "Last-Event-ID");
    if (!id && evhttp_find_header(h, "Last-Event-ID")) {
        evhttp_send_error(req, 400, "Duplicate cursor");
        return;
    }
    if (id && *id) {
        if (golem_runtime_cursor_parse((golem_string_view){id, strlen(id)}, &cursor) != GOLEM_OK) {
            evhttp_send_error(req, 400, "Invalid cursor");
            return;
        }
        after = &cursor;
    }
    golem_runtime_event record;
    golem_runtime_event_page page;
    golem_status st = golem_event_reader_read(b->reader, after, &record, 1, &page);
    if (st != GOLEM_OK) {
        evhttp_send_error(req, st == GOLEM_ERR_STALE_RESULT ? 410 : 409,
                          st == GOLEM_ERR_STALE_RESULT ? "Retention gap; explicit restart required"
                                                       : "Cursor conflict");
        return;
    }
    subscriber *s = NULL;
    for (size_t i = 0; i < SUBSCRIBERS; ++i)
        if (!b->clients[i].request) {
            s = &b->clients[i];
            break;
        }
    if (!s) {
        evhttp_send_error(req, 503, "Subscriber capacity");
        return;
    }
    s->request = req;
    s->has_cursor = after != NULL;
    if (after)
        s->cursor = *after;
    evhttp_connection_set_closecb(evhttp_request_get_connection(req), disconnected, s);
    struct evkeyvalq *out = evhttp_request_get_output_headers(req);
    evhttp_add_header(out, "Content-Type", "text/event-stream; charset=utf-8");
    evhttp_add_header(out, "Cache-Control", "no-store");
    evhttp_add_header(out, "X-Content-Type-Options", "nosniff");
    evhttp_add_header(out, "X-Accel-Buffering", "no");
    evhttp_send_reply_start(req, 200, "OK");
    static const char source[] =
        "retry: 1000\nevent: source\ndata: "
        "{\"durability\":\"admission-journal\",\"transient_worker_gap\":true}\n\n";
    if (!send_bytes(s, source, sizeof(source) - 1)) {
        drop(s);
        return;
    }
    pump(b, s);
}
static void stop(evutil_socket_t fd, short events, void *context)
{
    (void)fd;
    (void)events;
    event_base_loopbreak(context);
}
int main(int argc, char **argv)
{
    if (argc != 4) {
        fprintf(stderr, "usage: golem-events ABS_ADMISSION_DIR PRIVATE_TOKEN_FILE PORT\n");
        return 2;
    }
    char *end = NULL;
    long port = strtol(argv[3], &end, 10);
    if (!*argv[3] || *end || port < 0 || port > 65535)
        return 2;
    bridge b = {.credential_path = argv[2], .healthy = true};
    if (!credential(argv[2], b.bearer)) {
        fprintf(stderr, "invalid private credential file\n");
        return 1;
    }
    if (golem_event_reader_open(argv[1], NULL, &b.reader) != GOLEM_OK)
        return 1;
    struct rlimit limit;
    if (getrlimit(RLIMIT_NOFILE, &limit)) {
        golem_event_reader_close(b.reader);
        return 1;
    }
    if (limit.rlim_cur > 128)
        limit.rlim_cur = 128;
    if (setrlimit(RLIMIT_NOFILE, &limit)) {
        golem_event_reader_close(b.reader);
        return 1;
    }
    (void)signal(SIGPIPE, SIG_IGN);
    b.base = event_base_new();
    struct evhttp *http = b.base ? evhttp_new(b.base) : NULL;
    if (!http) {
        if (b.base)
            event_base_free(b.base);
        golem_event_reader_close(b.reader);
        return 1;
    }
    evhttp_set_max_headers_size(http, 4096);
    evhttp_set_max_body_size(http, 0);
    evhttp_set_timeout(http, 10);
    evhttp_set_gencb(http, request, &b);
    struct evhttp_bound_socket *bound =
        evhttp_bind_socket_with_handle(http, "127.0.0.1", (ev_uint16_t)port);
    struct sockaddr_in address;
    socklen_t length = sizeof(address);
    int rc = 1;
    struct event *timer = NULL, *term = NULL, *interrupt = NULL;
    if (!bound ||
        getsockname(evhttp_bound_socket_get_fd(bound), (struct sockaddr *)&address, &length))
        goto cleanup;
    snprintf(b.authority, sizeof(b.authority), "127.0.0.1:%u", (unsigned)ntohs(address.sin_port));
    timer = event_new(b.base, -1, EV_PERSIST, tick, &b);
    term = evsignal_new(b.base, SIGTERM, stop, b.base);
    interrupt = evsignal_new(b.base, SIGINT, stop, b.base);
    struct timeval interval = {0, 250000};
    if (!timer || !term || !interrupt || event_add(timer, &interval) || event_add(term, NULL) ||
        event_add(interrupt, NULL))
        goto cleanup;
    printf("http://%s/events\n", b.authority);
    fflush(stdout);
    rc = event_base_dispatch(b.base) < 0 ? 1 : 0;
cleanup:
    if (timer)
        event_free(timer);
    if (term)
        event_free(term);
    if (interrupt)
        event_free(interrupt);
    evhttp_free(http);
    event_base_free(b.base);
    golem_event_reader_close(b.reader);
    OPENSSL_cleanse(b.bearer, sizeof(b.bearer));
    return rc;
}
