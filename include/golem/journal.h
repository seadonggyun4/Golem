#ifndef GOLEM_JOURNAL_H
#define GOLEM_JOURNAL_H
#include "golem/core.h"
#include "golem/types.h"
#include "golem/evidence.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_JOURNAL_SCHEMA_VERSION 1u
#define GOLEM_JOURNAL_HEADER_SIZE 32u
#define GOLEM_JOURNAL_MAX_PAYLOAD 1048576u
#define GOLEM_JOURNAL_MAX_LIST_ITEMS 256u
#define GOLEM_JOURNAL_EVENT_SIZE 32u

/* Stable wire codes. One journal contains exactly one WorkRun. */
typedef enum golem_journal_type {
    GOLEM_JOURNAL_CREATED = 1,
    GOLEM_JOURNAL_STARTED = 2,
    GOLEM_JOURNAL_FINISHED = 3,
    GOLEM_JOURNAL_REENTERED = 4,
    GOLEM_JOURNAL_CANCELLED = 5
} golem_journal_type;

typedef struct golem_journal golem_journal;
/* Read-only diagnostic snapshot. stream_status describes the first invalid
 * frame; GOLEM_OK from inspect means the report was produced, not stream health.
 * valid_bytes is a structural prefix, NOT authorization to resume execution.
 * chain_head is a derived SHA256 commitment, NOT a signature or on-disk v2.
 * Retain the head outside the journal's trust boundary to detect rewriting or
 * prefix truncation. Empty stream head is 32 zero bytes. */
typedef struct golem_journal_inspection {
    size_t valid_bytes;
    uint64_t records;
    golem_status stream_status;
    golem_diagnostic failure;
    golem_digest source_digest;
    golem_digest chain_head;
} golem_journal_inspection;

/* Inputs borrowed; output caller-owned and unchanged on API/crypto error.
 * SHA256("golem.journal.chain.v1" || previous_head || SHA256(encoded_frame)).
 * CRC, version and contiguous sequence are checked before adding each frame.
 * Does not perform semantic replay, read files, repair bytes or run agents. */
golem_status golem_journal_inspect(golem_bytes bytes, golem_journal_inspection *out);
typedef struct golem_journal_record {
    golem_journal_type type;
    uint64_t sequence;
    golem_bytes payload; /* Borrowed from the encoded input. */
} golem_journal_record;

/* Caller-owned cursor over immutable borrowed bytes. Do not edit fields.
 * On error, cursor and record outputs remain unchanged. diagnostics may change. */
typedef struct golem_journal_reader {
    golem_bytes bytes;
    size_t offset;
    uint64_t next_sequence;
} golem_journal_reader;

/* Non-created event value. Zero initialize before filling fields.
 * STARTED: stage, attempt, token, outcome=RUNNING, external/authorized.
 * FINISHED: stage, attempt, token, PASSED/NONE/met or FAILED/failure/!met.
 * REENTERED: target stage only. CANCELLED: stage=NONE only.
 * Unused fields must be zero; stage/failure/status wire codes are pinned in v1. */
typedef struct golem_journal_event {
    golem_journal_type type;
    golem_stage stage;
    uint32_t attempt;
    uint64_t attempt_sequence;
    golem_stage_status outcome;
    golem_failure failure;
    bool external_effect;
    bool authorized;
    bool requirements_met;
} golem_journal_event;

/* All inputs borrowed for the call except reader backing bytes. Output storage
 * must not overlap input or owner storage. No input ownership transfers.
 * Errors preserve outputs except diagnostics and documented required sizes.
 * Diagnostic offsets are byte positions; no automatic corruption repair.
 * CRC32 detects accidental corruption; it is NOT authentication.
 * Codecs/reader use no heap. String data must not contain embedded NUL. */
golem_status golem_journal_crc32(golem_bytes bytes, uint32_t *out);
golem_status golem_journal_record_encode(golem_journal_type type, uint64_t sequence,
    golem_bytes payload, void *destination, size_t capacity, size_t *required,
    golem_diagnostic *diagnostic);
/* Decodes the first frame, not necessarily the entire input. payload borrows
 * input. On success consumed is frame length; CRC/header/version validated. */
golem_status golem_journal_record_decode(golem_bytes bytes,
    golem_journal_record *out, size_t *consumed, golem_diagnostic *diagnostic);
golem_status golem_journal_reader_init(golem_journal_reader *reader, golem_bytes bytes);
/* EOF: OK with has_record=false, record unchanged. No partial-tail acceptance.
 * Sequence starts at 1 and must be contiguous. */
golem_status golem_journal_reader_next(golem_journal_reader *reader,
    golem_journal_record *out, bool *has_record, golem_diagnostic *diagnostic);
/* Encode functions: NULL/0 is a size query. required updates on OK or
 * BUFFER_TOO_SMALL; short destinations are untouched. Text metadata is copied. */
golem_status golem_journal_created_encode(const char *run_id,
    const golem_work_capsule *capsule, uint32_t max_attempts,
    void *destination, size_t capacity, size_t *required, golem_diagnostic *diagnostic);
golem_status golem_journal_event_encode(const golem_journal_event *event,
    void *destination, size_t capacity, size_t *required, golem_diagnostic *diagnostic);
golem_status golem_journal_event_decode(const golem_journal_record *record,
    golem_journal_event *out, golem_diagnostic *diagnostic);

/* POSIX regular-file backend (macOS/Linux); creates if absent, never truncates.
 * Copies allocator (NULL=default). Context must outlive handle; close consumes
 * handle even on I/O error. Advisory exclusive lock held for handle lifetime.
 * Existing stream is fully frame/CRC/sequence checked, not semantically replayed.
 * Truncated/corrupt/version-incompatible streams are never opened for append. */
golem_status golem_journal_open(const char *path, const golem_allocator *allocator,
    golem_journal **out, golem_diagnostic *diagnostic);
/* Appends one structurally valid frame; sequence assigned internally. Success
 * includes fsync(file). Caller owns payload. Semantic event validation belongs
 * to replay. I/O failure may leave a partial/durable record and poisons handle:
 * close/reopen/inspect before deciding whether to retry. Never blindly retry.
 * One writer thread per handle; locks are advisory, not a security boundary.
 * Parent directory durability for newly created files is caller responsibility. */
golem_status golem_journal_append(golem_journal *journal,
    golem_journal_type type, golem_bytes payload, uint64_t *sequence,
    golem_diagnostic *diagnostic);
golem_status golem_journal_close(golem_journal *journal, golem_diagnostic *diagnostic);
/* Strict transactional replay: returns a new owned WorkRun only if all records
 * pass framing and Core transition validation. Free via golem_work_run_free.
 * Input may end at a valid unfinished state. On error no partial run escapes.
 * Does not execute agents or verify CAS/leases/signatures; requirements are
 * recorded caller attestations, as in the current in-memory Core.
 * Compatibility wrapper over replay.h. Gaps/empty streams map to CORRUPT_JOURNAL,
 * a first event without creation maps to INVALID_STATE. Use the incremental
 * engine for specific missing-record errors, reports, and endpoint checks. */
golem_status golem_journal_replay(golem_bytes bytes, const golem_allocator *allocator,
    golem_work_run **out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
