#include "profile_internal.h"
#include <string.h>

typedef struct profile_slot {
    golem_digest request;
    golem_runtime_profile *profile;
    size_t pins;
} profile_slot;
struct golem_runtime_profile_cache {
    golem_allocator allocator;
    profile_slot slots[GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS];
    size_t next;
    bool busy;
};

golem_status golem_runtime_profile_cache_create(const golem_allocator *allocator,
                                                golem_runtime_profile_cache **out)
{
    if (!out || golem_allocator_validate(allocator) != GOLEM_OK)
        return GOLEM_ERR_INVALID_ARGUMENT;
    void *memory = NULL;
    golem_status status =
        golem_allocator_alloc(allocator, sizeof(golem_runtime_profile_cache), &memory);
    if (status == GOLEM_OK) {
        golem_runtime_profile_cache *cache = memory;
        memset(cache, 0, sizeof(*cache));
        cache->allocator = allocator ? *allocator : golem_allocator_default();
        *out = cache;
    }
    return status;
}

golem_status golem_runtime_profile_cache_acquire(golem_runtime_profile_cache *cache,
                                                 golem_bytes json,
                                                 golem_runtime_profile_check check, void *context,
                                                 const golem_runtime_profile **out)
{
    if (!cache || !check || !out || (!json.data && json.size))
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (cache->busy)
        return GOLEM_ERR_INVALID_STATE;
    if (json.size > GOLEM_RUNTIME_PROFILE_MAX_BYTES)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    golem_digest digest;
    golem_status status = golem_digest_bytes(json, &digest);
    if (status != GOLEM_OK)
        return status;
    size_t chosen = GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS;
    for (size_t i = 0; i < GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS; ++i)
        if (cache->slots[i].profile && dw_equal(&cache->slots[i].request, &digest)) {
            chosen = i;
            break;
        }
    golem_runtime_profile *candidate = NULL;
    bool hit = chosen < GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS;
    if (hit) {
        if (cache->slots[chosen].pins == SIZE_MAX)
            return GOLEM_ERR_OVERFLOW;
        candidate = cache->slots[chosen].profile;
    } else {
        for (size_t i = 0; i < GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS; ++i) {
            size_t index = (cache->next + i) % GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS;
            if (!cache->slots[index].pins) {
                chosen = index;
                break;
            }
        }
        if (chosen == GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS)
            return GOLEM_ERR_BUDGET_EXHAUSTED;
        status = golem_runtime_profile_parse(json, &cache->allocator, &candidate, NULL);
    }
    if (status == GOLEM_OK) {
        cache->busy = true;
        status = check(context, candidate);
        cache->busy = false;
    }
    if (status == GOLEM_OK) {
        profile_slot *slot = &cache->slots[chosen];
        if (!hit) {
            golem_runtime_profile_free(slot->profile);
            *slot = (profile_slot){digest, candidate, 0};
            cache->next = (chosen + 1) % GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS;
        }
        ++slot->pins;
        *out = candidate;
    } else if (!hit)
        golem_runtime_profile_free(candidate);
    return status;
}

golem_status golem_runtime_profile_cache_release(golem_runtime_profile_cache *cache,
                                                 const golem_runtime_profile *profile)
{
    if (!cache || !profile)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (cache->busy)
        return GOLEM_ERR_INVALID_STATE;
    for (size_t i = 0; i < GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS; ++i)
        if (cache->slots[i].profile == profile && cache->slots[i].pins) {
            --cache->slots[i].pins;
            return GOLEM_OK;
        }
    return GOLEM_ERR_INVALID_STATE;
}

golem_status golem_runtime_profile_cache_close(golem_runtime_profile_cache *cache)
{
    if (!cache)
        return GOLEM_OK;
    if (cache->busy)
        return GOLEM_ERR_INVALID_STATE;
    for (size_t i = 0; i < GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS; ++i)
        if (cache->slots[i].pins)
            return GOLEM_ERR_INVALID_STATE;
    for (size_t i = 0; i < GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS; ++i)
        golem_runtime_profile_free(cache->slots[i].profile);
    golem_allocator allocator = cache->allocator;
    return golem_allocator_free(&allocator, cache);
}
