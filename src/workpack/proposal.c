#include "golem/workpack.h"
#include "../workflow/role_internal.h"
#include <string.h>

static bool number(struct json_object *o, const char *key, uint64_t lo, uint64_t hi)
{
    return json_object_is_type(dw_get(o, key), json_type_int) &&
        json_object_get_int64(dw_get(o, key)) >= 0 && dw_uint(o, key) >= lo && dw_uint(o, key) <= hi;
}
static bool narrative(struct json_object *v)
{
    if (!json_object_is_type(v, json_type_string)) return false;
    const unsigned char *s = (const unsigned char *)json_object_get_string(v);
    if (!*s || strlen((const char *)s) > 2048) return false;
    bool meaningful = false;
    for (; *s; ++s) {
        if (*s < 32 || *s == 127) return false;
        if (*s > 32) meaningful = true;
    }
    return meaningful;
}
static bool narratives(struct json_object *a)
{
    if (!ds_array(a, 0, 32)) return false;
    for (size_t i = 0; i < json_object_array_length(a); ++i)
        if (!narrative(json_object_array_get_idx(a, i))) return false;
    return true;
}
static bool choice(const char *s, const char *a, const char *b, const char *c)
{ return !strcmp(s, a) || !strcmp(s, b) || !strcmp(s, c); }
static bool artifact_ref(struct json_object *artifacts, const char *digest)
{
    for (size_t i = 0; i < json_object_array_length(artifacts); ++i)
        if (!strcmp(dw_text(json_object_array_get_idx(artifacts, i), "digest"), digest)) return true;
    return false;
}
static golem_status proposal(golem_bytes input, struct json_object **out)
{
    struct json_object *o = NULL;
    golem_status st = golem_json_parse(input, GOLEM_WORKPACK_PROPOSAL_MAX_JSON, &o);
    const char *keys[] = {"schema", "proposal_id", "work", "pack_digest", "binding_receipt", "contract_digest",
        "artifacts", "verifier", "findings", "confidence", "limitations", "recommendation", "unresolved_questions"};
    const char *wk[] = {"identity", "generation"};
    const char *vk[] = {"principal_ref", "model_declared", "provider_declared", "status"};
    struct json_object *w = dw_get(o, "work"), *v = dw_get(o, "verifier"), *a = dw_get(o, "artifacts"), *f = dw_get(o, "findings");
    golem_digest digest;
    if (st != GOLEM_OK) goto done;
    st = GOLEM_ERR_PARSE;
    if (!dw_keys(o, keys, 13) || strcmp(dw_text(o, "schema"), "golem.workpack.verifier-proposal.v0") ||
        !dw_id(dw_text(o, "proposal_id")) || !dw_keys(w, wk, 2) || !dw_id(dw_text(w, "identity")) ||
        !number(w, "generation", 1, GOLEM_DOCUMENT_MAX_REVISIONS + 1) ||
        !dw_digest(o, "pack_digest", &digest) || !dw_digest(o, "binding_receipt", &digest) ||
        !dw_digest(o, "contract_digest", &digest) || !dw_keys(v, vk, 4) ||
        !dw_id(dw_text(v, "principal_ref")) || !dw_id(dw_text(v, "model_declared")) || !dw_id(dw_text(v, "provider_declared")) ||
        !choice(dw_text(v, "status"), "SUCCEEDED", "FAILED", "UNKNOWN") ||
        !choice(dw_text(o, "confidence"), "UNCERTAIN", "LIMITED", "SUPPORTED") ||
        !choice(dw_text(o, "recommendation"), "NEEDS_OWNER_REVIEW", "REJECT_PROPOSAL", "NO_BLOCKING_FINDING_OBSERVED") ||
        (strcmp(dw_text(v, "status"), "SUCCEEDED") && strcmp(dw_text(o, "recommendation"), "NEEDS_OWNER_REVIEW")) ||
        !narratives(dw_get(o, "limitations")) || !narratives(dw_get(o, "unresolved_questions")) ||
        !ds_array(a, 1, 32) || !ds_array(f, 0, 32)) goto done;
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *x = json_object_array_get_idx(a, i);
        const char *ak[] = {"digest", "size"};
        if (!dw_keys(x, ak, 2) || !dw_digest(x, "digest", &digest) || !number(x, "size", 1, GOLEM_DOCUMENT_MAX_BODY)) goto done;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(dw_text(x, "digest"), dw_text(json_object_array_get_idx(a, j), "digest"))) goto done;
    }
    for (size_t i = 0; i < json_object_array_length(f); ++i) {
        struct json_object *x = json_object_array_get_idx(f, i), *refs = dw_get(x, "evidence_refs");
        const char *fk[] = {"id", "severity", "summary", "evidence_refs"};
        if (!dw_keys(x, fk, 4) || !dw_id(dw_text(x, "id")) ||
            !choice(dw_text(x, "severity"), "INFO", "WARNING", "BLOCKING") || !narrative(dw_get(x, "summary")) || !ds_array(refs, 1, 32)) goto done;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(dw_text(x, "id"), dw_text(json_object_array_get_idx(f, j), "id"))) goto done;
        for (size_t j = 0; j < json_object_array_length(refs); ++j) {
            struct json_object *ref = json_object_array_get_idx(refs, j);
            if (!json_object_is_type(ref, json_type_string) || !artifact_ref(a, json_object_get_string(ref))) goto done;
            for (size_t k = 0; k < j; ++k)
                if (json_object_equal(ref, json_object_array_get_idx(refs, k))) goto done;
        }
    }
    st = GOLEM_OK;
