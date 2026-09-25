#include "template_internal.h"
#include "role_internal.h"
#include <string.h>

static bool integer(struct json_object *o, const char *key, uint64_t min, uint64_t max)
{
    return json_object_is_type(dw_get(o, key), json_type_int) &&
           json_object_get_int64(dw_get(o, key)) >= 0 && dw_uint(o, key) >= min &&
           dw_uint(o, key) <= max;
}

static bool development(const char *kind)
{
    return !strcmp(kind, "feature") || !strcmp(kind, "bugfix");
}

golem_status wt_model(struct json_object *o)
{
    const char *keys[] = {"schema_version", "id",     "version",       "kind",
                          "mode",           "stages", "role_contract", "budget"};
    const char *kind = dw_text(o, "kind");
    bool dev = development(kind);
    struct json_object *stages = dw_get(o, "stages"), *budget = dw_get(o, "budget"),
                       *contract = dw_get(o, "role_contract");
    const char *bk[] = {"context_bytes", "max_reentries"};
    if (!dw_keys(o, keys, 8) || !integer(o, "schema_version", 1, 1) ||
        !integer(o, "version", 1, 65535) || !dw_id(dw_text(o, "id")) ||
        (!dev && strcmp(kind, "review") && strcmp(kind, "research")) ||
        strcmp(dw_text(o, "mode"), dev ? "development" : "documents") || !ds_array(stages, 6, 6) ||
        !dw_keys(budget, bk, 2) ||
        !integer(budget, "context_bytes", 1, GOLEM_WORKFLOW_CONTEXT_MAX) ||
        !integer(budget, "max_reentries", 1, 32))
        return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < 6; ++i) {
        struct json_object *stage = json_object_array_get_idx(stages, i);
        const char *sk[] = {"stage", "when", "reason", "after"};
        const char *when = dw_text(stage, "when");
        if (!dw_keys(stage, sk, 4) || strcmp(dw_text(stage, "stage"), wf_stages[i]) ||
            !ds_prose(stage, "reason") || strlen(dw_text(stage, "reason")) > 1024 ||
            strcmp(dw_text(stage, "after"), i ? wf_stages[i - 1] : "") ||
            (strcmp(when, "ALWAYS") && !(i == 1 && !strcmp(when, "SCOPE_UX")) &&
             !(i == 2 && !strcmp(when, "SCOPE_PUBLISHING"))))
            return GOLEM_ERR_INVALID_GRAPH;
    }
    golem_status st = rc_contract(contract);
    if (st != GOLEM_OK)
        return st;
    if (strcmp(dw_text(contract, "mode"), dw_text(o, "mode")))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    bool plan = false, implementation = false, qa = false, reviewer = false;
    struct json_object *rules = dw_get(contract, "rules");
    for (size_t i = 0; i < json_object_array_length(rules); ++i) {
        struct json_object *r = json_object_array_get_idx(rules, i);
        plan |=
            !strcmp(dw_text(r, "kind"), "planning") && !strcmp(dw_text(r, "predicate"), "MARKDOWN");
        implementation |= !strcmp(dw_text(r, "predicate"), "DEVELOPMENT");
        qa |= !strcmp(dw_text(r, "kind"), "qa-result") &&
              !strcmp(dw_text(r, "predicate"), dev ? "QA_PASS" : "MARKDOWN");
        reviewer |= !strcmp(dw_text(r, "predicate"), "REVIEW");
    }
    return plan && qa && reviewer && (!dev || implementation) ? GOLEM_OK
                                                              : GOLEM_ERR_REQUIREMENTS_UNMET;
}

golem_status golem_workflow_template_validate(golem_bytes input, golem_digest *digest)
{
    if (!digest)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = NULL;
    golem_status st = golem_json_parse(input, GOLEM_ROLE_MAX_JSON, &o);
    if (st == GOLEM_OK)
        st = wt_model(o);
    if (st == GOLEM_OK)
        st = ex_hash(o, digest);
    json_object_put(o);
    return st;
}

