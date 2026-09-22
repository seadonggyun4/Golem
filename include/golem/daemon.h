#ifndef GOLEM_DAEMON_H
#define GOLEM_DAEMON_H

#include "golem/runtime.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_DAEMON_VERSION 1u
#define GOLEM_DAEMON_MAX_JOBS 256u
typedef struct golem_daemon golem_daemon;
typedef enum golem_daemon_state {
    GOLEM_DAEMON_READY, GOLEM_DAEMON_COMPLETE, GOLEM_DAEMON_ATTENTION, GOLEM_DAEMON_BUSY
} golem_daemon_state;
typedef struct golem_daemon_job {
    uint64_t ticket;
    char run_id[96];
    golem_daemon_state state;
    golem_status reason;
    golem_work_snapshot work;
} golem_daemon_job;
typedef struct golem_daemon_recovery_report {
    size_t jobs, repaired, ready, complete, attention, busy;
} golem_daemon_recovery_report;
/* Exclusive daemon-owner lock, no adapter callbacks or old lease restoration.
 * Validate immutable write-ahead frames and metadata before appending a missing
 * journal suffix (including an exact partial-frame prefix). Never truncate,
 * overwrite, invent results, or redispatch a RUNNING attempt. Repeated recovery
 * of an unchanged queue makes no writes. Per-job faults appear in report/inspect;
 * top-level errors preserve report but earlier repairs may have committed.
 * Legacy jobs without recovery metadata require manual reconciliation.
 * Trusted local filesystem only; CRC/digests are not authentication. */
golem_status golem_daemon_recover(const char *root, golem_daemon_recovery_report *out);
typedef struct golem_daemon_ops {
    /* Trusted local, synchronous executor. Same lifecycle/evidence contract as
     * runtime.execute. Directory is immutable borrowed storage for this call.
     * Supervisor may heartbeat runtime while polling. No daemon API reentry. */
    golem_status (*execute)(void *context, golem_runtime *runtime, golem_work_run *run,
        const char *job_directory, const golem_stage_snapshot *stage, uint64_t deadline_ns,
        golem_runtime_result *out);
} golem_daemon_ops;
/* POSIX local queue, one foreground owner using flock, one stage per tick in
 * ticket-order round robin. Existing absolute root, no symlink components.
 * Root/parents are trusted and must remain stable; not a hostile-user sandbox.
 * init is idempotent only on a valid v1 queue; no cleanup/truncation/overwrite.
 * Failed submissions can leave hidden unpublished directories for inspection.
 * Max 256 published jobs and 16 MiB journal/job. Completed jobs retained.
 * All data private (0700 directories, 0600 metadata). No remote resources/UI.
 * Inputs borrowed for call; open copies ops/path, borrows context until close.
 * Default heap ownership; close frees handle. Serialize calls; no callback free.
 * init/submit/inspect usable without daemon owner; queue publication is locked.
 * inspect does not execute or create files. Output count/array unchanged on error. */
golem_status golem_daemon_init(const char *root);
golem_status golem_daemon_submit(const char *root, const char *run_id, const golem_work_capsule *capsule,
    const golem_runtime_options *options, uint64_t *ticket);
golem_status golem_daemon_inspect(const char *root, golem_daemon_job *jobs, size_t capacity, size_t *count);
/* open performs the same callback-free recovery sweep while holding ownership.
 * A concurrent submission can delay startup by up to 100 ten-ms lock retries;
 * an already-owned daemon lock is never retried. */
golem_status golem_daemon_open(const char *root, const golem_daemon_ops *ops, void *context, golem_daemon **out);
/* worked=true means one job was attempted, including a policy/worker failure.
 * Per-job failures persist attention state; other jobs can continue. Failure to
 * persist quarantine stops this handle. Transient queue-lock contention returns
 * worked=false; a foreground caller should poll again. RUNNING after restart is
 * attention, never redispatch.
 * READY/FAILED recovery uses journal replay, fresh lease and original limits.
 * Completed journal is a host attestation, not independent business acceptance.
 * Host handles evidence verification; no generic provider/cost recovery claim. */
golem_status golem_daemon_tick(golem_daemon *daemon, bool *worked);
golem_status golem_daemon_close(golem_daemon *daemon);
#ifdef __cplusplus
}
#endif

#endif
