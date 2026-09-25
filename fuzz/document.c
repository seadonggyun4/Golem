#include "golem/document.h"
#include "golem/approval.h"
#include "golem/event_reader.h"
#include "golem/discovery.h"
#include "golem/workflow.h"
#include "golem/workflow_template.h"
#include "golem/agent_session.h"
#include "golem/session_binding.h"
#include "golem/execution.h"
#include "golem/proof.h"
#include "golem/candidate.h"
#include "golem/inventory.h"
#include "golem/reentry.h"
#include "golem/completion.h"
#include "golem/role_contract.h"
#include "golem/research.h"
#include "golem/runtime_profile.h"
#include "golem/context.h"
#include "golem/runtime_event.h"
#include "../src/inventory/git_record.h"
#include <stddef.h>
#include <stdint.h>
int LLVMFuzzerTestOneInput(const uint8_t *data,size_t size)
{
    static const char meta[] =
        "{\"schema_version\":1,\"work_id\":\"work\",\"document_id\":\"plan\",\"revision\":1,"
        "\"kind\":\"planning\",\"stage\":\"planning\",\"producer_attempt\":\"attempt\","
        "\"parents\":[],\"requirement_ids\":[\"REQ-1\"],\"scope_revision\":1,\"template_version\":1,"
        "\"policy_version\":1,\"source_snapshot\":\"0000000000000000000000000000000000000000000000000000000000000000\","
        "\"supersedes\":\"\",\"expected_generation\":1}";
    if(size>GOLEM_DOCUMENT_MAX_BODY+1) return 0;
    in_git_entry git_entry;
    (void)in_git_entry_parse((golem_bytes){data,size}, false, &git_entry);
    (void)in_git_entry_parse((golem_bytes){data,size}, true, &git_entry);
    golem_runtime_cursor cursor;
    (void)golem_runtime_cursor_parse((golem_string_view){(const char *)data,size}, &cursor);
    if (golem_runtime_cursor_parse((golem_string_view){(const char *)data,size}, &cursor) == GOLEM_OK) {
        golem_runtime_event event = {.version = 1, .cursor = cursor,
            .kind = GOLEM_EVENT_QUEUED, .origin = GOLEM_EVENT_ADMISSION_JOURNAL};
        char frame[1024]; size_t frame_size;
        (void)golem_runtime_event_sse(&event, frame, sizeof(frame), &frame_size);
        (void)golem_runtime_event_sse(&event, frame, size % sizeof(frame), &frame_size);
    }
    (void)golem_context_request_validate((golem_bytes){data,size},NULL);
    golem_runtime_profile *profile = NULL;
    (void)golem_runtime_profile_parse((golem_bytes){data,size},NULL,&profile,NULL);
    golem_runtime_profile_free(profile);
    (void)golem_agent_request_validate((golem_bytes){data,size},NULL);
    (void)golem_approval_request_validate((golem_bytes){data,size});
    (void)golem_session_binding_request_validate((golem_bytes){data,size});
    (void)golem_reentry_validate((golem_bytes){data,size},NULL);
    (void)golem_completion_validate((golem_bytes){data,size},NULL);
    (void)golem_research_validate((golem_bytes){data,size},NULL);
    (void)golem_research_redaction_validate((golem_bytes){data,size},NULL);
    (void)golem_research_bundle_verify((golem_bytes){data,size},NULL);
    (void)golem_proof_integrity((golem_bytes){data,size},NULL,NULL);
    golem_digest contract_digest;
    (void)golem_workflow_template_validate((golem_bytes){data,size},&contract_digest);
    golem_execution_reply expanded = {0};
    (void)golem_workflow_template_expand((golem_bytes){data,size}, (golem_bytes){data,size}, &expanded);
    golem_execution_reply_free(&expanded);
    (void)golem_role_validate((golem_bytes){data,size},&contract_digest,NULL);
    (void)golem_role_request_validate((golem_bytes){data,size},NULL);
    (void)golem_candidate_validate((golem_bytes){data,size},&contract_digest,NULL);
    (void)golem_inventory_policy_validate((golem_bytes){data,size},NULL);
    static const char inventory_policy[] = "{\"schema_version\":1,\"protected\":[],\"excluded\":[],\"limit\":{\"mode\":\"UNLIMITED\"}}";
    golem_inventory_reply inventory = {0};
    (void)golem_inventory_compare((golem_bytes){data,size},(golem_bytes){data,size},
        (golem_bytes){(const uint8_t *)inventory_policy,sizeof(inventory_policy)-1},&inventory,NULL);
    golem_inventory_reply_free(&inventory);
    (void)golem_execution_contract_validate((golem_bytes){data,size},&contract_digest,NULL);
    /* Mutate bounded typed edges as well as serialized document envelopes. */
    if(size>=4) {
        golem_dependency_node nodes[16];
        golem_document_freshness states[16];
        size_t parents[16];
        static const char *ids[]={"a","b","c","d","e","f","g","h",
                                  "i","j","k","l","m","n","o","p"};
        size_t count=size/4; if(count>16) count=16;
        for(size_t i=0;i<count;++i) {
            parents[i]=data[4*i+2]%17;
            nodes[i]=(golem_dependency_node){"work",ids[data[4*i]%16],
                1u+data[4*i+1]%4u,{{1}},&parents[i],data[4*i+3]%2u};
        }
        (void)golem_document_graph_evaluate(nodes,count,NULL,states,count,NULL);
    }
    golem_discovery_result result;
    (void)golem_discovery_validate((golem_bytes){data,size},&result,NULL);
    size_t required;
    (void)golem_discovery_report((golem_bytes){data,size},"research",NULL,0,&required,NULL);
    (void)golem_work_spec_validate((golem_bytes){data,size},NULL);
    (void)golem_document_validate((golem_bytes){data,size},(golem_bytes){data,size},NULL);
    (void)golem_document_validate((golem_bytes){(const uint8_t *)meta,sizeof(meta)-1},(golem_bytes){data,size},NULL);
    return 0;
}
