#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "../../src/intent/journal.h"
#include "test.h"
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>

static golem_bytes bytes(const char *s) { return (golem_bytes){(const uint8_t *)s, strlen(s)}; }
static golem_status guard(void *context) { return context ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED; }
static int clean(int root)
{
    int fd = openat(root, ".", O_RDONLY | O_DIRECTORY); CHECK(fd >= 0);
    DIR *dir = fdopendir(fd); CHECK(dir != NULL);
    struct dirent *e;
    while ((e = readdir(dir))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
        struct stat sb; CHECK(fstatat(root, e->d_name, &sb, AT_SYMLINK_NOFOLLOW) == 0);
        if (S_ISDIR(sb.st_mode)) {
            int child = openat(root, e->d_name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW); CHECK(child >= 0);
            CHECK(clean(child) == 0); CHECK(close(child) == 0);
        }
        CHECK(unlinkat(root, e->d_name, S_ISDIR(sb.st_mode) ? AT_REMOVEDIR : 0) == 0);
    }
    CHECK(closedir(dir) == 0); return 0;
}
int main(void)
{
    char path[] = "/tmp/golem-intent-reader-XXXXXX"; CHECK(mkdtemp(path) != NULL);
    int root = open(path, O_RDONLY | O_DIRECTORY); CHECK(root >= 0);
    gi_journal *j = NULL; CHECK(gi_journal_open(root, &j) == GOLEM_OK);
    golem_digest raw, source_digest, baseline_digest, zero = {{0}}, op, request;
    char raw_hex[65], source_hex[65]; size_t required;
    CHECK(golem_digest_bytes(bytes("abc"), &raw) == GOLEM_OK);
    CHECK(golem_digest_format(&raw, raw_hex, sizeof(raw_hex), &required) == GOLEM_OK);
    char source[2048], baseline[2048];
    int n = snprintf(source, sizeof(source),
        "{\"schema\":\"golem.intent.source.v1\",\"project_id\":\"demo\",\"work_id\":null,"
        "\"created_by_assertion\":\"fixture\",\"body\":{\"body_cas\":\"%s\",\"byte_length\":3,"
        "\"media_type\":\"text/plain\",\"encoding\":\"UTF-8\",\"origin\":\"MODEL_DRAFT\","
        "\"capture_ref\":\"fixture\",\"designation\":{\"scope_id\":\"opaque\","
        "\"ranges\":[{\"start\":0,\"end\":3}],\"purpose\":\"PRODUCT_REQUIREMENT\","
        "\"decision_ref\":\"%s\"},\"execution_authority\":false}}", raw_hex, raw_hex);
    CHECK(n > 0 && (size_t)n < sizeof(source));
    gi_source_input input = {bytes(source), bytes("abc")};
    CHECK(gi_source_identity(input.control, input.text, &source_digest, NULL) == GOLEM_OK);
    CHECK(golem_digest_format(&source_digest, source_hex, sizeof(source_hex), &required) == GOLEM_OK);
    n = snprintf(baseline, sizeof(baseline),
        "{\"schema\":\"golem.intent.baseline.v1\",\"project_id\":\"demo\",\"work_id\":null,"
        "\"created_by_assertion\":\"fixture\",\"body\":{\"source_refs\":[\"%s\"],"
        "\"previous_baseline_digest\":null,\"decision_refs\":[],\"requirement_refs\":[],\"constraint_refs\":[],"
        "\"issuer_policy_ref\":\"%s\",\"coverage_manifest\":[{\"source_ref\":\"%s\",\"rows\":[{"
        "\"start\":0,\"end\":3,\"classification\":\"QUESTION_REQUIRED\",\"requirement_refs\":[],"
        "\"constraint_refs\":[],\"rationale\":\"fixture\",\"review_refs\":[]}]}]}}", source_hex, raw_hex, source_hex);
    CHECK(n > 0 && (size_t)n < sizeof(baseline));
    CHECK(gi_baseline_identity(bytes(baseline), &baseline_digest, NULL) == GOLEM_OK);
    CHECK(golem_digest_bytes(bytes("operation"), &op) == GOLEM_OK);
    CHECK(golem_digest_bytes(bytes("request"), &request) == GOLEM_OK);
    gi_journal_receipt receipt;
    CHECK(gi_journal_store_objects(j, &op, &request, 0, &zero, bytes(baseline), &input, 1, guard, &root, &receipt) == GOLEM_OK);
    gi_journal_status before, after;
    CHECK(gi_journal_inspect(j, &before) == GOLEM_OK);
    gi_baseline_read result = {0};
    CHECK(gi_journal_read_baseline(j, &op, &request, &baseline_digest, &result) == GOLEM_OK);
    CHECK(result.commit_sequence == 1 && !memcmp(&result.event, &receipt.digest, sizeof(receipt.digest)));
    CHECK(!memcmp(&result.observed_head, &before.head, sizeof(before.head)));
    CHECK(result.graph.baseline.size == strlen(baseline) && !memcmp(result.graph.baseline.data, baseline, strlen(baseline)));
    CHECK(result.graph.source_count == 1 && result.graph.coverage.baseline.has_questions);
    CHECK(result.graph.coverage.source_bytes == 3 && result.graph.coverage.designated_bytes == 3);
    CHECK(!result.graph.coverage.baseline.source_coverage_unverified && result.graph.coverage.baseline.references_unverified);
    CHECK(result.graph.coverage.baseline.semantic_review_required && result.graph.coverage.adoption_unverified && result.graph.coverage.issuer_unverified);
    CHECK(result.graph.sources[0].control.size == strlen(source) && !memcmp(result.graph.sources[0].control.data, source, strlen(source)));
    CHECK(result.graph.sources[0].text.size == 3 && !memcmp(result.graph.sources[0].text.data, "abc", 3));
    gi_object_graph_dispose(&result.graph);
    gi_baseline_read sentinel; memset(&sentinel, 0xa5, sizeof(sentinel)); result = sentinel;
    CHECK(gi_journal_read_baseline(j, &op, &request, &zero, &result) != GOLEM_OK);
    CHECK(!memcmp(&result, &sentinel, sizeof(result)));
    CHECK(gi_journal_read_baseline(j, &zero, &request, &baseline_digest, &result) == GOLEM_ERR_NOT_FOUND);
    CHECK(!memcmp(&result, &sentinel, sizeof(result)));

    int fd = openat(root, "00000001.objects-prep", O_RDONLY); CHECK(fd >= 0);
    char prep[8192]; ssize_t pn = read(fd, prep, sizeof(prep)); CHECK(pn > 0 && (size_t)pn < sizeof(prep)); CHECK(close(fd) == 0);
    golem_bytes manifest = {(const uint8_t *)prep, (size_t)pn};
    size_t total = strlen(baseline) + strlen(source) + 3;
    gi_object_graph graph, saved; memset(&saved, 0xa5, sizeof(saved)); graph = saved;
    const size_t limits[] = {0, strlen(baseline), strlen(baseline) + strlen(source), total - 1};
    for (size_t i = 0; i < sizeof(limits) / sizeof(limits[0]); ++i) {
        CHECK(gi_object_graph_load(root, manifest, limits[i], &graph) == GOLEM_ERR_OVERFLOW);
        CHECK(!memcmp(&graph, &saved, sizeof(graph)));
    }
    CHECK(gi_object_graph_load(root, manifest, total, &graph) == GOLEM_OK);
    gi_object_graph_dispose(&graph);
    CHECK(gi_journal_inspect(j, &after) == GOLEM_OK);
    CHECK(before.committed == after.committed && !memcmp(&before.head, &after.head, sizeof(before.head)));
    CHECK(!memcmp(&before.usage, &after.usage, sizeof(before.usage)));
    gi_journal_close(j); CHECK(clean(root) == 0); CHECK(close(root) == 0); CHECK(rmdir(path) == 0);
    return 0;
}
