#include "role_internal.h"
#include <string.h>

static bool integer(struct json_object *o, const char *key, uint64_t lo, uint64_t hi)
{
    return json_object_is_type(dw_get(o, key), json_type_int) &&
           json_object_get_int64(dw_get(o, key)) >= 0 && dw_uint(o, key) >= lo &&
           dw_uint(o, key) <= hi;
}

golem_status rc_contract(struct json_object *c)
{
    const char *keys[] = {"schema_version",  "id",   "mode", "allowed_effects",
                          "max_assessments", "rules"};
    if (!dw_keys(c, keys, 6) || !integer(c, "schema_version", 1, 1) || !dw_id(dw_text(c, "id")) ||
        (strcmp(dw_text(c, "mode"), "development") && strcmp(dw_text(c, "mode"), "documents")) ||
        strcmp(dw_text(c, "allowed_effects"), "NONE") || !integer(c, "max_assessments", 1, 32) ||
        !ds_array(dw_get(c, "rules"), 1, GOLEM_ROLE_MAX_RULES))
        return GOLEM_ERR_PARSE;
    struct json_object *rules = dw_get(c, "rules");
    for (size_t i = 0; i < json_object_array_length(rules); ++i) {
        struct json_object *r = json_object_array_get_idx(rules, i);
        const char *rk[] = {"role", "stage", "kind", "predicate", "independent_review"};
        int k = wf_kind(dw_text(r, "kind"));
        if (!dw_keys(r, rk, 5) || k < 0 || strcmp(dw_text(r, "stage"), wf_stages[wf_stage(k)]) ||
            !json_object_is_type(dw_get(r, "independent_review"), json_type_boolean))
            return GOLEM_ERR_PARSE;
        const char *role = dw_text(r, "role"), *p = dw_text(r, "predicate");
        bool valid = (!strcmp(role, "researcher") && k == 0 && !strcmp(p, "MARKDOWN")) ||
                     (!strcmp(role, "implementer") && k == 4 && !strcmp(p, "DEVELOPMENT")) ||
                     (!strcmp(role, "no-change") && k == 4 && !strcmp(p, "NO_CHANGE")) ||
                     (!strcmp(role, "qa") && k == 6 && !strcmp(p, "QA_PASS")) ||
                     (!strcmp(role, "reviewer") && k == 7 && !strcmp(p, "REVIEW")) ||
                     (!strcmp(role, "doc-only") && k != 4 && !strcmp(p, "MARKDOWN"));
        if (!valid ||
            (strcmp(role, "reviewer") &&
             json_object_get_boolean(dw_get(r, "independent_review"))) ||
            (!strcmp(dw_text(c, "mode"), "documents") &&
             (!strcmp(p, "DEVELOPMENT") || !strcmp(p, "NO_CHANGE") || !strcmp(p, "QA_PASS"))))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(dw_text(json_object_array_get_idx(rules, j), "kind"), dw_text(r, "kind")))
                return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}

