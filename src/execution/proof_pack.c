#define _POSIX_C_SOURCE 200809L
#include "proof_internal.h"
#include "../research/bundle_internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int key_compare(const void *a, const void *b)
{
    return memcmp(a, b, sizeof(golem_digest));
}

static const char *verdict(struct json_object *o)
{
    const char *s = dw_text(o, "status");
    return !strcmp(s, "PASS")    ? "PASS"
           : !strcmp(s, "FAIL")  ? "FAIL"
           : !strcmp(s, "ERROR") ? "ERROR"
                                 : "UNKNOWN";
}

static bool copy_digest(struct json_object *to, struct json_object *from, const char *key)
{
    golem_digest digest;
    return dw_digest(from, key, &digest) && dw_add_digest(to, key, &digest);
}

/* Allowlisted values only: source paths, IDs, argv, case names and log text
 * never enter Markdown. Ordinals replace source identities in MINIMAL. */
static const char *reason(struct json_object *o)
{
    static const char *const reasons[] = {"EXECUTION_ERROR",
                                          "TIMEOUT",
                                          "LEASE_EXPIRED",
                                          "REENTRY_DEADLINE_EXHAUSTED",
                                          "LOG_LIMIT",
                                          "SIGNAL",
                                          "CLOCK_ERROR",
                                          "CASE_ERROR",
                                          "NONZERO_EXIT",
                                          "DECLARED_CASES_PASSED",
                                          "CASE_FAILED",
                                          "INVALID_OR_MISSING_CASES",
                                          "EVIDENCE_INCOMPLETE",
                                          "SNAPSHOT_CHANGED",
                                          "DECLARED_GATES_PASSED",
                                          "GATE_NOT_PASSED"};
    for (size_t i = 0; i < sizeof(reasons) / sizeof(reasons[0]); ++i)
        if (!strcmp(dw_text(o, "reason"), reasons[i]))
            return reasons[i];
    return "UNKNOWN";
}

static golem_status run_facts(golem_document_store *store, struct json_object *bundle, bool link,
                              size_t ordinal, struct json_object **out)
{
    struct json_object *run = json_object_new_object();
    struct json_object *gates = json_object_new_array();
    golem_status st = GOLEM_OK;
    bool historical =
        !strcmp(dw_text(bundle, "log_availability"), "HISTORICAL_DISCARDED_COMPLETENESS_UNKNOWN");
    if (!ex_uint(run, "run", ordinal) || !ex_text(run, "status", verdict(bundle)) ||
        !ex_text(run, "reason", reason(bundle)) ||
        !ex_text(run, "scope",
                 !strcmp(dw_text(bundle, "scope"), "POLICY_SCOPED_HEAD_INDEX_WORKTREE_NONATOMIC_V1")
                     ? "POLICY_SCOPED_NONATOMIC"
                     : "DECLARED_FILES_NONATOMIC") ||
        !dw_add(run, "gates", json_object_get(gates)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    const char *refs[] = {"qa_receipt", "checkpoint", "approved_contract", "input_manifest",
                          "source_snapshot"};
    for (size_t i = 0; st == GOLEM_OK && link && i < sizeof(refs) / sizeof(refs[0]); ++i)
        if (!copy_digest(run, bundle, refs[i]))
            st = GOLEM_ERR_PARSE;
    struct json_object *source = dw_get(bundle, "gates");
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(source); ++i) {
        struct json_object *g = json_object_array_get_idx(source, i);
        struct json_object *item = json_object_new_object(), *logs = json_object_new_array();
        if (!ex_uint(item, "gate", i + 1) || !ex_text(item, "status", verdict(g)) ||
            !ex_text(item, "reason", reason(g)) ||
            !dw_add(item, "exit_code",
                    json_object_new_int64(json_object_get_int64(dw_get(g, "exit_code")))) ||
            !ex_uint(item, "signal", dw_uint(g, "signal")) ||
            !dw_add(item, "timed_out",
                    json_object_new_boolean(json_object_get_boolean(dw_get(g, "timed_out")))) ||
            !dw_add(item, "logs", json_object_get(logs)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && link && !ex_text(item, "duration_availability", historical ? "UNKNOWN" : "RECORDED"))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && link && !historical && !ex_uint(item, "duration_ms", dw_uint(g, "duration_ms")))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        for (size_t j = 0; st == GOLEM_OK && j < 2; ++j) {
            struct json_object *log =
                historical ? NULL : json_object_array_get_idx(dw_get(g, "logs"), j);
            struct json_object *entry = json_object_new_object();
            const char *state = dw_text(log, "state");
            if (historical)
                state = "HISTORICAL_DISCARDED_COMPLETENESS_UNKNOWN";
            else if (strcmp(state, "COMPLETE") && strcmp(state, "TRUNCATED") &&
                     strcmp(state, "DISCARDED"))
                state = "UNKNOWN";
            if (!ex_text(entry, "stream", j ? "stderr" : "stdout") ||
                !ex_text(entry, "state", state) ||
                !dw_add(entry, "total_bytes_known",
                        json_object_new_boolean(!historical && json_object_get_boolean(dw_get(
                                                                   log, "total_bytes_known")))) ||
                !ex_text(entry, "included", "NONE_REFERENCE_ONLY"))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK && link && !historical) {
                if (!copy_digest(entry, log, "observed_digest") ||
                    !ex_uint(entry, "observed_bytes", dw_uint(log, "observed_bytes")) ||
                    !ex_uint(entry, "retained_bytes", dw_uint(log, "retained_bytes")) ||
                    !ex_uint(entry, "dropped_observed_bytes",
                             dw_uint(log, "dropped_observed_bytes")))
                    st = GOLEM_ERR_PARSE;
                if (st == GOLEM_OK && dw_get(log, "retained_receipt") &&
                    !copy_digest(entry, log, "retained_receipt"))
                    st = GOLEM_ERR_PARSE;
                if (st == GOLEM_OK && dw_get(log, "retained_receipt")) {
                    golem_digest key;
                    golem_receipt retained;
                    if (!dw_digest(log, "retained_receipt", &key))
                        st = GOLEM_ERR_PARSE;
                    else
                        st = golem_evidence_receipt_verify(store->cas, &key, &retained, NULL);
                    if (st == GOLEM_OK &&
                        !dw_add_digest(entry, "retained_artifact_digest", &retained.digest))
                        st = GOLEM_ERR_OUT_OF_MEMORY;
                }
            }
            if (st == GOLEM_OK && json_object_array_add(logs, entry) == 0)
                entry = NULL;
            else if (st == GOLEM_OK)
                st = GOLEM_ERR_OUT_OF_MEMORY;
            json_object_put(entry);
        }
        json_object_put(logs);
        if (st == GOLEM_OK && json_object_array_add(gates, item) == 0)
            item = NULL;
        else if (st == GOLEM_OK)
            st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(item);
    }
    json_object_put(gates);
    if (st == GOLEM_OK)
        *out = run;
    else
        json_object_put(run);
    return st;
}

