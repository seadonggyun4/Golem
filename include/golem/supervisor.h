#ifndef GOLEM_SUPERVISOR_H
#define GOLEM_SUPERVISOR_H
#include "golem/types.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_SUPERVISOR_OUTPUT_MAX 16384u
typedef struct golem_supervisor_result {
    uint8_t output[GOLEM_SUPERVISOR_OUTPUT_MAX], error[GOLEM_SUPERVISOR_OUTPUT_MAX];
    size_t output_size, error_size;
    int exit_code, signal_number;
    bool timed_out;
} golem_supervisor_result;
/* POSIX synchronous process supervisor: absolute trusted executable, explicit
 * argv, no shell/PATH lookup. Borrows all inputs for call. timeout_ns positive,
 * <= one hour; input <=16 KiB. Owns/reaps child; process group killed on every
 * exit/error to stop ordinary descendants. Not a sandbox: setsid/remote children
 * can escape. Host must not reap this child or ignore SIGCHLD concurrently.
 * No global signal disposition changes. stdout/stderr independently bounded.
 * Optional pulse runs about every 20 ms for cancellation/lease heartbeat; any
 * non-OK aborts and reaps. Must return promptly, never longjmp or retain inputs.
 * Output is published once spawn succeeds, including partial logs on errors.
 * Pre-spawn errors preserve output. Exit !=0/signal -> INCOMPLETE_WORK; timeout
 * same status with timed_out=true. Truncation/overflow never accepted as success.
 * Caller persists result/logs; no automatic retry or acceptance attestation. */
golem_status golem_supervisor_run(const char *executable, char *const argv[], golem_bytes input,
    uint64_t timeout_ns, golem_status (*pulse)(void *context), void *context, golem_supervisor_result *out);
/* Explicit child-only cwd/environment; does not change process-global state.
 * cwd is absolute; envp must be a NULL-terminated, caller-owned allowlist.
 * Same lifetime, output and non-sandbox rules as run. macOS/Linux backend. */
golem_status golem_supervisor_run_at(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout_ns,
    golem_status (*pulse)(void *context), void *context, golem_supervisor_result *out);
/* Additive observation API; preserves the original result layout. Observations
 * describe the direct child only, never sandbox containment or descendant death.
 * Initialized even on pre-spawn errors; result retains the legacy contract. */
typedef struct golem_supervisor_observation {
    bool spawned, reaped;
} golem_supervisor_observation;
/* Borrowed byte chunks before bounded protocol buffering. stream=0 stdout,
 * stream=1 stderr. Callback must be bounded, nonblocking, non-reentrant; non-OK
 * aborts and reaps. Never persist raw chunks without an approved retention policy.
 * eof is an actual pipe EOF observation, not inferred from child exit. Counts
 * cover bytes read, not bytes the child may have produced beyond cancellation.
 * Additive API: existing result/observation layouts and limits are unchanged. */
typedef struct golem_supervisor_stream {
    size_t struct_size;
    uint32_t version;
    golem_status (*write)(void *context, unsigned stream, golem_bytes chunk);
    void *context;
} golem_supervisor_stream;
typedef struct golem_supervisor_capture {
    bool spawned, reaped, eof[2];
    uint64_t observed_bytes[2];
} golem_supervisor_capture;
golem_status golem_supervisor_run_streamed(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout_ns,
    golem_status (*pulse)(void *context), void *context, golem_supervisor_result *out,
    const golem_supervisor_stream *stream, golem_supervisor_capture *capture);
/* Bounded bulk observation, not an adapter protocol response. Does not buffer
 * stdout/stderr in result (sizes remain zero). Each stream has an explicit
 * byte limit, 1..64 MiB. Limit overflow aborts/reaps without delivering the
 * over-limit chunk. Caller must require OK and both EOFs before publishing any
 * derived result. Partial callback observations are not a successful artifact.
 * Same borrowed-input, cancellation, retention and non-sandbox rules as above. */
golem_status golem_supervisor_run_bulk(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout_ns,
    golem_status (*pulse)(void *context), void *context, golem_supervisor_result *out,
    const golem_supervisor_stream *stream, const uint64_t limits[2],
    golem_supervisor_capture *capture);
golem_status golem_supervisor_run_observed(const char *executable, char *const argv[],
    const char *cwd, char *const envp[], golem_bytes input, uint64_t timeout_ns,
    golem_status (*pulse)(void *context), void *context, golem_supervisor_result *out,
    golem_supervisor_observation *observation);
#ifdef __cplusplus
}
#endif
#endif
