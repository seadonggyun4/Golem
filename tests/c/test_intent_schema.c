#include "../../src/intent/schema.h"
#include "../../src/common/json.h"
#include "test.h"
#include <stddef.h>
#include <string.h>

static golem_bytes bytes(const char *s)
{
    return (golem_bytes){(const uint8_t *)s, strlen(s)};
}
static int capacities(void)
{
    const size_t offsets[] = {offsetof(gi_capacity, control_bytes), offsetof(gi_capacity, source_bytes),
        offsetof(gi_capacity, baseline_source_bytes), offsetof(gi_capacity, requirements),
        offsetof(gi_capacity, trace_nodes), offsetof(gi_capacity, trace_edges), offsetof(gi_capacity, node_parents),
        offsetof(gi_capacity, unresolved), offsetof(gi_capacity, observations), offsetof(gi_capacity, dispatch_bytes)};
    const size_t maxima[] = {GI_CONTROL_MAX, GI_SOURCE_MAX, GI_BASELINE_SOURCE_MAX, GI_REQUIREMENT_MAX,
        GI_TRACE_NODE_MAX, GI_TRACE_EDGE_MAX, GI_PARENT_MAX, GI_OBLIGATION_MAX, GI_OBSERVATION_MAX, GI_DISPATCH_MAX};
    for (size_t i = 0; i < sizeof(offsets) / sizeof(*offsets); ++i) {
        gi_capacity capacity = {0};
        size_t *value = (size_t *)((unsigned char *)&capacity + offsets[i]);
        *value = maxima[i] - 1;
        CHECK(gi_capacity_validate(&capacity, NULL) == GOLEM_OK);
        *value = maxima[i];
        CHECK(gi_capacity_validate(&capacity, NULL) == GOLEM_OK);
        *value = maxima[i] + 1;
        golem_diagnostic diagnostic;
        CHECK(gi_capacity_validate(&capacity, &diagnostic) == GOLEM_ERR_OVERFLOW);
        CHECK(strncmp(diagnostic.message, "intent.limit.", 13) == 0);
        *value = SIZE_MAX;
        CHECK(gi_capacity_validate(&capacity, NULL) == GOLEM_ERR_OVERFLOW);
    }
    CHECK(gi_capacity_validate(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
static int utf8_ranges(void)
{
    const unsigned char raw[] = {'A', 0xea, 0xb0, 0x80, 0xf0, 0x9f, 0x98, 0x80, '\r', '\n', 0};
    golem_bytes text = {raw, sizeof(raw)};
    CHECK(gi_text_validate(text, NULL) == GOLEM_OK);
    const size_t boundaries[] = {0, 1, 4, 8, 9, 10, 11};
    for (size_t i = 0; i < sizeof(raw); ++i) {
        bool valid = false;
        for (size_t j = 0; j < sizeof(boundaries) / sizeof(*boundaries); ++j) valid |= i == boundaries[j];
        CHECK((gi_span_validate(text, (gi_span){i, sizeof(raw)}, NULL) == GOLEM_OK) == valid);
    }
    CHECK(gi_span_validate(text, (gi_span){4, 1}, NULL) == GOLEM_ERR_PARSE);
    CHECK(gi_span_validate(text, (gi_span){0, SIZE_MAX}, NULL) == GOLEM_ERR_PARSE);
    CHECK(gi_span_validate(text, (gi_span){1, 1}, NULL) == GOLEM_ERR_PARSE);
    CHECK(gi_span_validate(text, (gi_span){SIZE_MAX, SIZE_MAX}, NULL) == GOLEM_ERR_PARSE);
    const char *bad[] = {"\x80", "\xc0\xaf", "\xc1\xbf", "\xe0\x80\x80", "\xed\xa0\x80",
        "\xf0\x80\x80\x80", "\xf4\x90\x80\x80", "\xf5\x80\x80\x80", "\xff", "\xc2", "\xe1\x80", "\xf1\x80\x80", "\xe1x\x80"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) CHECK(gi_text_validate(bytes(bad[i]), NULL) == GOLEM_ERR_PARSE);
    CHECK(gi_text_validate(bytes("\xef\xbb\xbf\xf4\x8f\xbf\xbf"), NULL) == GOLEM_OK);
    CHECK(gi_text_validate((golem_bytes){NULL, 0}, NULL) == GOLEM_OK);
    CHECK(gi_text_validate((golem_bytes){NULL, 1}, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
static int coverage(void)
{
    golem_bytes text = bytes("0123456789");
    gi_span designation[] = {{5, 9}, {0, 2}, {1, 5}};
    gi_coverage_row rows[] = {{{4, 9}, GI_NON_NORMATIVE}, {{0, 5}, GI_NON_NORMATIVE}};
    gi_span saved[3]; memcpy(saved, designation, sizeof(saved));
    gi_coverage_row saved_rows[2]; memcpy(saved_rows, rows, sizeof(rows));
    gi_coverage_result out;
    CHECK(gi_coverage_validate(text, designation, 3, rows, 2, &out, NULL) == GOLEM_OK);
    CHECK(out.designated_bytes == 9 && out.classification_review_required && !out.has_questions);
    CHECK(memcmp(saved, designation, sizeof(saved)) == 0 && memcmp(saved_rows, rows, sizeof(rows)) == 0);
    rows[0].classification = GI_QUESTION_REQUIRED;
    CHECK(gi_coverage_validate(text, designation, 3, rows, 2, &out, NULL) == GOLEM_OK && out.has_questions);
    for (int kind = GI_REQUIREMENT; kind <= GI_QUESTION_REQUIRED; ++kind) {
        rows[0].classification = (gi_classification)kind;
        CHECK(gi_coverage_validate(text, designation, 3, rows, 2, &out, NULL) == GOLEM_OK);
        CHECK(out.classification_review_required);
    }
    gi_coverage_result sentinel; memset(&sentinel, 0xa5, sizeof(sentinel));
    rows[0].span.start = 6;
    out = sentinel;
    CHECK(gi_coverage_validate(text, designation, 3, rows, 2, &out, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(memcmp(&out, &sentinel, sizeof(out)) == 0);
    rows[0].span = (gi_span){4, 10};
    CHECK(gi_coverage_validate(text, designation, 3, rows, 2, &out, NULL) == GOLEM_ERR_INVALID_STATE);
    rows[0].span = (gi_span){4, 9}; rows[0].classification = (gi_classification)99;
    CHECK(gi_coverage_validate(text, designation, 3, rows, 2, &out, NULL) == GOLEM_ERR_PARSE);
    rows[0].classification = GI_CONTEXT;
    gi_span disconnected[] = {{0, 2}, {5, 9}};
    CHECK(gi_coverage_validate(text, disconnected, 2, rows, 2, &out, NULL) == GOLEM_ERR_INVALID_STATE);
    gi_coverage_row exact[] = {{{5, 9}, GI_REQUIREMENT}, {{0, 2}, GI_CONSTRAINT}};
    CHECK(gi_coverage_validate(text, disconnected, 2, exact, 2, &out, NULL) == GOLEM_OK && out.designated_bytes == 6);
    CHECK(gi_coverage_validate(text, designation, SIZE_MAX, rows, 2, &out, NULL) == GOLEM_ERR_OVERFLOW);
    CHECK(gi_coverage_validate(text, designation, 3, rows, SIZE_MAX, &out, NULL) == GOLEM_ERR_OVERFLOW);
    CHECK(gi_coverage_validate(text, designation, 0, rows, 2, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_coverage_validate(text, designation, 3, rows, 2, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    const unsigned char korean[] = {0xea, 0xb0, 0x80, 'x'};
    gi_span all = {0, 4}; gi_coverage_row split = {{0, 2}, GI_CONTEXT};
    CHECK(gi_coverage_validate((golem_bytes){korean, 4}, &all, 1, &split, 1, &out, NULL) == GOLEM_ERR_PARSE);
    return 0;
}
static unsigned mask(gi_span span)
{
    unsigned result = 0;
    for (size_t i = span.start; i < span.end; ++i) result |= 1u << i;
    return result;
}
static int coverage_model(void)
{
    gi_span spans[10]; size_t n = 0;
    for (size_t start = 0; start < 4; ++start)
        for (size_t end = start + 1; end <= 4; ++end) spans[n++] = (gi_span){start, end};
    size_t explored = 0;
    /* Independent bit-set oracle, including duplicates, arbitrary ordering,
     * overlaps, gaps and excursions beyond the adopted union. */
    for (size_t a = 0; a < n; ++a) for (size_t b = 0; b < n; ++b)
        for (size_t c = 0; c < n; ++c) for (size_t e = 0; e < n; ++e) {
            gi_span designated[] = {spans[a], spans[b]};
            gi_coverage_row rows[] = {{spans[c], GI_CONTEXT}, {spans[e], GI_NON_NORMATIVE}};
            gi_coverage_result out;
            bool exact = (mask(spans[a]) | mask(spans[b])) == (mask(spans[c]) | mask(spans[e]));
            golem_status status = gi_coverage_validate(bytes("abcd"), designated, 2, rows, 2, &out, NULL);
            CHECK(status == (exact ? GOLEM_OK : GOLEM_ERR_INVALID_STATE));
            if (exact) CHECK(out.classification_review_required);
            ++explored;
        }
    CHECK(explored == 10000);
    return 0;
}
static int source_sets(void)
{
    uint8_t *raw = malloc(GI_SOURCE_MAX + 1u);
    CHECK(raw != NULL); memset(raw, 'a', GI_SOURCE_MAX + 1u);
    CHECK(gi_text_validate((golem_bytes){raw, GI_SOURCE_MAX - 1u}, NULL) == GOLEM_OK);
    CHECK(gi_text_validate((golem_bytes){raw, GI_SOURCE_MAX}, NULL) == GOLEM_OK);
    CHECK(gi_text_validate((golem_bytes){raw, GI_SOURCE_MAX + 1u}, NULL) == GOLEM_ERR_OVERFLOW);
    golem_bytes sources[] = {{raw, GI_SOURCE_MAX}, {raw, GI_SOURCE_MAX}, {raw, GI_SOURCE_MAX}, {raw, GI_SOURCE_MAX}, {raw, 1}};
    size_t total = SIZE_MAX;
    sources[3].size--;
    CHECK(gi_source_set_validate(sources, 4, &total, NULL) == GOLEM_OK && total == GI_BASELINE_SOURCE_MAX - 1u);
    sources[3].size++;
    CHECK(gi_source_set_validate(sources, 4, &total, NULL) == GOLEM_OK && total == GI_BASELINE_SOURCE_MAX);
    total = 7;
    CHECK(gi_source_set_validate(sources, 5, &total, NULL) == GOLEM_ERR_OVERFLOW && total == 7);
    sources[1] = (golem_bytes){NULL, 1};
    CHECK(gi_source_set_validate(sources, 2, &total, NULL) == GOLEM_ERR_INVALID_ARGUMENT && total == 7);
    CHECK(gi_source_set_validate(sources, SIZE_MAX, &total, NULL) == GOLEM_ERR_OVERFLOW);
    free(raw);
    return 0;
}
static int source_shape(const char *path)
{
    FILE *f = fopen(path, "rb"); CHECK(f != NULL);
    char fixture[4096]; size_t n = fread(fixture, 1, sizeof(fixture), f);
    CHECK(!ferror(f) && n < sizeof(fixture)); CHECK(fclose(f) == 0);
    golem_bytes control = {(const uint8_t *)fixture, n};
    gi_source_result out, sentinel; memset(&sentinel, 0xa5, sizeof(sentinel));
    CHECK(gi_source_validate(control, bytes("abc"), &out, NULL) == GOLEM_OK);
    golem_digest identity, unchanged; memset(&unchanged, 0xa5, sizeof(unchanged));
    CHECK(gi_source_identity(control, bytes("abc"), &identity, NULL) == GOLEM_OK);
    identity = unchanged;
    CHECK(gi_source_identity(control, bytes("abd"), &identity, NULL) == GOLEM_ERR_PARSE);
    CHECK(memcmp(&identity, &unchanged, sizeof(identity)) == 0);
    CHECK(out.byte_length == 3 && out.designated_bytes == 3);
    struct json_object *o = NULL; CHECK(golem_json_parse(control, GI_CONTROL_MAX, &o) == GOLEM_OK);
    const char *root_keys[] = {"schema", "project_id", "work_id", "created_by_assertion", "body"};
    for (size_t i = 0; i < 5; ++i) {
        struct json_object *copy = NULL; CHECK(json_object_deep_copy(o, &copy, NULL) == 0);
        json_object_object_del(copy, root_keys[i]);
        out = sentinel;
        CHECK(gi_source_validate(bytes(json_object_to_json_string(copy)), bytes("abc"), &out, NULL) == GOLEM_ERR_PARSE);
        CHECK(memcmp(&out, &sentinel, sizeof(out)) == 0); json_object_put(copy);
    }
    out = sentinel;
    CHECK(gi_source_validate(control, bytes("abd"), &out, NULL) == GOLEM_ERR_PARSE);
    CHECK(memcmp(&out, &sentinel, sizeof(out)) == 0);
    CHECK(gi_source_validate(control, bytes("ab"), &out, NULL) == GOLEM_ERR_PARSE);
    const char *bad[] = {"{\"a\":1,\"a\":2}", "{\"a\":\"\\u0000\"}", "{} {}", "{}\x80"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i)
        CHECK(gi_source_validate(bytes(bad[i]), bytes("abc"), &out, NULL) == GOLEM_ERR_PARSE);
    char *padded = malloc(GI_CONTROL_MAX + 1u); CHECK(padded != NULL);
    memcpy(padded, fixture, n); memset(padded + n, ' ', GI_CONTROL_MAX + 1u - n);
    CHECK(gi_source_validate((golem_bytes){(uint8_t *)padded, GI_CONTROL_MAX - 1u}, bytes("abc"), &out, NULL) == GOLEM_OK);
    CHECK(gi_source_validate((golem_bytes){(uint8_t *)padded, GI_CONTROL_MAX}, bytes("abc"), &out, NULL) == GOLEM_OK);
    CHECK(gi_source_validate((golem_bytes){(uint8_t *)padded, GI_CONTROL_MAX + 1u}, bytes("abc"), &out, NULL) == GOLEM_ERR_OVERFLOW);
    free(padded);
    struct json_object *body = NULL; CHECK(json_object_object_get_ex(o, "body", &body));
    json_object_object_add(body, "media_type", json_object_new_string("application/pdf"));
    golem_diagnostic d;
    CHECK(gi_source_validate(bytes(json_object_to_json_string(o)), bytes("abc"), &out, &d) == GOLEM_ERR_UNSUPPORTED_VERSION);
    CHECK(strcmp(d.message, "intent.source.unsupported_media") == 0);
    json_object_object_add(body, "media_type", json_object_new_string("text/markdown"));
    json_object_object_add(o, "work_id", NULL);
    CHECK(gi_source_validate(bytes(json_object_to_json_string(o)), bytes("abc"), &out, NULL) == GOLEM_OK);
    uint8_t exact[] = {0xef, 0xbb, 0xbf, 'a', '\r', '\n', 0xea, 0xb0, 0x80, 'e', 0xcc, 0x81, 0};
    uint8_t saved[sizeof(exact)]; memcpy(saved, exact, sizeof(exact));
    golem_digest raw_digest; char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t required;
    CHECK(golem_digest_bytes((golem_bytes){exact, sizeof(exact)}, &raw_digest) == GOLEM_OK);
    CHECK(golem_digest_format(&raw_digest, hex, sizeof(hex), &required) == GOLEM_OK);
    json_object_object_add(body, "body_cas", json_object_new_string(hex));
    json_object_object_add(body, "byte_length", json_object_new_int64((int64_t)sizeof(exact)));
    struct json_object *designation = NULL, *ranges = NULL;
    CHECK(json_object_object_get_ex(body, "designation", &designation));
    CHECK(json_object_object_get_ex(designation, "ranges", &ranges));
    json_object_object_add(json_object_array_get_idx(ranges, 0), "end", json_object_new_int64((int64_t)sizeof(exact)));
    CHECK(gi_source_validate(bytes(json_object_to_json_string(o)), (golem_bytes){exact, sizeof(exact)}, &out, NULL) == GOLEM_OK);
    CHECK(memcmp(saved, exact, sizeof(exact)) == 0 && out.byte_length == sizeof(exact));
    CHECK(memcmp(&raw_digest, &out.body_cas, sizeof(raw_digest)) == 0);
    exact[4] = '\n';
    CHECK(gi_source_validate(bytes(json_object_to_json_string(o)), (golem_bytes){exact, sizeof(exact)}, &out, NULL) == GOLEM_ERR_PARSE);
    json_object_object_add(o, "baseline_digest", json_object_new_string("future"));
    CHECK(gi_source_validate(bytes(json_object_to_json_string(o)), bytes("abc"), &out, NULL) == GOLEM_ERR_PARSE);
    json_object_put(o);
    CHECK(gi_source_validate(control, bytes("abc"), NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
static int domain_identity(void)
{
    golem_bytes control = bytes("{\"schema\":\"golem.intent.source.v1\"}");
    golem_digest digest, expected, raw, sentinel; memset(&sentinel, 0xa5, sizeof(sentinel));
    CHECK(golem_digest_parse((golem_string_view){"d71f3461ed10a2a93d68bf0003bee0c22b5c9df7360ccc3b0b46cc0584244511", 64}, &expected) == GOLEM_OK);
    CHECK(gi_domain_digest(control, &digest, NULL) == GOLEM_OK);
    CHECK(memcmp(&digest, &expected, sizeof(digest)) == 0);
    CHECK(golem_digest_bytes(control, &raw) == GOLEM_OK && memcmp(&raw, &digest, sizeof(raw)) != 0);
    CHECK(gi_domain_digest(bytes(" {\"schema\":\"golem.intent.source.v1\"}\n"), &digest, NULL) == GOLEM_OK);
    CHECK(memcmp(&digest, &expected, sizeof(digest)) != 0);
    const char *unknown[] = {"{}", "{\"schema\":\"golem.intent.baseline.v2\"}",
        "{\"schema\":\"golem.intent.object-publication.v1\"}",
        "{\"schema\":\"golem.intent.source.v2\"}", "{\"schema\":\"golem.intent.source.v1\\u0000\"}",
        "{\"schema\":true}", "{\"schema\":\"golem.intent.source.v1\",\"schema\":\"other\"}"};
    for (size_t i = 0; i < sizeof(unknown) / sizeof(*unknown); ++i) {
        digest = sentinel;
        CHECK(gi_domain_digest(bytes(unknown[i]), &digest, NULL) != GOLEM_OK);
        CHECK(memcmp(&digest, &sentinel, sizeof(digest)) == 0);
    }
    CHECK(gi_domain_digest((golem_bytes){NULL, 1}, &digest, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_domain_digest(control, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    gi_source_result source;
    CHECK(gi_source_validate(control, bytes("abc"), &source, NULL) == GOLEM_ERR_PARSE);
    return 0;
}
int main(int argc, char **argv)
{
    CHECK(argc == 3);
    if (strcmp(argv[1], "capacities") == 0) return capacities();
    if (strcmp(argv[1], "utf8") == 0) return utf8_ranges();
    if (strcmp(argv[1], "coverage") == 0) return coverage();
    if (strcmp(argv[1], "coverage-model") == 0) return coverage_model();
    if (strcmp(argv[1], "source-set") == 0) return source_sets();
    if (strcmp(argv[1], "source") == 0) return source_shape(argv[2]);
    if (strcmp(argv[1], "domain") == 0) return domain_identity();
    return EXIT_FAILURE;
}
