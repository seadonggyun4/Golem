#define _POSIX_C_SOURCE 200809L
#include "bundle_internal.h"
#include "golem/version.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct rb_inventory {
    golem_document_store *store;
    golem_digest digests[RB_MAX_EVIDENCE];
    size_t count;
    bool linkable;
    struct json_object *items;
} rb_inventory;

static bool append(struct json_object *a, struct json_object *v)
{
    if (!v || json_object_array_add(a, v) != 0) { json_object_put(v); return false; }
    return true;
}
static bool boolean(struct json_object *o, const char *k, bool value)
{ return dw_add(o, k, json_object_new_boolean(value)); }
static golem_status inventory(rb_inventory *b, const golem_digest *digest, char alias[16])
{
    size_t i = 0;
    while (i < b->count && !dw_equal(digest, &b->digests[i])) ++i;
    (void)snprintf(alias, 16, "e%04u", (unsigned)i + 1);
    if (i < b->count) return GOLEM_OK;
    if (i == RB_MAX_EVIDENCE) return GOLEM_ERR_BUDGET_EXHAUSTED;
    uint64_t size;
    golem_status st = golem_evidence_verify(b->store->cas, digest, &size, NULL);
    if (st != GOLEM_OK) return st;
    struct json_object *o = json_object_new_object();
    if (!ex_text(o, "evidence_id", alias) || !ex_text(o, "disposition", "RAW_OMITTED") ||
        !ex_text(o, "reason", "STRUCTURAL_REDACTION") || !ex_text(o, "scope", "NO_TRANSITIVE_EXPANSION") ||
        !boolean(o, "source_bytes_verified_at_export", true)) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && b->linkable &&
        (!dw_add_digest(o, "source_sha256", digest) || !ex_uint(o, "source_size", size))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        if (!append(b->items, o)) st = GOLEM_ERR_OUT_OF_MEMORY;
    } else json_object_put(o);
    if (st == GOLEM_OK) b->digests[b->count++] = *digest;
    return st;
}
/* Only typed reference fields, never scan prose for apparent hashes or paths.
 * Referenced CAS bytes are verified but never traversed, decoded or copied. */
