#ifndef GOLEM_LINEAGE_INTERNAL_H
#define GOLEM_LINEAGE_INTERNAL_H
#include "golem/lineage.h"
#define GOLEM_LINEAGE_HEADER_BYTES 32u
#define GOLEM_LINEAGE_STAGE_BYTES 32u
#define GOLEM_LINEAGE_NODE_BYTES 64u
#define GOLEM_LINEAGE_MAX_BYTES (32u + GOLEM_LINEAGE_MAX_RUN_ID + \
    32u * GOLEM_LINEAGE_MAX_STAGES + 64u * GOLEM_LINEAGE_MAX_NODES + 4u * GOLEM_LINEAGE_MAX_EDGES)
typedef struct golem_lineage_entry {
    golem_lineage_node node;
    uint32_t start, count;
} golem_lineage_entry;
struct golem_lineage {
    golem_allocator allocator;
    char *run_id;
    golem_lineage_limits limits;
    golem_lineage_stats stats;
    golem_lineage_stage *stages;
    golem_lineage_entry *nodes;
    golem_lineage_id *edges;
};
golem_status golem_lineage_report(golem_diagnostic *d, golem_status status, const char *message);
golem_status golem_lineage_validate(const golem_lineage *graph);
#endif
