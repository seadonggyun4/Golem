#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/runtime_event.h"
#include "golem/worker.h"
#include "../../src/daemon/events_internal.h"
#include "test.h"
#include <dirent.h>
#include <string.h>
#include <unistd.h>

static int ring_test(void)
{
    ge_ring ring = {.stream = {{1}}};
    golem_runtime_event records[64], untouched = {.subject = 999};
    golem_runtime_event_page page;
    ge_append(&ring, (golem_runtime_event){.kind = GOLEM_EVENT_QUEUED});
    CHECK(ge_read(&ring, NULL, records, 1, &page) == GOLEM_OK && page.count == 1);
    golem_runtime_cursor old = page.next;
    for (size_t i = 0; i < 300; ++i)
        ge_append(&ring, (golem_runtime_event){.kind = GOLEM_EVENT_PREPARING});
    records[0] = untouched;
    CHECK(ge_read(&ring, &old, records, 64, &page) == GOLEM_ERR_STALE_RESULT);
    CHECK(records[0].subject == 999 && page.dropped == 45 && page.missed == 44 && !page.count);
    CHECK(ge_read(&ring, NULL, records, 64, &page) == GOLEM_OK && page.count == 64);
    CHECK(records[0].cursor.sequence == 46);
    golem_runtime_cursor next = page.next;
    CHECK(ge_read(&ring, &next, records, 64, &page) == GOLEM_OK);
    CHECK(records[0].cursor.sequence == next.sequence + 1);
    next.stream.bytes[0] ^= 1;
    CHECK(ge_read(&ring, &next, records, 64, &page) == GOLEM_ERR_INVALID_ARGUMENT);
    next = page.next;
    next.sequence = UINT64_MAX;
    CHECK(ge_read(&ring, &next, records, 64, &page) == GOLEM_ERR_INVALID_ARGUMENT);
    next = page.next;
    next.anchor.bytes[0] = 1;
    CHECK(ge_read(&ring, &next, records, 64, &page) == GOLEM_ERR_REPLAY_MISMATCH);
    CHECK(ge_read(&ring, NULL, records, 0, &page) == GOLEM_ERR_INVALID_ARGUMENT);
    ring.sequence = UINT64_MAX;
    ge_append(&ring, (golem_runtime_event){0});
    CHECK(ring.sequence == UINT64_MAX);
    return 0;
}
static int codec_test(void)
{
    golem_runtime_cursor c = {.stream = {{1}}, .sequence = UINT64_MAX, .anchor = {{2}}}, parsed;
    char text[GOLEM_RUNTIME_CURSOR_MAX], tiny = 'x';
    size_t n = 0;
    CHECK(golem_runtime_cursor_format(&c, &tiny, 1, &n) == GOLEM_ERR_BUFFER_TOO_SMALL &&
          tiny == 'x');
    CHECK(golem_runtime_cursor_format(&c, text, sizeof(text), &n) == GOLEM_OK);
    CHECK(golem_runtime_cursor_parse((golem_string_view){text, n}, &parsed) == GOLEM_OK);
    CHECK(parsed.sequence == UINT64_MAX && !memcmp(&parsed.stream, &c.stream, 32));
    text[0] = '2';
    CHECK(golem_runtime_cursor_parse((golem_string_view){text, n}, &parsed) != GOLEM_OK);
    text[0] = '1';
    text[67] = '9';
    CHECK(golem_runtime_cursor_parse((golem_string_view){text, n}, &parsed) != GOLEM_OK);
    CHECK(golem_runtime_event_name((golem_runtime_event_kind)999) == NULL);
    return 0;
}
static void *oom(void *ctx, size_t n)
{
    (void)ctx;
    (void)n;
    return NULL;
}
static void nofree(void *ctx, void *p)
{
    (void)ctx;
    (void)p;
}
static int durable_test(const char *root)
{
    golem_admission_options o = {
        .size = sizeof(o), .version = 1, .create = true, .limits = {1, 1000, 1024, 0}};
    golem_admission *a = NULL;
    CHECK(golem_admission_open(root, &o, &a) == GOLEM_OK);
    golem_runtime_event records[64];
    golem_runtime_event_page page;
    CHECK(golem_admission_events(a, NULL, records, 64, &page) == GOLEM_OK && page.count == 2);
    CHECK(records[0].kind == GOLEM_EVENT_INITIALIZED && records[1].kind == GOLEM_EVENT_RECOVERY);
    golem_runtime_cursor before = page.next;
    golem_admission_request req = {.operation = "secret-operation",
                                   .work = "secret-work",
                                   .session = "secret-session",
                                   .cpu_millis = 1,
                                   .memory_bytes = 1,
                                   .runtime_binding = {{1}}};
    uint64_t id;
    CHECK(golem_admission_enqueue(a, &req, &id) == GOLEM_OK);
    golem_admission_ticket t;
    CHECK(golem_admission_grant(a, &t) == GOLEM_OK);
    CHECK(golem_admission_cancel(a, t.token) == GOLEM_OK);
    golem_digest ns;
    golem_admission_checkpoint first, last;
    CHECK(golem_admission_identity(a, &ns, &first) == GOLEM_OK);
    CHECK(golem_runtime_events_snapshot(root, NULL, &before, records, 64, &page) == GOLEM_OK);
    CHECK(page.count == 3 && records[0].kind == GOLEM_EVENT_QUEUED &&
          records[1].kind == GOLEM_EVENT_ADMITTED);
    CHECK(records[2].kind == GOLEM_EVENT_CANCEL_REQUESTED && !records[2].elapsed_known &&
          !records[2].status_known);
    CHECK(golem_admission_identity(a, &ns, &last) == GOLEM_OK && first.records == last.records);
    golem_allocator fail = {NULL, oom, nofree};
    CHECK(golem_runtime_events_snapshot(root, &fail, NULL, records, 64, &page) ==
          GOLEM_ERR_OUT_OF_MEMORY);
    for (int format = 1; format <= 3; ++format) {
        size_t n;
        char tiny = 'z';
        CHECK(golem_runtime_events_export(records, &page, (golem_runtime_event_format)format, &tiny,
                                          1, &n) == GOLEM_ERR_BUFFER_TOO_SMALL);
        CHECK(tiny == 'z');
        char *bytes = malloc(n + 1);
        CHECK(bytes);
        CHECK(golem_runtime_events_export(records, &page, (golem_runtime_event_format)format, bytes,
                                          n, &n) == GOLEM_OK);
        bytes[n] = 0;
        CHECK(strstr(bytes, "DERIVED_ONLY") && !strstr(bytes, "secret-") &&
              !strstr(bytes, "timeUnixNano"));
        free(bytes);
    }
    golem_runtime_cursor retained = page.next;
    CHECK(golem_admission_close(a) == GOLEM_OK);
    o.create = false;
    CHECK(golem_admission_open(root, &o, &a) == GOLEM_OK);
    CHECK(golem_admission_events(a, &retained, records, 64, &page) == GOLEM_OK && page.count == 1);
    CHECK(records[0].kind == GOLEM_EVENT_RECOVERY);
    CHECK(golem_admission_close(a) == GOLEM_OK);
    return 0;
}
static int worker_test(void)
{
    golem_worker_options options = golem_worker_options_default();
    golem_worker_pool *p = NULL, *other = NULL;
    CHECK(golem_worker_open(&options, &p) == GOLEM_OK);
    CHECK(golem_worker_open(&options, &other) == GOLEM_OK);
    char *args[] = {"/usr/bin/true", "secret-argument", NULL}, *env[] = {"SECRET=hidden", NULL};
    golem_worker_request r = {.executable = args[0],
                              .cwd = "/",
                              .argv = args,
                              .envp = env,
                              .cpu_units = 1,
                              .memory_bytes = 1,
                              .timeout_ns = 1000000000,
                              .lease_ns = 1000000000,
                              .io_slots = 1,
                              .resource_class = GOLEM_WORKER_QA};
    uint64_t id;
    CHECK(golem_worker_submit(p, &r, &id) == GOLEM_OK);
    golem_runtime_event events[64];
    golem_runtime_event_page page;
    CHECK(golem_worker_events(p, NULL, events, 64, &page) == GOLEM_OK && page.count == 2);
    golem_runtime_cursor cursor = page.next;
    CHECK(golem_worker_events(other, &cursor, events, 64, &page) == GOLEM_ERR_INVALID_ARGUMENT);
    for (size_t i = 0; i < 200; ++i)
        CHECK(golem_worker_start(p, id, NULL, NULL, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_worker_events(p, &cursor, events, 64, &page) == GOLEM_ERR_STALE_RESULT);
    golem_worker_snapshot snapshot;
    CHECK(golem_worker_inspect(p, id, &snapshot) == GOLEM_OK &&
          snapshot.state == GOLEM_WORKER_QUEUED);
    CHECK(golem_worker_cancel(p, id) == GOLEM_OK);
    CHECK(golem_worker_acknowledge(p, id, NULL, NULL) == GOLEM_OK);
    CHECK(golem_worker_events(p, NULL, events, 64, &page) == GOLEM_OK);
    bool cancelled = false, finished = false, ack = false;
    do {
        for (size_t i = 0; i < page.count; ++i) {
            cancelled |= events[i].kind == GOLEM_EVENT_CANCEL_REQUESTED;
            finished |= events[i].kind == GOLEM_EVENT_FINISHED;
            ack |= events[i].kind == GOLEM_EVENT_ACKNOWLEDGED;
        }
        cursor = page.next;
        CHECK(golem_worker_events(p, &cursor, events, 64, &page) == GOLEM_OK);
    } while (page.count);
    CHECK(cancelled && finished && ack);
    CHECK(golem_worker_close(p) == GOLEM_OK && golem_worker_close(other) == GOLEM_OK);
    return 0;
}
int main(int argc, char **argv)
{
    CHECK(argc >= 2);
    if (argc == 3 && !strcmp(argv[1], "fill")) {
        golem_admission_options o = {.size = sizeof(o), .version = 1};
        golem_admission *a = NULL;
        CHECK(golem_admission_open(argv[2], &o, &a) == GOLEM_OK);
        for (size_t i = 0; i < 260; ++i)
            CHECK(golem_admission_resize(a, (golem_admission_limits){1, 1000, 1024, 0}) == GOLEM_OK);
        CHECK(golem_admission_close(a) == GOLEM_OK);
        return 0;
    }
    if (!strcmp(argv[1], "ring"))
        return ring_test();
    if (!strcmp(argv[1], "codec"))
        return codec_test();
    if (!strcmp(argv[1], "worker"))
        return worker_test();
    if (argc == 3 && !strcmp(argv[1], "fixture"))
        return durable_test(argv[2]);
    CHECK(!strcmp(argv[1], "durable"));
    char root[] = "/tmp/golem-events-XXXXXX", real[4096];
    CHECK(mkdtemp(root) && realpath(root, real));
    CHECK(durable_test(real) == 0);
    DIR *dir = opendir(real);
    CHECK(dir);
    struct dirent *entry;
    while ((entry = readdir(dir))) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."))
            continue;
        CHECK(unlinkat(dirfd(dir), entry->d_name, 0) == 0);
    }
    CHECK(closedir(dir) == 0 && rmdir(real) == 0);
    return 0;
}