done:
    if (st == GOLEM_OK) *out = o; else json_object_put(o);
    return st;
}
golem_status golem_workpack_proposal_validate(golem_bytes input, golem_digest *digest, golem_diagnostic *d)
{
    if (!digest) return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, "PACK_PROPOSAL_OUTPUT");
    struct json_object *o = NULL; golem_digest found;
    golem_status st = proposal(input, &o);
    if (st == GOLEM_OK) st = golem_digest_bytes(input, &found);
    if (st == GOLEM_OK) *digest = found;
    json_object_put(o); return dw_report(d, st, "PACK_PROPOSAL_UNTRUSTED_CLAIM");
}
/* Only current document bodies in the bound selection's native role closure.
 * This is not a general CAS reader or a caller-supplied evidence allowlist. */
static golem_status artifacts(golem_document_store *s, struct json_object *binding, struct json_object **out)
{
    dw_entry *selection = dw_find(s, dw_text(binding, "selection_id"), 0);
    if (!selection) return GOLEM_ERR_NOT_FOUND;
    struct json_object *enrollment = rc_enrollment(s, dw_text(binding, "selection_id"));
    struct json_object *rules = dw_get(dw_get(dw_get(enrollment, "request"), "contract"), "rules");
    wf_graph g = {0}; golem_status st = wf_graph_make(s, &g);
    size_t roots[GOLEM_ROLE_MAX_RULES + 1], count = 1; roots[0] = (size_t)(selection - s->entries);
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(rules); ++i) {
        dw_entry *entry = NULL;
        st = wf_role_pick(s, selection, wf_kind(dw_text(json_object_array_get_idx(rules, i), "kind")), &g, &entry);
        if (st == GOLEM_ERR_NOT_FOUND) st = GOLEM_OK;
        else if (st == GOLEM_OK) roots[count++] = (size_t)(entry - s->entries);
    }
    bool selected[GOLEM_DOCUMENT_MAX_REVISIONS];
    if (st == GOLEM_OK) st = wf_closure(s, &g, roots, count, selected);
    struct json_object *a = json_object_new_array();
    if (!a && st == GOLEM_OK) st = GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < s->count; ++i) if (selected[i]) {
        uint64_t size = 0;
        st = g.states[i] == GOLEM_DOCUMENT_CURRENT ? wf_integrity(s, i, &size) : GOLEM_ERR_STALE_RESULT;
        if (st == GOLEM_OK) {
            struct json_object *x = json_object_new_object();
            if (!dw_add_digest(x, "digest", &s->entries[i].result.body_digest) || !ex_uint(x, "size", size)) {
                json_object_put(x); st = GOLEM_ERR_OUT_OF_MEMORY;
            } else if (!wf_append(a, x)) st = GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    wf_graph_free(s, &g);
    if (st == GOLEM_OK) *out = a; else json_object_put(a);
    return st;
}
golem_status golem_workpack_assess(golem_document_store *s, const golem_bytes *inputs, size_t count,
                                  golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !inputs || !out || !count || count > GOLEM_WORKPACK_MAX_PROPOSALS || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, "PACK_ASSESS_INPUT");
    golem_execution_reply explained = {0}, native = {0};
    struct json_object *view = NULL, *binding = NULL, *allowed = NULL, *claims = json_object_new_array(), *evaluation = NULL;
    struct json_object *request = NULL, *report = NULL;
    golem_status st = golem_workpack_explain(s, &explained, d);
    if (st == GOLEM_OK) st = golem_json_parse((golem_bytes){explained.data, explained.size}, GOLEM_DOCUMENT_MAX_JSON, &view);
    if (st == GOLEM_OK && strcmp(dw_text(view, "current_mapping"), "APPLICABLE")) st = GOLEM_ERR_REQUIREMENTS_UNMET;
    const char *raw = dw_text(s->workpack_binding, "request_json");
    if (st == GOLEM_OK) st = golem_json_parse((golem_bytes){(const uint8_t *)raw, strlen(raw)}, 131072, &binding);
    if (st == GOLEM_OK) st = artifacts(s, binding, &allowed);
    bool disagreement = false;
    for (size_t i = 0; st == GOLEM_OK && i < count; ++i) {
        struct json_object *p = NULL; golem_digest digest, expected;
        st = proposal(inputs[i], &p);
        if (st == GOLEM_OK && (strcmp(dw_text(dw_get(p, "work"), "identity"), dw_text(s->spec, "work_id")) ||
            dw_uint(dw_get(p, "work"), "generation") != s->count + 1 ||
            !dw_digest(p, "binding_receipt", &digest) || !dw_equal(&digest, &s->workpack_binding_digest) ||
            !dw_digest(p, "contract_digest", &digest) || !dw_digest(binding, "role_contract_digest", &expected) || !dw_equal(&digest, &expected) ||
            !dw_digest(p, "pack_digest", &digest) || !dw_digest(dw_get(s->workpack_binding, "scope"), "manifest_digest", &expected) || !dw_equal(&digest, &expected))) st = GOLEM_ERR_STALE_RESULT;
        struct json_object *a = dw_get(p, "artifacts");
        for (size_t j = 0; st == GOLEM_OK && j < json_object_array_length(a); ++j) {
            bool found = false;
            for (size_t k = 0; k < json_object_array_length(allowed); ++k)
                if (json_object_equal(json_object_array_get_idx(a, j), json_object_array_get_idx(allowed, k))) found = true;
            if (!found) st = GOLEM_ERR_IDENTITY_MISMATCH;
        }
        for (size_t j = 0; st == GOLEM_OK && j < i; ++j) {
            struct json_object *other = dw_get(json_object_array_get_idx(claims, j), "proposal");
            if (!strcmp(dw_text(p, "proposal_id"), dw_text(other, "proposal_id")) ||
                !strcmp(dw_text(dw_get(p, "verifier"), "principal_ref"), dw_text(dw_get(other, "verifier"), "principal_ref"))) st = GOLEM_ERR_IDENTITY_MISMATCH;
            if (strcmp(dw_text(p, "recommendation"), dw_text(other, "recommendation")) ||
                !json_object_equal(dw_get(p, "findings"), dw_get(other, "findings"))) disagreement = true;
        }
        if (st == GOLEM_OK) st = golem_digest_bytes(inputs[i], &digest);
        if (st == GOLEM_OK) {
            struct json_object *claim = json_object_new_object();
            if (!dw_add_digest(claim, "proposal_digest", &digest) || !dw_add(claim, "proposal", json_object_get(p))) {
                json_object_put(claim); st = GOLEM_ERR_OUT_OF_MEMORY;
            } else if (!wf_append(claims, claim)) st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        json_object_put(p);
    }
    if (st == GOLEM_OK) {
        request = json_object_new_object();
        if (!ex_uint(request, "schema_version", 1) || !ex_text(request, "operation", "evaluate") ||
            !ex_text(request, "selection_id", dw_text(binding, "selection_id")) || !ex_text(request, "key", "workpack-proposal-observation") ||
            !ex_uint(request, "expected_generation", s->count + 1) || json_object_object_add(request, "review", NULL) != 0) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK) {
        const char *text = json_object_to_json_string_ext(request, JSON_C_TO_STRING_PLAIN);
        st = golem_role_call(s, (golem_bytes){(const uint8_t *)text, strlen(text)}, NULL, &native, d);
    }
    if (st == GOLEM_OK) st = golem_json_parse((golem_bytes){native.data, native.size}, GOLEM_DOCUMENT_MAX_JSON, &evaluation);
    if (st == GOLEM_OK) {
        report = json_object_new_object();
        if (!ex_text(report, "schema", "golem.workpack.assessment.v0") || !ex_text(report, "decision", "NEEDS_OWNER_REVIEW") ||
            !ex_text(report, "identity_status", "UNVERIFIED_DECLARATIONS") || !ex_text(report, "model_truth", "NOT_EVALUATED") ||
            !dw_add(report, "authorized", json_object_new_boolean(false)) || !dw_add(report, "completion_evaluated", json_object_new_boolean(false)) ||
            !dw_add(report, "declared_disagreement", json_object_new_boolean(disagreement)) ||
            !dw_add_digest(report, "binding_receipt", &s->workpack_binding_digest) ||
            !dw_add(report, "claims", json_object_get(claims)) || !dw_add(report, "native_role_evaluation", json_object_get(evaluation))) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK) st = ex_emit(report, out);
    golem_execution_reply_free(&explained); golem_execution_reply_free(&native);
    json_object_put(view); json_object_put(binding); json_object_put(allowed); json_object_put(claims);
    json_object_put(evaluation); json_object_put(request); json_object_put(report);
    return dw_report(d, st, "PACK_ASSESS_NO_AUTHORITY");
}
