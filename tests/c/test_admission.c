#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "../../src/daemon/admission_internal.h"
#include "test.h"
#include <dirent.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static unsigned exploration_seed, exploration_depth;
static bool exploring;
static struct { uint64_t ticket; ga_operation operation; } exploration_trace[64];
static void print_exploration_trace(void)
{
    if (!exploring)
        return;
    fprintf(stderr, "admission model seed=%u depth=%u\n", exploration_seed, exploration_depth);
    for (unsigned i = 0; i < exploration_depth; ++i)
        fprintf(stderr, "ticket=%llu operation=%u\n",
                (unsigned long long)exploration_trace[i].ticket,
                (unsigned)exploration_trace[i].operation);
}

#undef CHECK
#define CHECK(condition)                                                                           \
    do {                                                                                           \
        if (!(condition)) {                                                                        \
            fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition);                        \
            print_exploration_trace();                                                             \
            exit(EXIT_FAILURE);                                                                    \
        }                                                                                          \
    } while (0)

typedef struct fixture {
    char root[128];
    golem_admission *a;
} fixture;
static golem_admission_options options(void)
{
    return (golem_admission_options){.size = sizeof(golem_admission_options),
                                     .version = GOLEM_ADMISSION_VERSION,
                                     .create = true,
                                     .limits = {2, 2000, 4096, 2}};
}
static fixture create(void)
{
    fixture f = {.root = "/private/tmp/golem-admission-XXXXXX"};
#ifndef __APPLE__
    (void)snprintf(f.root, sizeof(f.root), "/tmp/golem-admission-XXXXXX");
#endif
    CHECK(mkdtemp(f.root));
    golem_admission_options o = options();
    CHECK(golem_admission_open(f.root, &o, &f.a) == GOLEM_OK);
    return f;
}
static void cleanup(fixture *f)
{
    CHECK(golem_admission_close(f->a) == GOLEM_OK);
    f->a = NULL;
    DIR *d = opendir(f->root);
    CHECK(d);
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, ".."))
            continue;
        CHECK(unlinkat(dirfd(d), e->d_name, 0) == 0);
    }
    CHECK(closedir(d) == 0);
    CHECK(rmdir(f->root) == 0);
}
static golem_admission_request request(unsigned n, unsigned work, unsigned session, bool foreground)
{
    golem_admission_request r = {.runtime_binding = {{1}},
                                 .cpu_millis = 1000,
                                 .memory_bytes = 1024,
                                 .foreground = foreground};
    (void)snprintf(r.operation, sizeof(r.operation), "op-%u", n);
    (void)snprintf(r.work, sizeof(r.work), "work-%u", work);
    (void)snprintf(r.session, sizeof(r.session), "session-%u", session);
    return r;
}
static uint64_t submit(golem_admission *a, golem_admission_request r)
{
    uint64_t ticket;
    CHECK(golem_admission_enqueue(a, &r, &ticket) == GOLEM_OK);
    return ticket;
}
static golem_status publish(void *context, const golem_digest *id,
                            const golem_admission_ticket *ticket, golem_digest *out)
{
    unsigned *calls = context;
    CHECK(ga_nonzero(id, sizeof(*id)));
    CHECK(ticket->state == GOLEM_ADMISSION_GRANTED);
    ++*calls;
    *out = (golem_digest){{2}};
    return GOLEM_OK;
}
static golem_status execute(void *context, const golem_admission_ticket *ticket, golem_digest *out)
{
    unsigned *calls = context;
    CHECK(ticket->state == GOLEM_ADMISSION_RUNNING);
    CHECK(ga_nonzero(&ticket->binding_receipt, 32));
    ++*calls;
    *out = (golem_digest){{3}};
    return GOLEM_OK;
}
static const golem_admission_dispatch_ops ops = {publish, execute};
static void finish(golem_admission *a, golem_admission_ticket t)
{
    unsigned calls = 0;
    CHECK(golem_admission_dispatch(a, t.token, &ops, &calls) == GOLEM_OK);
    CHECK(calls == 2);
    CHECK(golem_admission_dispatch(a, t.token, &ops, &calls) == GOLEM_ERR_INVALID_STATE);
    CHECK(calls == 2);
}
static void basic(void)
{
    fixture f = create();
    golem_admission_request r = request(1, 1, 1, false);
    uint64_t unchanged = 77;
    r.cpu_millis = 2001;
    CHECK(golem_admission_enqueue(f.a, &r, &unchanged) == GOLEM_ERR_BUDGET_EXHAUSTED);
    r.cpu_millis = 1000;
    r.memory_bytes = 4097;
    CHECK(golem_admission_enqueue(f.a, &r, &unchanged) == GOLEM_ERR_BUDGET_EXHAUSTED);
    CHECK(unchanged == 77);
    r.memory_bytes = 1024;
    CHECK(submit(f.a, r) == 1);
    CHECK(submit(f.a, r) == 1);
    r.cpu_millis = 1;
    CHECK(golem_admission_enqueue(f.a, &r, &unchanged) == GOLEM_ERR_IDENTITY_MISMATCH);
    CHECK(unchanged == 77);
    CHECK(submit(f.a, request(2, 1, 2, false)) == 2);
    CHECK(submit(f.a, request(3, 2, 1, false)) == 3);
    golem_admission_ticket t;
    CHECK(golem_admission_grant(f.a, &t) == GOLEM_OK && t.token.ticket == 1);
    golem_admission_ticket sentinel = t;
    CHECK(golem_admission_grant(f.a, &t) == GOLEM_ERR_NOT_FOUND);
    CHECK(!memcmp(&sentinel, &t, sizeof(t)));
    CHECK(golem_admission_release(f.a, t.token) == GOLEM_ERR_INVALID_STATE);
    finish(f.a, t);
    golem_admission_checkpoint before, after;
    golem_digest id;
    CHECK(golem_admission_identity(f.a, &id, &before) == GOLEM_OK);
    CHECK(golem_admission_release(f.a, t.token) == GOLEM_OK);
    CHECK(golem_admission_settle(f.a, t.token, (golem_digest){{3}}) == GOLEM_OK);
    CHECK(golem_admission_settle(f.a, t.token, (golem_digest){{4}}) == GOLEM_ERR_IDENTITY_MISMATCH);
    CHECK(golem_admission_identity(f.a, &id, &after) == GOLEM_OK);
    CHECK(before.records == after.records);
    CHECK(golem_admission_grant(f.a, &t) == GOLEM_OK && t.token.ticket == 2);
    CHECK(golem_admission_cancel(f.a, t.token) == GOLEM_OK);
    CHECK(golem_admission_grant(f.a, &t) == GOLEM_OK && t.token.ticket == 3);
    cleanup(&f);
}
static void fairness(void)
{
    fixture f = create();
    CHECK(submit(f.a, request(1, 1, 1, false)) == 1);
    for (unsigned i = 2; i <= 6; ++i)
        (void)submit(f.a, request(i, i, i, true));
    golem_admission_ticket a, b, c;
    CHECK(golem_admission_grant(f.a, &a) == GOLEM_OK && a.token.ticket == 2);
    CHECK(golem_admission_grant(f.a, &b) == GOLEM_OK && b.token.ticket == 3);
    CHECK(golem_admission_grant(f.a, &c) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_admission_resize(f.a, (golem_admission_limits){1, 1000, 1024, 2}) == GOLEM_OK);
    finish(f.a, a);
    CHECK(golem_admission_grant(f.a, &c) == GOLEM_ERR_NOT_FOUND);
    finish(f.a, b);
    CHECK(golem_admission_grant(f.a, &c) == GOLEM_OK && c.token.ticket == 1);
    finish(f.a, c);
    CHECK(golem_admission_grant(f.a, &c) == GOLEM_OK && c.token.ticket == 4);
    CHECK(golem_admission_resize(f.a, (golem_admission_limits){32, UINT64_MAX, UINT64_MAX, 0}) ==
          GOLEM_OK);
    golem_admission_request huge = request(7, 7, 7, false);
    huge.cpu_millis = UINT64_MAX;
    huge.memory_bytes = UINT64_MAX;
    (void)submit(f.a, huge);
    CHECK(golem_admission_cancel(f.a, c.token) == GOLEM_OK);
    for (uint64_t i = 5; i <= 6; ++i) {
        CHECK(golem_admission_grant(f.a, &c) == GOLEM_OK && c.token.ticket == i);
        CHECK(golem_admission_cancel(f.a, c.token) == GOLEM_OK);
    }
    CHECK(golem_admission_grant(f.a, &c) == GOLEM_OK && c.token.ticket == 7);
    (void)submit(f.a, request(8, 8, 8, false));
    CHECK(golem_admission_grant(f.a, &a) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_admission_cancel(f.a, c.token) == GOLEM_OK);
    CHECK(golem_admission_grant(f.a, &a) == GOLEM_OK && a.token.ticket == 8);
    cleanup(&f);
}
static void nested(void)
{
    fixture f = create();
    CHECK(golem_admission_resize(f.a, (golem_admission_limits){1, 1000, 1024, 0}) == GOLEM_OK);
    (void)submit(f.a, request(1, 1, 1, false));
    golem_admission_ticket parent, child;
    CHECK(golem_admission_grant(f.a, &parent) == GOLEM_OK);
    golem_admission_request r = request(2, 1, 1, false);
    r.parent = 1;
    (void)submit(f.a, r);
    CHECK(golem_admission_cancel(f.a, parent.token) == GOLEM_ERR_INVALID_STATE);
    unsigned calls = 0;
    CHECK(golem_admission_dispatch(f.a, parent.token, &ops, &calls) == GOLEM_ERR_INVALID_STATE);
    CHECK(calls == 0);
    CHECK(golem_admission_grant(f.a, &child) == GOLEM_OK && child.token.ticket == 2);
    r = request(3, 1, 1, false);
    r.parent = 2;
    uint64_t out;
    CHECK(golem_admission_enqueue(f.a, &r, &out) == GOLEM_ERR_INVALID_STATE);
    r.parent = 1;
    r.cpu_millis = 1001;
    CHECK(golem_admission_enqueue(f.a, &r, &out) == GOLEM_ERR_INVALID_STATE);
    finish(f.a, child);
    CHECK(golem_admission_release(f.a, child.token) == GOLEM_OK);
    finish(f.a, parent);
    cleanup(&f);
}
static void capacity(void)
{
    fixture f = create();
    for (unsigned i = 1; i <= GOLEM_ADMISSION_MAX_TICKETS; ++i)
        CHECK(submit(f.a, request(i, i, i, false)) == i);
    golem_admission_request r = request(257, 257, 257, false);
    uint64_t out = 99;
    CHECK(golem_admission_enqueue(f.a, &r, &out) == GOLEM_ERR_QUEUE_FULL && out == 99);
    CHECK(submit(f.a, request(1, 1, 1, false)) == 1);
    r.operation[0] = '/';
    CHECK(golem_admission_enqueue(f.a, &r, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    cleanup(&f);
}

static ga_event event_for(const ga_model *m, uint64_t ticket, ga_operation operation)
{
    ga_event e = {.operation = operation, .ticket = ticket, .epoch = m->epoch};
    if (operation == GA_BIND || operation == GA_SETTLE)
        e.proof = (golem_digest){{7}};
    e.boot = m->boot;
    memcpy(e.nonce, m->instance, 16);
    return e;
}
static void invariant(const ga_model *m)
{
    uint64_t slots = 0, cpu = 0, memory = 0;
    for (uint64_t i = 0; i < m->count; ++i) {
        if (!ga_live(m->tickets[i].state))
            continue;
        ++slots;
        cpu += m->tickets[i].request.cpu_millis;
        memory += m->tickets[i].request.memory_bytes;
        for (uint64_t j = i + 1; j < m->count; ++j) {
            if (!ga_live(m->tickets[j].state))
                continue;
            CHECK(strcmp(m->tickets[i].request.session, m->tickets[j].request.session));
            CHECK(strcmp(m->tickets[i].request.work, m->tickets[j].request.work));
        }
    }
    CHECK(slots <= m->limits.slots && cpu <= m->limits.cpu_millis &&
          memory <= m->limits.memory_bytes);
}
static unsigned state_key(const ga_model *m)
{
    unsigned key = (unsigned)m->bypasses;
    for (unsigned i = 0; i < 3; ++i)
        key = key * 20 + (unsigned)m->tickets[i].state +
              (ga_nonzero(&m->tickets[i].binding_receipt, 32) ? 10u : 0u);
    return key;
}
static void explore_model(const ga_model *m, bool visited[32000], unsigned *states)
{
    unsigned key = state_key(m);
    CHECK(key < 32000);
    if (visited[key])
        return;
    visited[key] = true;
    ++*states;
    invariant(m);
    ga_model *next = malloc(sizeof(*next));
    CHECK(next);
    for (uint64_t i = 1; i <= 3; ++i) {
        const ga_operation choices[] = {GA_GRANT, GA_BIND, GA_START, GA_RUN,
                                        GA_CANCEL, GA_SETTLE, GA_RELEASE};
        for (size_t c = 0; c < sizeof(choices) / sizeof(choices[0]); ++c) {
            *next = *m;
            ga_event e = event_for(m, i, choices[c]);
            if (ga_apply(next, &e) != GOLEM_OK)
                continue;
            CHECK(exploration_depth < 64);
            exploration_trace[exploration_depth].ticket = i;
            exploration_trace[exploration_depth++].operation = choices[c];
            explore_model(next, visited, states);
            --exploration_depth;
        }
    }
    free(next);
}
static void explore(void)
{
    unsigned states = 0;
    for (unsigned assignments = 0; assignments < 64; ++assignments) {
        exploring = true;
        exploration_seed = assignments;
        exploration_depth = 0;
        ga_model *m = calloc(1, sizeof(*m));
        CHECK(m);
        ga_event init = {
            .operation = GA_INIT,
            .ticket = 2,
            .epoch = 2,
            .request = {.cpu_millis = 2000, .memory_bytes = 4096, .runtime_binding = {{1}}}};
        CHECK(ga_apply(m, &init) == GOLEM_OK);
        ga_event boot = {.operation = GA_BOOT, .epoch = 1, .nonce = {1}, .boot = {{1}}};
        CHECK(ga_apply(m, &boot) == GOLEM_OK);
        for (unsigned i = 0; i < 3; ++i) {
            ga_event e = {.operation = GA_ENQUEUE,
                          .ticket = i + 1,
                          .request = request(i + 1, (assignments >> (i + 3)) & 1,
                                             (assignments >> i) & 1, i != 0)};
            CHECK(ga_apply(m, &e) == GOLEM_OK);
        }
        bool visited[32000] = {false};
        explore_model(m, visited, &states);
        free(m);
    }
    exploring = false;
    CHECK(states > 1000);
    printf("bounded exploration: %u states across 64 lane assignments\n", states);
}

static void crash_boundary(unsigned boundary)
{
    fixture f = create();
    (void)submit(f.a, request(1, 1, 1, false));
    CHECK(golem_admission_close(f.a) == GOLEM_OK);
    f.a = NULL;
    pid_t pid = fork();
    CHECK(pid >= 0);
    if (pid == 0) {
        golem_admission_options o = options();
        CHECK(golem_admission_open(f.root, &o, &f.a) == GOLEM_OK);
        golem_admission_ticket t;
        CHECK(golem_admission_grant(f.a, &t) == GOLEM_OK);
        const ga_operation steps[] = {GA_BIND, GA_START, GA_RUN, GA_SETTLE, GA_RELEASE};
        for (unsigned i = 0; i < boundary; ++i) {
            ga_event e = event_for(&f.a->model, 1, steps[i]);
            CHECK(ga_commit(f.a, &e) == GOLEM_OK);
        }
        CHECK(kill(getpid(), SIGKILL) == 0);
        _exit(9);
    }
    int status;
    CHECK(waitpid(pid, &status, 0) == pid);
    CHECK(WIFSIGNALED(status) && WTERMSIG(status) == SIGKILL);
    golem_admission_options o = options();
    CHECK(golem_admission_open(f.root, &o, &f.a) == GOLEM_OK);
    golem_admission_ticket t;
    CHECK(golem_admission_lookup(f.a, "op-1", &t) == GOLEM_OK);
    golem_admission_state expected = boundary < 2    ? GOLEM_ADMISSION_CANCELLED
                                     : boundary < 4  ? GOLEM_ADMISSION_RECONCILE_REQUIRED
                                     : boundary == 4 ? GOLEM_ADMISSION_SETTLING
                                                     : GOLEM_ADMISSION_RELEASED;
    CHECK(t.state == expected);
    golem_admission_token stale = t.token;
    --stale.epoch;
    CHECK(golem_admission_release(f.a, stale) == GOLEM_ERR_STALE_LEASE);
    unsigned calls = 0;
    CHECK(golem_admission_dispatch(f.a, t.token, &ops, &calls) == GOLEM_ERR_INVALID_STATE &&
          !calls);
    if (expected == GOLEM_ADMISSION_RECONCILE_REQUIRED) {
        CHECK(golem_admission_release(f.a, t.token) == GOLEM_ERR_INVALID_STATE);
        CHECK(golem_admission_settle(f.a, t.token, (golem_digest){{7}}) == GOLEM_OK);
    }
    if (boundary >= 2)
        CHECK(golem_admission_release(f.a, t.token) == GOLEM_OK);
    CHECK(golem_admission_close(f.a) == GOLEM_OK);
    f.a = NULL;
    CHECK(golem_admission_open(f.root, &o, &f.a) == GOLEM_OK);
    CHECK(golem_admission_lookup(f.a, "op-1", &t) == GOLEM_OK);
    CHECK(t.state == (boundary < 2 ? GOLEM_ADMISSION_CANCELLED : GOLEM_ADMISSION_RELEASED));
    cleanup(&f);
}
static void recovery(void)
{
    for (unsigned i = 0; i <= 5; ++i)
        crash_boundary(i);
    fixture f = create();
    (void)submit(f.a, request(1, 1, 1, false));
    golem_admission_ticket p, c;
    CHECK(golem_admission_grant(f.a, &p) == GOLEM_OK);
    golem_admission_request r = request(2, 1, 1, false);
    r.parent = 1;
    (void)submit(f.a, r);
    CHECK(golem_admission_grant(f.a, &c) == GOLEM_OK);
    ga_event e = event_for(&f.a->model, 2, GA_BIND);
    CHECK(ga_commit(f.a, &e) == GOLEM_OK);
    e.operation = GA_START;
    e.proof = (golem_digest){0};
    CHECK(ga_commit(f.a, &e) == GOLEM_OK);
    CHECK(golem_admission_close(f.a) == GOLEM_OK);
    f.a = NULL;
    golem_admission_options o = options();
    CHECK(golem_admission_open(f.root, &o, &f.a) == GOLEM_OK);
    CHECK(golem_admission_lookup(f.a, "op-1", &p) == GOLEM_OK &&
          p.state == GOLEM_ADMISSION_RECONCILE_REQUIRED);
    CHECK(golem_admission_lookup(f.a, "op-2", &c) == GOLEM_OK &&
          c.state == GOLEM_ADMISSION_RECONCILE_REQUIRED);
    CHECK(golem_admission_settle(f.a, p.token, (golem_digest){{7}}) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_admission_settle(f.a, c.token, (golem_digest){{7}}) == GOLEM_OK);
    CHECK(golem_admission_release(f.a, c.token) == GOLEM_OK);
    CHECK(golem_admission_settle(f.a, p.token, (golem_digest){{7}}) == GOLEM_OK);
    CHECK(golem_admission_release(f.a, p.token) == GOLEM_OK);
    cleanup(&f);
}
static void identity(void)
{
    fixture f = create(), other = create();
    golem_digest id, id2;
    golem_admission_checkpoint cp, cp2;
    CHECK(golem_admission_identity(f.a, &id, &cp) == GOLEM_OK);
    CHECK(golem_admission_identity(other.a, &id2, &cp2) == GOLEM_OK && memcmp(&id, &id2, 32));
    golem_admission_options o = options();
    golem_admission *a = NULL;
    CHECK(golem_admission_open(f.root, &o, &a) == GOLEM_ERR_JOURNAL_BUSY && a == NULL);
    char alias[160];
    (void)snprintf(alias, sizeof(alias), "%s-alias", f.root);
    CHECK(symlink(f.root, alias) == 0);
    CHECK(golem_admission_open(alias, &o, &a) == GOLEM_ERR_IO);
    CHECK(unlink(alias) == 0);
    CHECK(golem_admission_close(f.a) == GOLEM_OK);
    f.a = NULL;
    CHECK(rename(f.root, alias) == 0);
    CHECK(strlen(alias) < sizeof(f.root));
    (void)strcpy(f.root, alias);
    o.expected = &cp;
    CHECK(golem_admission_open(f.root, &o, &f.a) == GOLEM_OK);
    CHECK(golem_admission_identity(f.a, &id2, &cp2) == GOLEM_OK && !memcmp(&id, &id2, 32));
    pid_t pid = fork();
    CHECK(pid >= 0);
    if (pid == 0) {
        CHECK(golem_admission_resize(f.a, o.limits) == GOLEM_ERR_INVALID_STATE);
        _exit(0);
    }
    int status;
    CHECK(waitpid(pid, &status, 0) == pid && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    cleanup(&f);
    cleanup(&other);
}
static void corruption(void)
{
    for (unsigned mode = 0; mode < 4; ++mode) {
        fixture f = create();
        (void)submit(f.a, request(1, 1, 1, false));
        golem_digest id;
        golem_admission_checkpoint cp;
        CHECK(golem_admission_identity(f.a, &id, &cp) == GOLEM_OK);
        CHECK(golem_admission_close(f.a) == GOLEM_OK);
        f.a = NULL;
        char path[256];
        (void)snprintf(path, sizeof(path), "%s/%020u", f.root, mode == 1 ? 2 : 3);
        if (mode == 1 || mode == 2)
            CHECK(unlink(path) == 0);
        else {
            int fd = open(path, O_WRONLY);
            CHECK(fd >= 0);
            if (mode == 0) {
                uint8_t b = 99;
                CHECK(pwrite(fd, &b, 1, 100) == 1);
            } else
                CHECK(ftruncate(fd, 200) == 0);
            CHECK(close(fd) == 0);
        }
        golem_admission_options o = options();
        o.expected = &cp;
        CHECK(golem_admission_open(f.root, &o, &f.a) != GOLEM_OK && f.a == NULL);
        cleanup(&f);
    }
    ga_event e = {.operation = GA_BOOT, .epoch = 1, .nonce = {1}, .boot = {{1}}}, decoded;
    uint8_t frame[GA_FRAME_SIZE];
    golem_admission_checkpoint cp = {0};
    CHECK(ga_encode(&e, cp, frame) == GOLEM_OK);
    const char golden[] = "f78d3aba68e3c5181f4cbb0245269bb571cc83c3aa3d5ee36d119993a232ed12";
    golem_digest expected;
    CHECK(golem_digest_parse((golem_string_view){golden, 64}, &expected) == GOLEM_OK);
    CHECK(!memcmp(frame + 480, expected.bytes, 32));
    CHECK(ga_decode(frame, cp, &decoded) == GOLEM_OK);
    for (size_t i = 0; i < sizeof(frame); ++i) {
        frame[i] ^= 1;
        CHECK(ga_decode(frame, cp, &decoded) != GOLEM_OK);
        frame[i] ^= 1;
    }
}
typedef struct tracked_allocator {
    unsigned live, calls;
    bool fail;
} tracked_allocator;
static void *tracked_allocate(void *context, size_t size)
{
    tracked_allocator *t = context;
    ++t->calls;
    if (t->fail)
        return NULL;
    void *p = malloc(size);
    if (p)
        ++t->live;
    return p;
}
static void tracked_free(void *context, void *pointer)
{
    tracked_allocator *t = context;
    CHECK(t->live);
    --t->live;
    free(pointer);
}
static void ownership(void)
{
    fixture f = create();
    CHECK(golem_admission_close(f.a) == GOLEM_OK);
    f.a = NULL;
    tracked_allocator tracked = {.fail = true};
    golem_allocator allocator = {&tracked, tracked_allocate, tracked_free};
    golem_admission_options o = options();
    o.allocator = &allocator;
    CHECK(golem_admission_open(f.root, &o, &f.a) == GOLEM_ERR_OUT_OF_MEMORY && f.a == NULL);
    CHECK(tracked.live == 0);
    tracked.fail = false;
    CHECK(golem_admission_open(f.root, &o, &f.a) == GOLEM_OK && tracked.live == 1);
    allocator = (golem_allocator){0}; /* Handle has copied callbacks, not the descriptor. */
    cleanup(&f);
    CHECK(tracked.live == 0 && tracked.calls == 2);
}
typedef struct reentrant {
    golem_admission *a;
    unsigned executes;
    bool zero, fail;
} reentrant;
static golem_status guarded_publish(void *context, const golem_digest *id,
                                    const golem_admission_ticket *ticket, golem_digest *out)
{
    reentrant *r = context;
    (void)id;
    CHECK(golem_admission_cancel(r->a, ticket->token) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_admission_close(r->a) == GOLEM_ERR_INVALID_STATE);
    if (r->fail)
        return GOLEM_ERR_IO;
    *out = (golem_digest){{0}};
    if (!r->zero)
        out->bytes[0] = 1;
    return GOLEM_OK;
}
static golem_status uncertain_execute(void *context, const golem_admission_ticket *ticket,
                                      golem_digest *out)
{
    reentrant *r = context;
    (void)ticket;
    (void)out;
    ++r->executes;
    return GOLEM_ERR_IO;
}
static void guards(void)
{
    fixture f = create();
    (void)submit(f.a, request(1, 1, 1, false));
    golem_admission_ticket t;
    CHECK(golem_admission_grant(f.a, &t) == GOLEM_OK);
    const golem_admission_dispatch_ops guarded = {guarded_publish, uncertain_execute};
    golem_admission_token stale = t.token;
    stale.instance[0] ^= 1;
    CHECK(golem_admission_cancel(f.a, stale) == GOLEM_ERR_STALE_LEASE);
    stale = t.token;
    stale.boot.bytes[0] ^= 1;
    CHECK(golem_admission_release(f.a, stale) == GOLEM_ERR_STALE_LEASE);
    reentrant r = {.a = f.a, .zero = true};
    CHECK(golem_admission_dispatch(f.a, t.token, &guarded, &r) == GOLEM_ERR_INVALID_STATE);
    r.zero = false;
    r.fail = true;
    CHECK(golem_admission_dispatch(f.a, t.token, &guarded, &r) == GOLEM_ERR_IO);
    CHECK(r.executes == 0);
    r.fail = false;
    CHECK(golem_admission_dispatch(f.a, t.token, &guarded, &r) == GOLEM_ERR_IO);
    CHECK(r.executes == 1);
    CHECK(golem_admission_dispatch(f.a, t.token, &guarded, &r) == GOLEM_ERR_INVALID_STATE);
    CHECK(r.executes == 1);
    CHECK(golem_admission_cancel(f.a, t.token) == GOLEM_OK);
    CHECK(golem_admission_lookup(f.a, "op-1", &t) == GOLEM_OK &&
          t.state == GOLEM_ADMISSION_CANCEL_REQUESTED);
    CHECK(golem_admission_release(f.a, t.token) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_admission_settle(f.a, t.token, (golem_digest){{5}}) == GOLEM_OK);
    CHECK(golem_admission_release(f.a, t.token) == GOLEM_OK);
    cleanup(&f);
}
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    if (!strcmp(argv[1], "basic"))
        basic();
    else if (!strcmp(argv[1], "fairness"))
        fairness();
    else if (!strcmp(argv[1], "nested"))
        nested();
    else if (!strcmp(argv[1], "capacity"))
        capacity();
    else if (!strcmp(argv[1], "explore"))
        explore();
    else if (!strcmp(argv[1], "recovery"))
        recovery();
    else if (!strcmp(argv[1], "identity"))
        identity();
    else if (!strcmp(argv[1], "corruption"))
        corruption();
    else if (!strcmp(argv[1], "ownership"))
        ownership();
    else if (!strcmp(argv[1], "guards"))
        guards();
    else
        CHECK(false);
    return 0;
}
