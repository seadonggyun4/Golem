#include "golem/completion.h"
#include "test.h"
#include <string.h>
int main(void)
{
    const char *bad[]={"null","[]","{}","{\"schema_version\":1,\"schema_version\":1}",
        "{\"schema_version\":2,\"operation\":\"resume\",\"selection_id\":\"selection\"}",
        "{\"schema_version\":1,\"operation\":\"finalize\",\"selection_id\":\"selection\"}"};
    for(size_t i=0;i<sizeof(bad)/sizeof(*bad);++i)
        CHECK(golem_completion_validate((golem_bytes){(const uint8_t *)bad[i],strlen(bad[i])},NULL)!=GOLEM_OK);
    const char *good="{\"schema_version\":1,\"operation\":\"resume\",\"selection_id\":\"selection\"}";
    CHECK(golem_completion_validate((golem_bytes){(const uint8_t *)good,strlen(good)},NULL)==GOLEM_OK);
    golem_execution_reply out={(uint8_t *)"sentinel",8};
    CHECK(golem_completion_call(NULL,(golem_bytes){NULL,0},&out,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_completion_report(NULL,0,false,&out,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(out.size==8 && !strcmp((char *)out.data,"sentinel"));
    return 0;
}
