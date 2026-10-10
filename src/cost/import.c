#include "internal.h"
#include "../common/json.h"
#include "../core/internal.h"
#include <string.h>

static const char *text(struct json_object *o, const char *key)
{
    struct json_object *v = NULL;
    return json_object_object_get_ex(o, key, &v) && json_object_is_type(v, json_type_string) &&
        (size_t)json_object_get_string_len(v) == strlen(json_object_get_string(v))
        ? json_object_get_string(v) : NULL;
}
static bool copy_text(struct json_object *o, const char *key, char *out, size_t capacity)
{
    const char *s = text(o, key);
    if (s == NULL || *s == '\0' || strlen(s) >= capacity) return false;
    memcpy(out, s, strlen(s) + 1); return true;
}
static bool number(struct json_object *o, const char *key, uint64_t *out)
{
    const char *s = text(o, key); uint64_t value = 0;
    if (s == NULL || *s == '\0' || (s[0] == '0' && s[1] != '\0')) return false;
    for (; *s != '\0'; ++s) {
        if (*s < '0' || *s > '9') return false;
        uint64_t digit = (uint64_t)(*s - '0');
        if (value > (UINT64_MAX - digit) / 10) return false;
        value = value * 10 + digit;
    }
    *out = value; return true;
}
static bool flag(struct json_object *o, const char *key, bool *out)
{
    struct json_object *v = NULL;
    if (!json_object_object_get_ex(o, key, &v) || !json_object_is_type(v, json_type_boolean)) return false;
    *out = json_object_get_boolean(v) != 0; return true;
}
static golem_status decode(golem_bytes bytes, const char *expected_run_id,
    uint64_t *sequence, golem_provider_usage *out, bool *partial, bool extended)
{
    if (expected_run_id == NULL || *expected_run_id == '\0' || sequence == NULL || out == NULL)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = NULL, *u = NULL;
    golem_status status = golem_json_parse(bytes, 16384, &o);
    if (status != GOLEM_OK) return status;
    const char *schema = text(o, "schema"), *run_id = text(o, "run_id");
    golem_provider_usage report = {0}; uint64_t seq = 0;
    status = GOLEM_ERR_PARSE;
    bool version2 = schema != NULL && strcmp(schema, "golem.native-cost-report.v2") == 0;
    if (schema == NULL || (strcmp(schema, "golem.native-cost-report.v1") != 0 &&
        !(extended && version2))) goto done;
    if (run_id == NULL || strcmp(run_id, expected_run_id) != 0) { status = GOLEM_ERR_IDENTITY_MISMATCH; goto done; }
    if (json_object_object_length(o) != 12 || !number(o, "sequence", &seq) || seq == 0 ||
        !copy_text(o, "request_id", report.request_id, sizeof(report.request_id)) ||
        !copy_text(o, "provider", report.provider, sizeof(report.provider)) ||
        !copy_text(o, "model", report.model, sizeof(report.model)) ||
        !copy_text(o, "price_revision", report.price_revision, sizeof(report.price_revision)) ||
        !copy_text(o, "currency", report.currency, sizeof(report.currency)) ||
        !flag(o, "usage_known", &report.actual.usage_known) ||
        !flag(o, "cost_known", &report.actual.cost_known) || !number(o, "nano_cost", &report.actual.nano_cost) ||
        !json_object_object_get_ex(o, "usage", &u) || !json_object_is_type(u, json_type_object) ||
        json_object_object_length(u) != 5 ||
        !number(u, "input_tokens", &report.actual.usage.input_tokens) ||
        !number(u, "cached_input_tokens", &report.actual.usage.cached_input_tokens) ||
        !number(u, "output_tokens", &report.actual.usage.output_tokens) ||
        !number(u, "reasoning_tokens", &report.actual.usage.reasoning_tokens) ||
        !number(u, "tool_calls", &report.actual.usage.tool_calls) ||
        !golem_cost_report_amount_valid(&report.actual, version2 && !report.actual.usage_known)) goto done;
    for (size_t i = 0; i < 3; ++i)
        if (report.currency[i] < 'A' || report.currency[i] > 'Z') goto done;
    if (report.currency[3] != '\0') goto done;
    *sequence = seq; *out = report; *partial = version2 && !report.actual.usage_known; status = GOLEM_OK;
done:
    json_object_put(o); return status;
}
golem_status golem_cost_report_decode(golem_bytes bytes, const char *run_id,
    uint64_t *sequence, golem_provider_usage *out)
{
    bool partial;
    return decode(bytes, run_id, sequence, out, &partial, false);
}
golem_status golem_cost_report_decode_extended(golem_bytes bytes, const char *run_id,
    uint64_t *sequence, golem_provider_usage *out, bool *partial)
{
    if (partial == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    return decode(bytes, run_id, sequence, out, partial, true);
}
golem_status golem_work_run_cost_report_json(golem_work_run *run, golem_bytes json)
{
    if (run == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status status = golem_core_ownership_check(run);
    if (status != GOLEM_OK) return status;
    uint64_t sequence; golem_provider_usage report; bool partial;
    status = golem_cost_report_decode_extended(json, golem_work_run_id_borrow(run), &sequence, &report, &partial);
    return status == GOLEM_OK ? (partial ? golem_cost_report_apply(run, sequence, &report, true) :
        golem_work_run_cost_report(run, sequence, &report)) : status;
}
