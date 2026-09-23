#define _POSIX_C_SOURCE 200809L
#include "bundle_internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

const char *const rb_names[RB_FILES] = {"research-case.json", "attempt-decisions.jsonl",
    "outcome-adjudications.jsonl", "cohort-observations.jsonl", "metrics.json",
    "evidence-inventory.json", "redaction-policy.md", "narrative.md", "manifest.json", "checksums.sha256"};

golem_status rb_policy(golem_bytes b, struct json_object **out)
{
    struct json_object *o = NULL;
    golem_status st = golem_json_parse(b, GOLEM_RESEARCH_REDACTION_MAX_JSON, &o);
    const char *keys[] = {"schema_version", "profile", "acknowledge_linkability"};
    if (st == GOLEM_OK && (!dw_keys(o, keys, 3) ||
        !json_object_is_type(dw_get(o, "acknowledge_linkability"), json_type_boolean))) st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK && dw_uint(o, "schema_version") != 1) st = GOLEM_ERR_UNSUPPORTED_VERSION;
    if (st == GOLEM_OK) {
        bool link = !strcmp(dw_text(o, "profile"), "LINKABLE");
        if ((!link && strcmp(dw_text(o, "profile"), "MINIMAL")) ||
            link != (json_object_get_boolean(dw_get(o, "acknowledge_linkability")) != 0)) st = GOLEM_ERR_POLICY_DENIED;
    }
    if (st == GOLEM_OK) *out = o; else json_object_put(o);
    return st;
}
golem_status golem_research_redaction_validate(golem_bytes b, golem_diagnostic *d)
{
    struct json_object *o = NULL; golem_status st = rb_policy(b, &o);
    json_object_put(o); return dw_report(d, st, NULL);
}
bool rb_file(struct json_object *files, const char *name, struct json_object *value)
{
    if (!value) return false;
    const char *text = json_object_to_json_string_ext(value, JSON_C_TO_STRING_PLAIN);
    return text && ex_text(files, name, text);
}
golem_status rb_checksums(struct json_object *files, char **out, size_t *size)
{
    char *data = NULL; size_t n = 0; FILE *f = open_memstream(&data, &n);
    if (!f) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = GOLEM_OK;
    for (size_t i = 0; st == GOLEM_OK && i < RB_FILES-1; ++i) {
        struct json_object *v = dw_get(files, rb_names[i]);
        if (!json_object_is_type(v, json_type_string)) { st = GOLEM_ERR_PARSE; break; }
        const char *text = json_object_get_string(v); golem_digest digest; char hex[65]; size_t needed;
        st = golem_digest_bytes((golem_bytes){(const uint8_t *)text, (size_t)json_object_get_string_len(v)}, &digest);
        if (st == GOLEM_OK) st = golem_digest_format(&digest, hex, sizeof(hex), &needed);
        if (st == GOLEM_OK && fprintf(f, "%s  %s\n", hex, rb_names[i]) < 0) st = GOLEM_ERR_IO;
    }
    if (fclose(f) != 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK) { *out = data; *size = n; } else free(data);
    return st;
}
golem_status golem_research_bundle_verify(golem_bytes b, golem_diagnostic *d)
{
    struct json_object *o = NULL, *manifest = NULL;
    golem_status st = golem_json_parse(b, GOLEM_RESEARCH_BUNDLE_MAX_JSON, &o);
    const char *keys[] = {"schema_version", "files"};
    struct json_object *files = dw_get(o, "files");
    if (st == GOLEM_OK && (!dw_keys(o, keys, 2) || dw_uint(o, "schema_version") != 1 ||
        !dw_keys(files, rb_names, RB_FILES))) st = GOLEM_ERR_PARSE;
    for (size_t i = 0; st == GOLEM_OK && i < RB_FILES; ++i)
        if (!json_object_is_type(dw_get(files, rb_names[i]), json_type_string)) st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK) {
        const char *m = dw_text(files, "manifest.json");
        st = golem_json_parse((golem_bytes){(const uint8_t *)m, strlen(m)}, GOLEM_RESEARCH_BUNDLE_MAX_JSON, &manifest);
    }
    struct json_object *items = dw_get(manifest, "files");
    const char *mk[] = {"schema_version", "format", "golem_version", "privacy", "time_basis", "redaction_policy",
        "raw_evidence_included", "public_release_approved", "acceptance_verified", "independent_review",
        "selected_record_count", "files", "source_work_head"};
    struct json_object *checked_policy = NULL;
    if (st == GOLEM_OK) {
        const char *p = json_object_to_json_string_ext(dw_get(manifest, "redaction_policy"), JSON_C_TO_STRING_PLAIN);
        st = p ? rb_policy((golem_bytes){(const uint8_t *)p, strlen(p)}, &checked_policy) : GOLEM_ERR_PARSE;
    }
    bool linkable = !strcmp(dw_text(checked_policy, "profile"), "LINKABLE");
    if (st == GOLEM_OK && (!dw_keys(manifest, mk, linkable ? 13 : 12) ||
        strcmp(dw_text(manifest, "privacy"), "PRIVATE_REVIEW_REQUIRED") ||
        strcmp(dw_text(manifest, "time_basis"), "REPLAY_PREFIX_NO_WALL_CLOCK") ||
        !*dw_text(manifest, "golem_version") || strlen(dw_text(manifest, "golem_version")) > 64 ||
        dw_uint(manifest, "selected_record_count") < 1 || dw_uint(manifest, "selected_record_count") > GOLEM_RESEARCH_MAX_EVENTS))
        st = GOLEM_ERR_PARSE;
    for (size_t i = 6; st == GOLEM_OK && i < 10; ++i)
        if (!json_object_is_type(dw_get(manifest, mk[i]), json_type_boolean) || json_object_get_boolean(dw_get(manifest, mk[i])))
            st = GOLEM_ERR_PARSE;
    golem_digest head;
    if (st == GOLEM_OK && linkable && !dw_digest(manifest, "source_work_head", &head)) st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK && (dw_uint(manifest, "schema_version") != 1 ||
        strcmp(dw_text(manifest, "format"), "golem.case-study-bundle.v1") ||
        !json_object_is_type(items, json_type_array) || json_object_array_length(items) != RB_PAYLOADS)) st = GOLEM_ERR_PARSE;
    for (size_t i = 0; st == GOLEM_OK && i < RB_PAYLOADS; ++i) {
        struct json_object *item = json_object_array_get_idx(items, i), *v = dw_get(files, rb_names[i]);
        const char *ik[] = {"name", "size", "sha256"}; golem_digest expected, actual;
        if (!dw_keys(item, ik, 3) || strcmp(dw_text(item, "name"), rb_names[i]) ||
            !dw_digest(item, "sha256", &expected) || dw_uint(item, "size") != (uint64_t)json_object_get_string_len(v))
            st = GOLEM_ERR_PARSE;
        if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){(const uint8_t *)json_object_get_string(v),
            (size_t)json_object_get_string_len(v)}, &actual);
        if (st == GOLEM_OK && !dw_equal(&expected, &actual)) st = GOLEM_ERR_DIGEST_MISMATCH;
    }
    char *checksums = NULL; size_t n = 0;
    if (st == GOLEM_OK) st = rb_checksums(files, &checksums, &n);
    if (st == GOLEM_OK && (n != (size_t)json_object_get_string_len(dw_get(files, "checksums.sha256")) ||
        memcmp(checksums, dw_text(files, "checksums.sha256"), n))) st = GOLEM_ERR_DIGEST_MISMATCH;
    free(checksums); json_object_put(checked_policy); json_object_put(manifest); json_object_put(o);
    return dw_report(d, st, st == GOLEM_OK ? "file integrity only; no authenticity or privacy attestation" : NULL);
}
