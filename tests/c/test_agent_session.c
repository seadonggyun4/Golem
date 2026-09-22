#include "golem/agent_session.h"
#include "test.h"
#include <string.h>
int main(void)
{
    const char *valid="{\"schema_version\":1,\"operation\":\"start\",\"work_id\":\"work\",\"key\":\"start\",\"expected_sequence\":0,\"selection_id\":\"selection\"}";
    CHECK(golem_agent_request_validate((golem_bytes){(const uint8_t *)valid,strlen(valid)},NULL)==GOLEM_OK);
    const char *invalid[]={"null","[]","{}","{\"schema_version\":2}",
        "{\"schema_version\":1,\"schema_version\":1,\"operation\":\"status\",\"work_id\":\"work\"}",
        "{\"schema_version\":1,\"operation\":\"start\",\"work_id\":\"work\",\"key\":\"start\",\"expected_sequence\":-1,\"selection_id\":\"selection\"}",
        "{\"schema_version\":1,\"operation\":\"start\",\"work_id\":\"work\",\"key\":\"start\",\"expected_sequence\":false,\"selection_id\":\"selection\"}"};
    for(size_t i=0;i<sizeof(invalid)/sizeof(*invalid);++i)
        CHECK(golem_agent_request_validate((golem_bytes){(const uint8_t *)invalid[i],strlen(invalid[i])},NULL)!=GOLEM_OK);
    CHECK(golem_agent_request_validate((golem_bytes){NULL,0},NULL)!=GOLEM_OK);
    golem_agent_reply reply={(uint8_t *)(uintptr_t)1,17};
    CHECK(golem_agent_session_call(NULL,(golem_bytes){NULL,0},NULL,&reply,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(reply.data==(uint8_t *)(uintptr_t)1 && reply.size==17);
    reply=(golem_agent_reply){malloc(1),1}; CHECK(reply.data);
    golem_agent_reply_free(&reply); CHECK(!reply.data && !reply.size);
    golem_agent_reply_free(&reply); golem_agent_reply_free(NULL);
    return 0;
}
