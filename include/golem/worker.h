#ifndef GOLEM_WORKER_H
#define GOLEM_WORKER_H
#include "golem/admission.h"
#include "golem/supervisor.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_WORKER_VERSION 1u
#define GOLEM_WORKER_MAX_JOBS 64u
#define GOLEM_WORKER_PAYLOAD_MAX 32768u
#define GOLEM_WORKER_VECTOR_MAX 64u
typedef struct golem_worker_pool golem_worker_pool;
typedef enum golem_worker_class {
    GOLEM_WORKER_QA = 1,
    GOLEM_WORKER_BACKGROUND = 2
} golem_worker_class;
typedef enum golem_worker_state {
    GOLEM_WORKER_QUEUED = 1,
    GOLEM_WORKER_RUNNING,
    GOLEM_WORKER_CANCEL_REQUESTED,
    GOLEM_WORKER_FINISHED,
    GOLEM_WORKER_ATTENTION,
    GOLEM_WORKER_ACKNOWLEDGED
} golem_worker_state;
typedef struct golem_worker_limits {
    uint32_t worker_slots, io_slots, foreground_slots;
    uint64_t cpu_units, memory_bytes, queue_bytes;
} golem_worker_limits;
typedef struct golem_worker_options {
    size_t size;
    uint32_t version;
    golem_worker_limits limits;
    const golem_allocator *allocator;
} golem_worker_options;
typedef struct golem_worker_request {
    const char *executable, *cwd;
    char *const *argv;
    char *const *envp;
    golem_bytes input;
    uint64_t cpu_units, memory_bytes, timeout_ns, lease_ns;
    uint32_t io_slots;
    golem_worker_class resource_class;
} golem_worker_request;
typedef struct golem_worker_snapshot {
    golem_worker_state state;
    golem_status status;
    bool cancellation_requested, lease_expired;
    golem_supervisor_observation observation;
    golem_supervisor_result result;
} golem_worker_snapshot;
/* Opt-in process executor: one bounded supervisor thread per active job.
 * Default helper: one worker, no foreground reserve. Explicit zeros are invalid
 * for capacities/requests except foreground_slots and input.size. CPU/memory/IO
 * are reservations, NOT OS enforcement. Maximum 32 workers, 64 retained jobs.
 * foreground_slots reserves worker capacity from background, not OS CPU time.
 * Control APIs never wait for child termination or consume worker slots; they
 * are not wait-free/real-time guarantees. Admission disk commits may block.
 * Serialize all public calls on the creating thread/process. No fork reuse.
 * No Work store handle or caller callbacks enter supervisor threads. */
golem_worker_options golem_worker_options_default(void);
golem_status golem_worker_open(const golem_worker_options *options, golem_worker_pool **out);
/* Copies all request bytes. argv/envp <=64 strings each, total payload <=32KiB,
 * stdin <=16KiB. queue_bytes bounds outstanding (not acknowledged) payload.
 * Fixed storage for all 64 payloads/results remains allocated until close,
 * separately from this logical byte budget. OS thread stacks are additional.
 * Output unchanged on failure. IDs never reused during the pool lifetime. */
golem_status golem_worker_submit(golem_worker_pool *pool, const golem_worker_request *request,
                                 uint64_t *job);
/* Requires a GRANTED admission ticket; validates class/resources, then commits
 * admission_begin before launch. Existing RUNNING tickets cannot be redispatched.
 * Publisher must enforce current policy/lease and persist the Work binding; no
 * long-running execution inside it. Reentry is rejected. No shell/PATH lookup.
 * If begin fails, reconcile admission before retrying; a successful begin followed
 * by thread creation failure yields a FINISHED proven-nonexecution result. */
golem_status golem_worker_start(golem_worker_pool *pool, uint64_t job, golem_admission *admission,
                                const char *operation,
                                golem_status (*publish)(void *, const golem_digest *,
                                                        const golem_admission_ticket *,
                                                        golem_digest *),
                                void *context);
golem_status golem_worker_inspect(golem_worker_pool *pool, uint64_t job,
                                  golem_worker_snapshot *out);
golem_status golem_worker_cancel(golem_worker_pool *pool, uint64_t job);
/* Extend before expiry only. Host first renews actual lease; this local watchdog
 * is not a replacement for a durable lease. Duration positive <= one hour. */
golem_status golem_worker_heartbeat(golem_worker_pool *pool, uint64_t job, uint64_t lease_ns);
/* Host persists evidence, settles/releases admission, THEN acknowledges locally.
 * Rejects unobserved direct-child termination; no arbitrary force-release API.
 * ATTENTION needs external reconciliation, retained capacity until pool disposal
 * after all threads return. Reaping is not proof escaped descendants terminated. */
golem_status golem_worker_acknowledge(golem_worker_pool *pool, uint64_t job,
                                      golem_admission *admission, const char *operation);
/* Refuses queued/running jobs. Finished unacknowledged results may be discarded;
 * their durable admission reservations remain held for external reconciliation.
 * Joins only returned supervisors. Frees copied inputs/allocator.
 * Does not erase admission uncertainty or kill guessed/recycled PIDs. */
golem_status golem_worker_close(golem_worker_pool *pool);
#ifdef __cplusplus
}
#endif
#endif
