#include "qa_result.h"
#include "../document/internal.h"
#include "../execution/internal.h"
#include <string.h>
static bool eq(struct json_object *o, const char *k, const char *v)
{
    return !strcmp(dw_text(o, k), v);
}
static const char *case_status(struct json_object *contract, struct json_object *receipt,
                               struct json_object *map)
{
    struct json_object *expected = dw_get(contract, "gates"), *actual = dw_get(receipt, "gates"),
                       *gate = NULL, *result = NULL;
    if (!receipt)
        return "NOT_RUN";
    if (!json_object_is_type(expected, json_type_array))
        return "UNKNOWN";
    if (!json_object_is_type(actual, json_type_array) ||
        json_object_array_length(actual) != json_object_array_length(expected))
        return "UNKNOWN";
    for (size_t i = 0; i < json_object_array_length(expected); ++i) {
        struct json_object *wanted = json_object_array_get_idx(expected, i);
        size_t matches = 0;
        for (size_t j = 0; j < json_object_array_length(actual); ++j) {
            struct json_object *got = json_object_array_get_idx(actual, j);
            if (eq(got, "gate_id", dw_text(wanted, "id")) &&
                json_object_equal(dw_get(got, "version"), dw_get(wanted, "version")))
                ++matches;
            if (eq(receipt, "status", "PASS") && !eq(got, "status", "PASS"))
                return "UNKNOWN";
        }
        if (matches != 1)
            return "UNKNOWN";
    }
    for (size_t i = 0; i < json_object_array_length(expected); ++i) {
        struct json_object *g = json_object_array_get_idx(expected, i);
        if (eq(g, "id", dw_text(map, "gate_id")) &&
            json_object_equal(dw_get(g, "version"), dw_get(map, "gate_version")))
            gate = g;
    }
    for (size_t i = 0; i < json_object_array_length(actual); ++i) {
        struct json_object *g = json_object_array_get_idx(actual, i);
        if (eq(g, "gate_id", dw_text(map, "gate_id")) &&
            json_object_equal(dw_get(g, "version"), dw_get(map, "gate_version"))) {
            if (result)
                return "UNKNOWN";
            result = g;
        }
    }
    if (!gate || !result)
        return "UNKNOWN";
    if (eq(result, "status", "ERROR"))
        return "ERROR";
    if (eq(result, "status", "FAIL"))
        return "FAIL";
    if (!eq(result, "status", "PASS"))
        return "UNKNOWN";
    struct json_object *cases = dw_get(result, "cases"), *expected_cases = dw_get(gate, "cases");
    if (!json_object_is_type(cases, json_type_array) ||
        json_object_array_length(cases) != json_object_array_length(expected_cases))
        return "UNKNOWN";
    const char *found = NULL;
    for (size_t i = 0; i < json_object_array_length(cases); ++i) {
        struct json_object *c = json_object_array_get_idx(cases, i);
        const char *keys[] = {"id", "status"};
        bool known = false;
        if (!dw_keys(c, keys, 2))
            return "UNKNOWN";
        for (size_t j = 0; j < json_object_array_length(expected_cases); ++j)
            if (eq(json_object_array_get_idx(expected_cases, j), "id", dw_text(c, "id")))
                known = true;
        if (!known)
            return "UNKNOWN";
        for (size_t j = 0; j < i; ++j)
            if (eq(json_object_array_get_idx(cases, j), "id", dw_text(c, "id")))
                return "UNKNOWN";
        if (!eq(c, "status", "PASS") && !eq(c, "status", "FAIL") && !eq(c, "status", "ERROR"))
            return "UNKNOWN";
        /* A PASS gate cannot contain failed/error observations. */
        if (!eq(c, "status", "PASS"))
            return "UNKNOWN";
        if (eq(c, "id", dw_text(map, "case_id")))
            found = dw_text(c, "status");
    }
    return found ? found : "UNKNOWN";
}
static int rank(const char *s)
{
    const char *v[] = {"PASS", "NOT_RUN", "UNKNOWN", "FAIL", "ERROR"};
    for (int i = 0; i < 5; ++i)
        if (!strcmp(v[i], s))
            return i;
    return 2;
}
golem_status gi_qa_native_results(struct json_object *obligations, struct json_object *mapping,
                                  struct json_object *contract, struct json_object *receipt,
                                  struct json_object **out)
{
    if (!out || !json_object_is_type(obligations, json_type_array) ||
        json_object_array_length(obligations) > 4096 ||
        !json_object_is_type(mapping, json_type_array) || json_object_array_length(mapping) > 16384)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *rows = json_object_new_array();
    if (!rows)
        return GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; i < json_object_array_length(obligations); ++i) {
        struct json_object *o = json_object_array_get_idx(obligations, i),
                           *r = json_object_new_object(), *refs = json_object_new_array();
        const char *status = eq(o, "evidence_kind", "SEMANTIC_REVIEW") ? "NOT_RUN" : "UNKNOWN";
        bool found = false;
        if (eq(o, "evidence_kind", "NATIVE_QA"))
            for (size_t j = 0; j < json_object_array_length(mapping); ++j) {
                struct json_object *m = json_object_array_get_idx(mapping, j);
                if (!eq(m, "obligation_id", dw_text(o, "id")))
                    continue;
                const char *value = case_status(contract, receipt, m);
                if (!found || rank(value) > rank(status))
                    status = value;
                found = true;
            }
        if (!dw_add(r, "obligation_id", json_object_new_string(dw_text(o, "id"))) ||
            !dw_add(r, "evidence_refs", refs) ||
            !dw_add(r, "status", json_object_new_string(status)) ||
            json_object_array_add(rows, r) != 0) {
            json_object_put(r);
            json_object_put(rows);
            return GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    *out = rows;
    return GOLEM_OK;
}

/* Result/completion documents advance generation without changing QA inputs.
 * Do not mutate the receipt, omit dependency checks, or normalize other fields. */
golem_status gi_qa_manifest_matches(struct json_object *recorded, struct json_object *current)
{
    struct json_object *old = dw_get(recorded, "generation"), *now = dw_get(current, "generation"),
                       *copy = NULL;
    if (!json_object_is_type(recorded, json_type_object) ||
        !json_object_is_type(current, json_type_object) ||
        !json_object_is_type(old, json_type_int) || !json_object_is_type(now, json_type_int) ||
        json_object_get_int64(old) <= 0 || json_object_get_int64(now) <= 0 ||
        json_object_get_uint64(old) > json_object_get_uint64(now))
        return GOLEM_ERR_STALE_RESULT;
    if (json_object_deep_copy(recorded, &copy, NULL))
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st =
        dw_add(copy, "generation", json_object_get(now)) ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && !json_object_equal(copy, current))
        st = GOLEM_ERR_STALE_RESULT;
    json_object_put(copy);
    return st;
}
