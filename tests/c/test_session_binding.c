#include "golem/session_binding.h"
#include "test.h"
#include <string.h>
static golem_bytes bytes(const char *s)
{
    return (golem_bytes){(const uint8_t *)s, strlen(s)};
}
int main(void)
{
    CHECK(golem_session_binding_request_validate(
              bytes("{\"schema_version\":1,\"operation\":\"inspect\",\"work_id\":\"work\"}")) ==
          GOLEM_OK);
    const char *invalid[] = {
        "{}",
        "null",
        "[]",
        "{\"schema_version\":2}",
        "{\"schema_version\":1,\"operation\":\"inspect\",\"work_id\":\"work\",\"secret\":\"x\"}",
        ("{\"schema_version\":1,\"operation\":\"inspect\",\"work_id\":\"work\",\"work_id\":"
         "\"work\"}")};
    for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i)
        CHECK(golem_session_binding_request_validate(bytes(invalid[i])) != GOLEM_OK);
    golem_agent_reply out = {(uint8_t *)(uintptr_t)1, 17};
    CHECK(golem_session_binding_call(NULL, bytes("{}"), NULL, NULL, &out, NULL) ==
          GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(out.data == (uint8_t *)(uintptr_t)1 && out.size == 17);
    CHECK(golem_work_history(NULL, bytes("{}"), &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(out.data == (uint8_t *)(uintptr_t)1 && out.size == 17);
    CHECK(golem_session_fence_check(NULL, bytes("{}"), NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
