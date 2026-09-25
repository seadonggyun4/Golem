#include "internal.h"
#include "../workflow/role_internal.h"
#include "../workflow/template_internal.h"
#include <string.h>

golem_status co_markdown(struct json_object *record, golem_execution_reply *out)
{
    struct json_object *policy = dw_get(dw_get(record, "assessment"), "policy");
    if (dw_uint(record, "schema_version") == 1 && dw_uint(policy, "schema_version") == 1 &&
        !strcmp(dw_text(policy, "predicate"), RC_PREDICATE))
        return rc_markdown(record, out);
    if (dw_uint(record, "schema_version") != 1 || dw_uint(policy, "schema_version") != 1 ||
        strcmp(dw_text(policy, "predicate"), CO_EVALUATOR_V1) != 0)
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    return co_markdown_v1(record, out);
}

golem_status co_validate(struct json_object *request)
{
    if (dw_uint(request, "schema_version") == 2) {
        if (strcmp(dw_text(request, "operation"), "finalize"))
            return GOLEM_ERR_PARSE;
        struct json_object *copy = NULL;
        if (json_object_deep_copy(request, &copy, NULL))
            return GOLEM_ERR_OUT_OF_MEMORY;
        golem_status st =
            ex_uint(copy, "schema_version", 1) ? co_validate_v1(copy) : GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(copy);
        return st;
    }
    return co_validate_v1(request);
}

golem_status co_evaluate(golem_document_store *store, struct json_object *request, bool live,
                         struct json_object **out)
{
    golem_status guard = wt_guard(store, dw_text(request, "selection_id"));
    if (guard != GOLEM_OK)
        return guard;
    if (store->role_count)
        return rc_completion(store, request, live, out);
    if (dw_uint(request, "schema_version") != 1)
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    return co_evaluate_v1(store, request, live, out);
}

golem_status co_evaluate_record(golem_document_store *store, struct json_object *request,
                                struct json_object *record, struct json_object **out)
{
    /* The predicate was already bound into the assessment/policy digest in
     * schema 1. Dispatch from that historical identifier, not today's policy. */
    struct json_object *policy = dw_get(dw_get(record, "assessment"), "policy");
    const char *predicate = dw_text(policy, "predicate");
    if (!strcmp(predicate, RC_PREDICATE) && dw_uint(policy, "schema_version") == 1)
        return rc_completion(store, request, false, out);
    if (store && store->role_count)
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    if (!json_object_is_type(dw_get(policy, "predicate"), json_type_string) || predicate[0] == '\0')
        return GOLEM_ERR_CORRUPT_JOURNAL;
    if (strcmp(predicate, CO_EVALUATOR_V1) != 0 || dw_uint(policy, "schema_version") != 1)
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    return co_evaluate_v1(store, request, false, out);
}
