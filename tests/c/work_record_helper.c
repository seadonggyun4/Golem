#include "golem/session_binding.h"
#include "test.h"
#include <string.h>

static golem_status failed_clock(void *context, uint64_t *now, golem_digest *boot)
{
    (void)context;
    (void)now;
    (void)boot;
    return GOLEM_ERR_IO;
}
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    golem_document_store *s = NULL;
    CHECK(golem_document_store_open(argv[1], false, NULL, &s, NULL) == GOLEM_OK);
    golem_agent_reply out = {(uint8_t *)(uintptr_t)1, 17};
    const char *request = "{\"schema_version\":1,\"work_id\":\"example-work\","
                          "\"byte_budget\":33554432,\"document_head\":\"\",\"agent_head\":\"\"}";
    golem_agent_clock clock = {failed_clock, NULL};
    golem_diagnostic d;
    CHECK(golem_work_record(s, (golem_bytes){(const uint8_t *)request, strlen(request)},
                            &clock, &out, &d) == GOLEM_ERR_IO);
    CHECK(out.data == (uint8_t *)(uintptr_t)1 && out.size == 17);
    CHECK(strstr(d.message, "boot_identity_clock") != NULL);
    CHECK(golem_work_record(s, (golem_bytes){(const uint8_t *)"{}", 2}, NULL, &out, NULL) != GOLEM_OK);
    CHECK(out.data == (uint8_t *)(uintptr_t)1 && out.size == 17);
    CHECK(golem_work_record(NULL, (golem_bytes){NULL, 0}, NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_document_store_close(s) == GOLEM_OK);
    return 0;
}
