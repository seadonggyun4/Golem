#include "internal.h"
#include <stdio.h>
#include <string.h>

static bool id(const char *s)
{
    return ws_id(s) && strlen(s) <= 24;
}
static bool positive(struct json_object *o, const char *key)
{
    struct json_object *v = dw_get(o, key);
    return json_object_is_type(v, json_type_int) && json_object_get_int64(v) > 0 &&
           json_object_get_uint64(v) <= INT64_MAX;
}
golem_status cf_model(struct json_object *m)
{
    const char *keys[] = {"schema_version", "group_id",     "parallel_opt_in", "task_digest",
                          "base_commit",    "gates_digest", "protocol_digest", "currency",
                          "limits",         "candidates",   "cohort"};
    const char *limits[] = {"workers", "cpu", "memory", "io", "tokens", "nano_cost"};
    const char *member[] = {
        "id", "work_id", "session_id", "runtime_binding", "environment_digest", "resources"};
    const char *resources[] = {"cpu", "memory", "io", "tokens", "nano_cost"};
    if (!dw_keys(m, keys, 11) || !json_object_is_type(dw_get(m, "schema_version"), json_type_int) ||
        dw_uint(m, "schema_version") != 1 || !id(dw_text(m, "group_id")) ||
        !json_object_is_type(dw_get(m, "parallel_opt_in"), json_type_boolean) ||
        !ws_oid(dw_text(m, "base_commit")) ||
        !ds_array(dw_get(m, "candidates"), 1, GOLEM_CANDIDATE_MAX))
        return GOLEM_ERR_PARSE;
    golem_digest d;
    for (size_t i = 3; i <= 6; ++i)
        if (i != 4 && !dw_digest(m, keys[i], &d))
            return GOLEM_ERR_PARSE;
    const char *currency = dw_text(m, "currency");
    if (strlen(currency) != 3)
        return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < 3; ++i)
        if (currency[i] < 'A' || currency[i] > 'Z')
            return GOLEM_ERR_PARSE;
    struct json_object *cap = dw_get(m, "limits"), *members = dw_get(m, "candidates");
    if (!dw_keys(cap, limits, 6) || dw_uint(cap, "workers") > GOLEM_CANDIDATE_MAX)
        return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < 6; ++i)
        if (!positive(cap, limits[i]))
            return GOLEM_ERR_PARSE;
    if (!json_object_get_boolean(dw_get(m, "parallel_opt_in")) &&
        (json_object_array_length(members) != 1 || dw_uint(cap, "workers") != 1))
        return GOLEM_ERR_APPROVAL_REQUIRED;
    for (size_t i = 0; i < json_object_array_length(members); ++i) {
        struct json_object *v = json_object_array_get_idx(members, i), *r = dw_get(v, "resources");
        if (!dw_keys(v, member, 6) || !id(dw_text(v, "id")) || !dw_id(dw_text(v, "work_id")) ||
            strlen(dw_text(v, "work_id")) >= 96 || !dw_id(dw_text(v, "session_id")) ||
            strlen(dw_text(v, "session_id")) >= 96 || !dw_digest(v, "runtime_binding", &d) ||
            !dw_digest(v, "environment_digest", &d) || !dw_keys(r, resources, 5))
            return GOLEM_ERR_PARSE;
        for (size_t k = 0; k < 5; ++k)
            if (!positive(r, resources[k]) || dw_uint(r, resources[k]) > dw_uint(cap, resources[k]))
                return GOLEM_ERR_BUDGET_EXHAUSTED;
        for (size_t j = 0; j < i; ++j) {
            struct json_object *old = json_object_array_get_idx(members, j);
            for (size_t k = 0; k < 3; ++k)
                if (!strcmp(dw_text(old, member[k]), dw_text(v, member[k])))
                    return GOLEM_ERR_IDENTITY_MISMATCH;
        }
    }
    struct json_object *cohort = dw_get(m, "cohort");
    const char *ck[] = {"cohort_id", "cohort_digest", "case_id"};
    if (cohort && (!dw_keys(cohort, ck, 3) || !dw_id(dw_text(cohort, "cohort_id")) ||
                   !dw_id(dw_text(cohort, "case_id")) || !dw_digest(cohort, "cohort_digest", &d)))
        return GOLEM_ERR_PARSE;
    return GOLEM_OK;
}
golem_status golem_candidate_validate(golem_bytes bytes, golem_digest *out, golem_diagnostic *d)
{
    if (!out)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *m = NULL;
    golem_digest digest;
    golem_status st = golem_json_parse(bytes, GOLEM_DOCUMENT_MAX_JSON, &m);
    if (st == GOLEM_OK)
        st = cf_model(m);
    if (st == GOLEM_OK)
        st = ex_hash(m, &digest);
    json_object_put(m);
    if (st == GOLEM_OK)
        *out = digest;
    return dw_report(d, st, NULL);
}
struct json_object *cf_spec(cf_context *ctx, size_t i)
{
    return json_object_array_get_idx(dw_get(ctx->manifest, "candidates"), i);
}
const char *cf_state(cf_context *ctx, size_t i)
{
    return ctx->members[i] ? dw_text(ctx->members[i], "state") : "PLANNED";
}
bool cf_held(const char *s)
{
    return !strcmp(s, "RESERVED") || !strcmp(s, "START_INTENT") || !strcmp(s, "RUNNING") ||
           !strcmp(s, "CANCEL_REQUESTED") || !strcmp(s, "SETTLING");
}
void cf_operation(cf_context *ctx, size_t i, char out[64])
{
    (void)snprintf(out, 64, "cf-%s-%s", dw_text(ctx->manifest, "group_id"),
                   dw_text(cf_spec(ctx, i), "id"));
}
struct json_object *cf_token(const golem_admission_token *t)
{
    struct json_object *o = json_object_new_object();
    char instance[33];
    for (size_t i = 0; i < 16; ++i)
        (void)snprintf(instance + i * 2, 3, "%02x", t->instance[i]);
    if (!ex_uint(o, "ticket", t->ticket) || !ex_uint(o, "epoch", t->epoch) ||
        !ex_text(o, "instance", instance) || !dw_add_digest(o, "boot", &t->boot)) {
        json_object_put(o);
        return NULL;
    }
    return o;
}
bool cf_token_equal(struct json_object *o, const golem_admission_token *t)
{
    struct json_object *expected = cf_token(t);
    bool same = expected && json_object_equal(o, expected);
    json_object_put(expected);
    return same;
}
golem_status cf_ticket(cf_context *ctx, size_t i, golem_admission_ticket *out)
{
    char operation[64];
    cf_operation(ctx, i, operation);
    golem_status st = golem_admission_lookup(ctx->admission, operation, out);
    golem_digest namespace_id, expected;
    golem_admission_checkpoint checkpoint;
    if (st == GOLEM_OK)
        st = golem_admission_identity(ctx->admission, &namespace_id, &checkpoint);
    if (st == GOLEM_OK &&
        (!dw_digest(dw_get(ctx->members[i], "reservation"), "namespace", &expected) ||
         !dw_equal(&namespace_id, &expected)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *spec = cf_spec(ctx, i), *r = dw_get(spec, "resources");
    golem_digest binding;
    if (st == GOLEM_OK && (!dw_digest(spec, "runtime_binding", &binding) ||
                           strcmp(out->request.work, dw_text(spec, "work_id")) ||
                           strcmp(out->request.session, dw_text(spec, "session_id")) ||
                           out->request.parent || out->request.cpu_millis != dw_uint(r, "cpu") ||
                           out->request.memory_bytes != dw_uint(r, "memory") ||
                           !dw_equal(&binding, &out->request.runtime_binding)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    return st;
}
