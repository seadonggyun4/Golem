#include "proof_internal.h"
#include "../research/bundle_internal.h"
#include <stdlib.h>
#include <string.h>

const char *const proof_names[PROOF_FILES] = {"summary.md",    "proof.md",
                                              "comparison.md", "evidence-inventory.json",
                                              "manifest.json", "COMMIT.json"};

static golem_bytes file_bytes(struct json_object *files, size_t i)
{
    struct json_object *value = dw_get(files, proof_names[i]);
    return (golem_bytes){(const uint8_t *)json_object_get_string(value),
                         (size_t)json_object_get_string_len(value)};
}

/* Fixed insertion order is part of renderer v1, not a general JSON
 * canonicalization algorithm. All generated file bytes end with LF. */
static bool json_file(struct json_object *files, const char *name, struct json_object *value)
{
    const char *wire = json_object_to_json_string_ext(value, JSON_C_TO_STRING_PLAIN);
    if (!wire)
        return false;
    size_t n = strlen(wire);
    char *line = malloc(n + 2);
    if (!line)
        return false;
    memcpy(line, wire, n);
    line[n] = '\n';
    line[n + 1] = 0;
    bool ok = ex_text(files, name, line);
    free(line);
    return ok;
}

golem_status proof_seal(struct json_object *files, struct json_object *policy,
                        struct json_object **out)
{
    struct json_object *manifest = json_object_new_object();
    struct json_object *items = json_object_new_array();
    struct json_object *commit = json_object_new_object();
    struct json_object *pack = json_object_new_object();
    golem_status st = GOLEM_OK;
    if (!manifest || !items || !commit || !pack)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < PROOF_PAYLOADS; ++i) {
        golem_digest digest;
        golem_bytes b = file_bytes(files, i);
        st = golem_digest_bytes(b, &digest);
        struct json_object *entry = json_object_new_object();
        if (st == GOLEM_OK &&
            (!ex_text(entry, "name", proof_names[i]) || !ex_uint(entry, "size", b.size) ||
             !dw_add_digest(entry, "sha256", &digest)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && json_object_array_add(items, entry) == 0)
            entry = NULL;
        else if (st == GOLEM_OK)
            st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(entry);
    }
    if (st == GOLEM_OK &&
        (!ex_uint(manifest, "schema_version", 1) || !ex_uint(manifest, "renderer_version", 1) ||
         !ex_text(manifest, "format", "golem.proof-pack.v1") ||
         !ex_text(manifest, "privacy", "PRIVATE_REVIEW_REQUIRED") ||
         !ex_text(manifest, "time_basis", "RECEIPT_MONOTONIC_NO_WALL_CLOCK") ||
         !dw_add(manifest, "redaction", json_object_get(policy)) ||
         !dw_add(manifest, "raw_evidence_included", json_object_new_boolean(false)) ||
         !dw_add(manifest, "acceptance_verified", json_object_new_boolean(false)) ||
         !dw_add(manifest, "public_export_approved", json_object_new_boolean(false)) ||
         !dw_add(manifest, "files", json_object_get(items)) ||
         !json_file(files, "manifest.json", manifest)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_digest digest;
    if (st == GOLEM_OK)
        st = golem_digest_bytes(file_bytes(files, 4), &digest);
    if (st == GOLEM_OK &&
        (!ex_uint(commit, "schema_version", 1) ||
         !ex_text(commit, "format", "golem.proof-commit.v1") ||
         !dw_add_digest(commit, "manifest_sha256", &digest) ||
         !json_file(files, "COMMIT.json", commit) || !ex_uint(pack, "schema_version", 1) ||
         !dw_add(pack, "files", json_object_get(files))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(manifest);
    json_object_put(items);
    json_object_put(commit);
    if (st == GOLEM_OK)
        *out = pack;
    else
        json_object_put(pack);
    return st;
}

golem_status proof_parse(golem_bytes bytes, const golem_digest *expected, struct json_object **out,
                         golem_digest *digest)
{
    struct json_object *pack = NULL, *manifest = NULL, *policy = NULL, *sealed = NULL;
    const char *keys[] = {"schema_version", "files"};
    golem_status st = golem_json_parse(bytes, GOLEM_DOCUMENT_MAX_JSON, &pack);
    struct json_object *files = dw_get(pack, "files");
    if (st == GOLEM_OK && (!dw_keys(pack, keys, 2) || dw_uint(pack, "schema_version") != 1 ||
                           !dw_keys(files, proof_names, PROOF_FILES)))
        st = GOLEM_ERR_PARSE;
    for (size_t i = 0; st == GOLEM_OK && i < PROOF_FILES; ++i) {
        struct json_object *v = dw_get(files, proof_names[i]);
        if (!json_object_is_type(v, json_type_string) ||
            strlen(json_object_get_string(v)) != (size_t)json_object_get_string_len(v))
            st = GOLEM_ERR_PARSE;
    }
    if (st == GOLEM_OK)
        st = golem_json_parse(file_bytes(files, 4), GOLEM_DOCUMENT_MAX_JSON, &manifest);
    if (st == GOLEM_OK) {
        const char *p =
            json_object_to_json_string_ext(dw_get(manifest, "redaction"), JSON_C_TO_STRING_PLAIN);
        st = p ? rb_policy((golem_bytes){(const uint8_t *)p, strlen(p)}, &policy) : GOLEM_ERR_PARSE;
    }
    /* Rebuilding the envelope validates every inventory entry, fixed flag,
     * version and commit byte, including unknown fields. It does not authenticate
     * payload facts; source verification is a separate operation. */
    struct json_object *copy = json_object_new_object();
    if (!copy && st == GOLEM_OK)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < PROOF_PAYLOADS; ++i)
        if (!dw_add(copy, proof_names[i], json_object_get(dw_get(files, proof_names[i]))))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = proof_seal(copy, policy, &sealed);
    if (st == GOLEM_OK && !json_object_equal(pack, sealed))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    golem_digest actual;
    if (st == GOLEM_OK)
        st = golem_digest_bytes(file_bytes(files, 4), &actual);
    if (st == GOLEM_OK && expected && !dw_equal(expected, &actual))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    json_object_put(copy);
    json_object_put(sealed);
    json_object_put(policy);
    json_object_put(manifest);
    if (st == GOLEM_OK) {
        *out = pack;
        *digest = actual;
    } else
        json_object_put(pack);
    return st;
}

golem_status golem_proof_integrity(golem_bytes bytes, const golem_digest *expected,
                                   golem_diagnostic *d)
{
    struct json_object *pack = NULL;
    golem_digest digest;
    golem_status st = proof_parse(bytes, expected, &pack, &digest);
    json_object_put(pack);
    return dw_report(d, st, NULL);
}
