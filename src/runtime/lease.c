#include "golem/lease.h"
#include <openssl/rand.h>
#include <string.h>

struct golem_lease {
    golem_allocator allocator;
    golem_lease_ops ops;
    void *context;
    golem_lease_snapshot current;
    uint64_t watermark, sequence;
    bool busy, poisoned;
};
static bool text_valid(const char *text)
{
    if (text == NULL || text[0] == 0) return false;
    size_t i = 0;
    while (i < GOLEM_LEASE_TEXT_CAPACITY && text[i] != 0) {
        if ((unsigned char)text[i] < 33 || (unsigned char)text[i] > 126) return false;
        ++i;
    }
    return i < GOLEM_LEASE_TEXT_CAPACITY;
}
static golem_status observe(golem_lease *l, uint64_t now)
{
    if (l == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (l->busy) return GOLEM_ERR_INVALID_STATE;
    if (l->poisoned) return GOLEM_ERR_STALE_LEASE;
    if (now < l->watermark) return GOLEM_ERR_INVALID_STATE;
    l->watermark = now; return GOLEM_OK;
}
static golem_status commit(golem_lease *l, golem_lease_event_type type, const golem_lease_snapshot *next)
{
    if (l->sequence == UINT64_MAX) return GOLEM_ERR_OVERFLOW;
    golem_lease_event event = {type, l->sequence + 1, l->watermark, *next};
    l->busy = true;
    golem_status s = l->ops.record(l->context, &event);
    l->busy = false;
    if (s != GOLEM_OK) { l->poisoned = true; return s; }
    l->current = *next; ++l->sequence; return GOLEM_OK;
}
golem_status golem_lease_create(const char *resource, const golem_lease_ops *ops,
    void *context, const golem_allocator *allocator, golem_lease **out)
{
    if (!text_valid(resource) || ops == NULL || ops->record == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status s = golem_allocator_validate(allocator); if (s != GOLEM_OK) return s;
    void *memory = NULL; s = golem_allocator_alloc(allocator, sizeof(golem_lease), &memory);
    if (s != GOLEM_OK) return s;
    golem_lease *l = memory; *l = (golem_lease){0};
    l->allocator = allocator == NULL ? golem_allocator_default() : *allocator;
    l->ops = *ops; l->context = context; l->current.token.version = GOLEM_LEASE_VERSION;
    memcpy(l->current.resource, resource, strlen(resource) + 1);
    if (RAND_bytes(l->current.token.authority, sizeof(l->current.token.authority)) != 1) {
        golem_lease_free(l); return GOLEM_ERR_CRYPTO;
    }
    *out = l; return GOLEM_OK;
}
void golem_lease_free(golem_lease *l)
{
    if (l != NULL) { golem_allocator a = l->allocator; (void)golem_allocator_free(&a, l); }
}
golem_status golem_lease_validate(golem_lease *l, const golem_lease_token *token, uint64_t now)
{
    if (token == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status s = observe(l, now); if (s != GOLEM_OK) return s;
    if (token->version != GOLEM_LEASE_VERSION || !l->current.active || token->fence != l->current.token.fence ||
        memcmp(token->authority, l->current.token.authority, sizeof(token->authority)) != 0 || now >= l->current.expires_ns)
        return GOLEM_ERR_STALE_LEASE;
    return GOLEM_OK;
}
golem_status golem_lease_acquire(golem_lease *l, const char *owner,
    uint64_t now, uint64_t ttl, golem_lease_snapshot *out)
{
    if (!text_valid(owner) || out == NULL || ttl == 0) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status s = observe(l, now); if (s != GOLEM_OK) return s;
    if (l->current.active && now < l->current.expires_ns) return GOLEM_ERR_LEASE_BUSY;
    if (ttl > UINT64_MAX - now || l->current.token.fence == UINT64_MAX) return GOLEM_ERR_OVERFLOW;
    golem_lease_snapshot next = l->current;
    ++next.token.fence; next.active = true; next.expires_ns = now + ttl;
    memset(next.owner, 0, sizeof(next.owner)); memcpy(next.owner, owner, strlen(owner) + 1);
    s = commit(l, GOLEM_LEASE_ACQUIRED, &next);
    if (s == GOLEM_OK) *out = next;
    return s;
}
golem_status golem_lease_heartbeat(golem_lease *l, const golem_lease_token *token,
    uint64_t now, uint64_t ttl, golem_lease_snapshot *out)
{
    if (out == NULL || ttl == 0) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status s = golem_lease_validate(l, token, now); if (s != GOLEM_OK) return s;
    if (ttl > UINT64_MAX - now) return GOLEM_ERR_OVERFLOW;
    if (now + ttl < l->current.expires_ns) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_lease_snapshot next = l->current; next.expires_ns = now + ttl;
    s = commit(l, GOLEM_LEASE_HEARTBEAT, &next);
    if (s == GOLEM_OK) *out = next;
    return s;
}
golem_status golem_lease_release(golem_lease *l, const golem_lease_token *token, uint64_t now)
{
    golem_status s = golem_lease_validate(l, token, now); if (s != GOLEM_OK) return s;
    golem_lease_snapshot next = l->current; next.active = false;
    return commit(l, GOLEM_LEASE_RELEASED, &next);
}
const char *golem_lease_resource_borrow(const golem_lease *l) { return l == NULL ? NULL : l->current.resource; }
