#include "../../src/intent/schema.h"
#include "../../src/common/json.h"
#include "test.h"
#include <string.h>

#define A "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
#define B "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
#define C "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
static const char fixture[] =
    "{\"schema\":\"golem.intent.baseline.v1\",\"project_id\":\"demo\",\"work_id\":null,"
    "\"created_by_assertion\":\"unverified\",\"body\":{\"source_refs\":[\"" A "\"],"
    "\"previous_baseline_digest\":null,\"decision_refs\":[],\"requirement_refs\":[\"" B "\"],"
    "\"constraint_refs\":[],\"issuer_policy_ref\":\"" C "\",\"coverage_manifest\":[{"
    "\"source_ref\":\"" A "\",\"rows\":[{\"start\":0,\"end\":1,\"classification\":\"REQUIREMENT\","
    "\"requirement_refs\":[\"" B "\"],\"constraint_refs\":[],\"rationale\":\"proposal only\",\"review_refs\":[]}]}]}}";

static struct json_object *get(struct json_object *o, const char *key)
{
    struct json_object *v = NULL;
    (void)json_object_object_get_ex(o, key, &v);
    return v;
}
static struct json_object *fresh(void) { return json_tokener_parse(fixture); }
static int check_wire(const char *wire, size_t length, bool valid)
{
    gi_baseline_result out, before;
    memset(&out, 0x5a, sizeof(out)); memcpy(&before, &out, sizeof(out));
    char *copy = malloc(length ? length : 1);
    CHECK(copy != NULL); memcpy(copy, wire, length);
    golem_diagnostic d;
    golem_status st = gi_baseline_validate((golem_bytes){(const uint8_t *)wire, length}, &out, &d);
    CHECK((st == GOLEM_OK) == valid);
    CHECK(memcmp(copy, wire, length) == 0); free(copy);
    if (valid) CHECK(out.source_coverage_unverified && out.references_unverified && out.semantic_review_required);
    else {
        CHECK(memcmp(&out, &before, sizeof(out)) == 0);
        CHECK(strncmp(d.message, "intent.", 7) == 0);
    }
    return 0;
}
static int check(struct json_object *o, bool valid)
{
    const char *wire = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    int result = check_wire(wire, strlen(wire), valid);
    json_object_put(o);
    return result;
}
static int replace_wire(const char *old, const char *replacement, bool valid)
{
    const char *at = strstr(fixture, old); CHECK(at != NULL);
    size_t prefix = (size_t)(at - fixture), n = strlen(fixture) - strlen(old) + strlen(replacement);
    char *wire = malloc(n + 1); CHECK(wire != NULL);
    memcpy(wire, fixture, prefix);
    memcpy(wire + prefix, replacement, strlen(replacement));
    strcpy(wire + prefix + strlen(replacement), at + strlen(old));
    int result = check_wire(wire, n, valid); free(wire); return result;
}
static golem_bytes wire_bytes(struct json_object *o)
{
    const char *s = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    return (golem_bytes){(const uint8_t *)s, strlen(s)};
}
static struct json_object *source_fixture(void)
{
    return json_tokener_parse("{\"schema\":\"golem.intent.source.v1\",\"project_id\":\"demo\","
        "\"work_id\":null,\"created_by_assertion\":\"unverified\",\"body\":{\"body_cas\":\"" A "\","
        "\"byte_length\":5,\"media_type\":\"text/plain\",\"encoding\":\"UTF-8\",\"origin\":\"MODEL_DRAFT\","
        "\"capture_ref\":\"unverified\",\"designation\":{\"scope_id\":\"opaque\","
        "\"ranges\":[{\"start\":0,\"end\":5}],\"purpose\":\"PRODUCT_REQUIREMENT\","
        "\"decision_ref\":\"" B "\"},\"execution_authority\":false}}");
}
static int source_hash(struct json_object *source, golem_bytes text)
{
    golem_digest digest; char hex[65]; size_t required;
    CHECK(golem_digest_bytes(text, &digest) == GOLEM_OK);
    CHECK(golem_digest_format(&digest, hex, sizeof(hex), &required) == GOLEM_OK);
    json_object_object_add(get(source, "body"), "body_cas", json_object_new_string(hex));
    json_object_object_add(get(source, "body"), "byte_length", json_object_new_uint64(text.size));
    return 0;
}
static int bind_source(struct json_object *baseline, struct json_object *source, size_t index)
{
    golem_digest digest; char hex[65]; size_t required;
    CHECK(gi_domain_digest(wire_bytes(source), &digest, NULL) == GOLEM_OK);
    CHECK(golem_digest_format(&digest, hex, sizeof(hex), &required) == GOLEM_OK);
    struct json_object *b = get(baseline, "body");
    json_object_array_put_idx(get(b, "source_refs"), index, json_object_new_string(hex));
    struct json_object *entry = json_object_array_get_idx(get(b, "coverage_manifest"), index);
    json_object_object_add(entry, "source_ref", json_object_new_string(hex));
    return 0;
}
static int linked_check(struct json_object *baseline, gi_source_input *sources, size_t count,
    bool valid, size_t total, size_t designated, bool questions)
{
    gi_baseline_coverage_result out, before;
    memset(&out, 0x5a, sizeof(out)); memcpy(&before, &out, sizeof(out));
    golem_bytes wire = wire_bytes(baseline);
    golem_digest old[5], now;
    CHECK(count <= 2);
    CHECK(golem_digest_bytes(wire, &old[0]) == GOLEM_OK);
    for (size_t i = 0; i < count; ++i) {
        CHECK(golem_digest_bytes(sources[i].control, &old[1 + 2 * i]) == GOLEM_OK);
        CHECK(golem_digest_bytes(sources[i].text, &old[2 + 2 * i]) == GOLEM_OK);
    }
    golem_diagnostic d;
    golem_status st = gi_baseline_coverage_validate(wire, sources, count, &out, &d);
    CHECK((st == GOLEM_OK) == valid);
    CHECK(golem_digest_bytes(wire, &now) == GOLEM_OK && memcmp(&now, &old[0], sizeof(now)) == 0);
    for (size_t i = 0; i < count; ++i) {
        CHECK(golem_digest_bytes(sources[i].control, &now) == GOLEM_OK && memcmp(&now, &old[1 + 2 * i], sizeof(now)) == 0);
        CHECK(golem_digest_bytes(sources[i].text, &now) == GOLEM_OK && memcmp(&now, &old[2 + 2 * i], sizeof(now)) == 0);
    }
    if (!valid) {
        CHECK(memcmp(&out, &before, sizeof(out)) == 0);
        CHECK(strncmp(d.message, "intent.", 7) == 0);
    } else {
        CHECK(out.baseline.sources == count && out.source_bytes == total && out.designated_bytes == designated);
        CHECK(!out.baseline.source_coverage_unverified && out.baseline.references_unverified && out.baseline.semantic_review_required);
        CHECK(out.adoption_unverified && out.issuer_unverified && out.baseline.has_questions == questions);
    }
    return 0;
}
static int linked_limits(void)
{
    uint8_t *raw = malloc(GI_SOURCE_MAX); CHECK(raw != NULL);
    memset(raw, 'x', GI_SOURCE_MAX);
    golem_bytes text = {raw, GI_SOURCE_MAX};
    struct json_object *b = fresh(), *sources[5];
    struct json_object *m = get(get(b, "body"), "coverage_manifest");
    struct json_object *e = json_object_array_get_idx(m, 0);
    json_object_object_add(json_object_array_get_idx(get(e, "rows"), 0), "end", json_object_new_int(5));
    gi_source_input inputs[5];
    for (size_t i = 0; i < 4; ++i) {
        sources[i] = source_fixture();
        CHECK(source_hash(sources[i], text) == 0);
        char assertion[16]; (void)snprintf(assertion, sizeof(assertion), "source-%zu", i);
        json_object_object_add(sources[i], "created_by_assertion", json_object_new_string(assertion));
        if (i) json_object_array_add(m, json_tokener_parse(json_object_to_json_string(e)));
        CHECK(bind_source(b, sources[i], i) == 0);
        inputs[i] = (gi_source_input){wire_bytes(sources[i]), text};
    }
    gi_baseline_coverage_result out, before;
    CHECK(gi_baseline_coverage_validate(wire_bytes(b), inputs, 4, &out, NULL) == GOLEM_OK);
    CHECK(out.source_bytes == GI_BASELINE_SOURCE_MAX && out.designated_bytes == 20);
    memcpy(&before, &out, sizeof(out));
    sources[4] = source_fixture();
    golem_bytes one = {raw, 1};
    CHECK(source_hash(sources[4], one) == 0);
    json_object_array_add(m, json_tokener_parse(json_object_to_json_string(e)));
    CHECK(bind_source(b, sources[4], 4) == 0);
    inputs[4] = (gi_source_input){wire_bytes(sources[4]), one};
    golem_diagnostic d;
    CHECK(gi_baseline_coverage_validate(wire_bytes(b), inputs, 5, &out, &d) == GOLEM_ERR_OVERFLOW);
    CHECK(strcmp(d.message, "intent.limit.baseline_source_bytes") == 0);
    CHECK(memcmp(&before, &out, sizeof(out)) == 0);
    for (size_t i = 0; i < 5; ++i) json_object_put(sources[i]);
    json_object_put(b); free(raw);
    return 0;
}
static int linked_coverage(void)
{
    const uint8_t raw[] = {'A', 0xea, 0xb0, 0x80, 'Z'};
    golem_bytes text = {raw, sizeof(raw)};
    for (unsigned mode = 0; mode < 20; ++mode) {
        struct json_object *b = fresh(), *s = source_fixture(), *body = get(b, "body");
        CHECK(source_hash(s, text) == 0);
        struct json_object *e = json_object_array_get_idx(get(body, "coverage_manifest"), 0);
        struct json_object *rows = get(e, "rows"), *r = json_object_array_get_idx(rows, 0);
        struct json_object *ranges = get(get(get(s, "body"), "designation"), "ranges");
        struct json_object *range = json_object_array_get_idx(ranges, 0);
        json_object_object_add(r, "end", json_object_new_int(5));
        bool valid = mode == 0 || mode == 1 || mode == 2 || mode == 3 || mode == 17 || mode == 18;
        size_t designated = mode == 18 ? 4 : 5;
        switch (mode) {
        case 1: json_object_array_add(rows, json_object_get(r)); break;
        case 2: json_object_object_add(r, "classification", json_object_new_string("QUESTION_REQUIRED")); break;
        case 3: json_object_object_add(r, "classification", json_object_new_string("NON_NORMATIVE")); break;
        case 4: json_object_object_add(e, "rows", json_object_new_array()); break;
        case 5: json_object_object_add(r, "end", json_object_new_int(4)); break;
        case 6: json_object_object_add(r, "start", json_object_new_int(2)); break;
        case 7: json_object_object_add(r, "end", json_object_new_int(6)); break;
        case 8: json_object_object_add(r, "end", json_object_new_uint64(UINT64_MAX)); break;
        case 9: json_object_object_add(range, "end", json_object_new_int(4)); break;
        case 10: json_object_object_add(get(s, "body"), "body_cas", json_object_new_string(A)); break;
        case 11: json_object_object_add(get(s, "body"), "byte_length", json_object_new_int(4)); break;
        case 12: json_object_object_add(s, "project_id", json_object_new_string("other")); break;
        case 13: json_object_object_add(get(s, "body"), "media_type", json_object_new_string("application/pdf")); break;
        case 14: json_object_object_add(range, "start", json_object_new_int(2)); break;
        case 15: json_object_object_add(r, "end", json_object_new_int(2)); break;
        case 17: json_object_array_add(ranges, json_object_get(range)); break;
        case 18: json_object_object_add(range, "start", json_object_new_int(1));
                 json_object_object_add(r, "start", json_object_new_int(1)); break;
        case 19: json_object_object_add(range, "end", json_object_new_int(1));
                 json_object_array_add(ranges, json_tokener_parse("{\"start\":4,\"end\":5}")); break;
        default: break;
        }
        CHECK(bind_source(b, s, 0) == 0);
        if (mode == 16) json_object_object_add(s, "created_by_assertion", json_object_new_string("changed-after-binding"));
        gi_source_input input = {wire_bytes(s), text};
        CHECK(linked_check(b, &input, 1, valid, 5, designated, mode == 2) == 0);
        json_object_put(s); json_object_put(b);
    }
    const char *bw[] = {NULL, "one"}, *sw[] = {NULL, "one", "two"};
    for (size_t i = 0; i < 2; ++i) for (size_t j = 0; j < 3; ++j) {
        struct json_object *b = fresh(), *s = source_fixture();
        CHECK(source_hash(s, text) == 0);
        json_object_object_add(b, "work_id", bw[i] ? json_object_new_string(bw[i]) : NULL);
        json_object_object_add(s, "work_id", sw[j] ? json_object_new_string(sw[j]) : NULL);
        struct json_object *e = json_object_array_get_idx(get(get(b, "body"), "coverage_manifest"), 0);
        json_object_object_add(json_object_array_get_idx(get(e, "rows"), 0), "end", json_object_new_int(5));
        CHECK(bind_source(b, s, 0) == 0);
        gi_source_input input = {wire_bytes(s), text};
        CHECK(linked_check(b, &input, 1, j == 0 || (i == 1 && j == 1), 5, 5, false) == 0);
        json_object_put(s); json_object_put(b);
    }
    struct json_object *b = fresh(), *s = source_fixture(), *s2 = source_fixture();
    CHECK(source_hash(s, text) == 0 && source_hash(s2, text) == 0);
    json_object_object_add(s2, "created_by_assertion", json_object_new_string("second"));
    struct json_object *m = get(get(b, "body"), "coverage_manifest"), *e = json_object_array_get_idx(m, 0);
    json_object_object_add(json_object_array_get_idx(get(e, "rows"), 0), "end", json_object_new_int(5));
    json_object_array_add(m, json_tokener_parse(json_object_to_json_string(e)));
    CHECK(bind_source(b, s, 0) == 0 && bind_source(b, s2, 1) == 0);
    gi_source_input inputs[] = {{wire_bytes(s2), text}, {wire_bytes(s), text}};
    CHECK(linked_check(b, inputs, 2, true, 10, 10, false) == 0);
    CHECK(linked_check(b, inputs, 1, false, 0, 0, false) == 0);
    CHECK(linked_check(b, inputs, 0, false, 0, 0, false) == 0);
    struct json_object *last_row = json_object_array_get_idx(get(e, "rows"), 0);
    json_object_object_add(last_row, "end", json_object_new_int(4));
    CHECK(linked_check(b, inputs, 2, false, 0, 0, false) == 0);
    json_object_object_add(last_row, "end", json_object_new_int(5));
    inputs[1] = inputs[0];
    CHECK(linked_check(b, inputs, 2, false, 0, 0, false) == 0);
    inputs[1] = (gi_source_input){wire_bytes(s), {(const uint8_t *)"bad", 3}};
    CHECK(linked_check(b, inputs, 2, false, 0, 0, false) == 0);
    gi_baseline_coverage_result out;
    CHECK(gi_baseline_coverage_validate(wire_bytes(b), NULL, 2, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_baseline_coverage_validate(wire_bytes(b), inputs, 2, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    inputs[1].text = (golem_bytes){raw, GI_SOURCE_MAX + 1};
    CHECK(gi_baseline_coverage_validate(wire_bytes(b), inputs, 2, &out, NULL) == GOLEM_ERR_OVERFLOW);
    struct json_object *single = fresh();
    CHECK(gi_baseline_coverage_validate(wire_bytes(single), inputs, 2, &out, NULL) == GOLEM_ERR_INVALID_STATE);
    json_object_put(single);
    json_object_put(b); json_object_put(s); json_object_put(s2);
    return 0;
}
int main(void)
{
    CHECK(linked_limits() == 0);
    CHECK(linked_coverage() == 0);
    CHECK(check_wire(fixture, strlen(fixture), true) == 0);
    golem_digest identity, expected, saved;
    CHECK(gi_domain_digest((golem_bytes){(const uint8_t *)fixture, strlen(fixture)}, &identity, NULL)
        == GOLEM_OK);
    CHECK(gi_baseline_identity((golem_bytes){(const uint8_t *)fixture, strlen(fixture)}, &expected, NULL) == GOLEM_OK);
    CHECK(memcmp(&identity, &expected, sizeof(identity)) == 0);
    saved = identity;
    const char *incomplete = "{\"schema\":\"golem.intent.baseline.v1\"}";
    CHECK(gi_baseline_identity((golem_bytes){(const uint8_t *)incomplete, strlen(incomplete)}, &identity, NULL) != GOLEM_OK);
    CHECK(memcmp(&saved, &identity, sizeof(identity)) == 0);
    CHECK(gi_baseline_identity((golem_bytes){NULL, 0}, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(replace_wire("\"end\":1", "\"end\":18446744073709551616", false) == 0);
    CHECK(replace_wire("\"end\":1", "\"end\":18446744073709551615", true) == 0);
    CHECK(replace_wire("\"end\":1", "\"end\":1e0", false) == 0);
    CHECK(replace_wire("\"end\":1", "\"end\":1,\"end\":1", false) == 0);
    CHECK(replace_wire("\"work_id\":null", "\"work_id\":\"work-a\"", true) == 0);
    CHECK(replace_wire("\"work_id\":null", "\"work_id\":false", false) == 0);
    CHECK(replace_wire("\"previous_baseline_digest\":null", "\"previous_baseline_digest\":\"" B "\"", true) == 0);
    CHECK(replace_wire("\"previous_baseline_digest\":null", "\"previous_baseline_digest\":false", false) == 0);
    CHECK(replace_wire("proposal only", "\\ud800", false) == 0);
    CHECK(replace_wire("proposal only", "\\u0000", false) == 0);
    CHECK(replace_wire("proposal only", "\\ud83d\\ude00", true) == 0);
    CHECK(replace_wire("\"project_id\":\"demo\"", "\"project_id\":\"demo\",\"baseline_digest\":\"" A "\"", false) == 0);
    const char *levels[][8] = {
        {"schema", "project_id", "work_id", "created_by_assertion", "body", NULL},
        {"source_refs", "previous_baseline_digest", "decision_refs", "requirement_refs", "constraint_refs", "coverage_manifest", "issuer_policy_ref", NULL},
        {"source_ref", "rows", NULL},
        {"start", "end", "classification", "requirement_refs", "constraint_refs", "rationale", "review_refs", NULL}
    };
    for (size_t level = 0; level < 4; ++level) {
        for (size_t field = 0; levels[level][field]; ++field) {
            struct json_object *o = fresh(), *b = get(o, "body");
            struct json_object *entry = json_object_array_get_idx(get(b, "coverage_manifest"), 0);
            struct json_object *targets[] = {o, b, entry, json_object_array_get_idx(get(entry, "rows"), 0)};
            json_object_object_del(targets[level], levels[level][field]);
            CHECK(check(o, false) == 0);
        }
        struct json_object *o = fresh(), *b = get(o, "body");
        struct json_object *entry = json_object_array_get_idx(get(b, "coverage_manifest"), 0);
        struct json_object *targets[] = {o, b, entry, json_object_array_get_idx(get(entry, "rows"), 0)};
        json_object_object_add(targets[level], "ACTIVE", json_object_new_boolean(1));
        CHECK(check(o, false) == 0);
    }
    const char *arrays[] = {"source_refs", "decision_refs", "requirement_refs", "constraint_refs"};
    const char *bad_refs[] = {"", "abc", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg"};
    for (size_t i = 0; i < 4; ++i) {
        struct json_object *empty = fresh();
        json_object_object_add(get(empty, "body"), arrays[i], json_object_new_array());
        /* A removed requirement still referenced by a row is invalid. */
        CHECK(check(empty, i == 1 || i == 3) == 0);
        struct json_object *wrong_type = fresh();
        json_object_object_add(get(wrong_type, "body"), arrays[i], NULL);
        CHECK(check(wrong_type, false) == 0);
        for (size_t j = 0; j < 4; ++j) {
            struct json_object *o = fresh(), *a = json_object_new_array();
            json_object_array_add(a, json_object_new_string(bad_refs[j]));
            json_object_object_add(get(o, "body"), arrays[i], a);
            CHECK(check(o, false) == 0);
        }
        struct json_object *o = fresh(), *a = json_object_new_array();
        json_object_array_add(a, json_object_new_string(B)); json_object_array_add(a, json_object_new_string(B));
        json_object_object_add(get(o, "body"), arrays[i], a);
        CHECK(check(o, false) == 0);
    }
    struct json_object *empty_proposal = fresh(), *empty_body = get(empty_proposal, "body");
    json_object_object_add(empty_body, "requirement_refs", json_object_new_array());
    struct json_object *empty_entry = json_object_array_get_idx(get(empty_body, "coverage_manifest"), 0);
    json_object_object_add(empty_entry, "rows", json_object_new_array());
    CHECK(check(empty_proposal, true) == 0);
    struct json_object *multi = fresh(), *mb = get(multi, "body");
    struct json_object *mm = get(mb, "coverage_manifest"), *me = json_object_array_get_idx(mm, 0);
    struct json_object *mr = json_object_array_get_idx(get(me, "rows"), 0);
    json_object_array_add(get(mb, "source_refs"), json_object_new_string(B));
    struct json_object *second = json_object_new_object();
    json_object_object_add(second, "source_ref", json_object_new_string(B));
    json_object_object_add(second, "rows", json_object_new_array());
    json_object_array_add(mm, second);
    /* Manifest order need not match source_refs; input bytes remain untouched. */
    json_object_get(me); json_object_get(second);
    json_object_array_put_idx(mm, 0, second); json_object_array_put_idx(mm, 1, me);
    json_object_array_add(get(mb, "constraint_refs"), json_object_new_string(C));
    json_object_array_add(get(mr, "constraint_refs"), json_object_new_string(C));
    json_object_array_add(get(mr, "review_refs"), json_object_new_string(A));
    json_object_array_add(get(mb, "decision_refs"), json_object_new_string(A));
    CHECK(check(multi, true) == 0);
    for (unsigned mode = 0; mode < 15; ++mode) {
        struct json_object *o = fresh(), *b = get(o, "body");
        struct json_object *m = get(b, "coverage_manifest"), *e = json_object_array_get_idx(m, 0);
        struct json_object *rows = get(e, "rows"), *r = json_object_array_get_idx(rows, 0);
        bool valid = false;
        switch (mode) {
        case 0: json_object_object_add(e, "rows", json_object_new_array()); valid = true; break;
        case 1: json_object_object_add(r, "start", json_object_new_int(-1)); break;
        case 2: json_object_object_add(r, "end", json_object_new_int(0)); break;
        case 3: json_object_object_add(r, "end", json_object_new_double(1.0)); break;
        case 4: json_object_object_add(r, "rationale", json_object_new_string("")); break;
        case 5: json_object_object_add(r, "classification", json_object_new_string("PASS")); break;
        case 6: json_object_array_add(get(r, "constraint_refs"), json_object_new_string(C)); break;
        case 7: json_object_array_add(get(r, "requirement_refs"), json_object_new_string(C)); break;
        case 8: json_object_array_add(get(r, "requirement_refs"), json_object_new_string(B)); break;
        case 9: json_object_array_add(get(r, "review_refs"), json_object_new_string(C));
                json_object_array_add(get(r, "review_refs"), json_object_new_string(C)); break;
        case 10: json_object_object_add(e, "source_ref", json_object_new_string(B)); break;
        case 11: json_object_array_add(get(b, "source_refs"), json_object_new_string(B)); break;
        case 12: json_object_array_add(get(b, "source_refs"), json_object_new_string(B));
                 json_object_array_add(m, json_object_get(e)); break;
        case 13: json_object_array_add(rows, json_object_get(r)); valid = true; break;
        case 14: json_object_object_add(r, "end", json_object_new_uint64(UINT64_MAX)); valid = true; break;
        }
        CHECK(check(o, valid) == 0);
    }
    const char *classes[] = {"REQUIREMENT", "CONSTRAINT", "CONTEXT", "EXPLICIT_NON_GOAL", "NON_NORMATIVE", "QUESTION_REQUIRED"};
    for (size_t i = 0; i < 6; ++i) {
        struct json_object *o = fresh(), *b = get(o, "body");
        struct json_object *e = json_object_array_get_idx(get(b, "coverage_manifest"), 0);
        struct json_object *r = json_object_array_get_idx(get(e, "rows"), 0);
        json_object_object_add(r, "classification", json_object_new_string(classes[i]));
        const char *wire = json_object_to_json_string(o);
        gi_baseline_result result;
        CHECK(gi_baseline_validate((golem_bytes){(const uint8_t *)wire, strlen(wire)}, &result, NULL) == GOLEM_OK);
        CHECK(result.has_questions == (i == 5));
        CHECK(result.sources == 1 && result.requirements == 1 && result.coverage_rows == 1);
        CHECK(check(o, true) == 0);
    }
    for (size_t count = 1023; count <= 1025; ++count) {
        struct json_object *o = fresh(), *b = get(o, "body"), *a = get(b, "requirement_refs");
        for (size_t i = 1; i < count; ++i) {
            char ref[65]; (void)snprintf(ref, sizeof(ref), "%064zx", i);
            json_object_array_add(a, json_object_new_string(ref));
        }
        CHECK(check(o, count <= GI_REQUIREMENT_MAX) == 0);
    }
    char *padded = malloc(GI_CONTROL_MAX + 1); CHECK(padded != NULL);
    memset(padded, ' ', GI_CONTROL_MAX + 1); memcpy(padded, fixture, strlen(fixture));
    CHECK(check_wire(padded, GI_CONTROL_MAX, true) == 0);
    CHECK(check_wire(padded, GI_CONTROL_MAX + 1, false) == 0); free(padded);
    const char *bad[] = {"{}", "{\"body\":{},\"body\":{}}", "{\"x\":\"\\ud800\"}",
        "{\"x\":18446744073709551616}", "{\"x\":\"\\u0000\"}", "{\"x\":\"\xff\"}"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) CHECK(check_wire(bad[i], strlen(bad[i]), false) == 0);
    gi_baseline_result out;
    CHECK(gi_baseline_validate((golem_bytes){NULL, 1}, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_baseline_validate((golem_bytes){NULL, 0}, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
