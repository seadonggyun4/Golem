#ifndef GOLEM_PROOF_H
#define GOLEM_PROOF_H
#include "golem/execution.h"
#ifdef __cplusplus
extern "C" {
#endif

/* All inputs are borrowed. On failure output arguments are unchanged.
 * Replies are owned by the caller; release with golem_execution_reply_free.
 * Request v1 selects 1..8 distinct issued QA receipts and a phase-29E
 * MINIMAL/LINKABLE redaction policy. Rendering never executes or mutates Work.
 * These derived exports are not completion, freshness or privacy approvals. */
golem_status golem_proof_render(golem_document_store *store, golem_bytes request,
                                golem_execution_reply *out, golem_diagnostic *diagnostic);
/* Re-render against the source Work, not merely against embedded checksums. */
golem_status golem_proof_verify(golem_document_store *store, golem_bytes request, golem_bytes pack,
                                golem_diagnostic *diagnostic);
/* Integrity only. An independently trusted expected manifest digest is optional;
 * without it coordinated replacement is not detected. No source authentication. */
golem_status golem_proof_integrity(golem_bytes pack, const golem_digest *expected,
                                   golem_diagnostic *diagnostic);
/* Parent must already exist, be canonical absolute and contain no symlinks.
 * Publishes immutable parent/<manifest-sha256>/, commit marker last. Repeating
 * identical publication is safe. Conflicting existing bytes are never replaced.
 * IO failure may leave orphan files, or a visible commit of uncertain durability.
 * No ownership of the parent is transferred; no automatic cleanup is performed. */
golem_status golem_proof_publish(golem_bytes pack, const char *parent, golem_digest *manifest,
                                 golem_diagnostic *diagnostic);
/* Requires all fixed files and COMMIT.json. Pending temporary files have no
 * authority. No Work state is read or modified by directory verification. */
golem_status golem_proof_verify_directory(const char *parent, const golem_digest *manifest,
                                          golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
