#include "internal.h"
#include <string.h>

static void put32(uint8_t *p, uint32_t v)
{
    for (size_t i = 0; i < 4; ++i) p[i] = (uint8_t)(v >> (8 * i));
}
static uint32_t get32(const uint8_t *p)
{
    uint32_t v = 0;
    for (size_t i = 0; i < 4; ++i) v |= (uint32_t)p[i] << (8 * i);
    return v;
}
static void put64(uint8_t *p, uint64_t v)
{
    for (size_t i = 0; i < 8; ++i) p[i] = (uint8_t)(v >> (8 * i));
}
static uint64_t get64(const uint8_t *p)
{
    uint64_t v = 0;
    for (size_t i = 0; i < 8; ++i) v |= (uint64_t)p[i] << (8 * i);
    return v;
}

golem_status golem_lineage_encode(const golem_lineage *g, void *buffer, size_t capacity,
    size_t *required, golem_diagnostic *d)
{
    if (required == NULL || (buffer == NULL && capacity != 0))
        return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    golem_status status = golem_lineage_validate(g);
    if (status != GOLEM_OK) return golem_lineage_report(d, status, NULL);
    size_t length = strlen(g->run_id);
    size_t size = GOLEM_LINEAGE_HEADER_BYTES + length + GOLEM_LINEAGE_STAGE_BYTES * g->stats.stages +
        GOLEM_LINEAGE_NODE_BYTES * g->stats.nodes + 4u * g->stats.edges;
    *required = size;
    if (capacity < size) return golem_lineage_report(d, GOLEM_ERR_BUFFER_TOO_SMALL, NULL);
    uint8_t *p = buffer;
    memset(p, 0, GOLEM_LINEAGE_HEADER_BYTES);
    memcpy(p, "HWLG", 4); p[4] = GOLEM_LINEAGE_VERSION;
    put32(p + 8, (uint32_t)size); put32(p + 12, (uint32_t)length);
    put32(p + 16, g->stats.stages); put32(p + 20, g->stats.nodes); put32(p + 24, g->stats.edges);
    p += GOLEM_LINEAGE_HEADER_BYTES;
    memcpy(p, g->run_id, length); p += length;
    for (uint32_t i = 0; i < g->stats.stages; ++i) {
        const golem_lineage_stage *stage = &g->stages[i];
        put32(p, (uint32_t)stage->execution.stage); put32(p + 4, (uint32_t)stage->execution.status);
        put32(p + 8, (uint32_t)stage->execution.failure); put32(p + 12, stage->execution.attempt);
        put64(p + 16, stage->execution.sequence); put32(p + 24, stage->input); put32(p + 28, stage->last_node);
        p += GOLEM_LINEAGE_STAGE_BYTES;
    }
    for (uint32_t i = 0; i < g->stats.nodes; ++i) {
        const golem_lineage_entry *entry = &g->nodes[i];
        put32(p, (uint32_t)entry->node.kind); put32(p + 4, (uint32_t)entry->node.stage_sequence);
        put32(p + 8, entry->start); put32(p + 12, entry->count);
        size_t encoded;
        (void)golem_receipt_encode(&entry->node.content, p + 16, GOLEM_RECEIPT_SIZE, &encoded);
        p += GOLEM_LINEAGE_NODE_BYTES;
    }
    for (uint32_t i = 0; i < g->stats.edges; ++i) { put32(p, g->edges[i]); p += 4; }
    return golem_lineage_report(d, GOLEM_OK, NULL);
}

