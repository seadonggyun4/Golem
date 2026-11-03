#include "qa_paths.h"
#include "../common/json.h"
#include "../document/internal.h"
#include "golem/execution.h"
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
static const char *routes[] = {"UI", "API", "BATCH", "STATE_TRANSITION", "OTHER_LOCAL"};
static const char *stages[] = {"REQUIREMENTS",    "DESIGN",      "TASK_DECOMPOSITION",
                               "IMPLEMENTATION",  "TEST_DESIGN", "INTEGRATION",
                               "FINAL_VALIDATION"};
static bool eq(struct json_object *o, const char *k, const char *s)
{
    return !strcmp(dw_text(o, k), s);
}
static bool array(struct json_object *a, size_t max)
{
    return json_object_is_type(a, json_type_array) && json_object_array_length(a) <= max;
}
static bool text(struct json_object *o, const char *k)
{
    struct json_object *v = dw_get(o, k);
    const char *s = dw_text(o, k);
    if (!json_object_is_type(v, json_type_string) || !strlen(s) || strlen(s) > 4096 ||
        strlen(s) != (size_t)json_object_get_string_len(v))
        return false;
    bool content = false;
    for (size_t i = 0; s[i]; ++i)
        if (!isspace((unsigned char)s[i]) && s[i] != '.' && s[i] != '?' && s[i] != '-')
            content = true;
    if (!content)
        return false;
    /* A padded/lowercase placeholder is still not an exact rationale/oracle.
     * This finite spelling check makes no semantic completeness claim. */
    size_t begin = 0, end = strlen(s);
    while (begin < end && isspace((unsigned char)s[begin]))
        ++begin;
    while (end > begin && isspace((unsigned char)s[end - 1]))
        --end;
    const char *placeholders[] = {"TODO", "TBD", "N/A"};
    for (size_t i = 0; i < 3; ++i) {
        size_t n = strlen(placeholders[i]);
        bool same = end - begin == n;
        for (size_t j = 0; same && j < n; ++j)
            if (toupper((unsigned char)s[begin + j]) != placeholders[i][j])
                same = false;
        if (same)
            return false;
    }
    return true;
}
static bool dig(struct json_object *v, golem_digest *d)
{
    if (!json_object_is_type(v, json_type_string) || json_object_get_string_len(v) != 64)
        return false;
    const char *s = json_object_get_string(v);
    for (size_t i = 0; i < 64; ++i)
        if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f')))
            return false;
    return golem_digest_parse((golem_string_view){s, 64}, d) == GOLEM_OK;
}
static bool digest_is(struct json_object *o, const char *k, const golem_digest *d)
{
    golem_digest v;
    return dig(dw_get(o, k), &v) && !memcmp(v.bytes, d->bytes, 32);
}
static int index_of(const char *s, const char **values, size_t count)
{
    for (size_t i = 0; i < count; ++i)
        if (!strcmp(s, values[i]))
            return (int)i;
    return -1;
}
static int ref_index(struct json_object *v, struct json_object *refs)
{
    for (size_t i = 0; i < json_object_array_length(refs); ++i)
        if (json_object_equal(v, json_object_array_get_idx(refs, i)))
            return (int)i;
    return -1;
}
static bool envelope(struct json_object *o, struct json_object *base, const char *schema,
                     const golem_digest *baseline)
{
    const char *keys[] = {"schema",          "project_id", "work_id", "created_by_assertion",
                          "baseline_digest", "body"};
    return dw_keys(o, keys, 6) && eq(o, "schema", schema) && text(o, "created_by_assertion") &&
           json_object_equal(dw_get(o, "project_id"), dw_get(base, "project_id")) &&
           json_object_equal(dw_get(o, "work_id"), dw_get(base, "work_id")) &&
           digest_is(o, "baseline_digest", baseline);
}
static bool case_exists(struct json_object *contract, struct json_object *m)
{
    struct json_object *gates = dw_get(contract, "gates");
    for (size_t i = 0; i < json_object_array_length(gates); ++i) {
        struct json_object *g = json_object_array_get_idx(gates, i);
        if (!eq(g, "id", dw_text(m, "gate_id")) ||
            !json_object_equal(dw_get(g, "version"), dw_get(m, "gate_version")))
            continue;
        struct json_object *cases = dw_get(g, "cases");
        for (size_t j = 0; j < json_object_array_length(cases); ++j)
            if (eq(json_object_array_get_idx(cases, j), "id", dw_text(m, "case_id")))
                return true;
    }
    return false;
}
golem_status gi_qa_paths_inspect(const gi_qa_paths_inputs *in, gi_qa_paths_result *out,
                                 golem_diagnostic *diagnostic)
{
    if (!in || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    gi_review_binding bound;
    golem_status st = gi_review_bind(&in->baseline, &bound, diagnostic);
    if (st != GOLEM_OK)
        return st;
    gi_qa_paths_result result = {0};
    result.requirements = bound.requirements + bound.constraints;
    struct json_object *base = NULL, *app = NULL, *obs = NULL, *map = NULL, *contract = NULL,
                       *refs = json_object_new_array(), *nodes = json_object_new_object();
    unsigned char seen[256][5] = {{0}};
    size_t covered[1280] = {0}, mapped[4096] = {0};
    if (!refs || !nodes) {
        json_object_put(refs);
        json_object_put(nodes);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
#define PARSE(bytes, obj) do {st=golem_json_parse(bytes,GI_CONTROL_MAX,&obj);if(st!=GOLEM_OK)goto done;}while(0)
#define REQUIRE(expr) do {if(!(expr)){st=GOLEM_ERR_REQUIREMENTS_UNMET;goto done;}}while(0)
    PARSE(in->baseline.baseline, base);
    PARSE(in->applicability, app);
    PARSE(in->obligations, obs);
    PARSE(in->mapping, map);
    REQUIRE(envelope(app, base, "golem.intent.qa-applicability.v1", &bound.baseline) &&
            envelope(obs, base, "golem.intent.qa-obligations.v1", &bound.baseline) &&
            envelope(map, base, "golem.intent.qa-mapping.v1", &bound.baseline));
    st = gi_domain_digest(in->applicability, &result.applicability, diagnostic);
    if (st != GOLEM_OK)
        goto done;
    st = gi_domain_digest(in->obligations, &result.obligations, diagnostic);
    if (st != GOLEM_OK)
        goto done;
    st = gi_domain_digest(in->mapping, &result.mapping, diagnostic);
    if (st != GOLEM_OK)
        goto done;
    struct json_object *bb = dw_get(base, "body");
    const char *sets[] = {"requirement_refs", "constraint_refs"};
    for (size_t s = 0; s < 2; ++s) {
        struct json_object *a = dw_get(bb, sets[s]);
        for (size_t i = 0; i < json_object_array_length(a); ++i)
            if (json_object_array_add(refs, json_object_get(json_object_array_get_idx(a, i))) !=
                0) {
                st = GOLEM_ERR_OUT_OF_MEMORY;
                goto done;
            }
    }
    struct json_object *ab = dw_get(app, "body"), *ob = dw_get(obs, "body"),
                       *mb = dw_get(map, "body");
    const char *ak[] = {"rows"}, *ok[] = {"applicability_ref", "oracle_plan_ref", "obligations"},
               *mk[] = {"obligations_ref", "execution_contract_digest", "mappings"};
    REQUIRE(dw_keys(ab, ak, 1) && dw_keys(ob, ok, 3) && dw_keys(mb, mk, 3));
    struct json_object *rows = dw_get(ab, "rows"), *obligations = dw_get(ob, "obligations"),
                       *mappings = dw_get(mb, "mappings");
    golem_digest d;
    REQUIRE(array(rows, 1280) && json_object_array_length(rows) == result.requirements * 5 &&
            array(obligations, 4096) && array(mappings, 16384));
    REQUIRE(digest_is(ob, "applicability_ref", &result.applicability) &&
            digest_is(mb, "obligations_ref", &result.obligations) &&
            dig(dw_get(ob, "oracle_plan_ref"), &d));
    ++result.unsupported_references; /* oracle-plan typed validator not implemented */
    result.rows = json_object_array_length(rows);
    result.obligations_count = json_object_array_length(obligations);
    size_t targets_total = 0;
    for (size_t i = 0; i < result.rows; ++i) {
        struct json_object *r = json_object_array_get_idx(rows, i),
                           *targets = dw_get(r, "target_refs");
        const char *rk[] = {"requirement_ref", "route",      "target_refs", "disposition",
                            "rationale",       "review_ref", "decision_ref"};
        REQUIRE(dw_keys(r, rk, 7) && text(r, "rationale") && array(targets, 64));
        int requirement = ref_index(dw_get(r, "requirement_ref"), refs),
            route = index_of(dw_text(r, "route"), routes, 5);
        REQUIRE(requirement >= 0 && route >= 0 && !seen[requirement][route]);
        seen[requirement][route] = 1;
        bool undecided = eq(r, "disposition", "UNDECIDED"),
             required = eq(r, "disposition", "REQUIRED");
        REQUIRE(undecided || required || eq(r, "disposition", "NOT_APPLICABLE"));
        if (undecided)
            ++result.undecided;
        const char *review_keys[] = {"review_ref", "decision_ref"};
        for (size_t j = 0; j < 2; ++j) {
            struct json_object *v = dw_get(r, review_keys[j]);
            if (undecided && json_object_is_type(v, json_type_null))
                continue;
            REQUIRE(dig(v, &d));
            if (json_object_object_add(nodes, json_object_get_string(v), NULL) != 0) {
                st = GOLEM_ERR_OUT_OF_MEMORY;
                goto done;
            }
            REQUIRE(json_object_object_length(nodes) <= 4096);
            ++result.unsupported_references;
        }
        REQUIRE(!required || json_object_array_length(targets) > 0);
        targets_total += json_object_array_length(targets);
        REQUIRE(targets_total <= 16384);
        for (size_t j = 0; j < json_object_array_length(targets); ++j) {
            struct json_object *v = json_object_array_get_idx(targets, j);
            REQUIRE(dig(v, &d));
            for (size_t k = 0; k < j; ++k)
                REQUIRE(!json_object_equal(v, json_object_array_get_idx(targets, k)));
            if (json_object_object_add(nodes, json_object_get_string(v), NULL) != 0) {
                st = GOLEM_ERR_OUT_OF_MEMORY;
                goto done;
            }
            REQUIRE(json_object_object_length(nodes) <= 4096);
            ++result.unsupported_references;
        }
    }
    for (size_t i = 0; i < result.obligations_count; ++i) {
        struct json_object *o = json_object_array_get_idx(obligations, i);
        const char *keys[] = {"id",         "requirement_ref", "route",
                              "target_ref", "condition",       "expected_outcome",
                              "oracle_ref", "stage",           "evidence_kind"};
        REQUIRE(dw_keys(o, keys, 9) && dw_id(dw_text(o, "id")) && text(o, "condition") &&
                text(o, "expected_outcome") && dig(dw_get(o, "oracle_ref"), &d) &&
                index_of(dw_text(o, "stage"), stages, 7) >= 0);
        bool native = eq(o, "evidence_kind", "NATIVE_QA");
        REQUIRE(native || eq(o, "evidence_kind", "SEMANTIC_REVIEW"));
        if (native)
            ++result.native_obligations;
        else
            ++result.semantic_obligations;
        if (json_object_object_add(nodes, dw_text(o, "oracle_ref"), NULL) != 0) {
            st = GOLEM_ERR_OUT_OF_MEMORY;
            goto done;
        }
        REQUIRE(json_object_object_length(nodes) <= 4096);
        ++result.unsupported_references;
        for (size_t j = 0; j < i; ++j)
            REQUIRE(!eq(json_object_array_get_idx(obligations, j), "id", dw_text(o, "id")));
        bool found = false;
        for (size_t j = 0; j < result.rows; ++j) {
            struct json_object *r = json_object_array_get_idx(rows, j);
            if (!json_object_equal(dw_get(o, "requirement_ref"), dw_get(r, "requirement_ref")) ||
                !eq(o, "route", dw_text(r, "route")))
                continue;
            REQUIRE(eq(r, "disposition", "REQUIRED") &&
                    ref_index(dw_get(o, "target_ref"), dw_get(r, "target_refs")) >= 0);
            ++covered[j];
            found = true;
            break;
        }
        REQUIRE(found);
    }
    for (size_t i = 0; i < result.rows; ++i) {
        struct json_object *r = json_object_array_get_idx(rows, i);
        if (!eq(r, "disposition", "REQUIRED"))
            continue;
        REQUIRE(covered[i] > 0);
        struct json_object *targets = dw_get(r, "target_refs");
        for (size_t j = 0; j < json_object_array_length(targets); ++j) {
            bool found = false;
            for (size_t k = 0; k < result.obligations_count; ++k) {
                struct json_object *o = json_object_array_get_idx(obligations, k);
                if (json_object_equal(dw_get(o, "requirement_ref"), dw_get(r, "requirement_ref")) &&
                    eq(o, "route", dw_text(r, "route")) &&
                    json_object_equal(dw_get(o, "target_ref"),
                                      json_object_array_get_idx(targets, j)))
                    found = true;
            }
            REQUIRE(found);
        }
    }
    /* Every explicit acceptance oracle in each exact definition remains covered. */
    for (size_t i = 0; i < in->baseline.definition_count; ++i) {
        struct json_object *definition = NULL;
        st = golem_json_parse(in->baseline.definitions[i], GI_CONTROL_MAX, &definition);
        if (st != GOLEM_OK)
            goto done;
        struct json_object *oracles = dw_get(dw_get(definition, "body"), "acceptance_oracle_refs");
        bool complete = true;
        for (size_t j = 0; j < json_object_array_length(oracles); ++j) {
            bool found = false;
            for (size_t k = 0; k < result.obligations_count; ++k) {
                struct json_object *o = json_object_array_get_idx(obligations, k);
                if (json_object_equal(dw_get(o, "requirement_ref"),
                                      json_object_array_get_idx(refs, i)) &&
                    json_object_equal(dw_get(o, "oracle_ref"),
                                      json_object_array_get_idx(oracles, j)))
                    found = true;
            }
            if (!found)
                complete = false;
        }
        json_object_put(definition);
        REQUIRE(complete);
    }
    REQUIRE(result.native_obligations > 0);
    st = golem_execution_contract_validate(in->execution_contract, &result.execution_contract,
                                           diagnostic);
    if (st != GOLEM_OK)
        goto done;
    REQUIRE(digest_is(mb, "execution_contract_digest", &result.execution_contract));
    PARSE(in->execution_contract, contract);
    for (size_t i = 0; i < json_object_array_length(mappings); ++i) {
        struct json_object *m = json_object_array_get_idx(mappings, i);
        const char *keys[] = {"obligation_id", "gate_id", "gate_version", "case_id"};
        REQUIRE(dw_keys(m, keys, 4) && dw_id(dw_text(m, "obligation_id")) &&
                dw_id(dw_text(m, "gate_id")) && dw_id(dw_text(m, "case_id")) &&
                case_exists(contract, m));
        for (size_t j = 0; j < i; ++j) {
            struct json_object *old = json_object_array_get_idx(mappings, j);
            REQUIRE(!(eq(old, "obligation_id", dw_text(m, "obligation_id")) &&
                      eq(old, "gate_id", dw_text(m, "gate_id")) &&
                      json_object_equal(dw_get(old, "gate_version"), dw_get(m, "gate_version")) &&
                      eq(old, "case_id", dw_text(m, "case_id"))));
        }
        bool found = false;
        for (size_t j = 0; j < result.obligations_count; ++j) {
            struct json_object *o = json_object_array_get_idx(obligations, j);
            if (eq(o, "id", dw_text(m, "obligation_id"))) {
                REQUIRE(eq(o, "evidence_kind", "NATIVE_QA"));
                ++mapped[j];
                found = true;
                break;
            }
        }
        REQUIRE(found);
    }
    for (size_t i = 0; i < result.obligations_count; ++i)
        REQUIRE(!eq(json_object_array_get_idx(obligations, i), "evidence_kind", "NATIVE_QA") ||
                mapped[i] > 0);
    result.structurally_complete = result.undecided == 0;
    *out = result;
    st = GOLEM_OK;
done:
    json_object_put(nodes);
    json_object_put(refs);
    json_object_put(base);
    json_object_put(app);
    json_object_put(obs);
    json_object_put(map);
    json_object_put(contract);
    return st;
#undef REQUIRE
#undef PARSE
}
