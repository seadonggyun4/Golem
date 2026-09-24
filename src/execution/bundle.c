#include "internal.h"
#include <string.h>

/* The receipt is the root of identity. No user-supplied replacement source,
 * attempt, verdict or log inventory is accepted when assembling the bundle. */
golem_status ex_bundle_build(golem_document_store *s, const golem_digest *key,
                             struct json_object *qa, struct json_object **out)
{
    golem_digest checkpoint, contract, actual, manifest, snapshot;
    struct json_object *cp = NULL, *bundle = NULL;
    if (strcmp(dw_text(qa, "type"), "qa") ||
        strcmp(dw_text(qa, "work_id"), dw_text(s->spec, "work_id")) ||
        !dw_digest(qa, "checkpoint", &checkpoint))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    golem_status st = ex_load(s, &checkpoint, "checkpoint", &cp);
    struct json_object *c = dw_get(cp, "contract");
    if (st == GOLEM_OK)
        st = ex_contract(c);
    if (st == GOLEM_OK)
        st = ex_hash(c, &actual);
    if (st == GOLEM_OK &&
        (!dw_digest(cp, "contract_digest", &contract) || !dw_equal(&contract, &actual) ||
         dw_uint(qa, "schema_version") != dw_uint(c, "schema_version")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *gates = dw_get(qa, "gates"), *definitions = dw_get(c, "gates");
    if (st == GOLEM_OK && (!ds_array(gates, 1, 8) || json_object_array_length(gates) !=
                                                         json_object_array_length(definitions)))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(gates); ++i) {
        struct json_object *g = json_object_array_get_idx(gates, i);
        struct json_object *def = json_object_array_get_idx(definitions, i);
        if (strcmp(dw_text(g, "gate_id"), dw_text(def, "id")) ||
            dw_uint(g, "version") != dw_uint(def, "version"))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        if (st == GOLEM_OK && dw_uint(qa, "schema_version") >= 2)
            st = ex_logs_verify(s, g, dw_get(c, "log_retention"));
    }
    if (st == GOLEM_OK)
        st = ex_hash(dw_get(qa, "manifest"), &manifest);
    if (st == GOLEM_OK)
        st = ex_hash(dw_get(qa, "snapshot"), &snapshot);
    if (st == GOLEM_OK) {
        bundle = json_object_new_object();
        if (!ex_uint(bundle, "schema_version", 1) ||
            !ex_text(bundle, "type", "golem.verification-bundle.v1") ||
            !dw_add_digest(bundle, "qa_receipt", key) ||
            !ex_text(bundle, "work_id", dw_text(qa, "work_id")) ||
            !ex_text(bundle, "attempt_id", dw_text(qa, "attempt_id")) ||
            !dw_add_digest(bundle, "checkpoint", &checkpoint) ||
            !dw_add_digest(bundle, "approved_contract", &contract) ||
            !dw_add_digest(bundle, "input_manifest", &manifest) ||
            !dw_add_digest(bundle, "source_snapshot", &snapshot) ||
            !dw_add(bundle, "executables", json_object_get(dw_get(cp, "executables"))) ||
            !dw_add(bundle, "gates", json_object_get(gates)) ||
            !ex_text(bundle, "status", dw_text(qa, "status")) ||
            !ex_text(bundle, "reason", dw_text(qa, "reason")) ||
            !ex_text(bundle, "command_reference",
                     "checkpoint.contract.gates: argv, repository cwd, expected cases") ||
            !ex_text(bundle, "log_availability",
                     dw_uint(qa, "schema_version") == 1
                         ? "HISTORICAL_DISCARDED_COMPLETENESS_UNKNOWN"
                         : "PER_STREAM_DESCRIPTOR") ||
            !ex_text(bundle, "time_basis", "HOST_MONOTONIC_MILLISECONDS_NOT_WALL_TIME") ||
            !ex_text(bundle, "scope",
                     dw_uint(c, "schema_version") >= 4
                         ? "POLICY_SCOPED_HEAD_INDEX_WORKTREE_NONATOMIC_V1"
                         : "DECLARED_FILES_NONATOMIC_NOT_CANDIDATE_INVENTORY") ||
            !dw_add(bundle, "acceptance_verified", json_object_new_boolean(false)) ||
            !dw_add(bundle, "public_export_approved", json_object_new_boolean(false)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        *out = bundle;
    else
        json_object_put(bundle);
    json_object_put(cp);
    return st;
}

golem_status ex_bundle_check(golem_document_store *s, const golem_digest *key,
                             struct json_object *qa, bool publish)
{
    struct json_object *bundle = NULL, *stored = NULL;
    golem_digest digest;
    golem_status st = ex_bundle_build(s, key, qa, &bundle);
    if (st == GOLEM_OK)
        st = publish ? dw_put_json(s, bundle, &digest) : ex_hash(bundle, &digest);
    if (st == GOLEM_OK && !publish)
        st = dw_cas_json(s, &digest, &stored);
    if (st == GOLEM_OK && !publish && !json_object_equal(bundle, stored))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    json_object_put(bundle);
    json_object_put(stored);
    return st;
}

golem_status golem_execution_bundle_inspect(golem_document_store *s, const golem_digest *key,
                                            golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !key || !out || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *qa = NULL, *bundle = NULL;
    golem_status st = ex_load(s, key, "qa", &qa);
    if (st == GOLEM_OK)
        st = ex_bundle_build(s, key, qa, &bundle);
    if (st == GOLEM_OK)
        st = ex_emit(bundle, out);
    json_object_put(qa);
    json_object_put(bundle);
    return dw_report(d, st, NULL);
}

golem_status golem_execution_bundle_verify(golem_document_store *s, golem_bytes bytes,
                                           golem_diagnostic *d)
{
    if (!s || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *given = NULL, *expected = NULL;
    golem_execution_reply reply = {0};
    golem_digest key;
    golem_status st = golem_json_parse(bytes, GOLEM_DOCUMENT_MAX_JSON, &given);
    if (st == GOLEM_OK && !dw_digest(given, "qa_receipt", &key))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = golem_execution_bundle_inspect(s, &key, &reply, NULL);
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){reply.data, reply.size}, GOLEM_DOCUMENT_MAX_JSON,
                              &expected);
    if (st == GOLEM_OK && !json_object_equal(given, expected))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    golem_execution_reply_free(&reply);
    json_object_put(given);
    json_object_put(expected);
    return dw_report(d, st, NULL);
}
