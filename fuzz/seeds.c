#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/adapter_protocol.h"
#include "golem/research.h"
#include "golem/journal.h"
#include "golem/lineage.h"
#include "check.h"
#include <errno.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>

static const char *root;
static void directory(const char *path)
{
    if (mkdir(path, 0700) != 0) REQUIRE(errno == EEXIST);
}
static void save(const char *group, const char *name, const void *data, size_t size)
{
    char path[4096];
    int n = snprintf(path, sizeof(path), "%s/%s", root, group);
    REQUIRE(n > 0 && (size_t)n < sizeof(path)); directory(path);
    n = snprintf(path, sizeof(path), "%s/%s/%s", root, group, name);
    REQUIRE(n > 0 && (size_t)n < sizeof(path));
    FILE *f = fopen(path, "wb"); REQUIRE(f != NULL);
    REQUIRE(fwrite(data, 1, size, f) == size && fclose(f) == 0);
}
static void envelopes(const char *source)
{
    const char *names[] = {"capability.json", "request.json", "result.json"};
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i) {
        char path[4096]; uint8_t input[GOLEM_ADAPTER_JSON_MAX], packed[GOLEM_ADAPTER_MSGPACK_MAX];
        int n = snprintf(path, sizeof(path), "%s/fuzz/corpus/adapter_json/%s", source, names[i]);
        REQUIRE(n > 0 && (size_t)n < sizeof(path));
        FILE *f = fopen(path, "rb"); REQUIRE(f != NULL);
        size_t size = fread(input, 1, sizeof(input), f);
        REQUIRE(!ferror(f) && feof(f) && fclose(f) == 0);
        golem_adapter_envelope e; size_t required;
        REQUIRE(golem_adapter_envelope_decode((golem_bytes){input, size}, &e, NULL) == GOLEM_OK);
        save("adapter_json", names[i], input, size);
        REQUIRE(golem_adapter_msgpack_encode(&e, packed, sizeof(packed), &required, NULL) == GOLEM_OK);
        save("adapter_msgpack", names[i], packed, required);
    }
    const char malformed[] = "{\"type\":\"1\",\"type\":\"2\"}";
    save("adapter_json", "duplicate", malformed, sizeof(malformed) - 1);
    const uint8_t wide[] = {0xdf, 0xff, 0xff, 0xff, 0xff};
    save("adapter_msgpack", "oversized-map", wide, sizeof(wide));
}
static void journals(const char *source)
{
    const char *names[] = {"default", "cancelled", "reentry", "invalid_transition"};
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i) {
        char path[4096]; uint8_t bytes[8192]; size_t n = 0; unsigned value;
        int count = snprintf(path, sizeof(path), "%s/tests/c/fixtures/journal/v1_%s.hex", source, names[i]);
        REQUIRE(count > 0 && (size_t)count < sizeof(path));
        FILE *f = fopen(path, "r"); REQUIRE(f != NULL);
        int result;
        while ((result = fscanf(f, " %2x", &value)) == 1) {
            REQUIRE(n < sizeof(bytes) && value <= 255); bytes[n++] = (uint8_t)value;
        }
        REQUIRE(result == EOF && !ferror(f) && fclose(f) == 0);
        save("journal", names[i], bytes, n);
        size_t offset = 0, index = 0;
        while (offset < n) {
            golem_journal_record record; size_t consumed;
            REQUIRE(golem_journal_record_decode((golem_bytes){bytes + offset, n - offset}, &record, &consumed, NULL) == GOLEM_OK);
            char name[128];
            (void)snprintf(name, sizeof(name), "%s-payload-%zu", names[i], index++);
            save("journal", name, record.payload.data, record.payload.size);
            offset += consumed;
        }
    }
}
static void parsers(void)
{
    golem_policy_artifact a = {.revision = 1};
    REQUIRE(golem_policy_spec_init(&a.policy) == GOLEM_OK);
    uint8_t bytes[GOLEM_POLICY_ARTIFACT_SIZE]; size_t n;
    REQUIRE(golem_policy_artifact_encode(&a, bytes, sizeof(bytes), &n) == GOLEM_OK);
    save("policy_artifact", "deny", bytes, n);
    a.revision = UINT64_MAX;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) a.policy.permissions[i] = (golem_autonomy)(i % 4);
    REQUIRE(golem_policy_artifact_encode(&a, bytes, sizeof(bytes), &n) == GOLEM_OK);
    save("policy_artifact", "mixed", bytes, n);
    golem_receipt receipt = {.version = GOLEM_RECEIPT_VERSION, .algorithm = GOLEM_DIGEST_SHA256};
    REQUIRE(golem_digest_bytes((golem_bytes){NULL, 0}, &receipt.digest) == GOLEM_OK);
    uint8_t encoded[GOLEM_RECEIPT_SIZE];
    REQUIRE(golem_receipt_encode(&receipt, encoded, sizeof(encoded), &n) == GOLEM_OK);
    save("parser", "receipt", encoded, n);
    char digest[65]; REQUIRE(golem_digest_format(&receipt.digest, digest, sizeof(digest), &n) == GOLEM_OK);
    save("parser", "digest", digest, n - 1);
    const char *items[] = {"test"};
    golem_capsule_spec spec = {.id = "fuzz", .goal = "parser seed", .scope = {items, 1}, .acceptance = {items, 1}};
    golem_graph_spec stages; golem_stage_graph *stage_graph = NULL;
    REQUIRE(golem_stage_graph_default_spec(&stages) == GOLEM_OK);
    REQUIRE(golem_stage_graph_create(&stages, &stage_graph) == GOLEM_OK);
    spec.graph = stage_graph;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) spec.permissions[i] = GOLEM_AUTONOMY_AUTO_LOCAL;
    golem_work_capsule *capsule = NULL; golem_work_run *run = NULL; golem_lineage *graph = NULL;
    REQUIRE(golem_work_capsule_create(&spec, &capsule) == GOLEM_OK);
    REQUIRE(golem_work_run_create("fuzz", capsule, 2, &run) == GOLEM_OK);
    REQUIRE(golem_lineage_create("fuzz", NULL, NULL, &graph, NULL) == GOLEM_OK);
    golem_stage_snapshot stage; golem_lineage_id input, evidence;
    REQUIRE(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
    REQUIRE(golem_lineage_begin(graph, run, &receipt, NULL, 0, &input, NULL) == GOLEM_OK);
    REQUIRE(golem_lineage_add(graph, GOLEM_LINEAGE_EVIDENCE, &receipt, &input, 1, &evidence, NULL) == GOLEM_OK);
    REQUIRE(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    REQUIRE(golem_lineage_seal(graph, run, NULL) == GOLEM_OK);
    uint8_t wire[4096]; REQUIRE(golem_lineage_encode(graph, wire, sizeof(wire), &n, NULL) == GOLEM_OK);
    save("parser", "lineage", wire, n);
    golem_lineage_free(graph); golem_work_run_free(run); golem_work_capsule_free(capsule);
    golem_stage_graph_free(stage_graph);
}
static void documents(const char *source)
{
    const char *names[] = {"documents/work.json", "documents/planning.json", "documents/planning.md", "discovery/assessment.json", "agent-session/start.json", "agent-session/status.json", "execution/contract.json", "reentry/decision.json", "completion/finalize.json", "completion/resume.json", "research/request.json", "research/attempt-request.json", "research/outcome-enroll-request.json", "research/adjudication-request.json", "research/cohort-request.json", "research/cohort-observe-request.json", "research/redaction-minimal.json", "research/redaction-linkable.json"};
    for (size_t i = 0; i < sizeof(names)/sizeof(*names); ++i) {
        char path[4096]; uint8_t bytes[8192];
        int n = snprintf(path, sizeof(path), "%s/samples/%s", source, names[i]);
        REQUIRE(n > 0 && (size_t)n < sizeof(path));
        FILE *f = fopen(path, "rb"); REQUIRE(f != NULL);
        size_t size = fread(bytes, 1, sizeof(bytes), f);
        REQUIRE(!ferror(f) && feof(f) && fclose(f) == 0);
        save("document", strrchr(names[i],'/')+1, bytes, size);
    }
}
static void bundles(void)
{
    const char spec[] = "{\"schema_version\":1,\"work_id\":\"w\",\"request\":\"Synthetic\","
        "\"scope\":\"local\",\"non_goals\":\"execution\",\"permission\":\"AUTO_LOCAL\",\"max_revisions\":4,"
        "\"acceptance\":[{\"id\":\"R1\",\"criterion\":\"record\"}],\"policy_version\":1}";
    const char request[] = "{\"schema_version\":1,\"operation\":\"case-create\",\"key\":\"case\",\"record\":{"
        "\"schema_version\":1,\"work_id\":\"w\",\"case_id\":\"c\",\"project_id\":\"p\",\"case_type\":\"BENCHMARK_TASK\","
        "\"research_questions\":[{\"id\":\"q\",\"question\":\"Synthetic\"}],\"unit_of_analysis\":\"task\","
        "\"context\":{\"product\":\"test\",\"environment\":\"local\",\"tool\":\"C\",\"runner\":\"C\",\"constraints\":\"none\"},"
        "\"privacy_level\":\"PRIVATE\",\"pre_registered_plan_digest\":\"\"}}";
    const char policy[] = "{\"schema_version\":1,\"profile\":\"MINIMAL\",\"acknowledge_linkability\":false}";
    char path[4096];
    int n = snprintf(path, sizeof(path), "%s/bundle-source-XXXXXX", root);
    REQUIRE(n > 0 && (size_t)n < sizeof(path) && mkdtemp(path) != NULL);
    golem_document_store *s = NULL; golem_execution_reply reply = {0};
    REQUIRE(golem_document_store_create(path, (golem_bytes){(const uint8_t *)spec, sizeof(spec)-1}, NULL, &s, NULL) == GOLEM_OK);
    REQUIRE(golem_research_call(s, (golem_bytes){(const uint8_t *)request, sizeof(request)-1}, &reply, NULL) == GOLEM_OK);
    golem_execution_reply_free(&reply);
    REQUIRE(golem_research_bundle(s, "c", (golem_bytes){(const uint8_t *)policy, sizeof(policy)-1}, &reply, NULL) == GOLEM_OK);
    REQUIRE(golem_research_bundle_verify((golem_bytes){reply.data, reply.size}, NULL) == GOLEM_OK);
    save("document", "case-study-bundle.json", reply.data, reply.size);
    golem_execution_reply_free(&reply);
    REQUIRE(golem_research_observability(s, "c", (golem_bytes){(const uint8_t *)policy, sizeof(policy)-1},
        GOLEM_RESEARCH_EXPORT_OTLP_LOGS, &reply, NULL) == GOLEM_OK);
    save("document", "derived-otlp.json", reply.data, reply.size);
    golem_execution_reply_free(&reply);
    REQUIRE(golem_research_observability(s, "c", (golem_bytes){(const uint8_t *)policy, sizeof(policy)-1},
        GOLEM_RESEARCH_EXPORT_PROV_JSON, &reply, NULL) == GOLEM_OK);
    save("document", "derived-prov.json", reply.data, reply.size);
    golem_execution_reply_free(&reply);
    REQUIRE(golem_document_store_close(s) == GOLEM_OK);
}
int main(int argc, char **argv)
{
    REQUIRE(argc == 3); root = argv[1]; directory(root);
    envelopes(argv[2]); journals(argv[2]); parsers(); documents(argv[2]); bundles();
    return 0;
}
