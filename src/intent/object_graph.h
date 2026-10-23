#ifndef GOLEM_INTENT_OBJECT_GRAPH_H
#define GOLEM_INTENT_OBJECT_GRAPH_H
#include "schema.h"
/* Read-only complete baseline/source/raw membership and coverage verification.
 * No referent expansion beyond approved source objects, no adoption or ACTIVE. */
golem_status gi_object_graph_validate(int root, golem_bytes preparation,
    gi_baseline_coverage_result *out);
#endif
