#include "template_internal.h"
#include "role_internal.h"
#include <string.h>

/* Enrollment is a Work obligation, not a caller-selected shortcut. Keep the
 * same selection identity once any template revision has been registered. */
golem_status wt_guard(golem_document_store *s, const char *id)
{
    for (size_t i = 0; i < s->count; ++i) {
        struct json_object *meta = s->entries[i].meta;
        if (!wt_definition(dw_get(meta, "selection")))
            continue;
        if (strcmp(dw_text(meta, "document_id"), id))
            return GOLEM_ERR_POLICY_DENIED;
        dw_entry *plan = dw_find(s, id, 0);
        struct json_object *definition = wt_definition(dw_get(plan->meta, "selection"));
        struct json_object *enrolled = rc_enrollment(s, id);
        if (!definition || !enrolled ||
            !json_object_equal(dw_get(definition, "role_contract"),
                               dw_get(dw_get(enrolled, "request"), "contract")))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        break;
    }
    return GOLEM_OK;
}

golem_status wt_revision(golem_document_store *s, struct json_object *meta)
{
    struct json_object *definition = wt_definition(dw_get(meta, "selection"));
    for (size_t i = 0; i < s->count; ++i) {
        struct json_object *old_meta = s->entries[i].meta,
                           *old = wt_definition(dw_get(old_meta, "selection"));
        if (!old)
            continue;
        if (strcmp(dw_text(old_meta, "document_id"), dw_text(meta, "document_id")) || !definition ||
            strcmp(dw_text(old, "kind"), dw_text(definition, "kind")) ||
            !json_object_equal(dw_get(old, "role_contract"), dw_get(definition, "role_contract")) ||
            dw_uint(dw_get(definition, "budget"), "context_bytes") >
                dw_uint(dw_get(old, "budget"), "context_bytes") ||
            dw_uint(dw_get(definition, "budget"), "max_reentries") >
                dw_uint(dw_get(old, "budget"), "max_reentries"))
            return GOLEM_ERR_POLICY_DENIED;
        for (size_t stage = 0; stage < 6; ++stage)
            if (!strcmp(dw_text(json_object_array_get_idx(dw_get(old, "stages"), stage), "when"),
                        "ALWAYS") &&
                strcmp(
                    dw_text(json_object_array_get_idx(dw_get(definition, "stages"), stage), "when"),
                    "ALWAYS"))
                return GOLEM_ERR_POLICY_DENIED;
    }
    if (definition && s->role_count) {
        struct json_object *enrolled = rc_enrollment(s, dw_text(meta, "document_id"));
        if (!enrolled || !json_object_equal(dw_get(definition, "role_contract"),
                                            dw_get(dw_get(enrolled, "request"), "contract")))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    return GOLEM_OK;
}

golem_status wt_execution(golem_document_store *s, struct json_object *contract)
{
    const char *id = dw_text(contract, "selection_id");
    golem_status st = wt_guard(s, id);
    if (st != GOLEM_OK)
        return st;
    dw_entry *plan = dw_find(s, id, 0);
    struct json_object *definition = plan ? wt_definition(dw_get(plan->meta, "selection")) : NULL;
    if (!definition)
        return GOLEM_OK;
    if (strcmp(dw_text(definition, "mode"), "development"))
        return GOLEM_ERR_POLICY_DENIED;
    if (strcmp(dw_text(definition, "kind"), "bugfix"))
        return GOLEM_OK;
    bool reproduction = false, regression = false;
    struct json_object *gates = dw_get(contract, "gates");
    for (size_t i = 0; i < json_object_array_length(gates); ++i) {
        struct json_object *cases = dw_get(json_object_array_get_idx(gates, i), "cases");
        for (size_t j = 0; j < json_object_array_length(cases); ++j) {
            const char *case_id = dw_text(json_object_array_get_idx(cases, j), "id");
            reproduction |= !strcmp(case_id, "reproduction");
            regression |= !strcmp(case_id, "regression");
        }
    }
    return reproduction && regression ? GOLEM_OK : GOLEM_ERR_REQUIREMENTS_UNMET;
}
