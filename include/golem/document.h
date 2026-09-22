#ifndef GOLEM_DOCUMENT_H
#define GOLEM_DOCUMENT_H
#include "golem/evidence.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_DOCUMENT_VERSION 1u
#define GOLEM_DOCUMENT_MAX_BODY 1048576u
#define GOLEM_DOCUMENT_MAX_JSON 262144u
#define GOLEM_DOCUMENT_MAX_REVISIONS 4096u
#define GOLEM_DOCUMENT_MAX_PARENTS 64u
#define GOLEM_DOCUMENT_MAX_EDGES 16384u
#define GOLEM_DOCUMENT_ID_CAPACITY 65u

typedef struct golem_document_store golem_document_store;
typedef struct golem_document_result {
    uint64_t generation;
    uint32_t revision;
    golem_digest body_digest, manifest_digest, event_digest;
    /* Registration is durable even when projection_status is non-OK.
     * Repair with project; never resubmit under a different key to repair. */
    golem_status projection_status;
} golem_document_result;

/* JSON and Markdown inputs are borrowed, immutable for the call. No execution,
 * AI authorship, semantic acceptance, credential authentication or lease grants.
 * Validation is structural only. Unknown schema/template versions fail closed.
 * Optional diagnostic is caller-owned. No output mutation on failure. */
golem_status golem_work_spec_validate(golem_bytes specification, golem_diagnostic *diagnostic);
golem_status golem_document_validate(golem_bytes metadata, golem_bytes markdown,
    golem_diagnostic *diagnostic);

/* Private existing root, no symlink components or '..'. Create initializes a NEW
 * Work registry and its CAS. It never adopts/overwrites an existing registry.
 * Open verifies the complete committed hash chain, metadata and CAS bodies.
 * Lifetime flock: exclusive for writable, shared for read-only. Serialize handle
 * calls. Outputs owned until close; paths/inputs are copied or consumed at call.
 * allocator controls handle/entry array, not json-c/MD4C/OpenSSL allocations.
 * Its context must outlive close. No borrowed caller buffers survive calls.
 * IO/uncertain commit failures poison a writer: close/reopen before retry.
 * New files are 0400/0600, directories 0700; caller protects the root.
 * Initialization IO failure may leave an incomplete root, never auto-adopted. */
golem_status golem_document_store_create(const char *root, golem_bytes specification,
    const golem_allocator *allocator, golem_document_store **out, golem_diagnostic *diagnostic);
golem_status golem_document_store_open(const char *root, bool writable,
    const golem_allocator *allocator, golem_document_store **out, golem_diagnostic *diagnostic);
/* Consumes handle on all outcomes; NULL is accepted. */
golem_status golem_document_store_close(golem_document_store *store);
golem_status golem_document_generation(const golem_document_store *store, uint64_t *out);

/* Local trusted submission only: AUTO_LOCAL/ASK_ON_EXTERNAL_EFFECT allowed;
 * ASK_ALWAYS asks and DENY blocks. producer_attempt is attribution, not an authenticated claim.
 * expected_generation is a compare-and-swap precondition. parents must reference
 * the latest registered revisions; transitive freshness is a later workflow gate.
 * key is an ASCII identifier, unique for this Work. Idempotency binds exact JSON
 * and body bytes, not arbitrary equivalent JSON serializations. Same key/content
 * returns the same receipt even after later commits; conflicting reuse is denied.
 * Supersedes must match the prior document manifest digest. Revisions contiguous.
 * Successful registration is NOT business acceptance or workflow CURRENT.
 * projection_status reports materialization independently of the commit. */
golem_status golem_document_submit(golem_document_store *store, golem_bytes metadata,
    golem_bytes markdown, const char *key, golem_document_result *out,
    golem_diagnostic *diagnostic);
golem_status golem_document_inspect(golem_document_store *store, const char *document_id,
    uint32_t revision, golem_document_result *out, golem_diagnostic *diagnostic);
/* Raw UTF-8 bytes, no appended NUL. required is set on OK/BUFFER_TOO_SMALL only.
 * NULL/0 is a size query, short buffers untouched. No input/output aliasing. */
golem_status golem_document_body(golem_document_store *store, const char *document_id,
    uint32_t revision, void *buffer, size_t capacity, size_t *required,
    golem_diagnostic *diagnostic);
/* Same buffer contract; returns the exact registered metadata JSON bytes. */
golem_status golem_document_metadata(golem_document_store *store, const char *document_id,
    uint32_t revision, void *buffer, size_t capacity, size_t *required,
    golem_diagnostic *diagnostic);
/* Materialize documents/ID/rNNNN.md from verified CAS. Existing identical bytes
 * are accepted, absent files repaired, differing files/symlinks NEVER overwritten.
 * Requires writable handle; no revision/event change. */
golem_status golem_document_project(golem_document_store *store, const char *document_id,
    uint32_t revision, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