static golem_status references(rb_inventory *b, struct json_object *o, struct json_object *refs, unsigned depth)
{
    if (depth > 16) return GOLEM_ERR_BUDGET_EXHAUSTED;
    if (json_object_is_type(o, json_type_array)) {
        for (size_t i = 0; i < json_object_array_length(o); ++i) {
            golem_status st = references(b, json_object_array_get_idx(o, i), refs, depth+1);
            if (st != GOLEM_OK) return st;
        }
    } else if (json_object_is_type(o, json_type_object)) {
        json_object_object_foreach(o, key, value) {
            size_t n = strlen(key);
            bool reference = !strcmp(key, "digest") || !strcmp(key, "qa_receipt") || !strcmp(key, "supersedes") ||
                (n >= 7 && !strcmp(key+n-7, "_digest"));
            if (reference && *dw_text(o, key)) {
                golem_digest d; char alias[16];
                if (!dw_digest(o, key, &d)) return GOLEM_ERR_PARSE;
                golem_status st = inventory(b, &d, alias);
                if (st != GOLEM_OK) return st;
                struct json_object *v = json_object_new_object();
                if (!ex_text(v, "field", key) || !ex_text(v, "evidence_id", alias)) {
                    json_object_put(v); return GOLEM_ERR_OUT_OF_MEMORY;
                }
                if (!append(refs, v)) return GOLEM_ERR_OUT_OF_MEMORY;
            } else if (!reference) {
                golem_status st = references(b, value, refs, depth+1);
                if (st != GOLEM_OK) return st;
            }
        }
    }
    return GOLEM_OK;
}
static bool copy_fields(struct json_object *dest, struct json_object *source, const char *const *keys, size_t count)
{
    for (size_t i = 0; i < count; ++i)
        if (!dw_add(dest, keys[i], json_object_get(dw_get(source, keys[i])))) return false;
    return true;
}
#define COPY(d, s, a) copy_fields(d, s, a, sizeof(a)/sizeof(*(a)))
static golem_status jsonl(struct json_object *files, const char *name, struct json_object *array)
{
    char *data = NULL; size_t size = 0; FILE *f = open_memstream(&data, &size);
    if (!f) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = GOLEM_OK;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(array); ++i) {
        const char *text = json_object_to_json_string_ext(json_object_array_get_idx(array, i), JSON_C_TO_STRING_PLAIN);
        if (!text) st = GOLEM_ERR_OUT_OF_MEMORY;
        else if (fprintf(f, "%s\n", text) < 0) st = GOLEM_ERR_IO;
    }
    if (fclose(f) != 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && !ex_text(files, name, data ? data : "")) st = GOLEM_ERR_OUT_OF_MEMORY;
    free(data); return st;
}
golem_status golem_research_bundle(golem_document_store *s, const char *id, golem_bytes policy,
    golem_execution_reply *out, golem_diagnostic *diag)
{
    if (!s || !id || !dw_id(id) || !out) return dw_report(diag, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (s->poisoned) return dw_report(diag, GOLEM_ERR_INVALID_STATE, NULL);
    if (!strcmp(dw_text(s->spec, "permission"), "DENY")) return dw_report(diag, GOLEM_ERR_POLICY_DENIED, NULL);
    if (!strcmp(dw_text(s->spec, "permission"), "ASK_ALWAYS")) return dw_report(diag, GOLEM_ERR_APPROVAL_REQUIRED, NULL);
    struct json_object *p = NULL, *metrics = NULL;
    golem_status st = rb_policy(policy, &p);
    if (st == GOLEM_OK) st = rs_metrics(s, id, &metrics);
    if (st != GOLEM_OK) { json_object_put(p); json_object_put(metrics); return dw_report(diag, st, NULL); }
    rb_inventory *b = calloc(1, sizeof(*b));
    if (!b) { json_object_put(p); json_object_put(metrics); return dw_report(diag, GOLEM_ERR_OUT_OF_MEMORY, NULL); }
    b->store = s; b->linkable = !strcmp(dw_text(p, "profile"), "LINKABLE");
    b->items = json_object_new_array();
    struct json_object *files = json_object_new_object(), *case_view = NULL, *attempts = json_object_new_array();
    struct json_object *outcomes = json_object_new_array(), *cohorts = json_object_new_array();
    struct json_object *m = json_object_new_object(), *inv = json_object_new_object(), *manifest = json_object_new_object();
    struct json_object *entries = json_object_new_array(), *bundle = json_object_new_object();
    if (!b->items || !files || !attempts || !outcomes || !cohorts || !m || !inv || !manifest || !entries || !bundle)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    const char *attempt_ids[GOLEM_RESEARCH_MAX_EVENTS]; size_t attempt_count = 0, records = 0;
    for (size_t i = 0; st == GOLEM_OK && i < s->research_count; ++i) {
        struct json_object *request = dw_get(s->research[i], "request"), *r = dw_get(request, "record");
        if (strcmp(dw_text(r, "case_id"), id)) continue;
        const char *op = dw_text(request, "operation");
        struct json_object *v = json_object_new_object(), *refs = json_object_new_array(); char alias[16];
        if (!v || !refs) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) st = inventory(b, &s->research_digests[i], alias);
        if (st == GOLEM_OK && (!ex_uint(v, "ordinal", ++records) || !ex_text(v, "operation", op) ||
            !ex_text(v, "case", "case-1") || !ex_text(v, "source_evidence", alias))) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) st = references(b, r, refs, 0);
        if (st == GOLEM_OK && !dw_add(v, "references", json_object_get(refs))) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && !strcmp(op, "case-create")) {
            if (!ex_text(v, "case_type", dw_text(r, "case_type")) ||
                !ex_text(v, "context", "WITHHELD") || !ex_text(v, "research_questions", "WITHHELD")) st = GOLEM_ERR_OUT_OF_MEMORY;
            case_view = json_object_get(v);
        } else if (st == GOLEM_OK && (!strcmp(op, "attempt-plan") || !strcmp(op, "attempt-record"))) {
            size_t a = 0;
            while (a < attempt_count && strcmp(attempt_ids[a], dw_text(r, "attempt_id"))) ++a;
            if (a == attempt_count) attempt_ids[attempt_count++] = dw_text(r, "attempt_id");
            (void)snprintf(alias, sizeof(alias), "a%04u", (unsigned)a+1);
            if (!ex_text(v, "attempt", alias) || !ex_text(v, "actor_kind", dw_text(r, "actor_kind")) ||
                !ex_text(v, "hypothesis", "WITHHELD") || !ex_text(v, "intervention", "WITHHELD")) st = GOLEM_ERR_OUT_OF_MEMORY;
            const char *fields[] = {"classification", "next_action", "confidence"};
            if (st == GOLEM_OK && !strcmp(op, "attempt-record") && !COPY(v, r, fields)) st = GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK && !append(attempts, json_object_get(v))) st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (st == GOLEM_OK && rs_is_outcome(request)) {
            struct json_object *assessment = dw_get(s->research[i], "assessment");
            if (assessment) {
                const char *fields[] = {"normalized_status", "work_outcome", "pass_count", "fail_count", "error_count",
                    "skipped_count", "not_executed_count", "unknown_count"};
                if (!COPY(v, assessment, fields) || !ex_text(v, "basis", "HISTORICAL_DECLARED_OBSERVATIONS")) st = GOLEM_ERR_OUT_OF_MEMORY;
            } else if (!ex_uint(v, "required_case_count", json_object_array_length(dw_get(r, "required_cases")))) st = GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK && !append(outcomes, json_object_get(v))) st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (st == GOLEM_OK && !strcmp(op, "cohort-observe")) {
            const char *fields[] = {"status", "observed_arm", "leakage"};
            if (!COPY(v, r, fields) || !append(cohorts, json_object_get(v))) st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (st == GOLEM_OK) st = GOLEM_ERR_UNSUPPORTED_VERSION;
        json_object_put(v); json_object_put(refs);
    }
    const char *metric_fields[] = {"counts", "declared_classification_counts", "declared_actor_counts",
        "declared_next_action_counts", "latest_normalized_status_counts", "required_case_coverage",
        "adjudication_recovery", "unavailable"};
    if (st == GOLEM_OK && (!case_view || !ex_uint(m, "schema_version", 1) ||
        !ex_text(m, "rule", "golem.research-metrics.v1.redacted") || !COPY(m, metrics, metric_fields) ||
        !boolean(m, "acceptance_verified", false) || !ex_text(m, "omitted", "IDENTIFIERS_BOUNDARY_WORK_HISTORY_TIMESTAMPS") ||
        !ex_uint(inv, "schema_version", 1) || !ex_text(inv, "scope", "CASE_RESEARCH_RECORDS_AND_DIRECT_CAS_REFERENCES") ||
        !ex_uint(inv, "count", b->count) || !dw_add(inv, "items", json_object_get(b->items)) ||
        !rb_file(files, rb_names[0], case_view) || !rb_file(files, rb_names[4], m) || !rb_file(files, rb_names[5], inv)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) st = jsonl(files, rb_names[1], attempts);
    if (st == GOLEM_OK) st = jsonl(files, rb_names[2], outcomes);
    if (st == GOLEM_OK) st = jsonl(files, rb_names[3], cohorts);
    const char *redaction = b->linkable
        ? "# Redaction Policy\n\nLINKABLE: original IDs, prose, paths, timestamps and raw bytes withheld. Source SHA-256, sizes and Work head retained with explicit acknowledgement. Hashes enable linkage; not anonymization.\n"
        : "# Redaction Policy\n\nMINIMAL: original IDs, prose, paths, timestamps, source hashes/sizes and raw bytes withheld. Local aliases and categorical/count data retained. Rare combinations may identify a case. Not anonymization.\n";
    char narrative[1024];
    (void)snprintf(narrative, sizeof(narrative),
        "# Case Study\n\nPRIVATE_REVIEW_REQUIRED. Derived, structurally redacted projection.\n\n"
        "Case: case-1. Selected research records: %zu. Inventoried source objects: %zu.\n\n"
        "No raw evidence included. References are direct only; nested manifests, documents, source, other cases and orphan CAS objects are not expanded.\n\n"
        "Use metrics and outcome records as historical observations, not current completion or causal proof. Review omissions and original private evidence before drawing conclusions. No authored interpretation is included.\n", records, b->count);
    if (st == GOLEM_OK && (!ex_text(files, rb_names[6], redaction) || !ex_text(files, rb_names[7], narrative))) st = GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < RB_PAYLOADS; ++i) {
        const char *text = dw_text(files, rb_names[i]); golem_digest digest;
        st = golem_digest_bytes((golem_bytes){(const uint8_t *)text, strlen(text)}, &digest);
        struct json_object *v = json_object_new_object();
        if (st == GOLEM_OK && (!ex_text(v, "name", rb_names[i]) || !ex_uint(v, "size", strlen(text)) ||
            !dw_add_digest(v, "sha256", &digest))) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) { if (!append(entries, v)) st = GOLEM_ERR_OUT_OF_MEMORY; }
        else json_object_put(v);
    }
    if (st == GOLEM_OK && (!ex_uint(manifest, "schema_version", 1) ||
        !ex_text(manifest, "format", "golem.case-study-bundle.v1") || !ex_text(manifest, "golem_version", golem_version_string()) ||
        !ex_text(manifest, "privacy", "PRIVATE_REVIEW_REQUIRED") || !ex_text(manifest, "time_basis", "REPLAY_PREFIX_NO_WALL_CLOCK") ||
        !dw_add(manifest, "redaction_policy", json_object_get(p)) || !boolean(manifest, "raw_evidence_included", false) ||
        !boolean(manifest, "public_release_approved", false) || !boolean(manifest, "acceptance_verified", false) ||
        !boolean(manifest, "independent_review", false) || !ex_uint(manifest, "selected_record_count", records) ||
        !dw_add(manifest, "files", json_object_get(entries)))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && b->linkable && !dw_add_digest(manifest, "source_work_head", &s->last)) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && !rb_file(files, "manifest.json", manifest)) st = GOLEM_ERR_OUT_OF_MEMORY;
    char *checksums = NULL; size_t checksize = 0;
    if (st == GOLEM_OK) st = rb_checksums(files, &checksums, &checksize);
    if (st == GOLEM_OK && (!ex_text(files, "checksums.sha256", checksums) || !ex_uint(bundle, "schema_version", 1) ||
        !dw_add(bundle, "files", json_object_get(files)))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        const char *encoded = json_object_to_json_string_ext(bundle, JSON_C_TO_STRING_PLAIN);
        if (!encoded) st = GOLEM_ERR_OUT_OF_MEMORY;
        else if (strlen(encoded) > GOLEM_RESEARCH_BUNDLE_MAX_JSON) st = GOLEM_ERR_BUDGET_EXHAUSTED;
        else {
            size_t n = strlen(encoded); uint8_t *data = malloc(n+1);
            if (!data) st = GOLEM_ERR_OUT_OF_MEMORY;
            else { memcpy(data, encoded, n+1); *out = (golem_execution_reply){data, n}; }
        }
    }
    free(checksums); json_object_put(p); json_object_put(metrics); json_object_put(b->items); free(b);
    json_object_put(files); json_object_put(case_view); json_object_put(attempts); json_object_put(outcomes);
    json_object_put(cohorts); json_object_put(m); json_object_put(inv); json_object_put(manifest);
    json_object_put(entries); json_object_put(bundle);
    return dw_report(diag, st, NULL);
}
