#include "golem/workpack.h"
#include "golem/version.h"
#include "binding_internal.h"
#include "../common/record_internal.h"
#include "../workflow/role_internal.h"
#include "../agent_session/internal.h"
#include "../reentry/internal.h"
#include <stdlib.h>
#include <string.h>
#define WP_REQUEST_MAX 131072u
static golem_bytes bytes(const char *s) { return (golem_bytes){(const uint8_t *)s, strlen(s)}; }
static bool one(struct json_object *p, const char *key, const char *value)
{
    struct json_object *a = dw_get(p, key);
    return json_object_array_length(a) == 1 && !strcmp(json_object_get_string(json_object_array_get_idx(a, 0)), value);
}
static bool contains(struct json_object *a, const char *value)
{
    for (size_t i = 0; i < json_object_array_length(a); ++i)
        if (!strcmp(json_object_get_string(json_object_array_get_idx(a, i)), value)) return true;
    return false;
}
static golem_status parse(golem_bytes input, struct json_object **out, struct json_object **pack,
                          golem_digest *manifest)
{
    struct json_object *r = NULL, *p = NULL;
    golem_status st = golem_json_parse(input, WP_REQUEST_MAX, &r);
    const char *keys[] = {"schema_version", "key", "selection_id", "expected_generation", "mapping", "role_contract_digest", "pack_json"};
    golem_digest role;
    if (st == GOLEM_OK && (!dw_keys(r, keys, 7) || dw_uint(r, "schema_version") != 1 ||
        !dw_id(dw_text(r, "key")) || !dw_id(dw_text(r, "selection_id")) ||
        !json_object_is_type(dw_get(r, "expected_generation"), json_type_int) ||
        json_object_get_int64(dw_get(r, "expected_generation")) < 1 ||
        !json_object_is_type(dw_get(r, "pack_json"), json_type_string) ||
        strcmp(dw_text(r, "mapping"), "native-documents-v1") || !dw_digest(r, "role_contract_digest", &role))) st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK) st = golem_workpack_validate(bytes(dw_text(r, "pack_json")), manifest, NULL);
    if (st == GOLEM_OK) st = golem_json_parse(bytes(dw_text(r, "pack_json")), GOLEM_WORKPACK_MAX_JSON, &p);
    if (st == GOLEM_OK) { *out = r; *pack = p; }
    else { json_object_put(r); json_object_put(p); }
    return st;
}
static golem_status mapping(golem_document_store *s, struct json_object *r, struct json_object *p,
                            bool initial, const char *core_version)
{
    if (initial && dw_uint(r, "expected_generation") != s->count + 1) return GOLEM_ERR_STALE_RESULT;
    if (s->completion_count && initial) return GOLEM_ERR_REQUIREMENTS_UNMET;
    if (!strcmp(dw_text(s->spec, "permission"), "DENY")) return GOLEM_ERR_POLICY_DENIED;
    if (!strcmp(dw_text(s->spec, "permission"), "ASK_ALWAYS")) return GOLEM_ERR_APPROVAL_REQUIRED;
    dw_entry *selection = dw_find(s, dw_text(r, "selection_id"), 0);
    if (!selection || strcmp(dw_text(selection->meta, "kind"), "stage-selection") ||
        strcmp(dw_text(dw_get(selection->meta, "selection"), "mode"), "documents")) return GOLEM_ERR_REQUIREMENTS_UNMET;
    wf_graph graph = {0}; golem_status st = wf_graph_make(s, &graph);
    if (st == GOLEM_OK && graph.states[selection - s->entries] != GOLEM_DOCUMENT_CURRENT) st = GOLEM_ERR_STALE_RESULT;
    wf_graph_free(s, &graph); if (st != GOLEM_OK) return st;
    struct json_object *enrollment = rc_enrollment(s, dw_text(r, "selection_id"));
    if (!enrollment) return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *contract = dw_get(dw_get(enrollment, "request"), "contract");
    golem_digest expected, actual;
    if (!dw_digest(r, "role_contract_digest", &expected)) return GOLEM_ERR_PARSE;
    st = ex_hash(contract, &actual);
    if (st != GOLEM_OK) return st;
    if (!dw_equal(&expected, &actual)) return GOLEM_ERR_STALE_RESULT;
    if (strcmp(dw_text(contract, "mode"), "documents") || strcmp(dw_text(contract, "allowed_effects"), "NONE")) return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *rules = dw_get(contract, "rules"), *roles = dw_get(p, "roles");
    for (size_t i = 0; i < json_object_array_length(rules); ++i) {
        struct json_object *rule = json_object_array_get_idx(rules, i);
        if (strcmp(dw_text(rule, "predicate"), "MARKDOWN") || json_object_get_boolean(dw_get(rule, "independent_review")) ||
            !contains(roles, dw_text(rule, "role"))) return GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    for (size_t i = 0; i < json_object_array_length(roles); ++i) {
        bool found = false;
        for (size_t j = 0; j < json_object_array_length(rules); ++j)
            if (!strcmp(json_object_get_string(json_object_array_get_idx(roles, i)), dw_text(json_object_array_get_idx(rules, j), "role"))) found = true;
        if (!found) return GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    if (!one(p, "inputs", "selection") || !one(p, "evidence", "native-role-assessment")) return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *caps = dw_get(p, "capabilities"), *prohibited = dw_get(p, "prohibited_effects");
    for (size_t i = 0; i < json_object_array_length(caps); ++i) {
        const char *cap = json_object_get_string(json_object_array_get_idx(caps, i));
        if (strcmp(cap, "document.read") && strcmp(cap, "role.evaluate")) return GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    for (size_t i = 0; i < json_object_array_length(prohibited); ++i) {
        const char *effect = json_object_get_string(json_object_array_get_idx(prohibited, i));
        if (strcmp(effect, "execution.run") && strcmp(effect, "network.upload") && strcmp(effect, "release.publish")) return GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    bool compatible = false;
    st = golem_workpack_compatibility(bytes(dw_text(r, "pack_json")), (golem_string_view){core_version, strlen(core_version)}, &compatible, NULL);
    return st != GOLEM_OK ? st : compatible ? GOLEM_OK : GOLEM_ERR_UNSUPPORTED_VERSION;
}
/* No session owner is inferred from an agent's string. This first mapping supports
 * local documents without session history; any session requires a future verified
 * native owner/fence mapping, including stopped/expired/uncertain sessions. */
static golem_status live(golem_document_store *s)
{
    as_log log; golem_status st = as_load(s, NULL, NULL, &log);
    if (st == GOLEM_OK && log.sequence) st = GOLEM_ERR_REQUIREMENTS_UNMET;
    as_close(&log);
    if (st == GOLEM_OK) st = re_deadline(s);
    return st;
}
static golem_status scope(golem_document_store *s, golem_bytes input, const golem_digest *manifest,
                          const char *core_version, struct json_object **out, golem_digest *digest)
{
    struct json_object *o = json_object_new_object(); golem_digest request, spec;
    golem_status st = golem_digest_bytes(input, &request);
    if (st == GOLEM_OK) st = ex_hash(s->spec, &spec);
    if (st == GOLEM_OK && (!ex_text(o, "domain", "golem.workpack.binding-approval.v1") ||
        !ex_text(o, "native_core_version", core_version) || !dw_add_digest(o, "request_digest", &request) || !dw_add_digest(o, "work_spec_digest", &spec) ||
        !dw_add_digest(o, "previous_work_frame", &s->last) || !dw_add_digest(o, "manifest_digest", manifest))) st = GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *r = NULL;
    if (st == GOLEM_OK) st = golem_json_parse(input, WP_REQUEST_MAX, &r);
    dw_entry *selection = st == GOLEM_OK ? dw_find(s, dw_text(r, "selection_id"), 0) : NULL;
    if (st == GOLEM_OK && (!selection || !dw_add_digest(o, "selection_manifest_digest", &selection->result.manifest_digest))) st = GOLEM_ERR_REQUIREMENTS_UNMET;
    json_object_put(r);
    if (st == GOLEM_OK) st = ex_hash(o, digest);
    if (st == GOLEM_OK) *out = o; else json_object_put(o);
    return st;
}
static golem_status receipt(struct json_object *event, const golem_digest *digest, golem_execution_reply *out)
{
    struct json_object *o = json_object_new_object();
    golem_status st = !dw_add(o, "binding", json_object_get(event)) || !dw_add_digest(o, "receipt_digest", digest) ||
        !ex_text(o, "semantics", "HISTORICAL_BINDING_NOT_EXECUTION_OR_COMPLETION") ? GOLEM_ERR_OUT_OF_MEMORY : ex_emit(o, out);
    json_object_put(o); return st;
}
static void adopt(golem_document_store *s, struct json_object *event, const golem_digest *payload, const golem_digest *frame)
{
    s->workpack_binding = json_object_get(event); s->workpack_binding_digest = *payload;
    s->last = *frame; ++s->event_count;
}
golem_status wp_apply(golem_document_store *s, struct json_object *event, const golem_digest *payload, const golem_digest *frame)
{
    const char *keys[] = {"schema_version", "type", "request_json", "scope", "approved_binding"};
    if (s->workpack_binding || !dw_keys(event, keys, 5) || dw_uint(event, "schema_version") != 1 ||
        strcmp(dw_text(event, "type"), "workpack-binding") || !json_object_is_type(dw_get(event, "request_json"), json_type_string)) return GOLEM_ERR_CORRUPT_JOURNAL;
    golem_bytes input = bytes(dw_text(event, "request_json"));
    struct json_object *r = NULL, *p = NULL, *o = NULL; golem_digest manifest, approved, actual;
    golem_status st = parse(input, &r, &p, &manifest);
    if (st == GOLEM_OK) st = mapping(s, r, p, true, dw_text(dw_get(event, "scope"), "native_core_version"));
    if (st == GOLEM_OK) st = scope(s, input, &manifest, dw_text(dw_get(event, "scope"), "native_core_version"), &o, &actual);
    if (st == GOLEM_OK && (!dw_digest(event, "approved_binding", &approved) || !dw_equal(&actual, &approved) ||
        !json_object_equal(o, dw_get(event, "scope")))) st = GOLEM_ERR_CORRUPT_JOURNAL;
    uint8_t *raw = NULL; size_t n = 0;
    if (st == GOLEM_OK) st = golem_evidence_read(s->cas, &manifest, GOLEM_WORKPACK_MAX_JSON, NULL, &raw, &n, NULL);
    if (st == GOLEM_OK && (n != strlen(dw_text(r, "pack_json")) || memcmp(raw, dw_text(r, "pack_json"), n))) st = GOLEM_ERR_CORRUPT_JOURNAL;
    if (st == GOLEM_OK) adopt(s, event, payload, frame);
    free(raw); json_object_put(r); json_object_put(p); json_object_put(o); return st;
}
golem_status golem_workpack_resolve(golem_document_store *s, golem_bytes input, golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out || s->poisoned) return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, "PACK_STORE");
    struct json_object *r = NULL, *p = NULL, *o = NULL; golem_digest manifest, digest;
    golem_status st = parse(input, &r, &p, &manifest);
    if (st == GOLEM_OK) st = mapping(s, r, p, true, GOLEM_VERSION_STRING);
    if (st == GOLEM_OK) st = live(s);
    if (st == GOLEM_OK && s->workpack_binding) st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK) st = scope(s, input, &manifest, GOLEM_VERSION_STRING, &o, &digest);
    if (st == GOLEM_OK && (!dw_add_digest(o, "binding_digest", &digest) || !ex_text(o, "status", "REVIEW_REQUIRED") ||
        !dw_add(o, "authorized", json_object_new_boolean(false)))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) st = ex_emit(o, out);
    json_object_put(r); json_object_put(p); json_object_put(o); return dw_report(d, st, "PACK_RESOLVE");
}
GOLEM_RECORDED_API(golem_workpack_bind,
    (golem_document_store *s, golem_bytes input, const golem_digest *approval,
     golem_execution_reply *out, golem_diagnostic *d), (s, input, approval, out, d), d)
{
    if (!s || !out || s->poisoned) return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, "PACK_STORE");
    struct json_object *r = NULL, *p = NULL, *o = NULL, *event = NULL;
    golem_digest manifest, digest, payload, frame; golem_execution_reply response = {0};
    golem_status st = parse(input, &r, &p, &manifest);
    if (st == GOLEM_OK && s->workpack_binding) {
        golem_digest saved;
        const char *raw = dw_text(s->workpack_binding, "request_json");
        if (strlen(raw) != input.size || memcmp(raw, input.data, input.size)) st = GOLEM_ERR_IDENTITY_MISMATCH;
        else if (!approval || !dw_digest(s->workpack_binding, "approved_binding", &saved) || !dw_equal(approval, &saved)) st = GOLEM_ERR_APPROVAL_REQUIRED;
        else st = receipt(s->workpack_binding, &s->workpack_binding_digest, out);
        goto done;
    }
    if (st == GOLEM_OK && !s->writable) st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK) st = mapping(s, r, p, true, GOLEM_VERSION_STRING);
    if (st == GOLEM_OK) st = live(s);
    if (st == GOLEM_OK) st = scope(s, input, &manifest, GOLEM_VERSION_STRING, &o, &digest);
    if (st == GOLEM_OK && (!approval || !dw_equal(approval, &digest))) st = GOLEM_ERR_APPROVAL_REQUIRED;
    if (st == GOLEM_OK) {
        event = json_object_new_object();
        if (!ex_uint(event, "schema_version", 1) || !ex_text(event, "type", "workpack-binding") ||
            !dw_add(event, "request_json", json_object_new_string_len((const char *)input.data, (int)input.size)) ||
            !dw_add(event, "scope", json_object_get(o)) || !dw_add_digest(event, "approved_binding", &digest)) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_receipt stored;
    if (st == GOLEM_OK) st = golem_evidence_put(s->cas, bytes(dw_text(r, "pack_json")), &stored, NULL);
    if (st == GOLEM_OK) st = dw_record_prepare(s, event, GOLEM_DOCUMENT_MAX_JSON, &payload);
    if (st == GOLEM_OK) st = receipt(event, &payload, &response);
    if (st == GOLEM_OK) st = dw_event_write(s, &payload, &frame);
    if (st == GOLEM_OK) { adopt(s, event, &payload, &frame); *out = response; response = (golem_execution_reply){0}; }
    if (st == GOLEM_ERR_IO) s->poisoned = true;
done:
    golem_execution_reply_free(&response); json_object_put(r); json_object_put(p); json_object_put(o); json_object_put(event);
    return dw_report(d, st, "PACK_BIND_NO_EXECUTION");
}
golem_status golem_workpack_explain(golem_document_store *s, golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out || s->poisoned) return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, "PACK_STORE");
    if (!s->workpack_binding) return dw_report(d, GOLEM_ERR_NOT_FOUND, "PACK_NOT_BOUND");
    struct json_object *r = NULL, *p = NULL, *o = json_object_new_object(); golem_digest manifest;
    golem_status st = parse(bytes(dw_text(s->workpack_binding, "request_json")), &r, &p, &manifest);
    golem_status current = st;
    if (current == GOLEM_OK) current = mapping(s, r, p, false, GOLEM_VERSION_STRING);
    if (current == GOLEM_OK) current = live(s);
    if (current == GOLEM_OK) {
        golem_digest saved;
        dw_entry *selection = dw_find(s, dw_text(r, "selection_id"), 0);
        if (!selection || !dw_digest(dw_get(s->workpack_binding, "scope"), "selection_manifest_digest", &saved) ||
            !dw_equal(&saved, &selection->result.manifest_digest)) current = GOLEM_ERR_STALE_RESULT;
    }
    uint8_t *raw = NULL; size_t n = 0;
    if (st == GOLEM_OK) st = golem_evidence_read(s->cas, &manifest, GOLEM_WORKPACK_MAX_JSON, NULL, &raw, &n, NULL);
    if (st == GOLEM_OK && (n != strlen(dw_text(r, "pack_json")) || memcmp(raw, dw_text(r, "pack_json"), n))) st = GOLEM_ERR_CORRUPT_JOURNAL;
    free(raw);
    if (st == GOLEM_OK && (!dw_add(o, "binding", json_object_get(s->workpack_binding)) ||
        !dw_add_digest(o, "receipt_digest", &s->workpack_binding_digest) ||
        !ex_uint(o, "current_generation", s->count + 1) ||
        !ex_text(o, "current_mapping", current == GOLEM_OK ? "APPLICABLE" : "BLOCKED") ||
        !ex_text(o, "blocker", golem_status_string(current)) ||
        !dw_add(o, "execution_authorized", json_object_new_boolean(false)) ||
        !ex_text(o, "pack_completion", "NOT_EVALUATED_USE_NATIVE_COMPLETION"))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) st = ex_emit(o, out);
    json_object_put(r); json_object_put(p); json_object_put(o); return dw_report(d, st, "PACK_EXPLAIN");
}
