#ifndef GOLEM_ERROR_H
#define GOLEM_ERROR_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef enum golem_status {
    GOLEM_OK = 0,
    GOLEM_ERR_INVALID_ARGUMENT = 1,
    GOLEM_ERR_OUT_OF_MEMORY = 2,
    GOLEM_ERR_PARSE = 3,
    GOLEM_ERR_POLICY_DENIED = 4,
    GOLEM_ERR_IO = 5,
    GOLEM_ERR_CORRUPT_JOURNAL = 6,
    GOLEM_ERR_INVALID_STATE = 7,
    GOLEM_ERR_INVALID_GRAPH = 8,
    GOLEM_ERR_NO_REENTRY = 9,
    GOLEM_ERR_ATTEMPT_LIMIT = 10,
    GOLEM_ERR_STALE_RESULT = 11,
    GOLEM_ERR_REQUIREMENTS_UNMET = 12,
    GOLEM_ERR_BUFFER_TOO_SMALL = 13,
    GOLEM_ERR_OVERFLOW = 14,
    GOLEM_ERR_UNSUPPORTED_VERSION = 15,
    GOLEM_ERR_TRUNCATED_JOURNAL = 16,
    GOLEM_ERR_JOURNAL_BUSY = 17,
    GOLEM_ERR_MISSING_RECORD = 18,
    GOLEM_ERR_REPLAY_MISMATCH = 19,
    GOLEM_ERR_INCOMPLETE_WORK = 20,
    GOLEM_ERR_NOT_FOUND = 21,
    GOLEM_ERR_DIGEST_MISMATCH = 22,
    GOLEM_ERR_SIZE_MISMATCH = 23,
    GOLEM_ERR_CRYPTO = 24,
    GOLEM_ERR_IDENTITY_MISMATCH = 25,
    GOLEM_ERR_APPROVAL_REQUIRED = 26,
    GOLEM_ERR_BUDGET_EXHAUSTED = 27,
    GOLEM_ERR_COST_INCOMPLETE = 28,
    GOLEM_ERR_COST_CAPACITY = 29,
    GOLEM_ERR_OPTIMIZATION_REJECTED = 30,
    GOLEM_ERR_STALE_LEASE = 31,
    GOLEM_ERR_LEASE_BUSY = 32
} golem_status;

/* Returns immutable process-lifetime storage; never free the result. */
const char *golem_status_string(golem_status status);

#define GOLEM_DIAGNOSTIC_MESSAGE_CAPACITY 256
#define GOLEM_DIAGNOSTIC_NO_OFFSET SIZE_MAX
/* Caller-owned, copyable diagnostic; no borrowed strings or allocations.
 * No errno/global last-error state. offset is a byte offset or NO_OFFSET.
 * Message always ends in NUL after clear/set. Unknown status values are kept. */
typedef struct golem_diagnostic {
    golem_status status;
    size_t offset;
    bool truncated;
    char message[GOLEM_DIAGNOSTIC_MESSAGE_CAPACITY];
} golem_diagnostic;
/* NULL output returns INVALID_ARGUMENT. Neither operation allocates. */
golem_status golem_diagnostic_clear(golem_diagnostic *diagnostic);
/* Copies a C string (NULL uses status text). Long messages are truncated with
 * truncated=true; the setter still returns OK and retains the original status.
 * message may point into diagnostic itself. No input ownership transfer. */
golem_status golem_diagnostic_set(golem_diagnostic *diagnostic,
                                         golem_status status, size_t offset, const char *message);

#ifdef __cplusplus
}
#endif
#endif
