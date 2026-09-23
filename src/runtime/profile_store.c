#include "profile_internal.h"
#include "../agent_session/internal.h"
#include <string.h>

golem_status rp_object(struct json_object *object, const golem_allocator *allocator,
                       golem_runtime_profile **out)
{
    const char *text =
        object ? json_object_to_json_string_ext(object, JSON_C_TO_STRING_PLAIN) : NULL;
    if (!text)
        return GOLEM_ERR_PARSE;
    return golem_runtime_profile_parse((golem_bytes){(const uint8_t *)text, strlen(text)},
                                       allocator, out, NULL);
}

static golem_status verify_field(golem_document_store *store, struct json_object *object,
                                 const char *field)
{
    golem_digest digest;
    uint64_t size;
    if (!dw_digest(object, field, &digest))
        return GOLEM_ERR_PARSE;
    golem_status status = golem_evidence_verify(store->cas, &digest, &size, NULL);
    if (status == GOLEM_OK && !strcmp(field, "adapter_descriptor_digest") && size > 16384)
        status = GOLEM_ERR_BUDGET_EXHAUSTED;
    return status;
}

golem_status rp_availability(golem_document_store *store, const golem_runtime_profile *profile)
{
    struct json_object *o = profile->object;
    golem_status status = GOLEM_OK;
    if (*dw_text(o, "observation_digest"))
        status = verify_field(store, o, "observation_digest");
    if (strcmp(dw_text(o, "restore_level"), "LOCAL_ARTIFACTS_AVAILABLE"))
        return status;
    const char *fields[] = {"engine_build_digest", "adapter_executable_digest",
                            "adapter_descriptor_digest", "config_digest", "policy_digest"};
    for (size_t i = 0; status == GOLEM_OK && i < sizeof(fields) / sizeof(*fields); ++i)
        status = verify_field(store, o, fields[i]);
    struct json_object *tools = dw_get(o, "tools");
    for (size_t i = 0; status == GOLEM_OK && i < json_object_array_length(tools); ++i)
        status = verify_field(store, json_object_array_get_idx(tools, i), "digest");
    return status;
}

static struct json_object *profile_event(const golem_digest *profile, const golem_digest *spec,
                                         size_t generation, const char *key,
                                         uint64_t agent_sequence)
{
    struct json_object *event = json_object_new_object();
    if (!dw_add(event, "schema_version", json_object_new_int(1)) ||
        !dw_add(event, "type", json_object_new_string("runtime-profile")) ||
        !dw_add(event, "generation", json_object_new_uint64(generation)) ||
        !dw_add(event, "agent_sequence", json_object_new_uint64(agent_sequence)) ||
        !dw_add(event, "key", json_object_new_string(key)) ||
        !dw_add_digest(event, "profile_digest", profile) ||
        !dw_add_digest(event, "work_spec_digest", spec)) {
        json_object_put(event);
        return NULL;
    }
    return event;
}

static golem_status spec_digest(struct json_object *spec, golem_digest *out)
{
    const char *text = json_object_to_json_string_ext(spec, JSON_C_TO_STRING_PLAIN);
    return text ? golem_digest_bytes((golem_bytes){(const uint8_t *)text, strlen(text)}, out)
                : GOLEM_ERR_OUT_OF_MEMORY;
}

/* V2 Work specs embed the initial profile. Its CAS object is committed BEFORE
 * the Work event, so a crash cannot produce a successfully opened unbound Work. */
golem_status rp_initial(golem_document_store *store, struct json_object *spec, bool publish)
{
    if (dw_uint(spec, "schema_version") == 1)
        return GOLEM_OK;
    golem_runtime_profile *profile = NULL;
    golem_status status = rp_object(dw_get(spec, "runtime_profile"), &store->allocator, &profile);
    if (status == GOLEM_OK)
        status = rp_availability(store, profile);
    golem_digest digest, identity;
    if (status == GOLEM_OK && publish)
        status = dw_put_json(store, profile->object, &digest);
    if (status == GOLEM_OK && !publish) {
        uint64_t size;
        status = golem_evidence_verify(store->cas, &profile->digest, &size, NULL);
    }
    if (status == GOLEM_OK && !publish)
        status = spec_digest(spec, &identity);
    if (status == GOLEM_OK && !publish) {
        struct json_object *event = profile_event(&profile->digest, &identity, 1, "initial", 0);
        if (!event)
            status = GOLEM_ERR_OUT_OF_MEMORY;
        else
            store->runtime_profiles[store->runtime_profile_count++] = event;
    }
    golem_runtime_profile_free(profile);
    return status;
}

