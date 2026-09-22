#ifndef GOLEM_DISCOVERY_H
#define GOLEM_DISCOVERY_H
#include "golem/document.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_DISCOVERY_VERSION 1u
#define GOLEM_DISCOVERY_DOCUMENT_VERSION 2u
#define GOLEM_DISCOVERY_MAX_ITEMS 64u
#define GOLEM_DISCOVERY_MAX_REPOSITORIES 8u
#define GOLEM_DISCOVERY_MAX_FILE_BYTES 1048576u
#define GOLEM_DISCOVERY_MAX_TOTAL_BYTES 16777216u
typedef struct golem_discovery_result {
    uint32_t findings, selected, questions, references, full_text_references;
    bool scope_ready;
    golem_digest snapshot_digest;
} golem_discovery_result;
/* Pure bounded structural validation. Inputs borrowed for the call. Output is
 * caller-owned, unchanged on error. scope_ready means internally consistent
 * local selection, NOT semantic approval, execution authority or verified QA.
 * No network, commands, or file reads. Research/observations are agent claims. */
golem_status golem_discovery_validate(golem_bytes assessment,
    golem_discovery_result *out, golem_diagnostic *diagnostic);
/* Deterministic Markdown draft projection of validated agent claims. kind is
 * discovery/research/scope. No fabricated investigation or execution. Parents
 * are initially absent; the agent adds registered parent links when appropriate.
 * Exact UTF-8 bytes, no NUL. NULL/0 queries size; short buffer is untouched.
 * required changes only on OK/BUFFER_TOO_SMALL. Inputs/output must not alias. */
golem_status golem_discovery_report(golem_bytes assessment, const char *kind,
    void *buffer, size_t capacity, size_t *required, golem_diagnostic *diagnostic);
/* Read-only allowlisted Git/filesystem snapshot. Executes only /usr/bin/git
 * through the bounded supervisor, never a shell, test, hook or project command.
 * Rejects GIT_* environment overrides. No recursive scan or source-text export.
 * Plan supplies private absolute roots, explicit paths and declared toolchain.
 * Output is allocated with allocator (NULL = default); free with the same
 * allocator. size excludes NUL, no NUL is promised. Both outputs unchanged on
 * failure. Dependencies use their own temporary allocators. Capture is bounded
 * but not an atomic multi-repository transaction. Requires quiescent input files.
 * Root/index/file identities are checked again before returning. */
golem_status golem_discovery_snapshot(golem_bytes plan, const golem_allocator *allocator,
    uint8_t **out, size_t *size, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
