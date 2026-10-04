#ifndef GOLEM_RECORD_H
#define GOLEM_RECORD_H
#include "golem/types.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct golem_record golem_record;
typedef struct golem_record_options {
    size_t struct_size;
    uint32_t version;
    const char *root; /* Existing private absolute directory; NULL uses GOLEM_RECORD_ROOT. */
    const char *kind;
    const char *operation;
    const char *executable; /* Optional absolute regular file, hashed before/after. */
    const char *cwd;
    char *const *argv;
    const char *source_manifest; /* Optional existing source identity artifact, hashed, not trusted. */
} golem_record_options;
typedef struct golem_record_result {
    size_t struct_size;
    uint32_t version;
    golem_status operation_status;
    int exit_code, signal_number; /* -1/0 when not a process outcome. */
    bool spawned, reaped, timed_out, eof[2];
} golem_record_result;
/* Additive recording scope. NULL/empty environment root disables recording (OK,
 * *out=NULL). Explicit root must be nonempty. An enabled scope writes durable
 * intent before returning; failure forbids dispatch. Finish consumes the scope,
 * returns recording status separately from operation status; never retry effects.
 * Invalid finish arguments/order leave the scope open for correction.
 * Scopes nest LIFO on their creating thread. No concurrent use, longjmp, or fork
 * across active scopes. Host must keep environment/cwd stable during calls.
 * Private unsigned observations, not authorization or complete descendant tracing.
 * No environment values/input bodies captured. argv/logs may contain secrets.
 * Missing result.json means incomplete/uncertain, never success. */
golem_status golem_record_begin(const golem_record_options *options, golem_record **out);
golem_status golem_record_write(golem_record *record, unsigned stream, golem_bytes bytes);
golem_status golem_record_finish(golem_record *record, const golem_record_result *result);
/* Synchronous host boundary for any C API operation. Does not invoke callback if
 * intent recording fails. Returns recording status; callback status is published
 * through operation_status even when final recording fails. The callback must
 * close any scopes it creates before returning. No scope is enabled
 * implicitly when neither options.root nor GOLEM_RECORD_ROOT is configured. */
golem_status golem_record_call(const golem_record_options *options,
    golem_status (*operation)(void *), void *context, golem_status *operation_status);
typedef struct golem_record_api_outcome {
    size_t struct_size;
    uint32_t version;
    const char *operation; /* Static name of the instrumented API. */
    bool dispatched; /* False means the API body was never called. */
    golem_status operation_status; /* Meaningful only if dispatched. */
    golem_status recording_status;
} golem_record_api_outcome;
/* Initialize out.struct_size=sizeof(*out), out.version=1. Copy this thread's last
 * completed automatic API boundary; false without writing if none, out is NULL,
 * or size/version is unsupported. Other APIs do not reset it: match operation
 * immediately after the call. Nested boundaries are replaced by their enclosing
 * boundary on return.
 * Once dispatched, the API preserves its operation return and output ownership
 * even if final recording fails. Enabled callers MUST inspect recording_status
 * too. Start failures forbid new dispatch and return a recording error, except
 * explicitly documented required controls (cancel/lease maintenance/release and
 * recovery queries and journal durability append), whose operation must run
 * even when recording cannot start. The void runtime destructor also records
 * its audit outcome here without suppressing release or adding a return value.
 * Those expose dispatched=true and the failed recording_status separately.
 * Finish failures also mark an enclosing record failed and emit diagnostics.
 * Effects/outputs may already exist; do not blindly retry.
 * Explicit record scopes and successful supervisor launches use their existing
 * separate result contracts, not this accessor. The getter performs no I/O. */
bool golem_record_last_api_outcome(golem_record_api_outcome *out);
#ifdef __cplusplus
}
#endif
#endif
