#include "golem/role_contract.h"
#include "../../src/completion/internal.h"
#include "../../src/workflow/role_internal.h"
#include "test.h"
#include <string.h>

static golem_bytes bytes(const char *s)
{
    return (golem_bytes){(const uint8_t *)s, strlen(s)};
}

int main(void)
{
    golem_digest sentinel = {{42}}, digest = sentinel;
    CHECK(golem_role_validate(bytes("{}"), &digest, NULL) == GOLEM_ERR_PARSE);
    CHECK(memcmp(&digest, &sentinel, sizeof(digest)) == 0);
    CHECK(golem_role_validate(bytes("{}"), NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_execution_reply reply = {(uint8_t *)&sentinel, 42};
    CHECK(golem_role_template(NULL, &reply) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_role_template("unknown", &reply) != GOLEM_OK);
    CHECK(reply.data == (uint8_t *)&sentinel && reply.size == 42);
    CHECK(golem_role_call(NULL, bytes("{}"), NULL, &reply, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    const char *names[] = {"implementer", "qa", "reviewer", "researcher", "doc-only", "no-change"};
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i) {
        reply = (golem_execution_reply){0};
        CHECK(golem_role_template(names[i], &reply) == GOLEM_OK);
        CHECK(golem_role_validate((golem_bytes){reply.data, reply.size}, &digest, NULL) ==
              GOLEM_OK);
        golem_execution_reply_free(&reply);
    }
    const char *valid =
        "{\"schema_version\":1,\"operation\":\"evaluate\",\"selection_id\":\"selection\","
        "\"key\":\"one\",\"expected_generation\":1,\"review\":null}";
    CHECK(golem_role_request_validate(bytes(valid), NULL) == GOLEM_OK);
    const char *bad[] = {
        "{}",
        "null",
        "[]",
        "{\"schema_version\":1,\"schema_version\":1}",
        "{\"schema_version\":1,\"operation\":\"status\",\"selection_id\":\"s\",\"extra\":true}",
        ("{\"schema_version\":1,\"operation\":\"assess\",\"selection_id\":\"s\",\"key\":\"k\","
         "\"expected_generation\":-1,\"review\":null}")};
    for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i)
        CHECK(golem_role_request_validate(bytes(bad[i]), NULL) != GOLEM_OK);
    uint8_t oversized[GOLEM_ROLE_MAX_JSON + 1];
    memset(oversized, ' ', sizeof(oversized));
    CHECK(golem_role_request_validate((golem_bytes){oversized, sizeof(oversized)}, NULL) !=
          GOLEM_OK);
    /* A different selection cannot recover a legacy completion path after
     * any role enrollment, even before looking for its documents. */
    golem_document_store store = {.role_count = 1};
    struct json_object *request = json_tokener_parse(
        "{\"schema_version\":1,\"operation\":\"finalize\",\"selection_id\":\"alternate\","
        "\"key\":\"bypass\",\"expected_generation\":1,\"issues\":[]}");
    CHECK(request != NULL);
    struct json_object *assessment = request;
    CHECK(co_evaluate(&store, request, true, &assessment) == GOLEM_ERR_REQUIREMENTS_UNMET);
    CHECK(assessment == request);
    json_object_put(request);
    struct json_object *checkpoint =
        json_tokener_parse("{\"contract\":{\"gates\":[{\"id\":\"unit\",\"version\":1,\"cases\":[{"
                           "\"id\":\"fix\"},{\"id\":\"regression\"}]}]}}");
    struct json_object *qa = json_tokener_parse(
        "{\"status\":\"PASS\",\"gates\":[{\"gate_id\":\"unit\",\"version\":1,\"status\":\"PASS\","
        "\"cases\":["
        "{\"id\":\"fix\",\"status\":\"PASS\"},{\"id\":\"regression\",\"status\":\"PASS\"}]}]}");
    CHECK(checkpoint && qa && rc_qa_cases(qa, checkpoint) == GOLEM_OK);
    struct json_object *gate = json_object_array_get_idx(dw_get(qa, "gates"), 0);
    struct json_object *test = json_object_array_get_idx(dw_get(gate, "cases"), 1);
    CHECK(ex_text(test, "status", "SKIPPED"));
    CHECK(rc_qa_cases(qa, checkpoint) == GOLEM_ERR_REQUIREMENTS_UNMET);
    CHECK(ex_text(test, "status", "PASS") && ex_text(test, "id", "fix"));
    CHECK(rc_qa_cases(qa, checkpoint) == GOLEM_ERR_REQUIREMENTS_UNMET);
    CHECK(json_object_array_del_idx(dw_get(gate, "cases"), 1, 1) == 0);
    CHECK(rc_qa_cases(qa, checkpoint) == GOLEM_ERR_REQUIREMENTS_UNMET);
    json_object_put(qa);
    json_object_put(checkpoint);
    return 0;
}
