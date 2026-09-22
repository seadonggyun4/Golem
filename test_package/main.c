#include "golem/core.h"
#include "golem/document.h"
#include "golem/discovery.h"
#include "golem/workflow.h"
#include "golem/agent_session.h"
#include "golem/execution.h"
#include "golem/reentry.h"
#include "golem/completion.h"
#include "golem/version.h"
#include <string.h>

int main(void)
{
    static const char reentry_status[]="{\"schema_version\":1,\"operation\":\"status\"}";
    static const char completion_resume[]="{\"schema_version\":1,\"operation\":\"resume\",\"selection_id\":\"selection\"}";
    if(golem_completion_validate((golem_bytes){(const uint8_t *)completion_resume,sizeof(completion_resume)-1},NULL)!=GOLEM_OK) return 1;
    if(golem_reentry_validate((golem_bytes){(const uint8_t *)reentry_status,sizeof(reentry_status)-1},NULL)!=GOLEM_OK) return 1;
    golem_digest digest;
    if(golem_execution_contract_validate((golem_bytes){NULL,0},&digest,NULL)!=GOLEM_ERR_PARSE) return 1;
    const char *request="{\"schema_version\":1,\"operation\":\"status\",\"work_id\":\"work\"}";
    if(golem_agent_request_validate((golem_bytes){(const uint8_t *)request,strlen(request)},NULL)!=GOLEM_OK) return 1;
    golem_dependency_node node = {"work", "plan", 1, {{1}}, NULL, 0};
    golem_document_freshness state;
    if (golem_document_graph_evaluate(&node, 1, NULL, &state, 1, NULL) != GOLEM_OK ||
        state != GOLEM_DOCUMENT_CURRENT) return 1;
    golem_discovery_result discovery;
    if (golem_discovery_validate((golem_bytes){NULL, 0}, &discovery, NULL) != GOLEM_ERR_PARSE) return 1;
    if (golem_document_validate((golem_bytes){NULL, 0},
        (golem_bytes){NULL, 0}, NULL) != GOLEM_ERR_PARSE) return 1;
    golem_graph_spec spec;
    golem_stage_graph *graph = NULL;
    if (strcmp(golem_version_string(), GOLEM_VERSION_STRING) != 0 ||
        golem_stage_graph_default_spec(&spec) != GOLEM_OK ||
        spec.count != GOLEM_STAGE_COUNT ||
        golem_stage_graph_create(&spec, &graph) != GOLEM_OK) return 1;
    golem_stage_graph_free(graph);
    return 0;
}
