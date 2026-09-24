#include "golem/execution.h"
#include "test.h"
#include <string.h>
int main(void)
{
    golem_digest digest={{42}},original=digest;
    const char *invalid[]={"{}","null","[]","{\"schema_version\":1,\"schema_version\":1}",
        "{\"schema_version\":1,\"selection_id\":\"x\",\"development_plan\":{},\"snapshot_plan\":{},\"gates\":[]}"};
    for(size_t i=0;i<sizeof(invalid)/sizeof(*invalid);++i) {
        CHECK(golem_execution_contract_validate((golem_bytes){(const uint8_t *)invalid[i],strlen(invalid[i])},&digest,NULL)!=GOLEM_OK);
        CHECK(memcmp(&digest,&original,sizeof(digest))==0);
    }
    CHECK(golem_execution_contract_validate((golem_bytes){NULL,0},NULL,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    golem_execution_reply out={(uint8_t *)"sentinel",8};
    CHECK(golem_execution_call(NULL,(golem_bytes){NULL,0},NULL,&out,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    golem_execution_approval approval = {.struct_size = sizeof(approval), .version = 99};
    CHECK(golem_execution_call_authorized(NULL,(golem_bytes){NULL,0},&approval,&out,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    approval.version = 1;
    approval.struct_size = 0;
    CHECK(golem_execution_call_authorized(NULL,(golem_bytes){NULL,0},&approval,&out,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_execution_render(NULL,(golem_bytes){NULL,0},&out,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(out.size==8 && strcmp((char *)out.data,"sentinel")==0);
    golem_execution_reply empty={0}; golem_execution_reply_free(&empty); golem_execution_reply_free(&empty);
    golem_execution_reply_free(NULL);
    return 0;
}
