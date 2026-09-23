#define _POSIX_C_SOURCE 200809L
#include "descriptor_internal.h"
#include <stdio.h>
#include <string.h>
#include <time.h>

static golem_status now_ns(uint64_t *out)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) || t.tv_sec < 0 ||
        (uint64_t)t.tv_sec > UINT64_MAX / UINT64_C(1000000000))
        return GOLEM_ERR_IO;
    *out = (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
    return GOLEM_OK;
}
golem_status golem_harness_probe(const golem_harness_probe_options *o,
                                 golem_harness_probe_result *out)
{
    if (!o || !out || o->size != sizeof(*o) || o->version != 1 || !o->executable ||
        o->executable[0] != '/' || !o->cwd || o->cwd[0] != '/' || !o->timeout_ns ||
        o->timeout_ns > UINT64_C(30000000000))
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (!o->allow_process)
        return GOLEM_ERR_POLICY_DENIED;
    golem_receipt before, after;
    golem_status s = golem_digest_file(o->executable, &before, NULL);
    if (s != GOLEM_OK)
        return s;
    if (memcmp(&before.digest, &o->expected_executable, sizeof(before.digest)))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    uint64_t start, end;
    s = now_ns(&start);
    if (s != GOLEM_OK)
        return s;
    golem_harness_probe_result result = {0};
    result.executable_digest = before.digest;
    result.process.exit_code = -1;
    char *argv[] = {(char *)o->executable, "--golem-describe", NULL};
    char *env[] = {"LANG=C", "LC_ALL=C", NULL};
    s = golem_supervisor_run_at(o->executable, argv, o->cwd, env, (golem_bytes){NULL, 0},
                                o->timeout_ns, NULL, NULL, &result.process);
    golem_status clock_status = now_ns(&end);
    if (clock_status == GOLEM_OK && end >= start)
        result.duration_ns = end - start;
    else if (s == GOLEM_OK)
        s = GOLEM_ERR_IO;
    golem_status hash_status = golem_digest_bytes(
        (golem_bytes){result.process.output, result.process.output_size}, &result.stdout_digest);
    if (hash_status == GOLEM_OK)
        hash_status = golem_digest_bytes(
            (golem_bytes){result.process.error, result.process.error_size}, &result.stderr_digest);
    if (s == GOLEM_OK)
        s = hash_status;
    golem_status file_status = golem_digest_file(o->executable, &after, NULL);
    if (s == GOLEM_OK)
        s = file_status;
    if (s == GOLEM_OK && memcmp(&before.digest, &after.digest, sizeof(before.digest)))
        s = GOLEM_ERR_IDENTITY_MISMATCH;
    if (s == GOLEM_OK)
        s = golem_adapter_descriptor_decode(
            (golem_bytes){result.process.output, result.process.output_size}, &result.claimed);
    if (s == GOLEM_OK)
        s = golem_adapter_descriptor_digest(&result.claimed, &result.descriptor_digest);
    result.status = s;
    *out = result;
    return s;
}
static bool add(struct json_object *o, const char *key, struct json_object *v)
{
    if (!o || !v || json_object_object_add(o, key, v)) {
        json_object_put(v);
        return false;
    }
    return true;
}
static bool hash(struct json_object *o, const char *key, const golem_digest *d)
{
    char hex[GOLEM_DIGEST_HEX_CAPACITY];
    size_t n;
    return golem_digest_format(d, hex, sizeof(hex), &n) == GOLEM_OK &&
           add(o, key, json_object_new_string(hex));
}
static bool decimal(struct json_object *o, const char *key, uint64_t value)
{
    char text[32];
    (void)snprintf(text, sizeof(text), "%llu", (unsigned long long)value);
    return add(o, key, json_object_new_string(text));
}
golem_status golem_harness_observation_encode(const golem_harness_observation *r, void *buffer,
                                              size_t capacity, size_t *required)
{
    if (!r || !r->epoch || r->expires_ns <= r->observed_ns)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *descriptor = NULL;
    golem_status s = golem_descriptor_object(&r->descriptor, &descriptor);
    if (s != GOLEM_OK)
        return s;
    struct json_object *o = json_object_new_object();
    if (!o) {
        json_object_put(descriptor);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    /* Add ownership-transferred object first so short-circuit failures cannot leak it. */
    bool ok = add(o, "descriptor", descriptor) && hash(o, "binding_digest", &r->binding_digest) &&
              hash(o, "clock_domain", &r->clock_domain) &&
              add(o, "domain", json_object_new_string("golem.harness-observation.v1")) &&
              decimal(o, "epoch", r->epoch) && hash(o, "evidence_digest", &r->evidence_digest) &&
              add(o, "execution_authorized", json_object_new_boolean(false)) &&
              decimal(o, "expires_ns", r->expires_ns) &&
              decimal(o, "observed_ns", r->observed_ns) &&
              hash(o, "profile_digest", &r->profile_digest) &&
              add(o, "schema_version", json_object_new_int(1));
    s = ok ? golem_descriptor_copy_json(o, buffer, capacity, required) : GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(o);
    return s;
}
golem_status golem_harness_probe_encode(const golem_harness_probe_result *r, void *buffer,
                                        size_t capacity, size_t *required)
{
    if (!r || r->process.output_size > GOLEM_SUPERVISOR_OUTPUT_MAX ||
        r->process.error_size > GOLEM_SUPERVISOR_OUTPUT_MAX)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = json_object_new_object();
    char duration[32];
    (void)snprintf(duration, sizeof(duration), "%llu", (unsigned long long)r->duration_ns);
    bool ok = hash(o, "descriptor_digest", &r->descriptor_digest) &&
              add(o, "domain", json_object_new_string("golem.harness-probe.v1")) &&
              add(o, "duration_ns", json_object_new_string(duration)) &&
              hash(o, "executable_digest", &r->executable_digest) &&
              add(o, "execution_authorized", json_object_new_boolean(false)) &&
              add(o, "exit_code", json_object_new_int(r->process.exit_code)) &&
              add(o, "host_capabilities_verified", json_object_new_boolean(false)) &&
              add(o, "schema_version", json_object_new_int(1)) &&
              add(o, "signal", json_object_new_int(r->process.signal_number)) &&
              add(o, "status", json_object_new_string(golem_status_string(r->status))) &&
              hash(o, "stderr_digest", &r->stderr_digest) &&
              hash(o, "stdout_digest", &r->stdout_digest) &&
              add(o, "timed_out", json_object_new_boolean(r->process.timed_out));
    golem_status s =
        ok ? golem_descriptor_copy_json(o, buffer, capacity, required) : GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(o);
    return s;
}
