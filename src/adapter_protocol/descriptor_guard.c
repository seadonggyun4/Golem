#include "descriptor_internal.h"
#include <string.h>

static bool nonzero(const golem_digest *d)
{
    golem_digest zero = {{0}};
    return memcmp(d, &zero, sizeof(*d)) != 0;
}
golem_status golem_harness_guard_check(const golem_harness_guard *g, const golem_adapter_request *r,
                                       const golem_adapter_capability *c,
                                       golem_evidence_store *store)
{
    if (!g || g->size != sizeof(*g) || g->version != 1 || !g->claimed || !g->required ||
        !g->observe || !g->now || !g->epoch || !nonzero(&g->profile_digest) ||
        !nonzero(&g->binding_digest) || !nonzero(&g->clock_domain) || !r || !c)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_digest digest;
    golem_status s = golem_adapter_descriptor_digest(g->claimed, &digest);
    if (s != GOLEM_OK)
        return s;
    if (memcmp(&digest, &g->descriptor_digest, sizeof(digest)) ||
        strcmp(c->adapter_id, g->claimed->adapter_id) || strcmp(r->adapter_id, c->adapter_id) ||
        c->stages != g->claimed->stages || c->effect != g->claimed->effect ||
        g->claimed->simulation != (c->simulation ? GOLEM_HARNESS_YES : GOLEM_HARNESS_NO))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    if (r->stage < 0 || r->stage >= GOLEM_STAGE_COUNT || !(g->required->stages & (1u << r->stage)))
        return GOLEM_ERR_POLICY_DENIED;
    golem_harness_observation observation = {0};
    s = g->observe(g->context, &observation);
    if (s != GOLEM_OK)
        return s;
    uint64_t now = 0;
    s = g->now(g->context, &now);
    if (s != GOLEM_OK)
        return s;
    if (observation.epoch != g->epoch ||
        memcmp(&observation.profile_digest, &g->profile_digest, sizeof(digest)) ||
        memcmp(&observation.binding_digest, &g->binding_digest, sizeof(digest)) ||
        memcmp(&observation.clock_domain, &g->clock_domain, sizeof(digest)) ||
        !nonzero(&observation.evidence_digest))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    if (observation.observed_ns > now || observation.expires_ns <= now ||
        observation.expires_ns <= observation.observed_ns)
        return GOLEM_ERR_STALE_RESULT;
    s = golem_harness_compatible(g->claimed, &observation.descriptor, g->required);
    uint64_t evidence_size;
    if (s == GOLEM_OK)
        s = golem_evidence_verify(store, &observation.evidence_digest, &evidence_size, NULL);
    /* Evidence verification can take time. Never allow it to carry an expired
     * observation across the dispatch boundary. */
    if (s == GOLEM_OK)
        s = g->now(g->context, &now);
    if (s == GOLEM_OK && (now < observation.observed_ns || now >= observation.expires_ns))
        s = GOLEM_ERR_STALE_RESULT;
    return s;
}
