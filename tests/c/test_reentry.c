#include "golem/reentry.h"
#include "test.h"
#include <string.h>
int main(void)
{
    const char *bad[]={"null","[]","{}","{\"schema_version\":1,\"schema_version\":1,\"operation\":\"status\"}",
        "{\"schema_version\":1,\"operation\":\"status\",\"authority\":true}",
        "{\"schema_version\":2,\"operation\":\"status\"}","{\"schema_version\":1,\"operation\":\"decide\"}"};
    for(size_t i=0;i<sizeof(bad)/sizeof(*bad);++i)
        CHECK(golem_reentry_validate((golem_bytes){(const uint8_t *)bad[i],strlen(bad[i])},NULL)!=GOLEM_OK);
    const char *status="{\"schema_version\":1,\"operation\":\"status\"}";
    CHECK(golem_reentry_validate((golem_bytes){(const uint8_t *)status,strlen(status)},NULL)==GOLEM_OK);
    golem_execution_reply out={(uint8_t *)"sentinel",8};
    CHECK(golem_reentry_call(NULL,(golem_bytes){NULL,0},&out,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_reentry_report(NULL,0,false,&out,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(out.size==8 && strcmp((char *)out.data,"sentinel")==0);
    return 0;
}
