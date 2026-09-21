#ifndef GOLEM_EVIDENCE_H
#define GOLEM_EVIDENCE_H

#include <stdbool.h>
#include "golem/types.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_DIGEST_SIZE 32
#define GOLEM_DIGEST_HEX_CAPACITY 65
#define GOLEM_RECEIPT_SIZE 48
#define GOLEM_RECEIPT_VERSION 1
#define GOLEM_DIGEST_SHA256 1

/* Independent, copyable values. Never serialize the native struct layout.
 * A receipt describes bytes, not author identity, acceptance or authenticity. */
typedef struct golem_digest { uint8_t bytes[GOLEM_DIGEST_SIZE]; } golem_digest;
typedef struct golem_receipt {
    uint16_t version;
    uint16_t algorithm;
    uint64_t size;
    golem_digest digest;
} golem_receipt;
typedef struct golem_evidence_store golem_evidence_store;

/* Inputs are borrowed and must remain immutable for the call; outputs are
 * caller-owned, independent values.
 * Outputs remain unchanged on failure except optional diagnostics and documented
 * required sizes. Outputs must not alias inputs. OpenSSL manages its own internal
 * allocations; the supplied allocator controls only Golem-owned handles.
 * No secret redaction, signing, journal association or automatic gate approval.
 * POSIX backend: macOS/Linux. Caller synchronizes close against concurrent calls. */
golem_status golem_digest_bytes(golem_bytes bytes, golem_digest *out);
/* Hashes a regular artifact with bounded buffering; rejects symlink path components,
 * '..', and detected changes during reading. Requires a quiescent source for a
 * coherent snapshot; cannot defend against a malicious concurrent file writer. */
golem_status golem_digest_file(const char *path, golem_receipt *out, golem_diagnostic *diagnostic);
/* Strict 64-character lowercase hexadecimal key. No prefix/path syntax accepted. */
golem_status golem_digest_parse(golem_string_view hex, golem_digest *out);
/* required includes NUL. NULL/0 queries size; short buffer is untouched. */
golem_status golem_digest_format(const golem_digest *digest, char *buffer, size_t capacity, size_t *required);

/* Root must already exist. All path components must be real directories, without
 * '..' or symlinks. create=true initializes objects/sha256; false performs no
 * writes and disables put/import/receipt_store. Holds directory descriptors, not
 * borrowed paths. *out owns the handle; allocator context must outlive close.
 * Store must be privately controlled: no hostile same-user directory mutations.
 * New directories 0700, published objects 0400; existing permissions unchanged. */
golem_status golem_evidence_open(const char *root, bool create, const golem_allocator *allocator,
    golem_evidence_store **out, golem_diagnostic *diagnostic);
/* Consumes handle even on close error. NULL is a successful no-op. */
golem_status golem_evidence_close(golem_evidence_store *store);

/* Streaming file import and byte put hash exactly the bytes written. Atomic
 * no-replace publication, file/directory fsync before success. Existing objects
 * are reverified, never repaired/overwritten. Errors may leave a complete object
 * (durability uncertain); crashes may leave unreferenced .tmp-* files.
 * Receipt output is a value; persist it explicitly with receipt_store if needed. */
golem_status golem_evidence_put(golem_evidence_store *store, golem_bytes bytes,
    golem_receipt *out, golem_diagnostic *diagnostic);
golem_status golem_evidence_import(golem_evidence_store *store, const char *path,
    golem_receipt *out, golem_diagnostic *diagnostic);
/* Reads and hashes the entire object; size output changes only on success.
 * No files/directories are created. Missing object is NOT_FOUND. */
golem_status golem_evidence_verify(golem_evidence_store *store, const golem_digest *digest,
    uint64_t *size, golem_diagnostic *diagnostic);
/* Bounded verified read for manifest consumers. Rejects an object larger than
 * max_size with OVERFLOW before allocation. Returns an owned byte allocation
 * (one allocated byte for empty content) and its logical size only after digest
 * verification; free using golem_allocator_free with the SAME allocator.
 * max_size may be zero to allow only empty content. No store allocator borrowing.
 * Both outputs unchanged on failure; no partially read/unverified bytes escape. */
golem_status golem_evidence_read(golem_evidence_store *store, const golem_digest *digest,
    size_t max_size, const golem_allocator *allocator, uint8_t **out, size_t *size, golem_diagnostic *diagnostic);

/* Canonical 48-byte little-endian v1 receipt. Exact length, version and algorithm
 * checked on decode; encoding uses caller storage, no allocations. required is
 * set on OK/BUFFER_TOO_SMALL only. NULL buffer/0 is a size query. */
golem_status golem_receipt_encode(const golem_receipt *receipt, void *buffer,
    size_t capacity, size_t *required);
golem_status golem_receipt_decode(golem_bytes bytes, golem_receipt *out);
/* Store encoded receipt as another CAS object. Does not assert target presence.
 * Verify checks receipt object hash, schema, then target hash AND recorded size.
 * receipt_digest must be independently trusted; CAS integrity is not provenance. */
golem_status golem_evidence_receipt_store(golem_evidence_store *store,
    const golem_receipt *receipt, golem_digest *out, golem_diagnostic *diagnostic);
golem_status golem_evidence_receipt_verify(golem_evidence_store *store,
    const golem_digest *receipt_digest, golem_receipt *out, golem_diagnostic *diagnostic);

#ifdef __cplusplus
}
#endif

#endif
