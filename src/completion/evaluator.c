#include "internal.h"
#include <string.h>

golem_status co_validate(struct json_object *request)
{
    return co_validate_v1(request);
}

golem_status co_evaluate(golem_document_store *store, struct json_object *request, bool live,
                         struct json_object **out)
{
    return co_evaluate_v1(store, request, live, out);
}

golem_status co_evaluate_record(golem_document_store *store, struct json_object *request,
                                struct json_object *record, struct json_object **out)
{
    /* The predicate was already bound into the assessment/policy digest in
     * schema 1. Dispatch from that historical identifier, not today's policy. */
    struct json_object *policy = dw_get(dw_get(record, "assessment"), "policy");
    const char *predicate = dw_text(policy, "predicate");
    if (!json_object_is_type(dw_get(policy, "predicate"), json_type_string) || predicate[0] == '\0')
        return GOLEM_ERR_CORRUPT_JOURNAL;
    if (strcmp(predicate, CO_EVALUATOR_V1) != 0 || dw_uint(policy, "schema_version") != 1)
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    return co_evaluate_v1(store, request, false, out);
}
