#ifndef GOLEM_INTENT_OBJECT_GRAPH_H
#define GOLEM_INTENT_OBJECT_GRAPH_H
#include "schema.h"
typedef struct gi_object_graph {
    golem_bytes baseline;
    gi_source_input *sources;
    size_t source_count;
    gi_baseline_coverage_result coverage;
} gi_object_graph;
/* Owns exact bytes in baseline source order. Failure leaves out unchanged.
 * byte_limit bounds retained original bytes, not allocator overhead. */
golem_status gi_object_graph_load(int root, golem_bytes preparation,
    size_t byte_limit, gi_object_graph *out);
void gi_object_graph_dispose(gi_object_graph *graph);
/* Read-only complete baseline/source/raw membership and coverage verification.
 * No referent expansion beyond approved source objects, no adoption or ACTIVE. */
golem_status gi_object_graph_validate(int root, golem_bytes preparation,
    gi_baseline_coverage_result *out);
#endif
