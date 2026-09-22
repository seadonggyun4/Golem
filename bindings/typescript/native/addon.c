#include <node_api.h>
#include "golem/binding.h"

static napi_value fail(napi_env env, const char *message)
{
    (void)napi_throw_type_error(env, "ERR_GOLEM_ARGUMENT", message); return NULL;
}
static napi_value call(napi_env env, napi_callback_info info)
{
    size_t argc = 3; napi_value args[3];
    if (napi_get_cb_info(env, info, &argc, args, NULL, NULL) != napi_ok || argc != 2)
        return fail(env, "call requires an operation and a Uint8Array");
    double op;
    if (napi_get_value_double(env, args[0], &op) != napi_ok ||
        (op != GOLEM_BINDING_VALIDATE && op != GOLEM_BINDING_REPLAY)) return fail(env, "invalid operation");
    bool typed = false;
    if (napi_is_typedarray(env, args[1], &typed) != napi_ok || !typed) return fail(env, "expected Uint8Array");
    napi_typedarray_type type; size_t size, offset; void *data; napi_value backing;
    if (napi_get_typedarray_info(env, args[1], &type, &size, &data, &backing, &offset) != napi_ok ||
        type != napi_uint8_array) return fail(env, "expected Uint8Array");
    bool ordinary = false, detached = false;
    if (napi_is_arraybuffer(env, backing, &ordinary) != napi_ok || !ordinary ||
        napi_is_detached_arraybuffer(env, backing, &detached) != napi_ok || detached)
        return fail(env, "shared or detached buffers are not supported");
    char *result = NULL; size_t result_size = 0;
    int32_t status = golem_binding_call((uint32_t)op, data, size, &result, &result_size);
    if (status != 0) {
        napi_value message, error, code;
        if (napi_create_string_utf8(env, golem_binding_status_message(status), NAPI_AUTO_LENGTH, &message) != napi_ok ||
            napi_create_error(env, NULL, message, &error) != napi_ok ||
            napi_create_int32(env, status, &code) != napi_ok ||
            napi_set_named_property(env, error, "golemStatus", code) != napi_ok) return fail(env, "cannot construct native error");
        (void)napi_throw(env, error); return NULL;
    }
    napi_value text;
    napi_status s = napi_create_string_utf8(env, result, result_size, &text);
    golem_binding_free(result);
    if (s != napi_ok) return fail(env, "cannot construct native result");
    return text;
}
NAPI_MODULE_INIT()
{
    napi_value function, version;
    if (napi_create_function(env, "call", NAPI_AUTO_LENGTH, call, NULL, &function) != napi_ok ||
        napi_set_named_property(env, exports, "call", function) != napi_ok ||
        napi_create_uint32(env, golem_binding_abi_version(), &version) != napi_ok ||
        napi_set_named_property(env, exports, "abiVersion", version) != napi_ok)
        return fail(env, "cannot initialize Golem addon");
    return exports;
}
