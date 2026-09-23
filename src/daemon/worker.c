#define _POSIX_C_SOURCE 200809L
#include "golem/worker.h"
#include "events_internal.h"
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define WORKER_HOUR UINT64_C(3600000000000)
typedef struct worker_job {
    golem_worker_request request;
    char payload[GOLEM_WORKER_PAYLOAD_MAX];
    char *argv[GOLEM_WORKER_VECTOR_MAX + 1], *envp[GOLEM_WORKER_VECTOR_MAX + 1];
    size_t bytes;
    pthread_t thread;
    bool threaded, reserved, terminal_observed;
    golem_digest authority;
    golem_admission_token token;
    atomic_bool done, cancelled, expired;
    atomic_uint_fast64_t deadline;
    golem_worker_state state;
    golem_status status;
    golem_supervisor_observation observation;
    golem_supervisor_result result;
} worker_job;
struct golem_worker_pool {
    golem_allocator allocator;
    golem_worker_limits limits;
    pthread_t coordinator;
    pid_t owner;
    bool busy;
    uint64_t count, bytes;
    ge_ring events;
    uint64_t opened_ns;
    bool events_enabled, clock_known;
    worker_job jobs[GOLEM_WORKER_MAX_JOBS];
};

static golem_status now_ns(uint64_t *out)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) || t.tv_sec < 0)
        return GOLEM_ERR_IO;
    if ((uint64_t)t.tv_sec > (UINT64_MAX - (uint64_t)t.tv_nsec) / UINT64_C(1000000000))
        return GOLEM_ERR_OVERFLOW;
    *out = (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
    return GOLEM_OK;
}
static golem_status ready(golem_worker_pool *p)
{
    if (!p)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (p->owner != getpid() || !pthread_equal(p->coordinator, pthread_self()) || p->busy)
        return GOLEM_ERR_INVALID_STATE;
    return GOLEM_OK;
}
static void observe(golem_worker_pool *p, uint64_t id, golem_runtime_event_kind kind,
                    bool status_known, golem_status status)
{
    if (!p->events_enabled) return;
    golem_runtime_event e = {.kind = kind, .origin = GOLEM_EVENT_WORKER_OBSERVATION,
        .subject = id, .status_known = status_known, .status = status};
    uint64_t now;
    if (p->clock_known && now_ns(&now) == GOLEM_OK && now >= p->opened_ns) {
        e.elapsed_known = true;
        e.elapsed_ns = now - p->opened_ns;
    }
    ge_append(&p->events, e);
}
static void collect(golem_worker_pool *p);
static golem_status find(golem_worker_pool *p, uint64_t id, worker_job **out)
{
    golem_status s = ready(p);
    if (s != GOLEM_OK)
        return s;
    if (!id || id > p->count)
        return GOLEM_ERR_NOT_FOUND;
    *out = &p->jobs[id - 1];
    return GOLEM_OK;
}
golem_worker_options golem_worker_options_default(void)
{
    return (golem_worker_options){.size = sizeof(golem_worker_options),
                                  .version = GOLEM_WORKER_VERSION,
                                  .limits = {.worker_slots = 1,
                                             .io_slots = 1,
                                             .cpu_units = 1000,
                                             .memory_bytes = UINT64_C(1073741824),
                                             .queue_bytes = 1048576}};
}
golem_status golem_worker_open(const golem_worker_options *o, golem_worker_pool **out)
{
    if (!o || !out || o->size != sizeof(*o))
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (o->version != GOLEM_WORKER_VERSION)
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    const golem_worker_limits *l = &o->limits;
    if (!l->worker_slots || l->worker_slots > 32 || !l->io_slots || !l->cpu_units ||
        !l->memory_bytes || !l->queue_bytes || l->foreground_slots >= l->worker_slots ||
        l->queue_bytes > GOLEM_WORKER_MAX_JOBS * (uint64_t)GOLEM_WORKER_PAYLOAD_MAX)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status s = golem_allocator_validate(o->allocator);
    if (s != GOLEM_OK)
        return s;
    golem_allocator a = o->allocator ? *o->allocator : golem_allocator_default();
    golem_worker_pool *p;
    s = golem_allocator_alloc(&a, sizeof(*p), (void **)&p);
    if (s != GOLEM_OK)
        return s;
    /* Initialize only used jobs at submission; no multi-megabyte stack temporary. */
    p->allocator = a;
    p->limits = *l;
    p->coordinator = pthread_self();
    p->owner = getpid();
    p->busy = false;
    p->count = p->bytes = 0;
    p->events_enabled = ge_initialize(&p->events);
    p->clock_known = now_ns(&p->opened_ns) == GOLEM_OK;
    observe(p, 0, GOLEM_EVENT_INITIALIZED, false, GOLEM_OK);
    *out = p;
    return GOLEM_OK;
}
static golem_status copy_string(worker_job *j, const char *s, const char **out)
{
    if (!s)
        return GOLEM_ERR_INVALID_ARGUMENT;
    size_t left = sizeof(j->payload) - j->bytes;
    size_t n = strnlen(s, left);
    if (n == left)
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    char *dest = j->payload + j->bytes;
    memcpy(dest, s, n + 1);
    j->bytes += n + 1;
    *out = dest;
    return GOLEM_OK;
}
static golem_status copy_vector(worker_job *j, char *const *src, char **dest)
{
    if (!src)
        return GOLEM_ERR_INVALID_ARGUMENT;
    for (size_t i = 0; i <= GOLEM_WORKER_VECTOR_MAX; ++i) {
        if (!src[i]) {
            dest[i] = NULL;
            return GOLEM_OK;
        }
        if (i == GOLEM_WORKER_VECTOR_MAX)
            break;
        const char *s;
        golem_status status = copy_string(j, src[i], &s);
        if (status != GOLEM_OK)
            return status;
        dest[i] = (char *)s;
    }
    return GOLEM_ERR_BUFFER_TOO_SMALL;
}
golem_status golem_worker_submit(golem_worker_pool *p, const golem_worker_request *r, uint64_t *id)
{
    golem_status s = ready(p);
    if (s != GOLEM_OK)
        return s;
    if (!r || !id || !r->executable || r->executable[0] != '/' || !r->cwd || r->cwd[0] != '/' ||
        !r->argv || !r->argv[0] || !r->envp || !r->cpu_units || !r->memory_bytes || !r->io_slots ||
        !r->timeout_ns || r->timeout_ns > WORKER_HOUR || !r->lease_ns ||
        r->lease_ns > WORKER_HOUR || r->input.size > 16384 || (r->input.size && !r->input.data) ||
        (r->resource_class != GOLEM_WORKER_QA && r->resource_class != GOLEM_WORKER_BACKGROUND))
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->cpu_units > p->limits.cpu_units || r->memory_bytes > p->limits.memory_bytes ||
        r->io_slots > p->limits.io_slots)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    if (p->count == GOLEM_WORKER_MAX_JOBS)
        return GOLEM_ERR_QUEUE_FULL;
    worker_job *j = &p->jobs[p->count];
    j->request = *r;
    j->bytes = 0;
    s = copy_string(j, r->executable, &j->request.executable);
    if (s == GOLEM_OK)
        s = copy_string(j, r->cwd, &j->request.cwd);
    if (s == GOLEM_OK)
        s = copy_vector(j, r->argv, j->argv);
    if (s == GOLEM_OK)
        s = copy_vector(j, r->envp, j->envp);
    if (s != GOLEM_OK)
        return s;
    if (r->input.size > sizeof(j->payload) - j->bytes)
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    j->request.input.data = (const uint8_t *)(j->payload + j->bytes);
    if (r->input.size)
        memcpy(j->payload + j->bytes, r->input.data, r->input.size);
    j->bytes += r->input.size;
    if (j->bytes > p->limits.queue_bytes - p->bytes)
        return GOLEM_ERR_QUEUE_FULL;
    j->request.argv = j->argv;
    j->request.envp = j->envp;
    j->state = GOLEM_WORKER_QUEUED;
    j->status = GOLEM_OK;
    j->result = (golem_supervisor_result){.exit_code = -1};
    j->observation = (golem_supervisor_observation){0};
    j->threaded = j->reserved = j->terminal_observed = false;
    j->token = (golem_admission_token){0};
    atomic_init(&j->done, false);
    atomic_init(&j->cancelled, false);
    atomic_init(&j->expired, false);
    atomic_init(&j->deadline, 0);
    p->bytes += j->bytes;
    *id = ++p->count;
    observe(p, *id, GOLEM_EVENT_QUEUED, false, GOLEM_OK);
    return GOLEM_OK;
}
static golem_status pulse(void *context)
{
    worker_job *j = context;
    if (atomic_load(&j->cancelled))
        return GOLEM_ERR_INCOMPLETE_WORK;
    uint64_t now;
    golem_status s = now_ns(&now);
    if (s != GOLEM_OK)
        return s;
    if (now >= atomic_load(&j->deadline)) {
        atomic_store(&j->expired, true);
        return GOLEM_ERR_STALE_LEASE;
    }
    return GOLEM_OK;
}
static void *execute(void *context)
{
    worker_job *j = context;
    /* Cancel/lease may have changed while the supervisor thread was scheduled. */
    j->status = pulse(j);
    if (j->status == GOLEM_OK)
        j->status = golem_supervisor_run_observed(j->request.executable, j->argv, j->request.cwd,
                                                  j->envp, j->request.input, j->request.timeout_ns,
                                                  pulse, j, &j->result, &j->observation);
    atomic_store_explicit(&j->done, true, memory_order_release);
    return NULL;
}
static bool fits(golem_worker_pool *p, worker_job *target)
{
    uint64_t cpu = p->limits.cpu_units, memory = p->limits.memory_bytes;
    uint32_t io = p->limits.io_slots, slots = 0, background = 0;
    for (uint64_t i = 0; i < p->count; ++i) {
        worker_job *j = &p->jobs[i];
        if (!j->reserved)
            continue;
        ++slots;
        background += j->request.resource_class == GOLEM_WORKER_BACKGROUND;
        cpu -= j->request.cpu_units;
        memory -= j->request.memory_bytes;
        io -= j->request.io_slots;
    }
    return slots < p->limits.worker_slots && target->request.cpu_units <= cpu &&
           target->request.memory_bytes <= memory && target->request.io_slots <= io &&
           (target->request.resource_class != GOLEM_WORKER_BACKGROUND ||
            background < p->limits.worker_slots - p->limits.foreground_slots);
}
static golem_status
worker_start(golem_worker_pool *p, uint64_t id, golem_admission *a, const char *operation,
                   golem_status (*publish)(void *, const golem_digest *,
                                           const golem_admission_ticket *, golem_digest *),
                   void *context)
{
    worker_job *j;
    golem_status s = find(p, id, &j);
    if (s != GOLEM_OK)
        return s;
    if (!publish || !operation || !a)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->state != GOLEM_WORKER_QUEUED)
        return GOLEM_ERR_INVALID_STATE;
    if (!fits(p, j))
        return GOLEM_ERR_LEASE_BUSY;
    golem_admission_ticket t;
    s = golem_admission_lookup(a, operation, &t);
    if (s != GOLEM_OK)
        return s;
    if (t.state != GOLEM_ADMISSION_GRANTED || t.request.parent ||
        t.request.cpu_millis != j->request.cpu_units ||
        t.request.memory_bytes != j->request.memory_bytes ||
        t.request.foreground != (j->request.resource_class == GOLEM_WORKER_QA))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    golem_admission_checkpoint checkpoint;
    s = golem_admission_identity(a, &j->authority, &checkpoint);
    if (s != GOLEM_OK)
        return s;
    uint64_t now;
    s = now_ns(&now);
    if (s != GOLEM_OK)
        return s;
    if (now > UINT64_MAX - j->request.lease_ns)
        return GOLEM_ERR_OVERFLOW;
    p->busy = true;
    s = golem_admission_begin(a, t.token, publish, context, &t);
    p->busy = false;
    if (s != GOLEM_OK)
        return s;
    /* Lease duration includes publication; slow publication cannot extend it. */
    atomic_store(&j->deadline, now + j->request.lease_ns);
    j->token = t.token;
    j->reserved = true;
    j->state = GOLEM_WORKER_RUNNING;
    if (pthread_create(&j->thread, NULL, execute, j)) {
        j->status = GOLEM_ERR_IO;
        atomic_store(&j->done, true);
    } else {
        j->threaded = true;
    }
    return GOLEM_OK;
}
golem_status golem_worker_start(golem_worker_pool *p, uint64_t id, golem_admission *a,
    const char *operation, golem_status (*publish)(void *, const golem_digest *,
    const golem_admission_ticket *, golem_digest *), void *context)
{
    worker_job *j;
    golem_status s = find(p, id, &j);
    if (s != GOLEM_OK) return s;
    if (j->state != GOLEM_WORKER_QUEUED) return GOLEM_ERR_INVALID_STATE;
    collect(p);
    observe(p, id, GOLEM_EVENT_PREPARING, false, GOLEM_OK);
    s = worker_start(p, id, a, operation, publish, context);
    observe(p, id, s == GOLEM_OK && j->threaded ? GOLEM_EVENT_DISPATCHED :
        s == GOLEM_ERR_LEASE_BUSY ? GOLEM_EVENT_CAPACITY_BLOCKED : GOLEM_EVENT_PREPARATION_FAILED,
        s != GOLEM_OK || !j->threaded, s != GOLEM_OK ? s : j->threaded ? GOLEM_OK : j->status);
    collect(p);
    return s;
}
static golem_worker_state state(worker_job *j)
{
    if (j->state == GOLEM_WORKER_ACKNOWLEDGED || j->state == GOLEM_WORKER_QUEUED)
        return j->state;
    if (atomic_load_explicit(&j->done, memory_order_acquire))
        return j->observation.spawned && !j->observation.reaped ? GOLEM_WORKER_ATTENTION
                                                                : GOLEM_WORKER_FINISHED;
    return atomic_load(&j->cancelled) ? GOLEM_WORKER_CANCEL_REQUESTED : GOLEM_WORKER_RUNNING;
}
static void collect(golem_worker_pool *p)
{
    for (uint64_t i = 0; i < p->count; ++i) {
        worker_job *j = &p->jobs[i];
        golem_worker_state st = state(j);
        if (!j->terminal_observed && (st == GOLEM_WORKER_FINISHED || st == GOLEM_WORKER_ATTENTION)) {
            observe(p, i + 1, st == GOLEM_WORKER_ATTENTION ? GOLEM_EVENT_RECONCILE : GOLEM_EVENT_FINISHED,
                    true, j->status);
            j->terminal_observed = true;
        }
    }
}
golem_status golem_worker_events(golem_worker_pool *p, const golem_runtime_cursor *after,
    golem_runtime_event *records, size_t capacity, golem_runtime_event_page *page)
{
    golem_status s = ready(p);
    if (s != GOLEM_OK) return s;
    if (!p->events_enabled) return GOLEM_ERR_CRYPTO;
    collect(p);
    return ge_read(&p->events, after, records, capacity, page);
}
golem_status golem_worker_inspect(golem_worker_pool *p, uint64_t id, golem_worker_snapshot *out)
{
    worker_job *j;
    golem_status s = find(p, id, &j);
    if (s != GOLEM_OK)
        return s;
    if (!out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    collect(p);
    golem_worker_snapshot snapshot = {.state = state(j),
                                      .cancellation_requested = atomic_load(&j->cancelled),
                                      .lease_expired = atomic_load(&j->expired),
                                      .result = {.exit_code = -1}};
    if (snapshot.state == GOLEM_WORKER_FINISHED || snapshot.state == GOLEM_WORKER_ATTENTION ||
        snapshot.state == GOLEM_WORKER_ACKNOWLEDGED) {
        snapshot.status = j->status;
        snapshot.observation = j->observation;
        snapshot.result = j->result;
    }
    *out = snapshot;
    return GOLEM_OK;
}
golem_status golem_worker_cancel(golem_worker_pool *p, uint64_t id)
{
    worker_job *j;
    golem_status s = find(p, id, &j);
    if (s != GOLEM_OK)
        return s;
    if (state(j) == GOLEM_WORKER_ACKNOWLEDGED)
        return GOLEM_ERR_INVALID_STATE;
    collect(p);
    if (!atomic_exchange(&j->cancelled, true))
        observe(p, id, GOLEM_EVENT_CANCEL_REQUESTED, false, GOLEM_OK);
    if (j->state == GOLEM_WORKER_QUEUED) {
        j->status = GOLEM_ERR_INCOMPLETE_WORK;
        j->state = GOLEM_WORKER_FINISHED;
        atomic_store(&j->done, true);
    }
    return GOLEM_OK;
}
golem_status golem_worker_heartbeat(golem_worker_pool *p, uint64_t id, uint64_t duration)
{
    worker_job *j;
    golem_status s = find(p, id, &j);
    if (s != GOLEM_OK)
        return s;
    if (!duration || duration > WORKER_HOUR)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (state(j) != GOLEM_WORKER_RUNNING || atomic_load(&j->expired))
        return GOLEM_ERR_STALE_LEASE;
    uint64_t now;
    s = now_ns(&now);
    if (s != GOLEM_OK)
        return s;
    if (now >= atomic_load(&j->deadline))
        return GOLEM_ERR_STALE_LEASE;
    if (now > UINT64_MAX - duration)
        return GOLEM_ERR_OVERFLOW;
    atomic_store(&j->deadline, now + duration);
    return GOLEM_OK;
}
golem_status golem_worker_acknowledge(golem_worker_pool *p, uint64_t id, golem_admission *a,
                                      const char *operation)
{
    worker_job *j;
    golem_status s = find(p, id, &j);
    if (s != GOLEM_OK)
        return s;
    golem_worker_state st = state(j);
    if (st == GOLEM_WORKER_ACKNOWLEDGED)
        return GOLEM_OK;
    if (st != GOLEM_WORKER_FINISHED)
        return GOLEM_ERR_INVALID_STATE;
    if (j->token.ticket) {
        golem_digest authority;
        golem_admission_checkpoint checkpoint;
        golem_admission_ticket ticket;
        if (!a || !operation)
            return GOLEM_ERR_INVALID_ARGUMENT;
        s = golem_admission_identity(a, &authority, &checkpoint);
        if (s == GOLEM_OK)
            s = golem_admission_lookup(a, operation, &ticket);
        if (s != GOLEM_OK)
            return s;
        if (memcmp(&authority, &j->authority, sizeof(authority)) ||
            ticket.token.ticket != j->token.ticket || ticket.token.epoch != j->token.epoch ||
            memcmp(ticket.token.instance, j->token.instance, sizeof(j->token.instance)) ||
            memcmp(&ticket.token.boot, &j->token.boot, sizeof(j->token.boot)))
            return GOLEM_ERR_STALE_LEASE;
        if (ticket.state != GOLEM_ADMISSION_RELEASED)
            return GOLEM_ERR_INVALID_STATE;
    }
    j->reserved = false;
    collect(p);
    p->bytes -= j->bytes;
    j->state = GOLEM_WORKER_ACKNOWLEDGED;
    observe(p, id, GOLEM_EVENT_ACKNOWLEDGED, false, GOLEM_OK);
    return GOLEM_OK;
}
golem_status golem_worker_close(golem_worker_pool *p)
{
    if (!p)
        return GOLEM_OK;
    golem_status s = ready(p);
    if (s != GOLEM_OK)
        return s;
    for (uint64_t i = 0; i < p->count; ++i) {
        golem_worker_state st = state(&p->jobs[i]);
        if (st != GOLEM_WORKER_ACKNOWLEDGED && st != GOLEM_WORKER_ATTENTION &&
            st != GOLEM_WORKER_FINISHED)
            return GOLEM_ERR_INVALID_STATE;
    }
    for (uint64_t i = 0; i < p->count; ++i) {
        if (p->jobs[i].threaded) {
            if (pthread_join(p->jobs[i].thread, NULL))
                return GOLEM_ERR_IO;
            p->jobs[i].threaded = false;
        }
    }
    golem_allocator a = p->allocator;
    return golem_allocator_free(&a, p);
}
