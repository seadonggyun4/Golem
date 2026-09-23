#ifndef GOLEM_CONTEXT_H
#define GOLEM_CONTEXT_H
#include "golem/document.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_CONTEXT_VERSION 1u
#define GOLEM_CONTEXT_MAX 2097152u
#define GOLEM_CONTEXT_REQUEST_MAX 32768u
/* Optional trusted, deterministic tokenizer over the COMPLETE returned JSON bytes.
 * id pins tokenizer/model/version; callbacks borrow input, must not reenter the
 * store or retain bytes. No approximate bytes/4 token accounting. NULL supports
 * only token_budget=0/tokenizer_id="none". Context must outlive the call. */
typedef struct golem_context_tokenizer {
    const char *id;
    void *context;
    golem_status (*count)(void *context, golem_bytes bytes, uint64_t *tokens);
} golem_context_tokenizer;
golem_status golem_context_request_validate(golem_bytes request, golem_diagnostic *diagnostic);
/* Derived, read-only projection of verified current workflow inputs. Request
 * schema/renderer version 1, extractive-v1 or original-v1 recipe. Machine facts
 * are never authored by an agent: full Work spec, metadata, reentry/research/
 * completion history, workflow next action and protected status/requirement lines.
 * Arbitrary natural-language meaning is NOT guaranteed; read originals for it.
 * JSON includes Markdown, exact source refs, omission inventory and untrusted
 * agent note. Does not authorize, approve, submit a document or compact a journal.
 * Inputs borrowed; serialize store calls. Store allocator owns scratch; json-c
 * owns JSON allocations. Caller owns output. NULL/0 queries size, short buffers
 * untouched. required changes only on OK/BUFFER_TOO_SMALL. No input/output alias.
 * Entire output must fit byte and optional exact token budgets, including facts.
 * Any missing/tampered/stale source fails closed. No silent partial facts. */
golem_status golem_context_render(golem_document_store *store, golem_bytes request,
                                  const golem_context_tokenizer *tokenizer, void *buffer,
                                  size_t capacity, size_t *required, golem_diagnostic *diagnostic);
/* Explicit immutable CAS publication, subject to store permission. No Work event,
 * registry revision or completion change. Preserve returned receipt independently.
 * Identical bytes share a CAS identity; altered recipe/note/input yields new bytes.
 * Output unchanged on error. IO uncertainty may leave an unreferenced CAS object. */
golem_status golem_context_publish(golem_document_store *store, golem_bytes request,
                                   const golem_context_tokenizer *tokenizer, golem_receipt *receipt,
                                   golem_diagnostic *diagnostic);
/* Read CAS by independently retained digest, then rebuild against current Work.
 * Caller supplies CURRENT expected source snapshot, never trusts the artifact's
 * snapshot as a freshness oracle. Full byte comparison, not just stored hash.
 * Changed Work head, inputs, facts or renderer are not silently accepted.
 * On missing projection/unknown recipe, caller may render original-v1 using its
 * independently retained request. Missing originals or insufficient budget still
 * block. This API never guesses an untrusted artifact's replacement authority. */
golem_status golem_context_read(golem_document_store *store, const golem_digest *digest,
                                const golem_digest *expected_source,
                                const golem_context_tokenizer *tokenizer, void *buffer,
                                size_t capacity, size_t *required, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
