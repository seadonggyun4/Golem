#include "internal.h"
#include <string.h>

golem_status golem_lineage_report(golem_diagnostic *d, golem_status status, const char *message)
{
    if (d != NULL) (void)golem_diagnostic_set(d, status, GOLEM_DIAGNOSTIC_NO_OFFSET, message);
    return status;
}

static bool limits_valid(golem_lineage_limits l)
{
    return l.stages > 0 && l.stages <= GOLEM_LINEAGE_MAX_STAGES &&
        l.nodes > 0 && l.nodes <= GOLEM_LINEAGE_MAX_NODES &&
        l.edges > 0 && l.edges <= GOLEM_LINEAGE_MAX_EDGES;
}

golem_status golem_lineage_create(const char *run_id, const golem_lineage_limits *limits,
    const golem_allocator *allocator, golem_lineage **out, golem_diagnostic *d)
{
    golem_lineage_limits l = limits == NULL ? (golem_lineage_limits){64, 1024, 4096} : *limits;
    if (run_id == NULL || out == NULL || !limits_valid(l) || golem_allocator_validate(allocator) != GOLEM_OK)
        return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    size_t length = 0;
    while (length <= GOLEM_LINEAGE_MAX_RUN_ID && run_id[length] != '\0') ++length;
    if (length == 0 || length > GOLEM_LINEAGE_MAX_RUN_ID)
        return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, "invalid run ID length");
    void *memory = NULL;
    golem_status status = golem_allocator_alloc(allocator, sizeof(golem_lineage), &memory);
    if (status != GOLEM_OK) return golem_lineage_report(d, status, NULL);
    golem_lineage *g = memory;
    *g = (golem_lineage){0};
    g->allocator = allocator == NULL ? golem_allocator_default() : *allocator;
    g->limits = l;
    status = golem_allocator_alloc(&g->allocator, length + 1, &memory);
    if (status == GOLEM_OK) { g->run_id = memory; memcpy(g->run_id, run_id, length + 1); }
    if (status == GOLEM_OK) status = golem_allocator_alloc(&g->allocator, l.stages * sizeof(*g->stages), &memory);
    if (status == GOLEM_OK) g->stages = memory;
    if (status == GOLEM_OK) status = golem_allocator_alloc(&g->allocator, l.nodes * sizeof(*g->nodes), &memory);
    if (status == GOLEM_OK) g->nodes = memory;
    if (status == GOLEM_OK) status = golem_allocator_alloc(&g->allocator, l.edges * sizeof(*g->edges), &memory);
    if (status == GOLEM_OK) g->edges = memory;
    if (status != GOLEM_OK) golem_lineage_free(g);
    else *out = g;
    return golem_lineage_report(d, status, NULL);
}

