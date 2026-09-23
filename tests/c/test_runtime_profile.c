#include "golem/runtime_profile.h"
#include "test.h"
#include <json-c/json.h>
#include <string.h>

static const char zero[] = "0000000000000000000000000000000000000000000000000000000000000000";
static struct json_object *fixture(void)
{
    struct json_object *o = json_object_new_object();
    const char *hashes[] = {"engine_build_digest", "adapter_executable_digest",
                            "adapter_descriptor_digest", "config_digest", "policy_digest"};
    json_object_object_add(o, "schema_version", json_object_new_int(1));
    json_object_object_add(o, "domain", json_object_new_string("golem.runtime-profile.v1"));
    json_object_object_add(o, "engine_abi", json_object_new_int(1));
    for (size_t i = 0; i < sizeof(hashes) / sizeof(*hashes); ++i)
        json_object_object_add(o, hashes[i], json_object_new_string(zero));
    json_object_object_add(o, "platform", json_object_new_string("fixture-only"));
    json_object_object_add(o, "provider_reported", json_object_new_string("fixture-provider"));
    json_object_object_add(o, "model_reported", json_object_new_string("fixture-model"));
    json_object_object_add(o, "provider_observed", json_object_new_string(""));
    json_object_object_add(o, "model_observed", json_object_new_string(""));
    json_object_object_add(o, "observation_digest", json_object_new_string(""));
    json_object_object_add(o, "restore_level", json_object_new_string("IDENTITY_ONLY"));
    json_object_object_add(o, "tools", json_object_new_array());
    return o;
}
static golem_bytes encoded(struct json_object *o)
{
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    return (golem_bytes){(const uint8_t *)text, strlen(text)};
}
static int codec(void)
{
    struct json_object *o = fixture(), *reverse = json_object_new_object();
    const char *keys[16];
    size_t count = 0;
    json_object_object_foreach(o, key, value)
    {
        (void)value;
        keys[count++] = key;
    }
    while (count) {
        struct json_object *v = NULL;
        const char *key = keys[--count];
        CHECK(json_object_object_get_ex(o, key, &v));
        CHECK(json_object_object_add(reverse, key, json_object_get(v)) == 0);
    }
    golem_runtime_profile *a = NULL, *b = NULL;
    CHECK(golem_runtime_profile_parse(encoded(o), NULL, &a, NULL) == GOLEM_OK);
    CHECK(golem_runtime_profile_parse(encoded(reverse), NULL, &b, NULL) == GOLEM_OK);
    golem_digest da, db;
    CHECK(golem_runtime_profile_digest(a, &da) == GOLEM_OK);
    CHECK(golem_runtime_profile_digest(b, &db) == GOLEM_OK);
    CHECK(!memcmp(&da, &db, sizeof(da)));
    uint8_t bytes[4096];
    memset(bytes, 0xa5, sizeof(bytes));
    size_t required = 0;
    CHECK(golem_runtime_profile_encode(a, bytes, 1, &required) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(bytes[0] == 0xa5 && required > 1);
    CHECK(golem_runtime_profile_encode(a, bytes, sizeof(bytes), &required) == GOLEM_OK);
    CHECK(golem_digest_bytes((golem_bytes){bytes, required}, &db) == GOLEM_OK);
    CHECK(!memcmp(&da, &db, sizeof(da)));
    CHECK(!memcmp(bytes, "{\"adapter_descriptor_digest\":", 29));
    golem_runtime_profile_free(a);
    golem_runtime_profile_free(b);
    json_object_put(reverse);
    json_object_put(o);
    return 0;
}
static int invalid(void)
{
    const char *fields[] = {"api_key", "token", "environment", "authorization", "password"};
    for (size_t i = 0; i < sizeof(fields) / sizeof(*fields); ++i) {
        struct json_object *o = fixture();
        json_object_object_add(o, fields[i], json_object_new_string("not-a-real-secret"));
        golem_runtime_profile *p = (void *)(uintptr_t)1;
        CHECK(golem_runtime_profile_parse(encoded(o), NULL, &p, NULL) == GOLEM_ERR_PARSE);
        CHECK(p == (void *)(uintptr_t)1);
        json_object_put(o);
    }
    struct json_object *o = fixture();
    golem_runtime_profile *p = NULL;
    json_object_object_add(o, "engine_abi", json_object_new_uint64(UINT64_MAX));
    CHECK(golem_runtime_profile_parse(encoded(o), NULL, &p, NULL) != GOLEM_OK);
    json_object_object_add(o, "engine_abi", json_object_new_boolean(true));
    CHECK(golem_runtime_profile_parse(encoded(o), NULL, &p, NULL) != GOLEM_OK);
    json_object_object_add(o, "engine_abi", json_object_new_int(1));
    json_object_object_add(o, "provider_observed", json_object_new_string("unverified"));
    CHECK(golem_runtime_profile_parse(encoded(o), NULL, &p, NULL) != GOLEM_OK);
    json_object_object_add(o, "schema_version", json_object_new_int(2));
    CHECK(golem_runtime_profile_parse(encoded(o), NULL, &p, NULL) == GOLEM_ERR_UNSUPPORTED_VERSION);
    json_object_put(o);
    const char *bad[] = {"{}", "[]", "{\"x\":1,\"x\":2}", "{\"x\":\"\\u0000\"}",
                         "{\"x\":\"\xff\"}"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i)
        CHECK(golem_runtime_profile_parse((golem_bytes){(const uint8_t *)bad[i], strlen(bad[i])},
                                          NULL, &p, NULL) != GOLEM_OK);
    return 0;
}
typedef struct check_context {
    size_t calls;
    golem_status result;
} check_context;
static golem_status check(void *context, const golem_runtime_profile *profile)
{
    check_context *c = context;
    golem_digest digest;
    ++c->calls;
    return golem_runtime_profile_digest(profile, &digest) == GOLEM_OK ? c->result
                                                                      : GOLEM_ERR_INVALID_STATE;
}
static int cache(void)
{
    golem_runtime_profile_cache *c = NULL;
    CHECK(golem_runtime_profile_cache_create(NULL, &c) == GOLEM_OK);
    struct json_object *o = fixture();
    check_context context = {0, GOLEM_ERR_POLICY_DENIED};
    const golem_runtime_profile *a = NULL, *b = NULL;
    CHECK(golem_runtime_profile_cache_acquire(c, encoded(o), check, &context, &a) ==
          GOLEM_ERR_POLICY_DENIED);
    CHECK(!a && context.calls == 1);
    context.result = GOLEM_OK;
    CHECK(golem_runtime_profile_cache_acquire(c, encoded(o), check, &context, &a) == GOLEM_OK);
    CHECK(golem_runtime_profile_cache_acquire(c, encoded(o), check, &context, &b) == GOLEM_OK);
    CHECK(a == b && context.calls == 3);
    context.result = GOLEM_ERR_POLICY_DENIED;
    CHECK(golem_runtime_profile_cache_acquire(c, encoded(o), check, &context, &b) ==
          GOLEM_ERR_POLICY_DENIED);
    CHECK(context.calls == 4 && a == b);
    CHECK(golem_runtime_profile_cache_close(c) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_runtime_profile_cache_release(c, a) == GOLEM_OK);
    CHECK(golem_runtime_profile_cache_release(c, b) == GOLEM_OK);
    CHECK(golem_runtime_profile_cache_release(c, b) == GOLEM_ERR_INVALID_STATE);
    const golem_runtime_profile *pins[64];
    context.result = GOLEM_OK;
    for (unsigned i = 0; i < 64; ++i) {
        json_object_object_add(o, "engine_abi", json_object_new_int((int)i + 1));
        CHECK(golem_runtime_profile_cache_acquire(c, encoded(o), check, &context, &pins[i]) ==
              GOLEM_OK);
    }
    json_object_object_add(o, "engine_abi", json_object_new_int(65));
    CHECK(golem_runtime_profile_cache_acquire(c, encoded(o), check, &context, &b) ==
          GOLEM_ERR_BUDGET_EXHAUSTED);
    CHECK(golem_runtime_profile_cache_release(c, pins[0]) == GOLEM_OK);
    CHECK(golem_runtime_profile_cache_acquire(c, encoded(o), check, &context, &b) == GOLEM_OK);
    for (size_t i = 1; i < 64; ++i)
        CHECK(golem_runtime_profile_cache_release(c, pins[i]) == GOLEM_OK);
    CHECK(golem_runtime_profile_cache_release(c, b) == GOLEM_OK);
    CHECK(golem_runtime_profile_cache_close(c) == GOLEM_OK);
    json_object_put(o);
    return 0;
}
typedef struct allocation_context {
    size_t live;
    bool fail;
} allocation_context;
static void *allocate(void *ctx, size_t size)
{
    allocation_context *c = ctx;
    if (c->fail)
        return NULL;
    void *p = malloc(size);
    if (p)
        ++c->live;
    return p;
}
static void deallocate(void *ctx, void *p)
{
    allocation_context *c = ctx;
    --c->live;
    free(p);
}
static int ownership(void)
{
    allocation_context context = {0, true};
    golem_allocator allocator = {&context, allocate, deallocate};
    struct json_object *o = fixture();
    golem_runtime_profile *p = NULL;
    CHECK(golem_runtime_profile_parse(encoded(o), &allocator, &p, NULL) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(!p && !context.live);
    context.fail = false;
    CHECK(golem_runtime_profile_parse(encoded(o), &allocator, &p, NULL) == GOLEM_OK);
    json_object_put(o);
    CHECK(context.live == 1);
    golem_runtime_profile_free(p);
    CHECK(context.live == 0);
    golem_runtime_profile_free(NULL);
    return 0;
}
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    if (!strcmp(argv[1], "codec"))
        return codec();
    if (!strcmp(argv[1], "invalid"))
        return invalid();
    if (!strcmp(argv[1], "cache"))
        return cache();
    if (!strcmp(argv[1], "ownership"))
        return ownership();
    return 1;
}
