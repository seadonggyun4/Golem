#ifndef GOLEM_REPLAY_H
#define GOLEM_REPLAY_H
#include "golem/journal.h"
#ifdef __cplusplus
extern "C" {
#endif

typedef struct golem_replay golem_replay;
typedef enum golem_replay_state {
    GOLEM_REPLAY_ACTIVE = 0,
    GOLEM_REPLAY_FAILED = 1,
    GOLEM_REPLAY_FINISHED = 2
} golem_replay_state;

/* Recovery actions are guidance, not execution authorization. No action here
 * runs an agent, grants a lease, or bypasses policy/evidence verification. */
typedef enum golem_recovery_action {
    GOLEM_RECOVERY_NONE = 0,
    GOLEM_RECOVERY_CHECK_POLICY = 1,
    GOLEM_RECOVERY_RECONCILE_ATTEMPT = 2,
    GOLEM_RECOVERY_EVALUATE_REENTRY = 3,
    GOLEM_RECOVERY_RESOLVE_BLOCK = 4
} golem_recovery_action;

typedef struct golem_replay_options {
    /* Optional identity, deep-copied at create. NULL accepts any run ID. */
    const char *expected_run_id;
    /* Exact endpoint from separately retained metadata, NOT from the input
     * being verified. Both positive when enabled; both zero otherwise.
     * Detects whole-record tail loss; does not authenticate content. */
    bool has_expected_boundary;
    uint64_t expected_records;
    uint64_t expected_bytes;
    /* Only SUCCEEDED/CANCELLED are terminal. Default permits valid prefixes. */
    bool require_terminal;
} golem_replay_options;

typedef struct golem_replay_progress {
    golem_replay_state state;
    uint64_t verified_records;
    uint64_t verified_bytes;
    size_t buffered_bytes;
} golem_replay_progress;

typedef struct golem_replay_report {
    uint64_t verified_records;
    uint64_t verified_bytes;
    uint64_t next_record_sequence; /* zero means sequence exhausted */
    golem_work_snapshot work;
    bool has_latest_attempt;
    golem_stage_snapshot latest_attempt;
    golem_recovery_action action;
} golem_replay_report;

/* NULL options means all-zero defaults. NULL allocator means C heap.
 * Allocator callbacks/context are copied; context must outlive engine and
 * returned run. Options (including ID) are copied. Caller frees engine with
 * replay_free, and any finished run independently with work_run_free.
 * Inputs borrowed only during calls. Outputs/diagnostics must not alias inputs
 * or owner storage. Serialize all access to one engine.
 * Outputs unchanged on error except diagnostics. Diagnostics use absolute byte
 * offsets. No partial WorkRun is exposed by any failure path. */
golem_status golem_replay_create(const golem_replay_options *options,
    const golem_allocator *allocator, golem_replay **out, golem_diagnostic *diagnostic);
/* Copy a separately retained exact checkpoint before the first input byte.
 * finish rejects any content/endpoint mismatch without exposing a WorkRun.
 * Not an authentication mechanism; caller establishes checkpoint trust.
 * May be set once only. No public struct layout changes for existing clients. */
golem_status golem_replay_expect_checkpoint(golem_replay *replay,
    const golem_journal_checkpoint *checkpoint);
/* Chunk boundaries are arbitrary, including within headers/fields. No input
 * pointer retained. Empty chunks allowed. Complete frames are checked/applied;
 * at most one bounded frame buffer is retained. Stream length <= SIZE_MAX.
 * Any feed error on ACTIVE poisons engine and discards its private run; no
 * retry/resume of that engine. FAILED/FINISHED return INVALID_STATE. */
golem_status golem_replay_feed(golem_replay *replay, golem_bytes chunk,
    golem_diagnostic *diagnostic);
/* Declares EOF, checks pending frame/identity/endpoint/terminal constraints,
 * transfers owned run on success and optionally writes a value-only report.
 * Failure on ACTIVE poisons/discards state. Success seals engine; finish cannot
 * be repeated. A RUNNING report requires reconciliation, NEVER blind retry. */
golem_status golem_replay_finish(golem_replay *replay, golem_work_run **out,
    golem_replay_report *report, golem_diagnostic *diagnostic);
/* Value-only progress is available even after failure, for diagnosis. Verified
 * prefix positions are NOT authorization to truncate or ignore invalid bytes. */
golem_status golem_replay_progress_get(const golem_replay *replay,
    golem_replay_progress *out);
void golem_replay_free(golem_replay *replay); /* NULL is a no-op. */

/* Reconstruct a file while retaining journal's existing exclusive writer lock.
 * Uses bounded reads from the same descriptor; no pathname reopen/TOCTOU gap.
 * Handle must be healthy. Returns independent owned run and optional report.
 * Uses journal's allocator: its context must outlive the returned run too.
 * No file edits, fsync, truncation, or Core execution. Success does not release
 * the lock or combine future appends with Core mutations into a transaction.
 * Failure after engine creation poisons journal for further appends; close it.
 * Preflight/engine-creation errors (including OOM) leave journal usable.
 * Advisory locks exclude cooperating writers, not hostile in-place rewrites. */
golem_status golem_journal_recover(golem_journal *journal,
    const golem_replay_options *options, golem_work_run **out,
    golem_replay_report *report, golem_diagnostic *diagnostic);

#ifdef __cplusplus
}
#endif
#endif
