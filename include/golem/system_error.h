#ifndef GOLEM_SYSTEM_ERROR_H
#define GOLEM_SYSTEM_ERROR_H
#include "golem/error.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_SYSTEM_ERROR_CAPACITY 8
#define GOLEM_SYSTEM_ERROR_LABEL_CAPACITY 64
/* Observations, not inferred causes of the enclosing operation's final status.
 * No paths, argv, payloads or localized strerror text are collected. */
typedef struct golem_system_error {
    golem_status status;
    int error_number; /* 0: validation failure, not an errno observation. */
    bool truncated;
    char component[GOLEM_SYSTEM_ERROR_LABEL_CAPACITY];
    char operation[GOLEM_SYSTEM_ERROR_LABEL_CAPACITY];
} golem_system_error;
typedef struct golem_system_error_scope {
    struct golem_system_error_scope *parent; /* Private while active. */
    size_t count;
    size_t omitted;
    golem_system_error entries[GOLEM_SYSTEM_ERROR_CAPACITY];
} golem_system_error_scope;
/* Caller-owned, allocation-free, same-thread LIFO scopes. Nested scopes are
 * isolated; an outer scope does not collect the inner scope's observations.
 * End before returning, longjmp, or handing storage to another thread. Scopes
 * are not aggregated across threads/processes; not an async-signal-safe API.
 * No active scope means no collection. Existing diagnostics/ABI are unchanged. */
golem_status golem_system_error_begin(golem_system_error_scope *scope);
golem_status golem_system_error_end(golem_system_error_scope *scope);
/* Capture only at the failure branch, BEFORE cleanup; pass saved errno only
 * when that syscall's return value makes it valid. Use literal bounded labels.
 * Returns status unchanged and preserves errno. Never retries or prints.
 * Retains first observation and the most recent seven; omitted is saturated. */
golem_status golem_system_error_note(golem_status status, const char *component,
                                   const char *operation, int saved_errno);
const char *golem_system_error_name(int error_number);
const char *golem_system_error_action(int error_number);
#ifdef __cplusplus
}
#endif
#endif
