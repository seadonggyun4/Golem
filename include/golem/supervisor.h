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
#ifdef __cplusplus
}
#endif
#endif
