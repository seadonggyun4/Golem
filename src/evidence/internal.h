#ifndef GOLEM_EVIDENCE_INTERNAL_H
#define GOLEM_EVIDENCE_INTERNAL_H
#include "golem/evidence.h"
#include <openssl/evp.h>

#define GOLEM_EVIDENCE_CHUNK 65536
#define GOLEM_SHA256_MAX_BYTES (UINT64_MAX / 8)

struct golem_evidence_store {
    golem_allocator allocator;
    int fd;
    bool writable;
};

golem_status golem_evidence_report(golem_diagnostic *d, golem_status status, const char *message);
golem_status golem_evidence_hash_begin(EVP_MD_CTX **out);
golem_status golem_evidence_hash_end(EVP_MD_CTX *ctx, golem_digest *out);
/* Internal descriptors are always closed by the caller. */
int golem_evidence_path_open(const char *path, bool directory);
golem_status golem_evidence_scan_fd(int fd, int copy_fd, golem_receipt *out);
golem_status golem_evidence_object_open(golem_evidence_store *store,
    const golem_digest *digest, int *out);
#endif