static golem_status markdown(struct json_object *facts, struct json_object *files)
{
    const char *inventory = json_object_to_json_string_ext(facts, JSON_C_TO_STRING_PLAIN);
    if (!inventory)
        return GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t kind = 0; kind < PROOF_PAYLOADS; ++kind) {
        char *text = NULL;
        size_t size = 0;
        FILE *f = open_memstream(&text, &size);
        if (!f)
            return GOLEM_ERR_OUT_OF_MEMORY;
        if (kind == 0)
            fprintf(f, "# Verification summary\n\nDerived projection; not Work completion or "
                       "public-release approval.\n\n");
        else if (kind == 1)
            fprintf(f,
                    "# Verification proof\n\nSource receipt verification is separate from file "
                    "integrity.\n"
                    "Raw stream digests, retained receipt digests and projection digests name "
                    "different domains;\n"
                    "equal hashes do not imply equal roles. No original logs are "
                    "included.\n\n```json\n%s\n```\n",
                    inventory);
        else if (kind == 2)
            fprintf(f, "# Descriptive comparison\n\nNo ranking, causal claim or candidate "
                       "eligibility is established.\n\n"
                       "| Run | QA outcome | Gates |\n| --- | --- | --- |\n");
        else
            fprintf(f, "%s\n", inventory);
        struct json_object *runs = dw_get(facts, "runs");
        for (size_t i = 0; (kind == 0 || kind == 2) && i < json_object_array_length(runs); ++i) {
            struct json_object *r = json_object_array_get_idx(runs, i);
            if (kind == 0)
                fprintf(f,
                        "- Run %zu: %s. Log availability is listed in evidence-inventory.json.\n",
                        i + 1, verdict(r));
            else
                fprintf(f, "| %zu | %s | %zu |\n", i + 1, verdict(r),
                        json_object_array_length(dw_get(r, "gates")));
        }
        bool failed = ferror(f) != 0;
        if (fclose(f) != 0)
            failed = true;
        bool added = !failed && ex_text(files, proof_names[kind], text);
        free(text);
        if (!added)
            return failed ? GOLEM_ERR_IO : GOLEM_ERR_OUT_OF_MEMORY;
    }
    return GOLEM_OK;
}

