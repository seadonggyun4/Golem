#include "internal.h"
#include <inttypes.h>
#include <stdio.h>

golem_status golem_lineage_verify(const golem_lineage *g, golem_evidence_store *store,
    size_t *verified, golem_diagnostic *d)
{
    if (store == NULL || verified == NULL) return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    golem_status status = golem_lineage_validate(g);
    if (status != GOLEM_OK) return golem_lineage_report(d, status, NULL);
    for (uint32_t i = 0; i < g->stats.nodes; ++i) {
        const golem_receipt *r = &g->nodes[i].node.content;
        uint64_t size;
        status = golem_evidence_verify(store, &r->digest, &size, NULL);
        if (status == GOLEM_OK && size != r->size) status = GOLEM_ERR_SIZE_MISMATCH;
        if (status != GOLEM_OK) {
            char message[96];
            (void)snprintf(message, sizeof(message), "lineage node %" PRIu32 ": %s", i + 1, golem_status_string(status));
            return golem_lineage_report(d, status, message);
        }
    }
    *verified = g->stats.nodes;
    return golem_lineage_report(d, GOLEM_OK, NULL);
}

golem_status golem_lineage_store(const golem_lineage *g, golem_evidence_store *store,
    golem_digest *out, golem_diagnostic *d)
{
    if (out == NULL) return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    size_t count, size;
    golem_status status = golem_lineage_verify(g, store, &count, d);
    if (status != GOLEM_OK) return status;
    status = golem_lineage_encode(g, NULL, 0, &size, d);
    if (status != GOLEM_ERR_BUFFER_TOO_SMALL) return status;
    void *memory = NULL;
    status = golem_allocator_alloc(&g->allocator, size, &memory);
    if (status == GOLEM_OK) status = golem_lineage_encode(g, memory, size, &size, d);
    golem_receipt stored;
    if (status == GOLEM_OK) status = golem_evidence_put(store, (golem_bytes){memory, size}, &stored, d);
    (void)golem_allocator_free(&g->allocator, memory);
    if (status == GOLEM_OK) *out = stored.digest;
    return golem_lineage_report(d, status, NULL);
}

golem_status golem_lineage_load(golem_evidence_store *store, const golem_digest *key,
    const golem_allocator *allocator, golem_lineage **out, golem_diagnostic *d)
{
    if (out == NULL) return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    uint8_t *data = NULL;
    size_t size;
    golem_status status = golem_evidence_read(store, key, GOLEM_LINEAGE_MAX_BYTES, allocator, &data, &size, d);
    if (status != GOLEM_OK) return status;
    golem_lineage *g = NULL;
    status = golem_lineage_decode((golem_bytes){data, size}, allocator, &g, d);
    (void)golem_allocator_free(allocator, data);
    size_t verified;
    if (status == GOLEM_OK) status = golem_lineage_verify(g, store, &verified, d);
    if (status == GOLEM_OK) *out = g;
    else golem_lineage_free(g);
    return status;
}
