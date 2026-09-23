#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/research.h"
#include "test.h"
#include <string.h>
#include <unistd.h>

static golem_bytes bytes(const char *s)
{ return (golem_bytes){(const uint8_t *)s, strlen(s)}; }
int main(int argc, char **argv)
{
    const char *bad[] = {"null", "[]", "{}", "{\"schema_version\":1,\"schema_version\":1}",
        "{\"schema_version\":1,\"operation\":\"adjudicate\",\"key\":\"x\",\"record\":{}}"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i)
        CHECK(golem_research_validate(bytes(bad[i]), NULL) != GOLEM_OK);
    golem_execution_reply out = {(uint8_t *)"sentinel", 8};
    CHECK(golem_research_call(NULL, bytes("{}"), &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_inspect(NULL, 1, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_report(NULL, 1, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_status(NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_metrics(NULL, NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_metrics_report(NULL, NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_compare(NULL, "cohort", &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    const char *redaction = "{\"schema_version\":1,\"profile\":\"MINIMAL\",\"acknowledge_linkability\":false}";
    CHECK(golem_research_redaction_validate(bytes(redaction), NULL) == GOLEM_OK);
    CHECK(golem_research_redaction_validate(bytes("{}"), NULL) != GOLEM_OK);
    CHECK(golem_research_bundle_verify(bytes("{}"), NULL) != GOLEM_OK);
    CHECK(golem_research_bundle(NULL, "case", bytes(redaction), &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_observability(NULL, "case", bytes(redaction),
        GOLEM_RESEARCH_EXPORT_OTLP_LOGS, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    const char *spec = "{\"schema_version\":1,\"work_id\":\"w\",\"request\":\"Research test\","
        "\"scope\":\"local records\",\"non_goals\":\"no execution\",\"permission\":\"AUTO_LOCAL\","
        "\"max_revisions\":4,\"acceptance\":[{\"id\":\"R1\",\"criterion\":\"record safely\"}],\"policy_version\":1}";
    char root[4096];
    CHECK(argc == 2);
    int n = snprintf(root, sizeof(root), "%s/research-api-XXXXXX", argv[1]);
    CHECK(n > 0 && (size_t)n < sizeof(root));
    CHECK(mkdtemp(root) != NULL);
    golem_document_store *s = NULL;
    CHECK(golem_document_store_create(root, bytes(spec), NULL, &s, NULL) == GOLEM_OK);
    uint64_t generation = 0;
    CHECK(golem_document_generation(s, &generation) == GOLEM_OK && generation == 1);
    CHECK(golem_research_inspect(s, 0, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_inspect(s, 1, &out, NULL) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_research_call(s, bytes("{}"), &out, NULL) != GOLEM_OK);
    CHECK(out.size == 8 && !strcmp((char *)out.data, "sentinel"));
    CHECK(golem_document_store_close(s) == GOLEM_OK);
    CHECK(golem_document_store_open(root, false, NULL, &s, NULL) == GOLEM_OK);
    CHECK(golem_research_metrics(s, "", &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_metrics(s, "../escape", &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_metrics(s, "missing", &out, NULL) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_research_metrics_report(s, "missing", &out, NULL) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_research_metrics(s, NULL, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_compare(s, NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_compare(s, "../escape", &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_compare(s, "missing", &out, NULL) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_research_compare(s, "cohort", NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_bundle(s, NULL, bytes(redaction), &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_bundle(s, "missing", bytes(redaction), &out, NULL) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_research_bundle(s, "case", bytes(redaction), NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_observability(s, "case", bytes(redaction),
        (golem_research_export_format)0, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_observability(s, NULL, bytes(redaction),
        GOLEM_RESEARCH_EXPORT_PROV_JSON, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_observability(s, "case", bytes(redaction),
        GOLEM_RESEARCH_EXPORT_OTLP_LOGS, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_research_observability(s, "missing", bytes(redaction),
        GOLEM_RESEARCH_EXPORT_PROV_JSON, &out, NULL) == GOLEM_ERR_NOT_FOUND);
    CHECK(out.size == 8 && !strcmp((char *)out.data, "sentinel"));
    CHECK(golem_research_metrics(s, NULL, &out, NULL) == GOLEM_OK);
    CHECK(out.size > 0);
    golem_execution_reply_free(&out);
    CHECK(golem_research_metrics_report(s, NULL, &out, NULL) == GOLEM_OK);
    CHECK(out.size > 0);
    golem_execution_reply_free(&out);
    CHECK(golem_research_call(s, bytes("{}"), &out, NULL) == GOLEM_ERR_POLICY_DENIED);
    CHECK(golem_research_status(s, &out, NULL) == GOLEM_OK);
    CHECK(out.size > 0);
    golem_execution_reply_free(&out);
    CHECK(golem_document_store_close(s) == GOLEM_OK);
    return 0;
}
