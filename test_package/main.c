#include "golem/core.h"
#include "golem/version.h"
#include <string.h>

int main(void)
{
    golem_graph_spec spec;
    golem_stage_graph *graph = NULL;
    if (strcmp(golem_version_string(), GOLEM_VERSION_STRING) != 0 ||
        golem_stage_graph_default_spec(&spec) != GOLEM_OK ||
        spec.count != GOLEM_STAGE_COUNT ||
        golem_stage_graph_create(&spec, &graph) != GOLEM_OK) return 1;
    golem_stage_graph_free(graph);
    return 0;
}