golem_status rc_request(struct json_object *r)
{
    const char *read[] = {"schema_version", "operation", "selection_id"};
    const char *write[] = {"schema_version",      "operation", "selection_id", "key",
                           "expected_generation", "contract"};
    const char *assess[] = {"schema_version",      "operation", "selection_id", "key",
                            "expected_generation", "review"};
    if (!integer(r, "schema_version", 1, 1) || !dw_id(dw_text(r, "selection_id")))
        return GOLEM_ERR_PARSE;
    const char *op = dw_text(r, "operation");
    if (!strcmp(op, "status"))
        return dw_keys(r, read, 3) ? GOLEM_OK : GOLEM_ERR_PARSE;
    bool enroll = !strcmp(op, "enroll");
    if ((!enroll && strcmp(op, "assess") && strcmp(op, "evaluate")) ||
        !dw_keys(r, enroll ? write : assess, 6) || !dw_id(dw_text(r, "key")) ||
        !integer(r, "expected_generation", 1, GOLEM_DOCUMENT_MAX_REVISIONS + 1))
        return GOLEM_ERR_PARSE;
    if (enroll)
        return rc_contract(dw_get(r, "contract"));
    struct json_object *v = dw_get(r, "review");
    if (!v)
        return GOLEM_OK;
    const char *vk[] = {"document", "targets", "decision", "findings", "qa_receipt"};
    golem_digest digest;
    if (!dw_keys(v, vk, 5) || !wf_reference(dw_get(v, "document")) ||
        !json_object_is_type(dw_get(v, "qa_receipt"), json_type_string) ||
        !ds_array(dw_get(v, "targets"), 1, 64) || !ds_array(dw_get(v, "findings"), 0, 32) ||
        (strcmp(dw_text(v, "decision"), "ACCEPT") && strcmp(dw_text(v, "decision"), "REVISE")) ||
        (strcmp(dw_text(v, "qa_receipt"), "") && !dw_digest(v, "qa_receipt", &digest)))
        return GOLEM_ERR_PARSE;
    struct json_object *a = dw_get(v, "targets");
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *t = json_object_array_get_idx(a, i);
        if (!wf_reference(t))
            return GOLEM_ERR_PARSE;
        for (size_t j = 0; j < i; ++j)
            if (json_object_equal(t, json_object_array_get_idx(a, j)))
                return GOLEM_ERR_PARSE;
    }
    a = dw_get(v, "findings");
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *f = json_object_array_get_idx(a, i);
        const char *fk[] = {"id", "blocking", "description"};
        if (!dw_keys(f, fk, 3) || !dw_id(dw_text(f, "id")) || !ds_prose(f, "description") ||
            strlen(dw_text(f, "description")) > 4096 ||
            !json_object_is_type(dw_get(f, "blocking"), json_type_boolean))
            return GOLEM_ERR_PARSE;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(dw_text(f, "id"), dw_text(json_object_array_get_idx(a, j), "id")))
                return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}

golem_status golem_role_validate(golem_bytes bytes, golem_digest *digest, golem_diagnostic *d)
{
    if (!digest)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *o = NULL;
    golem_digest found;
    golem_status st = golem_json_parse(bytes, GOLEM_ROLE_MAX_JSON, &o);
    if (st == GOLEM_OK)
        st = rc_contract(o);
    if (st == GOLEM_OK)
        st = ex_hash(o, &found);
    if (st == GOLEM_OK)
        *digest = found;
    json_object_put(o);
    return dw_report(d, st, NULL);
}

golem_status golem_role_request_validate(golem_bytes bytes, golem_diagnostic *d)
{
    struct json_object *o = NULL;
    golem_status st = golem_json_parse(bytes, GOLEM_ROLE_MAX_JSON, &o);
    if (st == GOLEM_OK)
        st = rc_request(o);
    json_object_put(o);
    return dw_report(d, st, NULL);
}

golem_status golem_role_template(const char *name, golem_execution_reply *out)
{
    if (!name || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    bool docs = !strcmp(name, "doc-only") || !strcmp(name, "researcher");
    const char *role = !strcmp(name, "development") ? "implementer" : name;
    const char *kind = !strcmp(role, "qa")         ? "qa-result"
                       : !strcmp(role, "reviewer") ? "completion"
                       : docs                      ? "planning"
                                                   : "development-result";
    const char *predicate = docs                         ? "MARKDOWN"
                            : !strcmp(role, "qa")        ? "QA_PASS"
                            : !strcmp(role, "reviewer")  ? "REVIEW"
                            : !strcmp(role, "no-change") ? "NO_CHANGE"
                                                         : "DEVELOPMENT";
    struct json_object *c = json_object_new_object(), *rules = json_object_new_array(),
                       *r = json_object_new_object();
    golem_status st = GOLEM_OK;
    if (!ex_uint(c, "schema_version", 1) || !ex_text(c, "id", name) ||
        !ex_text(c, "mode", docs ? "documents" : "development") ||
        !ex_text(c, "allowed_effects", "NONE") || !ex_uint(c, "max_assessments", 16) ||
        !ex_text(r, "role", role) || !ex_text(r, "kind", kind) ||
        !ex_text(r, "stage", wf_stages[wf_stage(wf_kind(kind))]) ||
        !ex_text(r, "predicate", predicate) ||
        !dw_add(r, "independent_review", json_object_new_boolean(false)) ||
        !wf_append(rules, json_object_get(r)) || !dw_add(c, "rules", json_object_get(rules)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = rc_contract(c);
    if (st == GOLEM_OK)
        st = ex_emit(c, out);
    json_object_put(c);
    json_object_put(rules);
    json_object_put(r);
    return st;
}
