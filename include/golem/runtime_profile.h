#ifndef GOLEM_RUNTIME_PROFILE_H
#define GOLEM_RUNTIME_PROFILE_H
#include "golem/document.h"
#include "golem/replay.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_RUNTIME_PROFILE_VERSION 1u
#define GOLEM_RUNTIME_PROFILE_MAX_BYTES 65536u
#define GOLEM_RUNTIME_PROFILE_MAX_TOOLS 256u
#define GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS 64u

typedef struct golem_runtime_profile golem_runtime_profile;
typedef struct golem_runtime_profile_cache golem_runtime_profile_cache;

/* Strict secret-free field allowlist; opaque identifiers are never normalized.
 * Inputs borrowed for the call. Output owned, immutable, allocator context must
 * outlive free. JSON-C uses its own allocator. Outputs unchanged on failure.
 * Identity is SHA-256 of the versioned canonical JSON including its domain.
 * Identity/observations are NOT execution permission or remote reproducibility. */
golem_status golem_runtime_profile_parse(golem_bytes json, const golem_allocator *allocator,
                                         golem_runtime_profile **out, golem_diagnostic *diagnostic);
void golem_runtime_profile_free(golem_runtime_profile *profile);
golem_status golem_runtime_profile_digest(const golem_runtime_profile *profile, golem_digest *out);
/* Caller-owned buffer, no NUL. Size query/short buffer sets required only;
 * insufficient buffer is untouched. Otherwise outputs unchanged on failure. */
golem_status golem_runtime_profile_encode(const golem_runtime_profile *profile, void *buffer,
                                          size_t capacity, size_t *required);

/* Each acquire invokes current_check, INCLUDING hits: policy revocation,
 * executable/config/tool identity and probe freshness belong to this trusted
 * callback. It must not reenter the cache. No callback result is cached.
 * A failed probe/check cannot become a successful memo entry. Cache memoizes
 * parsing/encoding, not permission. Serialize calls. Acquired profiles are
 * borrowed until release; never profile_free them. Pinned entries aren't evicted.
 * Exact request bytes are the memo key (all identity inputs must be in profile).
 * Actual preparation/discovery reuse is a separate opt-in prepared_runtime.h API.
 * close refuses outstanding borrows and otherwise consumes cache. */
typedef golem_status (*golem_runtime_profile_check)(void *context,
                                                    const golem_runtime_profile *profile);
golem_status golem_runtime_profile_cache_create(const golem_allocator *allocator,
                                                golem_runtime_profile_cache **out);
golem_status golem_runtime_profile_cache_acquire(golem_runtime_profile_cache *cache,
                                                 golem_bytes json,
                                                 golem_runtime_profile_check current_check,
                                                 void *context, const golem_runtime_profile **out);
golem_status golem_runtime_profile_cache_release(golem_runtime_profile_cache *cache,
                                                 const golem_runtime_profile *profile);
golem_status golem_runtime_profile_cache_close(golem_runtime_profile_cache *cache);

/* Register immutable generation in the Work hash chain and CAS. First call
 * enrolls a Work; cannot enroll during an existing unbound claim. Future claims
 * automatically pin the latest registered generation. Refresh never changes
 * existing claims. Same key/canonical profile returns original digest; different
 * profile conflicts. Current Work permission is checked even for retries.
 * CAS-local availability checks do not imply remote model availability.
 * IO may have committed: close/reopen, retry same key. No profile removal API.
 * Borrowed store/profile/key; output is value-only. */
golem_status golem_runtime_profile_register(golem_document_store *store,
                                            const golem_runtime_profile *profile, const char *key,
                                            golem_digest *out, golem_diagnostic *diagnostic);
/* Latest registered canonical profile, NOT necessarily a live attempt's profile.
 * NOT_FOUND means legacy/unenrolled, not a verified default. Buffer rules above. */
golem_status golem_runtime_profile_current(golem_document_store *store, void *buffer,
                                           size_t capacity, size_t *required);

/* Optional explicit bridge to the independent binary WorkRun domain. Caller
 * supplies a separately trusted checkpoint and exact run ID; both are verified
 * by semantic replay. Requires a live RUNNING current-agent claim with the exact
 * binding and matching StageRun stage. Does not execute/resume the WorkRun.
 * Immutable link receipt + journal snapshot are retained in Work CAS/hash chain.
 * Inputs borrowed for this call. Snapshot <=16 MiB. Same binding and identical
 * journal is idempotent; changed journal conflicts. Output unchanged on failure.
 * Current authority is rechecked even on retry. This is trusted local linkage,
 * not a cryptographically authenticated statement about who ran the WorkRun. */
golem_status golem_runtime_link_run(golem_document_store *store, const golem_digest *binding,
                                    golem_bytes journal, const char *expected_run_id,
                                    const golem_journal_checkpoint *checkpoint,
                                    golem_digest *receipt, golem_diagnostic *diagnostic);

#ifdef __cplusplus
}
#endif
#endif
