#include "internal.h"
#include "golem/gateway.h"
#include <string.h>

static golem_status payload_check(golem_envelope_encoding encoding, golem_bytes payload)
{
    size_t limit;
    switch (encoding) {
    case GOLEM_ENCODING_JSON: limit = GOLEM_ADAPTER_JSON_MAX; break;
    case GOLEM_ENCODING_MSGPACK: limit = GOLEM_ADAPTER_MSGPACK_MAX; break;
    default: return GOLEM_ERR_INVALID_ARGUMENT;
    }
    return payload.data != NULL && payload.size != 0 && payload.size <= limit ? GOLEM_OK : GOLEM_ERR_INVALID_ARGUMENT;
}
static golem_status decode(golem_envelope_encoding encoding, golem_bytes payload,
    golem_adapter_envelope *out, golem_diagnostic *d)
{
    return encoding == GOLEM_ENCODING_JSON ? golem_adapter_envelope_decode(payload, out, d) :
        golem_adapter_msgpack_decode(payload, out, d);
}
golem_status golem_gateway_envelope_prepare(golem_envelope_encoding encoding,
    golem_bytes payload, golem_gateway_envelope *out, golem_diagnostic *d)
{
    if (out == NULL) return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    golem_status s = payload_check(encoding, payload);
    golem_adapter_envelope parsed;
    if (s == GOLEM_OK) s = decode(encoding, payload, &parsed, d);
    golem_gateway_envelope e = {0}; e.version = GOLEM_GATEWAY_VERSION;
    e.encoding = encoding; e.payload = payload;
    if (s == GOLEM_OK) s = golem_digest_bytes(payload, &e.payload_digest);
    if (s == GOLEM_OK) *out = e;
    return golem_adapter_report(d, s);
}
golem_status golem_gateway_envelope_decode(const golem_gateway_envelope *e,
    golem_gateway_trust trust, golem_adapter_envelope *out, golem_diagnostic *d)
{
    if (e == NULL || out == NULL || (trust != GOLEM_GATEWAY_REQUIRE_SIGNATURE && trust != GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL))
        return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    if (e->version != GOLEM_GATEWAY_VERSION) return golem_adapter_report(d, GOLEM_ERR_UNSUPPORTED_VERSION);
    static const char empty_key[GOLEM_ADAPTER_ID_CAPACITY] = {0};
    if (trust == GOLEM_GATEWAY_REQUIRE_SIGNATURE || e->signature_scheme != GOLEM_SIGNATURE_NONE ||
        memcmp(e->key_id, empty_key, sizeof(empty_key)) != 0 || e->signature.size != 0 || e->signature.data != NULL)
        return golem_adapter_report(d, GOLEM_ERR_POLICY_DENIED);
    golem_status s = payload_check(e->encoding, e->payload);
    golem_digest digest;
    if (s == GOLEM_OK) s = golem_digest_bytes(e->payload, &digest);
    if (s == GOLEM_OK && memcmp(&digest, &e->payload_digest, sizeof(digest)) != 0) s = GOLEM_ERR_DIGEST_MISMATCH;
    golem_adapter_envelope parsed;
    if (s == GOLEM_OK) s = decode(e->encoding, e->payload, &parsed, d);
    if (s == GOLEM_OK) *out = parsed;
    return golem_adapter_report(d, s);
}
