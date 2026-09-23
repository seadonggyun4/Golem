#include "internal.h"
#include "../reentry/internal.h"
#include "../research/internal.h"
#include <string.h>

golem_status co_validate_v1(struct json_object *r)
{
    const char *base[] = {"schema_version", "operation", "selection_id"};
    const char *keys[] = {"schema_version",      "operation", "selection_id", "key",
                          "expected_generation", "issues"};
    if (dw_uint(r, "schema_version") != 1 || !dw_id(dw_text(r, "selection_id")))
        return GOLEM_ERR_PARSE;
    if (!strcmp(dw_text(r, "operation"), "resume"))
        return dw_keys(r, base, 3) ? GOLEM_OK : GOLEM_ERR_PARSE;
    if (strcmp(dw_text(r, "operation"), "finalize") || !dw_keys(r, keys, 6) ||
        !dw_id(dw_text(r, "key")) || !dw_uint(r, "expected_generation") ||
        dw_uint(r, "expected_generation") > GOLEM_DOCUMENT_MAX_REVISIONS + 1 ||
        !ds_array(dw_get(r, "issues"), 0, 32))
        return GOLEM_ERR_PARSE;
    struct json_object *a = dw_get(r, "issues");
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *v = json_object_array_get_idx(a, i);
        golem_digest d;
        const char *ik[] = {"id", "blocking", "description", "evidence_digest"};
        if (!dw_keys(v, ik, 4) || !dw_id(dw_text(v, "id")) ||
            !json_object_is_type(dw_get(v, "blocking"), json_type_boolean) ||
            !ds_prose(v, "description") || strlen(dw_text(v, "description")) > 4096 ||
            !dw_digest(v, "evidence_digest", &d))
            return GOLEM_ERR_PARSE;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(dw_text(v, "id"), dw_text(json_object_array_get_idx(a, j), "id")))
                return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}
golem_status golem_completion_validate(golem_bytes b, golem_diagnostic *d)
{
    struct json_object *r = NULL;
    golem_status st = golem_json_parse(b, GOLEM_DOCUMENT_MAX_JSON, &r);
    if (st == GOLEM_OK)
        st = co_validate(r);
    json_object_put(r);
    return dw_report(d, st, NULL);
}
