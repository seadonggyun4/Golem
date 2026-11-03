#include "internal.h"
#include "../intent/qa_result.h"
#include "../workflow/role_internal.h"
#include <string.h>
#include <stdlib.h>
static bool eq(struct json_object *o, const char *k, const char *v)
{
    return !strcmp(dw_text(o, k), v);
}
golem_status co_intent_validate(struct json_object *r)
{
    const char *read[] = {"schema_version", "operation", "selection_id"};
    const char *keys[] = {
        "schema_version",      "operation", "selection_id", "key",
        "expected_generation", "issues",    "predicate",    "intent_qa_observation"};
    if (dw_uint(r, "schema_version") != 3)
        return GOLEM_ERR_PARSE;
    if (eq(r, "operation", "resume"))
        return dw_keys(r, read, 3) && dw_id(dw_text(r, "selection_id")) ? GOLEM_OK
                                                                        : GOLEM_ERR_PARSE;
    golem_digest d;
    if (!dw_keys(r, keys, 8) || !eq(r, "operation", "finalize") ||
        !eq(r, "predicate", CO_INTENT_V1) || !dw_digest(r, "intent_qa_observation", &d))
        return GOLEM_ERR_PARSE;
    struct json_object *copy = NULL;
    if (json_object_deep_copy(r, &copy, NULL))
        return GOLEM_ERR_OUT_OF_MEMORY;
    json_object_object_del(copy, "predicate");
    json_object_object_del(copy, "intent_qa_observation");
    golem_status st =
        ex_uint(copy, "schema_version", 1) ? co_validate_v1(copy) : GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(copy);
    return st;
}
golem_status co_intent_evaluate(golem_document_store *s, struct json_object *r, bool live,
                                struct json_object **out)
{
    if (!s || !out || dw_uint(s->spec, "schema_version") != 3)
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    golem_status st = co_intent_validate(r);
    golem_digest requested;
    if (st == GOLEM_OK && (!eq(r, "operation", "finalize") || !s->intent_qa_count ||
                           !dw_digest(r, "intent_qa_observation", &requested)))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *qa = NULL, *a = NULL, *legacy = NULL, *policy = NULL;
    size_t index = s->intent_qa_count ? s->intent_qa_count - 1 : 0;
    if (st == GOLEM_OK && !dw_equal(&requested, &s->intent_qa_frames[index]))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK && live)
        st = gi_product_check(s, GI_PRODUCT_COMPLETION);
    if (st == GOLEM_OK && live)
        st = gi_qa_accepted(s, &qa);
    dw_entry *selection = dw_find(s, dw_text(r, "selection_id"), 0);
    struct json_object *plan = selection ? selection->meta : NULL;
    if (st == GOLEM_OK && !eq(dw_get(plan, "selection"), "mode", "development"))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK && s->role_count) {
        struct json_object *enrolled = rc_enrollment(s, dw_text(r, "selection_id"));
        if (!eq(dw_get(dw_get(enrolled, "request"), "contract"), "mode", "development"))
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    if (st == GOLEM_OK && json_object_deep_copy(r, &legacy, NULL))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        json_object_object_del(legacy, "predicate");
        json_object_object_del(legacy, "intent_qa_observation");
        if (!ex_uint(legacy, "schema_version", s->role_count ? 2 : 1))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        st = s->role_count ? rc_completion_base(s, legacy, live, &a)
                           : co_evaluate_v1_base(s, legacy, live, &a);
    struct json_object *observation = st == GOLEM_OK ? s->intent_qa[index] : NULL;
    struct json_object *candidate = dw_get(observation, "assessment"),
                       *body = dw_get(candidate, "body"),
                       *rows = dw_get(body, "obligation_results");
    if (st == GOLEM_OK &&
        (!eq(body, "execution_status", "PASS") ||
         !json_object_equal(dw_get(a, "qa_receipt"), dw_get(body, "execution_receipt_ref")) ||
         !json_object_is_type(rows, json_type_array) || !json_object_array_length(rows)))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(rows); ++i)
        if (!eq(json_object_array_get_idx(rows, i), "status", "PASS"))
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK) {
        policy = json_object_new_object();
        if (!ex_uint(policy, "schema_version", 1) || !ex_text(policy, "predicate", CO_INTENT_V1) ||
            !dw_add(policy, "native_policy", json_object_get(dw_get(a, "policy"))) ||
            !dw_add(policy, "intent_binding", json_object_get(dw_get(s->spec, "intent_binding"))) ||
            !ex_text(policy, "support_profile", "LOCAL_NO_MERGE"))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_digest pd;
    if (st == GOLEM_OK)
        st = ex_hash(policy, &pd);
    if (st == GOLEM_OK &&
        (!dw_add(a, "policy", json_object_get(policy)) || !dw_add_digest(a, "policy_digest", &pd) ||
         !dw_add_digest(a, "intent_qa_observation", &requested) ||
         !dw_add(a, "intent_qa_assessment",
                 json_object_get(dw_get(observation, "assessment_digest"))) ||
         !dw_add(a, "intent_qa_prepare_event",
                 json_object_get(dw_get(observation, "prepare_event"))) ||
         !dw_add(a, "intent_qa_accept_operation",
                 json_object_get(dw_get(observation, "accept_operation"))) ||
         !ex_text(a, "assurance", "LOCAL_COOPERATIVE_REVIEWED_NOT_PROVEN")))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        *out = a;
        a = NULL;
    }
    json_object_put(qa);
    json_object_put(a);
    json_object_put(legacy);
    json_object_put(policy);
    return st;
}
golem_status co_intent_markdown(struct json_object *record, golem_execution_reply *out)
{
    /* Reuse the native renderer; add the distinct predicate and historical scope. */
    struct json_object *copy = NULL;
    if (json_object_deep_copy(record, &copy, NULL))
        return GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *a = dw_get(copy, "assessment"), *p = dw_get(a, "policy"),
                       *native = dw_get(p, "native_policy");
    if (dw_uint(record, "schema_version") != 1 || dw_uint(p, "schema_version") != 1 ||
        (!eq(native, "predicate", CO_EVALUATOR_V1) && !eq(native, "predicate", RC_PREDICATE)) ||
        dw_uint(native, "schema_version") != 1) {
        json_object_put(copy);
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    }

    golem_status st =
        dw_add(a, "policy", json_object_get(native)) ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    golem_execution_reply base = {0};
    if (st == GOLEM_OK)
        st = co_markdown(copy, &base);
    if (st == GOLEM_OK) {
        const char *prefix =
            "# Intent local-no-merge completion\n\nPredicate: `golem.completion.intent.local-no-merge.v1`. Historical record; current QA acceptance must be rechecked. No merge/deploy assurance.\n\n";
        size_t n = strlen(prefix);
        uint8_t *bytes = base.size <= GOLEM_DOCUMENT_MAX_BODY - n ? malloc(n + base.size) : NULL;
        if (!bytes)
            st = GOLEM_ERR_OUT_OF_MEMORY;
        else {
            memcpy(bytes, prefix, n);
            memcpy(bytes + n, base.data, base.size);
            *out = (golem_execution_reply){bytes, n + base.size};
        }
    }
    golem_execution_reply_free(&base);
    json_object_put(copy);
    return st;
}
