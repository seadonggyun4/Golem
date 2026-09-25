#include "golem/approval.h"
#include "test.h"
#include <string.h>

static golem_bytes bytes(const char *s)
{
    return (golem_bytes){(const uint8_t *)s, strlen(s)};
}

int main(void)
{
    const char *valid =
        "{\"schema_version\":1,\"operation\":\"status\",\"request_receipt\":"
        "\"0000000000000000000000000000000000000000000000000000000000000000\"}";
    CHECK(golem_approval_request_validate(bytes(valid)) == GOLEM_OK);
    const char *future =
        "{\"schema_version\":2,\"operation\":\"status\",\"request_receipt\":"
        "\"0000000000000000000000000000000000000000000000000000000000000000\"}";
    CHECK(golem_approval_request_validate(bytes(future)) == GOLEM_ERR_UNSUPPORTED_VERSION);
    const char *invalid[] = {
        "{}", "null", "[]", "{\"schema_version\":2}",
        ("{\"schema_version\":1,\"operation\":\"approve\",\"key\":\"forged\","
         "\"request_receipt\":\"bad\",\"reason\":\"reviewed\"}"),
        ("{\"schema_version\":1,\"operation\":\"request\",\"key\":\"req\","
         "\"ttl_ms\":1,\"action\":null}"),
        ("{\"schema_version\":1,\"operation\":\"request\",\"key\":\"req\","
         "\"ttl_ms\":1,\"ttl_ms\":2,\"action\":{}}")};
    for (size_t i = 0; i < sizeof(invalid) / sizeof(*invalid); ++i)
        CHECK(golem_approval_request_validate(bytes(invalid[i])) != GOLEM_OK);
    golem_execution_reply out = {(uint8_t *)(uintptr_t)1, 17};
    CHECK(golem_approval_describe(NULL, bytes("{}"), &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_approval_call(NULL, bytes("{}"), NULL, NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_execution_call_receipted(NULL, bytes("{}"), NULL, NULL, NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(out.data == (uint8_t *)(uintptr_t)1 && out.size == 17);
    return 0;
}
