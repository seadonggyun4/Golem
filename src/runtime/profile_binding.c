#include "profile_internal.h"
#include "../workflow/internal.h"
#include <string.h>

static golem_status work_digest(golem_document_store *store, golem_digest *out)
{
    const char *text = json_object_to_json_string_ext(store->spec, JSON_C_TO_STRING_PLAIN);
    return text ? golem_digest_bytes((golem_bytes){(const uint8_t *)text, strlen(text)}, out)
                : GOLEM_ERR_OUT_OF_MEMORY;
}

golem_status rp_claim(golem_document_store *store, struct json_object *claim)
{
    if (!store->runtime_profile_count)
        return GOLEM_OK;
    struct json_object *generation = store->runtime_profiles[store->runtime_profile_count - 1];
    struct json_object *manifest = NULL, *binding = NULL;
    golem_digest input, work, digest, prepared;
    if (!dw_digest(claim, "manifest_digest", &input))
        return GOLEM_ERR_PARSE;
    golem_status status = dw_cas_json(store, &input, &manifest);
    if (status == GOLEM_OK)
        status = work_digest(store, &work);
    if (status == GOLEM_OK)
        status = dw_put_json(store, generation, &prepared);
    if (status == GOLEM_OK) {
        binding = json_object_new_object();
        if (!dw_add(binding, "schema_version", json_object_new_int(1)) ||
            !dw_add(binding, "domain", json_object_new_string("golem.execution-binding.v1")) ||
            !dw_add(binding, "work_id", json_object_get(dw_get(store->spec, "work_id"))) ||
            !dw_add_digest(binding, "work_spec_digest", &work) ||
            !dw_add_digest(binding, "input_manifest_digest", &input) ||
            !dw_add(binding, "selection", json_object_get(dw_get(manifest, "selection"))) ||
            !dw_add(binding, "attempt_id", json_object_get(dw_get(claim, "attempt_id"))) ||
            !dw_add(binding, "session_id", json_object_get(dw_get(claim, "session_id"))) ||
            !dw_add(binding, "claim_epoch", json_object_get(dw_get(claim, "epoch"))) ||
            !dw_add(binding, "runtime_generation",
                    json_object_get(dw_get(generation, "generation"))) ||
            !dw_add_digest(binding, "generation_digest", &prepared) ||
            !dw_add(binding, "profile_digest",
                    json_object_get(dw_get(generation, "profile_digest"))) ||
            !binding || json_object_object_add(binding, "work_run", NULL) != 0)
            status = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (status == GOLEM_OK)
        status = dw_put_json(store, binding, &digest);
    if (status == GOLEM_OK && !dw_add_digest(claim, "runtime_binding", &digest))
        status = GOLEM_ERR_OUT_OF_MEMORY;
    if (status == GOLEM_OK)
        status = rp_validate_claim(store, claim);
    json_object_put(binding);
    json_object_put(manifest);
    return status;
}

golem_status rp_validate_claim(golem_document_store *store, struct json_object *claim)
{
    golem_digest digest, work, expected, input;
    if (!dw_digest(claim, "runtime_binding", &digest))
        return GOLEM_ERR_PARSE;
    struct json_object *binding = NULL, *manifest = NULL, *object = NULL;
    golem_runtime_profile *profile = NULL;
    golem_status status = dw_cas_json(store, &digest, &binding);
    const char *keys[] = {"schema_version",
                          "domain",
                          "work_id",
                          "work_spec_digest",
                          "input_manifest_digest",
                          "selection",
                          "attempt_id",
                          "session_id",
                          "claim_epoch",
                          "runtime_generation",
                          "profile_digest",
                          "work_run",
                          "generation_digest"};
    if (status == GOLEM_OK &&
        (!dw_keys(binding, keys, 13) || dw_uint(binding, "schema_version") != 1 ||
         strcmp(dw_text(binding, "domain"), "golem.execution-binding.v1") ||
         strcmp(dw_text(binding, "work_id"), dw_text(store->spec, "work_id")) ||
         strcmp(dw_text(binding, "attempt_id"), dw_text(claim, "attempt_id")) ||
         strcmp(dw_text(binding, "session_id"), dw_text(claim, "session_id")) ||
         dw_uint(binding, "claim_epoch") != dw_uint(claim, "epoch") ||
         !dw_uint(binding, "runtime_generation") ||
         dw_uint(binding, "runtime_generation") > store->runtime_profile_count ||
         !dw_digest(binding, "work_spec_digest", &expected) ||
         !dw_digest(claim, "manifest_digest", &input) ||
         strcmp(dw_text(binding, "input_manifest_digest"), dw_text(claim, "manifest_digest")) ||
         dw_get(binding, "work_run") != NULL))
        status = GOLEM_ERR_IDENTITY_MISMATCH;
    if (status == GOLEM_OK)
        status = work_digest(store, &work);
    if (status == GOLEM_OK && !dw_equal(&work, &expected))
        status = GOLEM_ERR_IDENTITY_MISMATCH;
    if (status == GOLEM_OK)
        status = dw_cas_json(store, &input, &manifest);
    if (status == GOLEM_OK &&
        (!wf_reference(dw_get(binding, "selection")) ||
         !json_object_equal(dw_get(binding, "selection"), dw_get(manifest, "selection")) ||
         !wf_resolve(store, dw_get(binding, "selection"))))
        status = GOLEM_ERR_IDENTITY_MISMATCH;
    if (status == GOLEM_OK) {
        size_t admitted = 0;
        for (size_t i = 0; i < store->runtime_profile_count; ++i)
            if (dw_uint(store->runtime_profiles[i], "agent_sequence") < dw_uint(claim, "epoch"))
                admitted = i + 1;
        if (dw_uint(binding, "runtime_generation") != admitted)
            status = GOLEM_ERR_IDENTITY_MISMATCH;
    }
    if (status == GOLEM_OK) {
        struct json_object *generation =
            store->runtime_profiles[dw_uint(binding, "runtime_generation") - 1];
        if (strcmp(dw_text(binding, "profile_digest"), dw_text(generation, "profile_digest")) ||
            !dw_digest(binding, "profile_digest", &digest))
            status = GOLEM_ERR_IDENTITY_MISMATCH;
        golem_digest prepared;
        struct json_object *recorded = NULL;
        if (status == GOLEM_OK && !dw_digest(binding, "generation_digest", &prepared))
            status = GOLEM_ERR_PARSE;
        if (status == GOLEM_OK)
            status = dw_cas_json(store, &prepared, &recorded);
        if (status == GOLEM_OK && !json_object_equal(recorded, generation))
            status = GOLEM_ERR_IDENTITY_MISMATCH;
        json_object_put(recorded);
    }
    if (status == GOLEM_OK)
        status = dw_cas_json(store, &digest, &object);
    if (status == GOLEM_OK)
        status = rp_object(object, &store->allocator, &profile);
    if (status == GOLEM_OK && !dw_equal(&profile->digest, &digest))
        status = GOLEM_ERR_DIGEST_MISMATCH;
    if (status == GOLEM_OK)
        status = rp_availability(store, profile);
    golem_runtime_profile_free(profile);
    json_object_put(object);
    json_object_put(binding);
    json_object_put(manifest);
    return status;
}