golem_status golem_proof_render(golem_document_store *s, golem_bytes bytes,
                                golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || s->poisoned || !out)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *request = NULL, *policy = NULL, *pack = NULL;
    struct json_object *facts = json_object_new_object(), *runs = json_object_new_array();
    struct json_object *files = json_object_new_object();
    golem_status st = golem_json_parse(bytes, GOLEM_DOCUMENT_MAX_JSON, &request);
    const char *keys[] = {"schema_version", "renderer_version", "qa_receipts", "redaction"};
    struct json_object *receipts = dw_get(request, "qa_receipts");
    if (st == GOLEM_OK && (!dw_keys(request, keys, 4) || !ds_array(receipts, 1, 8)))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK &&
        (dw_uint(request, "schema_version") != 1 || dw_uint(request, "renderer_version") != 1))
        st = GOLEM_ERR_UNSUPPORTED_VERSION;
    if (st == GOLEM_OK) {
        const char *wire =
            json_object_to_json_string_ext(dw_get(request, "redaction"), JSON_C_TO_STRING_PLAIN);
        st = wire ? rb_policy((golem_bytes){(const uint8_t *)wire, strlen(wire)}, &policy)
                  : GOLEM_ERR_PARSE;
    }
    golem_digest selected[8];
    size_t count = st == GOLEM_OK ? json_object_array_length(receipts) : 0;
    for (size_t i = 0; st == GOLEM_OK && i < count; ++i) {
        struct json_object *key = json_object_array_get_idx(receipts, i);
        if (!json_object_is_type(key, json_type_string))
            st = GOLEM_ERR_PARSE;
        else
            st = golem_digest_parse((golem_string_view){json_object_get_string(key),
                                                        (size_t)json_object_get_string_len(key)},
                                    &selected[i]);
    }
    if (st == GOLEM_OK)
        qsort(selected, count, sizeof(selected[0]), key_compare);
    bool link = !strcmp(dw_text(policy, "profile"), "LINKABLE");
    /* Reconstruct policy insertion order, so request key order is immaterial. */
    struct json_object *canonical = json_object_new_object();
    if (st == GOLEM_OK &&
        (!files || !runs || !ex_uint(canonical, "schema_version", 1) ||
         !ex_text(canonical, "profile", link ? "LINKABLE" : "MINIMAL") ||
         !dw_add(canonical, "acknowledge_linkability", json_object_new_boolean(link)) ||
         !ex_uint(facts, "schema_version", 1) ||
         !ex_text(facts, "kind", "DERIVED_REFERENCE_INVENTORY") ||
         !dw_add(facts, "raw_evidence_included", json_object_new_boolean(false)) ||
         !dw_add(facts, "runs", json_object_get(runs))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < count; ++i) {
        struct json_object *bundle = NULL, *run = NULL;
        golem_execution_reply reply = {0};
        if (i && dw_equal(&selected[i - 1], &selected[i]))
            st = GOLEM_ERR_INVALID_ARGUMENT;
        if (st == GOLEM_OK)
            st = golem_execution_bundle_inspect(s, &selected[i], &reply, NULL);
        if (st == GOLEM_OK)
            st = golem_json_parse((golem_bytes){reply.data, reply.size}, GOLEM_DOCUMENT_MAX_JSON,
                                  &bundle);
        if (st == GOLEM_OK)
            st = run_facts(s, bundle, link, i + 1, &run);
        if (st == GOLEM_OK && json_object_array_add(runs, run) == 0)
            run = NULL;
        else if (st == GOLEM_OK)
            st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(run);
        json_object_put(bundle);
        golem_execution_reply_free(&reply);
    }
    if (st == GOLEM_OK)
        st = markdown(facts, files);
    if (st == GOLEM_OK)
        st = proof_seal(files, canonical, &pack);
    if (st == GOLEM_OK)
        st = ex_emit(pack, out);
    json_object_put(request);
    json_object_put(policy);
    json_object_put(canonical);
    json_object_put(facts);
    json_object_put(runs);
    json_object_put(files);
    json_object_put(pack);
    return dw_report(d, st, NULL);
}

golem_status golem_proof_verify(golem_document_store *s, golem_bytes request, golem_bytes bytes,
                                golem_diagnostic *d)
{
    struct json_object *given = NULL, *expected = NULL;
    golem_digest digest;
    golem_execution_reply reply = {0};
    golem_status st = proof_parse(bytes, NULL, &given, &digest);
    if (st == GOLEM_OK)
        st = golem_proof_render(s, request, &reply, NULL);
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){reply.data, reply.size}, GOLEM_DOCUMENT_MAX_JSON,
                              &expected);
    if (st == GOLEM_OK && !json_object_equal(given, expected))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    json_object_put(given);
    json_object_put(expected);
    golem_execution_reply_free(&reply);
    return dw_report(d, st, NULL);
}
