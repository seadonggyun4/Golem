#include "golem/workpack.h"
#include "check.h"
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    golem_digest result, saved, repeated;
    memset(&result, 0xa5, sizeof(result)); saved = result;
    golem_status status = golem_workpack_validate((golem_bytes){data,size}, &result, NULL);
    if (status != GOLEM_OK) REQUIRE(!memcmp(&result, &saved, sizeof(result)));
    else {
        REQUIRE(size <= GOLEM_WORKPACK_MAX_JSON);
        size_t required=0;bool compatible=false;
        REQUIRE(golem_workpack_inspect((golem_bytes){data,size},NULL,0,&required,NULL)==GOLEM_ERR_BUFFER_TOO_SMALL);
        REQUIRE(required>0 && required<=GOLEM_WORKPACK_MAX_JSON*2u+1u);
        REQUIRE(golem_workpack_compatibility((golem_bytes){data,size},(golem_string_view){"0.1.0",5},&compatible,NULL)==GOLEM_OK);
        REQUIRE(golem_digest_bytes((golem_bytes){data,size}, &repeated) == GOLEM_OK);
        REQUIRE(!memcmp(&result, &repeated, sizeof(result)));
    }
    result = saved;
    status = golem_workpack_proposal_validate((golem_bytes){data,size}, &result, NULL);
    if (status != GOLEM_OK) REQUIRE(!memcmp(&result, &saved, sizeof(result)));
    else {
        REQUIRE(size <= GOLEM_WORKPACK_PROPOSAL_MAX_JSON);
        REQUIRE(golem_digest_bytes((golem_bytes){data,size}, &repeated) == GOLEM_OK);
        REQUIRE(!memcmp(&result, &repeated, sizeof(result)));
    }
    golem_digest pin = {{0}};
    uint8_t sentinel = 42;
    golem_execution_reply reply = {&sentinel,1};
    status = golem_workpack_reference_observe((golem_bytes){data,size},&pin,&pin,&pin,&reply,NULL);
    if(status!=GOLEM_OK) REQUIRE(reply.data==&sentinel && reply.size==1);
    else golem_execution_reply_free(&reply);
    return 0;
}
