#include "internal.h"
#include <string.h>

golem_status golem_lineage_parents(const golem_lineage *g, golem_lineage_id id,
    golem_lineage_id *buffer, size_t capacity, size_t *required)
{
    if (g == NULL || required == NULL || (buffer == NULL && capacity != 0)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (id == 0 || id > g->stats.nodes) return GOLEM_ERR_NOT_FOUND;
    const golem_lineage_entry *entry = &g->nodes[id - 1];
    *required = entry->count;
    if (capacity < entry->count) return GOLEM_ERR_BUFFER_TOO_SMALL;
    if (entry->count != 0) memcpy(buffer, g->edges + entry->start, entry->count * sizeof(*buffer));
    return GOLEM_OK;
}

golem_status golem_lineage_predecessors(const golem_lineage *g, uint64_t sequence,
    bool transitive, golem_lineage_id *buffer, size_t capacity, size_t *required)
{
    if (g == NULL || required == NULL || (buffer == NULL && capacity != 0)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (sequence == 0 || sequence > g->stats.stages) return GOLEM_ERR_NOT_FOUND;
    uint32_t input = g->stages[sequence - 1].input;
    if (!transitive) return golem_lineage_parents(g, input, buffer, capacity, required);
    uint8_t visited[(GOLEM_LINEAGE_MAX_NODES + 7) / 8] = {0};
    const golem_lineage_entry *entry = &g->nodes[input - 1];
    for (uint32_t i = 0; i < entry->count; ++i) {
        uint32_t index = g->edges[entry->start + i] - 1;
        visited[index / 8] |= (uint8_t)(1u << (index % 8));
    }
    size_t count = 0;
    /* Reverse topological order expands each marked node exactly once. */
    for (uint32_t id = input - 1; id != 0; --id) {
        if ((visited[(id - 1) / 8] & (1u << ((id - 1) % 8))) == 0) continue;
        entry = &g->nodes[id - 1];
        if (entry->node.kind == GOLEM_LINEAGE_EVIDENCE) ++count;
        for (uint32_t i = 0; i < entry->count; ++i) {
            uint32_t index = g->edges[entry->start + i] - 1;
            visited[index / 8] |= (uint8_t)(1u << (index % 8));
        }
    }
    *required = count;
    if (capacity < count) return GOLEM_ERR_BUFFER_TOO_SMALL;
    size_t written = 0;
    for (uint32_t id = 1; id < input; ++id) {
        if ((visited[(id - 1) / 8] & (1u << ((id - 1) % 8))) != 0 &&
            g->nodes[id - 1].node.kind == GOLEM_LINEAGE_EVIDENCE) buffer[written++] = id;
    }
    return GOLEM_OK;
}
