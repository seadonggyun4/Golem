#ifndef GOLEM_PREPARED_RUNTIME_H
#define GOLEM_PREPARED_RUNTIME_H
#include "golem/runtime_profile.h"
#ifdef __cplusplus
extern "C" {
#endif

typedef struct golem_prepared_cache golem_prepared_cache;
typedef struct golem_prepared_runtime golem_prepared_runtime;
typedef struct golem_prepared_options {
    size_t size;
    uint32_t version;
    size_t capacity, max_bytes;
    uint64_t ttl_ns;
    void *context;
    /* Always checks live authority AND observes all discovery dependencies.
     * Digest must include provider scope, plugin/tool/config identity and epoch.
     * Must reject unknown/stale observations; secrets must not enter the digest. */
    golem_status (*observe)(void *, const golem_runtime_profile *, golem_digest *);
    /* Read-only discovery/preparation, called on misses only. No agent spawn,
     * permissions, credentials or mutable handles in output. Caller-owned buffer;
     * set used on success, never write beyond capacity. No automatic retries. */
    golem_status (*prepare)(void *, const golem_runtime_profile *, void *, size_t, size_t *);
    /* One monotonic clock domain throughout the cache lifetime. */
    golem_status (*clock_ns)(void *, uint64_t *);
} golem_prepared_options;

/* Additive process-local API; existing profile cache/Work wire formats unchanged.
 * Options/allocator copied; their contexts borrowed until close. Capacity 1..64,
 * max_bytes 1..65536, ttl 1ns..1h. Serialize all calls, including view/release.
 * Callbacks must be bounded/cooperative and cannot reenter this cache.
 * Memory bounded by (capacity + one pending miss) * max_bytes plus metadata.
 * Failures leave caller outputs unchanged. No disk/network effects in cache. */
golem_status golem_prepared_cache_create(const golem_prepared_options *options,
                                         const golem_allocator *allocator,
                                         golem_prepared_cache **out);
/* Profile borrowed only during call. Result borrowed until release; immutable.
 * A hit still checks authority/dependencies/time. Miss checks again after prepare.
 * No stale-on-error. Pins preserve bytes, NOT authority/freshness for execution.
 * Before execution use existing checked dispatch/lease policy, never this receipt. */
golem_status golem_prepared_cache_acquire(golem_prepared_cache *cache,
                                          const golem_runtime_profile *profile,
                                          const golem_prepared_runtime **out);
golem_status golem_prepared_runtime_view(const golem_prepared_runtime *runtime, golem_bytes *bytes,
                                         golem_digest *profile, golem_digest *dependencies,
                                         golem_digest *content);
/* Invalidate future hits without destroying outstanding borrowed bytes. */
golem_status golem_prepared_cache_invalidate(golem_prepared_cache *cache);
golem_status golem_prepared_cache_release(golem_prepared_cache *cache,
                                          const golem_prepared_runtime *runtime);
/* NULL succeeds; refuses outstanding borrows, otherwise consumes cache. */
golem_status golem_prepared_cache_close(golem_prepared_cache *cache);
#ifdef __cplusplus
}
#endif
#endif