void golem_lineage_free(golem_lineage *g)
{
    if (g == NULL) return;
    (void)golem_allocator_free(&g->allocator, g->edges);
    (void)golem_allocator_free(&g->allocator, g->nodes);
    (void)golem_allocator_free(&g->allocator, g->stages);
    (void)golem_allocator_free(&g->allocator, g->run_id);
    (void)golem_allocator_free(&g->allocator, g);
}
const char *golem_lineage_run_id_borrow(const golem_lineage *g) { return g == NULL ? NULL : g->run_id; }
golem_status golem_lineage_stats_get(const golem_lineage *g, golem_lineage_stats *out)
{
    if (g == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    *out = g->stats; return GOLEM_OK;
}
golem_status golem_lineage_stage_get(const golem_lineage *g, uint64_t sequence, golem_lineage_stage *out)
{
    if (g == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (sequence == 0 || sequence > g->stats.stages) return GOLEM_ERR_NOT_FOUND;
    *out = g->stages[sequence - 1]; return GOLEM_OK;
}
golem_status golem_lineage_node_get(const golem_lineage *g, golem_lineage_id id, golem_lineage_node *out)
{
    if (g == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (id == 0 || id > g->stats.nodes) return GOLEM_ERR_NOT_FOUND;
    *out = g->nodes[id - 1].node; return GOLEM_OK;
}

static golem_status receipt_valid(const golem_receipt *r)
{
    size_t required;
    golem_status status = golem_receipt_encode(r, NULL, 0, &required);
    return status == GOLEM_ERR_BUFFER_TOO_SMALL ? GOLEM_OK : status;
}

static golem_status snapshot(const golem_lineage *g, const golem_work_run *run, golem_stage_snapshot *out)
{
    if (run == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (strcmp(g->run_id, golem_work_run_id_borrow(run)) != 0) return GOLEM_ERR_IDENTITY_MISMATCH;
    const golem_stage_run *stage = golem_work_run_stage_borrow(run);
    if (stage == NULL) return GOLEM_ERR_INVALID_STATE;
    return golem_stage_run_snapshot_get(stage, out);
}

static golem_status parents_valid(const golem_lineage *g, const golem_lineage_id *parents,
    size_t count, bool input, uint32_t first)
{
    if (count != 0 && parents == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (count > GOLEM_LINEAGE_MAX_EDGES) return GOLEM_ERR_OVERFLOW;
    if ((first == 1 && input) ? count != 0 : count == 0) return GOLEM_ERR_INVALID_GRAPH;
    for (size_t i = 0; i < count; ++i) {
        uint32_t id = parents[i];
        if (id == 0 || id > g->stats.nodes || (i != 0 && id <= parents[i - 1])) return GOLEM_ERR_INVALID_GRAPH;
        if (input) {
            if (id >= first || g->nodes[id - 1].node.kind != GOLEM_LINEAGE_EVIDENCE)
                return GOLEM_ERR_INVALID_GRAPH;
        } else if (id < first) return GOLEM_ERR_INVALID_GRAPH;
    }
    return GOLEM_OK;
}

static void append(golem_lineage *g, golem_lineage_kind kind, const golem_receipt *receipt,
    const golem_lineage_id *parents, size_t count, golem_lineage_id *out)
{
    uint32_t id = ++g->stats.nodes;
    g->nodes[id - 1] = (golem_lineage_entry){{kind, g->stats.stages, *receipt}, g->stats.edges, (uint32_t)count};
    if (count != 0) memcpy(g->edges + g->stats.edges, parents, count * sizeof(*parents));
    g->stats.edges += (uint32_t)count;
    g->stages[g->stats.stages - 1].last_node = id;
    *out = id;
}

golem_status golem_lineage_begin(golem_lineage *g, const golem_work_run *run,
    const golem_receipt *input, const golem_lineage_id *parents, size_t count,
    golem_lineage_id *out, golem_diagnostic *d)
{
    if (g == NULL || out == NULL) return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (g->stats.has_open_stage) return golem_lineage_report(d, GOLEM_ERR_INVALID_STATE, "seal current stage first");
    golem_stage_snapshot stage;
    golem_status status = snapshot(g, run, &stage);
    if (status == GOLEM_OK && stage.status != GOLEM_STAGE_RUNNING) status = GOLEM_ERR_INVALID_STATE;
    if (status == GOLEM_OK && stage.sequence != (uint64_t)g->stats.stages + 1) status = GOLEM_ERR_STALE_RESULT;
    if (status == GOLEM_OK) {
        uint32_t expected = 1;
        for (uint32_t i = 0; i < g->stats.stages; ++i) if (g->stages[i].execution.stage == stage.stage) ++expected;
        if (stage.attempt != expected) status = GOLEM_ERR_STALE_RESULT;
    }
    if (status == GOLEM_OK) status = receipt_valid(input);
    if (status == GOLEM_OK) status = parents_valid(g, parents, count, true, g->stats.nodes + 1);
    if (status == GOLEM_OK && (g->stats.stages == g->limits.stages || g->stats.nodes == g->limits.nodes ||
        count > g->limits.edges - g->stats.edges)) status = GOLEM_ERR_BUFFER_TOO_SMALL;
    if (status == GOLEM_OK) {
        g->stages[g->stats.stages++] = (golem_lineage_stage){stage, g->stats.nodes + 1, 0};
        g->stats.has_open_stage = true;
        append(g, GOLEM_LINEAGE_STAGE_INPUT, input, parents, count, out);
    }
    return golem_lineage_report(d, status, NULL);
}

golem_status golem_lineage_add(golem_lineage *g, golem_lineage_kind kind,
    const golem_receipt *receipt, const golem_lineage_id *parents, size_t count,
    golem_lineage_id *out, golem_diagnostic *d)
{
    if (g == NULL || out == NULL || kind < GOLEM_LINEAGE_CONTEXT_BLOCK || kind > GOLEM_LINEAGE_EVIDENCE)
        return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (!g->stats.has_open_stage) return golem_lineage_report(d, GOLEM_ERR_INVALID_STATE, NULL);
    golem_status status = receipt_valid(receipt);
    if (status == GOLEM_OK) status = parents_valid(g, parents, count, false, g->stages[g->stats.stages - 1].input);
    if (status == GOLEM_OK && (g->stats.nodes == g->limits.nodes || count > g->limits.edges - g->stats.edges))
        status = GOLEM_ERR_BUFFER_TOO_SMALL;
    if (status == GOLEM_OK) append(g, kind, receipt, parents, count, out);
    return golem_lineage_report(d, status, NULL);
}

static bool terminal_valid(golem_stage_snapshot s)
{
    if (s.stage < GOLEM_STAGE_PLANNING || s.stage >= GOLEM_STAGE_COUNT || s.attempt == 0 || s.sequence == 0 ||
        s.failure < GOLEM_FAILURE_NONE || s.failure >= GOLEM_FAILURE_COUNT) return false;
    bool blocked = s.failure == GOLEM_FAILURE_POLICY_DENIED || s.failure == GOLEM_FAILURE_STALE_LEASE ||
        s.failure == GOLEM_FAILURE_BUDGET_EXHAUSTED;
    if (s.status == GOLEM_STAGE_PASSED || s.status == GOLEM_STAGE_CANCELLED) return s.failure == GOLEM_FAILURE_NONE;
    if (s.status == GOLEM_STAGE_BLOCKED) return blocked;
    return s.status == GOLEM_STAGE_FAILED && s.failure != GOLEM_FAILURE_NONE && !blocked;
}

golem_status golem_lineage_seal(golem_lineage *g, const golem_work_run *run, golem_diagnostic *d)
{
    if (g == NULL) return golem_lineage_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (!g->stats.has_open_stage) return golem_lineage_report(d, GOLEM_ERR_INVALID_STATE, NULL);
    golem_stage_snapshot current;
    golem_status status = snapshot(g, run, &current);
    golem_lineage_stage *stage = &g->stages[g->stats.stages - 1];
    if (status == GOLEM_OK && (current.sequence != stage->execution.sequence || current.stage != stage->execution.stage ||
        current.attempt != stage->execution.attempt)) status = GOLEM_ERR_STALE_RESULT;
    if (status == GOLEM_OK && !terminal_valid(current)) status = GOLEM_ERR_INVALID_STATE;
    bool evidence = false;
    for (uint32_t i = stage->input; i <= stage->last_node; ++i)
        evidence |= g->nodes[i - 1].node.kind == GOLEM_LINEAGE_EVIDENCE;
    if (status == GOLEM_OK && !evidence) status = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (status == GOLEM_OK) { stage->execution = current; g->stats.has_open_stage = false; }
    return golem_lineage_report(d, status, NULL);
}

golem_status golem_lineage_validate(const golem_lineage *g)
{
    if (g == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (g->stats.has_open_stage || g->stats.stages == 0) return GOLEM_ERR_INVALID_STATE;
    uint32_t attempts[GOLEM_STAGE_COUNT] = {0}, next = 1, edge = 0;
    for (uint32_t s = 0; s < g->stats.stages; ++s) {
        const golem_lineage_stage *stage = &g->stages[s];
        if (!terminal_valid(stage->execution) || stage->execution.sequence != (uint64_t)s + 1 ||
            stage->execution.attempt != ++attempts[stage->execution.stage] || stage->input != next ||
            stage->last_node < next || stage->last_node > g->stats.nodes) return GOLEM_ERR_INVALID_GRAPH;
        bool evidence = false;
        for (; next <= stage->last_node; ++next) {
            const golem_lineage_entry *entry = &g->nodes[next - 1];
            bool input = next == stage->input;
            if (entry->node.stage_sequence != (uint64_t)s + 1 || entry->node.kind < GOLEM_LINEAGE_STAGE_INPUT ||
                entry->node.kind > GOLEM_LINEAGE_EVIDENCE || (entry->node.kind == GOLEM_LINEAGE_STAGE_INPUT) != input ||
                receipt_valid(&entry->node.content) != GOLEM_OK || entry->start != edge ||
                entry->count > g->stats.edges - edge) return GOLEM_ERR_INVALID_GRAPH;
            if (parents_valid(g, g->edges + edge, entry->count, input, stage->input) != GOLEM_OK)
                return GOLEM_ERR_INVALID_GRAPH;
            for (uint32_t i = 0; i < entry->count; ++i) if (g->edges[edge + i] >= next) return GOLEM_ERR_INVALID_GRAPH;
            edge += entry->count;
            evidence |= entry->node.kind == GOLEM_LINEAGE_EVIDENCE;
        }
        if (!evidence) return GOLEM_ERR_INVALID_GRAPH;
    }
    return next - 1 == g->stats.nodes && edge == g->stats.edges ? GOLEM_OK : GOLEM_ERR_INVALID_GRAPH;
}