golem_status golem_lineage_decode(golem_bytes bytes, const golem_allocator *allocator,
    golem_lineage **out, golem_diagnostic *d)
{
    if (out == NULL || (bytes.data == NULL && bytes.size != 0) || golem_allocator_validate(allocator) != GOLEM_OK)
        return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (bytes.size < GOLEM_LINEAGE_HEADER_BYTES || memcmp(bytes.data, "HWLG", 4) != 0)
        return golem_lineage_report(d, GOLEM_ERR_PARSE, "invalid lineage header");
    const uint8_t *p = bytes.data;
    if (p[4] != GOLEM_LINEAGE_VERSION || p[5] != 0)
        return golem_lineage_report(d, GOLEM_ERR_UNSUPPORTED_VERSION, NULL);
    uint32_t length = get32(p + 12);
    golem_lineage_limits limits = {get32(p + 16), get32(p + 20), get32(p + 24)};
    if (p[6] != 0 || p[7] != 0 || get32(p + 28) != 0 ||
        length == 0 || length > GOLEM_LINEAGE_MAX_RUN_ID ||
        limits.stages == 0 || limits.stages > GOLEM_LINEAGE_MAX_STAGES ||
        limits.nodes == 0 || limits.nodes > GOLEM_LINEAGE_MAX_NODES ||
        limits.edges == 0 || limits.edges > GOLEM_LINEAGE_MAX_EDGES)
        return golem_lineage_report(d, GOLEM_ERR_PARSE, "invalid lineage bounds/flags");
    size_t expected = GOLEM_LINEAGE_HEADER_BYTES + length + GOLEM_LINEAGE_STAGE_BYTES * limits.stages +
        GOLEM_LINEAGE_NODE_BYTES * limits.nodes + 4u * limits.edges;
    if (expected != bytes.size || get32(p + 8) != expected)
        return golem_lineage_report(d, GOLEM_ERR_PARSE, "lineage size mismatch");
    p += GOLEM_LINEAGE_HEADER_BYTES;
    char run_id[GOLEM_LINEAGE_MAX_RUN_ID + 1];
    if (memchr(p, 0, length) != NULL) return golem_lineage_report(d, GOLEM_ERR_PARSE, "embedded NUL in run ID");
    memcpy(run_id, p, length); run_id[length] = '\0'; p += length;
    golem_lineage *g = NULL;
    golem_status status = golem_lineage_create(run_id, &limits, allocator, &g, d);
    if (status != GOLEM_OK) return status;
    g->stats = (golem_lineage_stats){limits.stages, limits.nodes, limits.edges, false};
    for (uint32_t i = 0; i < limits.stages; ++i) {
        /* Range-check before enum conversions to avoid implementation-defined values. */
        if (get32(p) >= GOLEM_STAGE_COUNT || get32(p + 4) > GOLEM_STAGE_CANCELLED ||
            get32(p + 8) >= GOLEM_FAILURE_COUNT) { status = GOLEM_ERR_INVALID_GRAPH; break; }
        g->stages[i] = (golem_lineage_stage){{(golem_stage)get32(p), (golem_stage_status)get32(p + 4),
            (golem_failure)get32(p + 8), get32(p + 12), get64(p + 16)}, get32(p + 24), get32(p + 28)};
        p += GOLEM_LINEAGE_STAGE_BYTES;
    }
    for (uint32_t i = 0; status == GOLEM_OK && i < limits.nodes; ++i) {
        if (get32(p) < GOLEM_LINEAGE_STAGE_INPUT || get32(p) > GOLEM_LINEAGE_EVIDENCE) {
            status = GOLEM_ERR_INVALID_GRAPH; break;
        }
        golem_lineage_entry *entry = &g->nodes[i];
        entry->node.kind = (golem_lineage_kind)get32(p);
        entry->node.stage_sequence = get32(p + 4); entry->start = get32(p + 8); entry->count = get32(p + 12);
        status = golem_receipt_decode((golem_bytes){p + 16, GOLEM_RECEIPT_SIZE}, &entry->node.content);
        p += GOLEM_LINEAGE_NODE_BYTES;
    }
    if (status == GOLEM_OK) {
        for (uint32_t i = 0; i < limits.edges; ++i) { g->edges[i] = get32(p); p += 4; }
        status = golem_lineage_validate(g);
    }
    if (status != GOLEM_OK) golem_lineage_free(g);
    else *out = g;
    return golem_lineage_report(d, status, NULL);
}
