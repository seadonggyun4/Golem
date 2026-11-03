/* Authored QC4 fixtures; execution remains NOT_RUN while validation is on HOLD. */
#include "../../src/intent/qa_result.h"
#include "../../src/common/json.h"
#include "test.h"
#include <string.h>
#include <stdlib.h>
static struct json_object *parse(const char *s)
{
    struct json_object *o = NULL;
    if (s[0] == '[') {
        size_t n = strlen(s) + 16;
        char *wrapped = malloc(n);
        if (!wrapped)
            abort();
        snprintf(wrapped, n, "{\"items\":%s}", s);
        if (golem_json_parse((golem_bytes){(const uint8_t *)wrapped, strlen(wrapped)}, 65536, &o) !=
            GOLEM_OK)
            abort();
        struct json_object *items = NULL;
        json_object_object_get_ex(o, "items", &items);
        json_object_get(items);
        json_object_put(o);
        free(wrapped);
        return items;
    }
    if (golem_json_parse((golem_bytes){(const uint8_t *)s, strlen(s)}, 65536, &o) != GOLEM_OK)
        abort();
    return o;
}
static struct json_object *get(struct json_object *o, const char *k)
{
    struct json_object *v = NULL;
    json_object_object_get_ex(o, k, &v);
    return v;
}
static int result(struct json_object *o, struct json_object *m, struct json_object *c,
                  const char *raw, const char *expected)
{
    struct json_object *r = raw ? parse(raw) : NULL, *out = NULL;
    CHECK(gi_qa_native_results(o, m, c, r, &out) == GOLEM_OK);
    CHECK(!strcmp(json_object_get_string(get(json_object_array_get_idx(out, 0), "status")),
                  expected));
    CHECK(!strcmp(json_object_get_string(get(json_object_array_get_idx(out, 1), "status")),
                  "NOT_RUN"));
    json_object_put(r);
    json_object_put(out);
    return 0;
}
int main(void)
{
    /* Native receipt bytes remain unchanged across submission-only counters. */
    struct json_object *old_manifest =
        parse("{\"generation\":4,\"documents\":[\"exact\"],\"source_snapshot\":\"pinned\"}");
    struct json_object *new_manifest =
        parse("{\"generation\":6,\"documents\":[\"exact\"],\"source_snapshot\":\"pinned\"}");
    CHECK(gi_qa_manifest_matches(old_manifest, new_manifest) == GOLEM_OK);
    CHECK(json_object_get_int(get(old_manifest, "generation")) == 4);
    json_object_object_add(new_manifest, "source_snapshot", json_object_new_string("changed"));
    CHECK(gi_qa_manifest_matches(old_manifest, new_manifest) == GOLEM_ERR_STALE_RESULT);
    json_object_object_add(new_manifest, "source_snapshot", json_object_new_string("pinned"));
    json_object_object_add(new_manifest, "generation", json_object_new_int(3));
    CHECK(gi_qa_manifest_matches(old_manifest, new_manifest) == GOLEM_ERR_STALE_RESULT);
    json_object_object_del(new_manifest, "generation");
    CHECK(gi_qa_manifest_matches(old_manifest, new_manifest) == GOLEM_ERR_STALE_RESULT);
    json_object_put(old_manifest);
    json_object_put(new_manifest);
    struct json_object *o = parse(
        "[{\"id\":\"o1\",\"evidence_kind\":\"NATIVE_QA\"},{\"id\":\"o2\",\"evidence_kind\":\"SEMANTIC_REVIEW\"}]");
    struct json_object *m = parse(
        "[{\"obligation_id\":\"o1\",\"gate_id\":\"g\",\"gate_version\":1,\"case_id\":\"c1\"}]");
    struct json_object *c = parse(
        "{\"gates\":[{\"id\":\"g\",\"version\":1,\"cases\":[{\"id\":\"c1\"},{\"id\":\"c2\"}]}]}");
    CHECK(result(o, m, c, NULL, "NOT_RUN") == 0);
    CHECK(
        result(
            o, m, c,
            "{\"gates\":[{\"gate_id\":\"g\",\"version\":1,\"status\":\"PASS\",\"cases\":[{\"id\":\"c1\",\"status\":\"PASS\"},{\"id\":\"c2\",\"status\":\"PASS\"}]}]}",
            "PASS") == 0);
    CHECK(
        result(
            o, m, c,
            "{\"gates\":[{\"gate_id\":\"g\",\"version\":1,\"status\":\"PASS\",\"cases\":[{\"id\":\"c1\",\"status\":\"PASS\"}]}]}",
            "UNKNOWN") == 0);
    CHECK(
        result(
            o, m, c,
            "{\"gates\":[{\"gate_id\":\"g\",\"version\":1,\"status\":\"PASS\",\"cases\":[{\"id\":\"c1\",\"status\":\"PASS\"},{\"id\":\"c1\",\"status\":\"PASS\"}]}]}",
            "UNKNOWN") == 0);
    CHECK(
        result(
            o, m, c,
            "{\"gates\":[{\"gate_id\":\"g\",\"version\":1,\"status\":\"PASS\",\"cases\":[{\"id\":\"c1\",\"status\":\"PASS\"},{\"id\":\"c2\",\"status\":\"FAIL\"}]}]}",
            "UNKNOWN") == 0);
    CHECK(result(o, m, c, "{\"gates\":[{\"gate_id\":\"g\",\"version\":1,\"status\":\"FAIL\"}]}",
                 "FAIL") == 0);
    CHECK(result(o, m, c, "{\"gates\":[{\"gate_id\":\"g\",\"version\":1,\"status\":\"ERROR\"}]}",
                 "ERROR") == 0);
    CHECK(result(o, m, c, "{\"gates\":[{\"gate_id\":\"other\",\"version\":1,\"status\":\"PASS\"}]}",
                 "UNKNOWN") == 0);
    /* Unsupported native statuses and contradictory aggregate PASS fail closed. */
    CHECK(
        result(
            o, m, c,
            "{\"gates\":[{\"gate_id\":\"g\",\"version\":1,\"status\":\"PASS\",\"cases\":[{\"id\":\"c1\",\"status\":\"SKIP\"},{\"id\":\"c2\",\"status\":\"PASS\"}]}]}",
            "UNKNOWN") == 0);
    CHECK(
        result(
            o, m, c,
            "{\"status\":\"PASS\",\"gates\":[{\"gate_id\":\"g\",\"version\":1,\"status\":\"FAIL\"}]}",
            "UNKNOWN") == 0);
    CHECK(result(o, m, c, "{\"gates\":[{\"gate_id\":\"g\",\"version\":2,\"status\":\"PASS\"}]}",
                 "UNKNOWN") == 0);
    /* Stage review identity changes with receipt, semantic identity with obligation. */
    golem_digest material = {{0}}, a, b, d;
    struct json_object *r1 = json_object_new_string("receipt-one"),
                       *r2 = json_object_new_string("receipt-two");
    CHECK(gi_qa_review_digest(&material, r1, NULL, &a) == GOLEM_OK);
    CHECK(gi_qa_review_digest(&material, r2, NULL, &b) == GOLEM_OK);
    CHECK(gi_qa_review_digest(&material, r1, json_object_array_get_idx(o, 0), &d) == GOLEM_OK);
    CHECK(memcmp(&a, &b, sizeof(a)) != 0);
    CHECK(memcmp(&a, &d, sizeof(a)) != 0);
    json_object_put(r1);
    json_object_put(r2);
    json_object_put(o);
    json_object_put(m);
    json_object_put(c);
    return 0;
}