static golem_status expand(struct json_object *o, struct json_object *p, struct json_object **out)
{
    const char *keys[] = {"schema_version", "mode", "scope", "decisions"};
    if (!dw_keys(p, keys, 4) || !integer(p, "schema_version", 1, 1) ||
        strcmp(dw_text(p, "mode"), dw_text(o, "mode")) || !wf_reference(dw_get(p, "scope")) ||
        !ds_array(dw_get(p, "decisions"), 6, 6))
        return GOLEM_ERR_PARSE;
    struct json_object *copy = NULL;
    if (json_object_deep_copy(p, &copy, NULL))
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = GOLEM_OK;
    for (size_t i = 0; st == GOLEM_OK && i < 6; ++i) {
        struct json_object *d = json_object_array_get_idx(dw_get(copy, "decisions"), i),
                           *rule = json_object_array_get_idx(dw_get(o, "stages"), i);
        const char *dk[] = {"stage", "status", "reason", "evidence", "reuse"};
        const char *status = dw_text(d, "status");
        if (!dw_keys(d, dk, 5) || strcmp(dw_text(d, "stage"), wf_stages[i]) ||
            !ds_prose(d, "reason") ||
            !json_object_equal(dw_get(d, "evidence"), dw_get(p, "scope")) || dw_get(d, "reuse") ||
            (strcmp(status, "REQUIRED") && strcmp(status, "NOT_APPLICABLE")) ||
            (i != 1 && i != 2 && strcmp(status, "REQUIRED"))) {
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
            break;
        }
        if (!strcmp(dw_text(rule, "when"), "ALWAYS") && !ex_text(d, "status", "REQUIRED"))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && !strcmp(dw_text(d, "status"), "REQUIRED") &&
            !ex_text(d, "reason", dw_text(rule, "reason")))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    struct json_object *instance = json_object_new_object();
    golem_digest digest;
    if (st == GOLEM_OK)
        st = ex_hash(o, &digest);
    if (st == GOLEM_OK &&
        (!dw_add(instance, "definition", json_object_get(o)) ||
         !dw_add_digest(instance, "digest", &digest) || !ex_uint(copy, "schema_version", 2) ||
         !dw_add(copy, "template_instance", json_object_get(instance))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        *out = copy;
    else
        json_object_put(copy);
    json_object_put(instance);
    return st;
}

struct json_object *wt_definition(struct json_object *p)
{
    return dw_get(dw_get(p, "template_instance"), "definition");
}

golem_status wt_selection(struct json_object *p)
{
    struct json_object *instance = dw_get(p, "template_instance"), *o = wt_definition(p);
    const char *keys[] = {"definition", "digest"};
    golem_digest expected, actual;
    if (!dw_keys(instance, keys, 2) || !dw_digest(instance, "digest", &expected))
        return GOLEM_ERR_PARSE;
    golem_status st = wt_model(o);
    if (st == GOLEM_OK)
        st = ex_hash(o, &actual);
    if (st == GOLEM_OK &&
        (!dw_equal(&expected, &actual) || strcmp(dw_text(p, "mode"), dw_text(o, "mode"))))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    for (size_t i = 0; st == GOLEM_OK && i < 6; ++i) {
        struct json_object *rule = json_object_array_get_idx(dw_get(o, "stages"), i),
                           *d = json_object_array_get_idx(dw_get(p, "decisions"), i);
        if ((!strcmp(dw_text(rule, "when"), "ALWAYS") &&
             strcmp(dw_text(d, "status"), "REQUIRED")) ||
            !strcmp(dw_text(d, "status"), "REUSED"))
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    return st;
}

golem_status golem_workflow_template_expand(golem_bytes input, golem_bytes selection,
                                            golem_execution_reply *out)
{
    if (!out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = NULL, *p = NULL, *result = NULL;
    golem_status st = golem_json_parse(input, GOLEM_ROLE_MAX_JSON, &o);
    if (st == GOLEM_OK)
        st = wt_model(o);
    if (st == GOLEM_OK)
        st = golem_json_parse(selection, GOLEM_DOCUMENT_MAX_JSON, &p);
    if (st == GOLEM_OK)
        st = expand(o, p, &result);
    if (st == GOLEM_OK)
        st = ex_emit(result, out);
    json_object_put(o);
    json_object_put(p);
    json_object_put(result);
    return st;
}

golem_status golem_workflow_template_instantiate(golem_document_store *s, const char *id,
                                                 uint32_t revision, golem_bytes input,
                                                 golem_execution_reply *out)
{
    if (!s || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = NULL;
    uint8_t *bytes = NULL;
    size_t size = 0;
    golem_status st = golem_json_parse(input, GOLEM_ROLE_MAX_JSON, &o);
    if (st == GOLEM_OK)
        st = wt_model(o);
    if (st == GOLEM_OK)
        st = golem_workflow_select(s, id, revision, dw_text(o, "mode"), NULL, 0, &size, NULL);
    if (st == GOLEM_ERR_BUFFER_TOO_SMALL)
        st = dw_scratch(s, size, &bytes);
    if (st == GOLEM_OK)
        st = golem_workflow_select(s, id, revision, dw_text(o, "mode"), bytes, size, &size, NULL);
    if (st == GOLEM_OK)
        st = golem_workflow_template_expand(input, (golem_bytes){bytes, size}, out);
    dw_scratch_free(s, bytes);
    json_object_put(o);
    return st;
}
