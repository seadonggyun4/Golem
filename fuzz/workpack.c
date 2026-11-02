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
        REQUIRE(golem_digest_bytes((golem_bytes){data,size}, &repeated) == GOLEM_OK);
        REQUIRE(!memcmp(&result, &repeated, sizeof(result)));
    }
    return 0;
}
