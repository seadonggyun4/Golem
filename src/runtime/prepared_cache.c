#include "golem/prepared_runtime.h"
#include <string.h>

struct golem_prepared_runtime {
    golem_digest profile, dependencies, content;
    uint8_t *bytes;
    size_t size, pins;
    uint64_t born;
    bool valid;
};
struct golem_prepared_cache {
    golem_allocator allocator;
    golem_prepared_options options;
    golem_prepared_runtime slots[GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS];
    size_t next;
    uint64_t last_time;
    bool busy, clock_seen;
};
static bool equal(const golem_digest *a, const golem_digest *b)
{
    return memcmp(a->bytes, b->bytes, sizeof(a->bytes)) == 0;
}
static void invalidate(golem_prepared_cache *c)
{
    for (size_t i = 0; i < c->options.capacity; ++i)
        c->slots[i].valid = false;
}
static golem_status clock_read(golem_prepared_cache *c, uint64_t *now)
{
    golem_status st = c->options.clock_ns(c->options.context, now);
    if (st == GOLEM_OK && c->clock_seen && *now < c->last_time)
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK) {
        c->last_time = *now;
        c->clock_seen = true;
    }
    return st;
}
golem_status golem_prepared_cache_create(const golem_prepared_options *o, const golem_allocator *a,
                                         golem_prepared_cache **out)
{
    if (!o || !out || o->size != sizeof(*o) || o->version != 1 || !o->capacity ||
        o->capacity > GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS || !o->max_bytes ||
        o->max_bytes > GOLEM_RUNTIME_PROFILE_MAX_BYTES || !o->ttl_ns ||
        o->ttl_ns > UINT64_C(3600000000000) || !o->observe || !o->prepare || !o->clock_ns ||
        golem_allocator_validate(a) != GOLEM_OK)
        return GOLEM_ERR_INVALID_ARGUMENT;
    void *memory = NULL;
    golem_status st = golem_allocator_alloc_zero(a, 1, sizeof(golem_prepared_cache), &memory);
    if (st == GOLEM_OK) {
        golem_prepared_cache *c = memory;
        c->allocator = a ? *a : golem_allocator_default();
        c->options = *o;
        *out = c;
    }
    return st;
}
golem_status golem_prepared_cache_acquire(golem_prepared_cache *c,
                                          const golem_runtime_profile *profile,
                                          const golem_prepared_runtime **out)
{
    if (!c || !profile || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (c->busy)
        return GOLEM_ERR_INVALID_STATE;
    c->busy = true;
    golem_digest identity, dependencies = {{0}};
    uint64_t now = 0;
    golem_status st = golem_runtime_profile_digest(profile, &identity);
    if (st == GOLEM_OK)
        st = c->options.observe(c->options.context, profile, &dependencies);
    if (st == GOLEM_OK)
        st = clock_read(c, &now);
    size_t chosen = c->options.capacity;
    if (st == GOLEM_OK) {
        for (size_t i = 0; i < c->options.capacity; ++i) {
            golem_prepared_runtime *r = &c->slots[i];
            if (!r->valid || !equal(&identity, &r->profile) ||
                !equal(&dependencies, &r->dependencies))
                continue;
            if (now - r->born >= c->options.ttl_ns) {
                r->valid = false;
                continue;
            }
            if (r->pins == SIZE_MAX)
                st = GOLEM_ERR_OVERFLOW;
            else {
                ++r->pins;
                *out = r;
            }
            c->busy = false;
            return st;
        }
        for (size_t i = 0; i < c->options.capacity; ++i) {
            size_t n = (c->next + i) % c->options.capacity;
            if (!c->slots[n].pins) {
                chosen = n;
                break;
            }
        }
        if (chosen == c->options.capacity)
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    void *bytes = NULL;
    size_t used = 0;
    if (st == GOLEM_OK)
        st = golem_allocator_alloc(&c->allocator, c->options.max_bytes, &bytes);
    if (st == GOLEM_OK)
        st = c->options.prepare(c->options.context, profile, bytes, c->options.max_bytes, &used);
    if (st == GOLEM_OK && (!used || used > c->options.max_bytes))
        st = GOLEM_ERR_SIZE_MISMATCH;
    golem_digest after = {{0}}, content;
    if (st == GOLEM_OK)
        st = c->options.observe(c->options.context, profile, &after);
    if (st == GOLEM_OK && !equal(&dependencies, &after))
        st = GOLEM_ERR_STALE_RESULT;
    uint64_t finish = 0;
    if (st == GOLEM_OK)
        st = clock_read(c, &finish);
    if (st == GOLEM_OK && finish - now >= c->options.ttl_ns)
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK)
        st = golem_digest_bytes((golem_bytes){bytes, used}, &content);
    if (st == GOLEM_OK) {
        golem_prepared_runtime *r = &c->slots[chosen];
        (void)golem_allocator_free(&c->allocator, r->bytes);
        *r = (golem_prepared_runtime){.profile = identity,
                                      .dependencies = dependencies,
                                      .content = content,
                                      .bytes = bytes,
                                      .size = used,
                                      .pins = 1,
                                      .born = now,
                                      .valid = true};
        c->next = (chosen + 1) % c->options.capacity;
        *out = r;
    } else {
        (void)golem_allocator_free(&c->allocator, bytes);
        invalidate(c);
    }
    c->busy = false;
    return st;
}
golem_status golem_prepared_runtime_view(const golem_prepared_runtime *r, golem_bytes *bytes,
                                         golem_digest *profile, golem_digest *dependencies,
                                         golem_digest *content)
{
    if (!r || !bytes || !profile || !dependencies || !content)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (!r->pins)
        return GOLEM_ERR_INVALID_STATE;
    *bytes = (golem_bytes){r->bytes, r->size};
    *profile = r->profile;
    *dependencies = r->dependencies;
    *content = r->content;
    return GOLEM_OK;
}
golem_status golem_prepared_cache_invalidate(golem_prepared_cache *c)
{
    if (!c)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (c->busy)
        return GOLEM_ERR_INVALID_STATE;
    invalidate(c);
    return GOLEM_OK;
}
golem_status golem_prepared_cache_release(golem_prepared_cache *c, const golem_prepared_runtime *r)
{
    if (!c || !r)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (c->busy)
        return GOLEM_ERR_INVALID_STATE;
    for (size_t i = 0; i < c->options.capacity; ++i) {
        if (&c->slots[i] == r && c->slots[i].pins) {
            --c->slots[i].pins;
            return GOLEM_OK;
        }
    }
    return GOLEM_ERR_INVALID_STATE;
}
golem_status golem_prepared_cache_close(golem_prepared_cache *c)
{
    if (!c)
        return GOLEM_OK;
    if (c->busy)
        return GOLEM_ERR_INVALID_STATE;
    for (size_t i = 0; i < c->options.capacity; ++i)
        if (c->slots[i].pins)
            return GOLEM_ERR_INVALID_STATE;
    golem_allocator a = c->allocator;
    for (size_t i = 0; i < c->options.capacity; ++i)
        (void)golem_allocator_free(&a, c->slots[i].bytes);
    return golem_allocator_free(&a, c);
}