golem_status rp_apply(golem_document_store *store, struct json_object *event,
                      const golem_digest *frame)
{
    if (!strcmp(dw_text(store->spec, "permission"), "DENY") ||
        !strcmp(dw_text(store->spec, "permission"), "ASK_ALWAYS"))
        return GOLEM_ERR_POLICY_DENIED;
    const char *keys[] = {
        "schema_version",   "type",          "generation", "key", "profile_digest",
        "work_spec_digest", "agent_sequence"};
    golem_digest digest, spec, expected;
    if (!dw_keys(event, keys, 7) || dw_uint(event, "schema_version") != 1 ||
        dw_uint(event, "agent_sequence") > GOLEM_AGENT_MAX_EVENTS ||
        strcmp(dw_text(event, "type"), "runtime-profile") || !dw_id(dw_text(event, "key")) ||
        !strcmp(dw_text(event, "key"), "initial") ||
        dw_uint(event, "generation") != store->runtime_profile_count + 1 ||
        store->runtime_profile_count >= GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS ||
        !dw_digest(event, "profile_digest", &digest) ||
        !dw_digest(event, "work_spec_digest", &spec))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    for (size_t i = 0; i < store->runtime_profile_count; ++i)
        if (!strcmp(dw_text(event, "key"), dw_text(store->runtime_profiles[i], "key")))
            return GOLEM_ERR_CORRUPT_JOURNAL;
    if (store->runtime_profile_count &&
        dw_uint(event, "agent_sequence") <
            dw_uint(store->runtime_profiles[store->runtime_profile_count - 1], "agent_sequence"))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    golem_status status = spec_digest(store->spec, &expected);
    if (status == GOLEM_OK && !dw_equal(&spec, &expected))
        status = GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *object = NULL;
    golem_runtime_profile *profile = NULL;
    if (status == GOLEM_OK)
        status = dw_cas_json(store, &digest, &object);
    if (status == GOLEM_OK)
        status = rp_object(object, &store->allocator, &profile);
    if (status == GOLEM_OK && !dw_equal(&profile->digest, &digest))
        status = GOLEM_ERR_DIGEST_MISMATCH;
    if (status == GOLEM_OK)
        status = rp_availability(store, profile);
    if (status == GOLEM_OK) {
        store->runtime_profiles[store->runtime_profile_count++] = json_object_get(event);
        store->last = *frame;
        ++store->event_count;
    }
    golem_runtime_profile_free(profile);
    json_object_put(object);
    return status;
}

golem_status golem_runtime_profile_register(golem_document_store *store,
                                            const golem_runtime_profile *profile, const char *key,
                                            golem_digest *out, golem_diagnostic *diagnostic)
{
    if (!store || !profile || !out || !dw_id(key) || !strcmp(key, "initial"))
        return dw_report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (store->poisoned)
        return dw_report(diagnostic, GOLEM_ERR_INVALID_STATE, NULL);
    const char *permission = dw_text(store->spec, "permission");
    if (!store->writable || !strcmp(permission, "DENY"))
        return dw_report(diagnostic, GOLEM_ERR_POLICY_DENIED, NULL);
    if (!strcmp(permission, "ASK_ALWAYS"))
        return dw_report(diagnostic, GOLEM_ERR_APPROVAL_REQUIRED, NULL);
    golem_status status = rp_availability(store, profile);
    if (status != GOLEM_OK)
        return dw_report(diagnostic, status, NULL);
    for (size_t i = 0; i < store->runtime_profile_count; ++i) {
        struct json_object *event = store->runtime_profiles[i];
        if (!strcmp(key, dw_text(event, "key"))) {
            golem_digest prior;
            if (!dw_digest(event, "profile_digest", &prior) || !dw_equal(&prior, &profile->digest))
                return dw_report(diagnostic, GOLEM_ERR_IDENTITY_MISMATCH, NULL);
            *out = prior;
            return dw_report(diagnostic, GOLEM_OK, NULL);
        }
    }
    if (store->runtime_profile_count >= GOLEM_RUNTIME_PROFILE_MAX_GENERATIONS)
        return dw_report(diagnostic, GOLEM_ERR_BUDGET_EXHAUSTED, NULL);
    as_log log = {.directory = -1};
    status = as_load(store, NULL, NULL, &log);
    if (status == GOLEM_OK && !store->runtime_profile_count && as_active(log.state))
        status = GOLEM_ERR_INVALID_STATE;
    uint64_t agent_sequence = log.sequence;
    as_close(&log);
    golem_digest digest, spec, payload, frame;
    if (status == GOLEM_OK)
        status = dw_put_json(store, profile->object, &digest);
    if (status == GOLEM_OK)
        status = spec_digest(store->spec, &spec);
    struct json_object *event =
        status == GOLEM_OK
            ? profile_event(&digest, &spec, store->runtime_profile_count + 1, key, agent_sequence)
            : NULL;
    if (status == GOLEM_OK && !event)
        status = GOLEM_ERR_OUT_OF_MEMORY;
    if (status == GOLEM_OK)
        status = dw_put_json(store, event, &payload);
    if (status == GOLEM_OK)
        status = dw_event_write(store, &payload, &frame);
    if (status == GOLEM_OK) {
        /* All validation/allocation preceded durable publication. */
        store->runtime_profiles[store->runtime_profile_count++] = json_object_get(event);
        store->last = frame;
        ++store->event_count;
        *out = digest;
    }
    if (status == GOLEM_ERR_IO)
        store->poisoned = true;
    json_object_put(event);
    return dw_report(diagnostic, status, NULL);
}

golem_status golem_runtime_profile_current(golem_document_store *store, void *buffer,
                                           size_t capacity, size_t *required)
{
    if (!store || !required || (!buffer && capacity))
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (store->poisoned)
        return GOLEM_ERR_INVALID_STATE;
    if (!store->runtime_profile_count)
        return GOLEM_ERR_NOT_FOUND;
    golem_digest digest;
    if (!dw_digest(store->runtime_profiles[store->runtime_profile_count - 1], "profile_digest",
                   &digest))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    uint8_t *data = NULL;
    size_t size = 0;
    golem_status status = golem_evidence_read(store->cas, &digest, GOLEM_RUNTIME_PROFILE_MAX_BYTES,
                                              &store->allocator, &data, &size, NULL);
    if (status == GOLEM_OK) {
        *required = size;
        if (capacity < size)
            status = GOLEM_ERR_BUFFER_TOO_SMALL;
        else
            memcpy(buffer, data, size);
    }
    dw_scratch_free(store, data);
    return status;
}
