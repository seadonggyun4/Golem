#include "golem/gateway.h"
#include "test.h"
#include <string.h>

static const uint8_t golden[] = {0x86, 0, 1, 1, 1, 4, 0xaa,
    'l','o','c','a','l','.','n','o','o','p', 14, 63, 15, 1, 16, 0xc3};
static golem_adapter_envelope sample(golem_adapter_message type)
{
    golem_adapter_envelope e = {0}; e.type = type;
    if (type == GOLEM_ADAPTER_CAPABILITY) {
        e.data.capability = (golem_adapter_capability){1, "local.noop", 63, GOLEM_EFFECT_LOCAL, true};
    } else {
        golem_adapter_request r = {0}; r.version = 1;
        strcpy(r.request_id, "request"); strcpy(r.run_id, "run"); strcpy(r.adapter_id, "local.noop");
        r.stage = GOLEM_STAGE_PLANNING; r.sequence = 1; r.attempt = 1;
        r.context.version = GOLEM_RECEIPT_VERSION; r.context.algorithm = GOLEM_DIGEST_SHA256;
        r.context.size = 3; r.context.digest.bytes[0] = 0xab;
        if (type == GOLEM_ADAPTER_RUN_STAGE) e.data.request = r;
        else {
            e.data.result.request = r; e.data.result.outcome = GOLEM_STAGE_PASSED;
            e.data.result.simulation = true; e.data.result.evidence = r.context;
            e.data.result.usage.usage_known = true; e.data.result.usage.cost_known = true;
        }
    }
    return e;
}
static int equivalent(const golem_adapter_envelope *a, const golem_adapter_envelope *b)
{
    char first[GOLEM_ADAPTER_JSON_MAX], second[GOLEM_ADAPTER_JSON_MAX]; size_t n, m;
    CHECK(golem_adapter_envelope_encode(a, first, sizeof(first), &n, NULL) == GOLEM_OK);
    CHECK(golem_adapter_envelope_encode(b, second, sizeof(second), &m, NULL) == GOLEM_OK);
    CHECK(n == m && memcmp(first, second, n) == 0); return 0;
}
static int roundtrip(void)
{
    for (int type = 1; type <= 3; ++type) {
        golem_adapter_envelope e = sample((golem_adapter_message)type), decoded, from_json;
        uint8_t mp[GOLEM_ADAPTER_MSGPACK_MAX], again[GOLEM_ADAPTER_MSGPACK_MAX];
        char json[GOLEM_ADAPTER_JSON_MAX]; size_t n, m, j;
        CHECK(golem_adapter_msgpack_encode(&e, mp, sizeof(mp), &n, NULL) == GOLEM_OK);
        CHECK(golem_adapter_msgpack_decode((golem_bytes){mp, n}, &decoded, NULL) == GOLEM_OK);
        CHECK(equivalent(&e, &decoded) == 0);
        CHECK(golem_adapter_envelope_encode(&decoded, json, sizeof(json), &j, NULL) == GOLEM_OK);
        CHECK(n < j / 2);
        CHECK(golem_adapter_envelope_decode((golem_bytes){(const uint8_t *)json, j - 1}, &from_json, NULL) == GOLEM_OK);
        CHECK(golem_adapter_msgpack_encode(&from_json, again, sizeof(again), &m, NULL) == GOLEM_OK);
        CHECK(n == m && memcmp(mp, again, n) == 0);
        if (type == 1) CHECK(n == sizeof(golden) && memcmp(mp, golden, n) == 0);
        printf("type=%d JSON=%zu MessagePack=%zu\n", type, j - 1, n);
        memset(mp, 0, sizeof(mp)); CHECK(equivalent(&e, &decoded) == 0);
    }
    return 0;
}
static int limits(void)
{
    static const uint64_t values[] = {1, 127, 128, 255, 256, 65535, 65536, UINT32_MAX, UINT64_C(4294967296), UINT64_MAX};
    for (size_t i = 0; i < sizeof(values) / sizeof(values[0]); ++i) {
        golem_adapter_envelope e = sample(GOLEM_ADAPTER_STAGE_RESULT), decoded;
        e.data.result.request.sequence = values[i]; e.data.result.request.attempt = UINT32_MAX;
        e.data.result.request.context.size = values[i]; e.data.result.evidence.size = values[i];
        e.data.result.request.has_predecessor = true; e.data.result.request.predecessor.bytes[31] = 0xff;
        e.data.result.usage.nano_cost = values[i];
        e.data.result.usage.usage = (golem_token_usage){values[i], values[i], values[i], values[i], values[i]};
        memset(e.data.result.request.run_id, 'x', GOLEM_ADAPTER_ID_CAPACITY - 1);
        uint8_t data[GOLEM_ADAPTER_MSGPACK_MAX]; size_t n;
        CHECK(golem_adapter_msgpack_encode(&e, data, sizeof(data), &n, NULL) == GOLEM_OK);
        CHECK(golem_adapter_msgpack_decode((golem_bytes){data, n}, &decoded, NULL) == GOLEM_OK);
        CHECK(equivalent(&e, &decoded) == 0);
        e.data.result.request.sequence = 0;
        CHECK(golem_adapter_msgpack_encode(&e, data, sizeof(data), &n, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    }
    return 0;
}
static int buffers(void)
{
    golem_adapter_envelope e = sample(GOLEM_ADAPTER_CAPABILITY), out;
    size_t n = 999; uint8_t data[128]; memset(data, 0xa5, sizeof(data));
    CHECK(golem_adapter_msgpack_encode(&e, NULL, 0, &n, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL && n == sizeof(golden));
    for (size_t capacity = 0; capacity < n; ++capacity) {
        CHECK(golem_adapter_msgpack_encode(&e, data, capacity, &n, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
        for (size_t i = 0; i < sizeof(data); ++i) CHECK(data[i] == 0xa5);
    }
    CHECK(golem_adapter_msgpack_encode(&e, data, n, &n, NULL) == GOLEM_OK && data[n] == 0xa5);
    CHECK(golem_adapter_msgpack_decode((golem_bytes){data, n}, &out, NULL) == GOLEM_OK);
    n = 999;
    CHECK(golem_adapter_msgpack_encode(NULL, data, sizeof(data), &n, NULL) == GOLEM_ERR_INVALID_ARGUMENT && n == 999);
    CHECK(golem_adapter_msgpack_encode(&e, NULL, 1, &n, NULL) == GOLEM_ERR_INVALID_ARGUMENT && n == 999);
    CHECK(golem_adapter_msgpack_encode(&e, data, sizeof(data), NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_adapter_msgpack_decode((golem_bytes){NULL, 1}, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_adapter_msgpack_decode((golem_bytes){golden, sizeof(golden)}, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
static int rejected(const uint8_t *data, size_t size)
{
    golem_adapter_envelope e = sample(GOLEM_ADAPTER_CAPABILITY), before = e;
    golem_diagnostic d;
    CHECK(golem_adapter_msgpack_decode((golem_bytes){data, size}, &e, &d) != GOLEM_OK);
    CHECK(d.status != GOLEM_OK && equivalent(&e, &before) == 0); return 0;
}
static int malformed(void)
{
    for (size_t i = 0; i < sizeof(golden); ++i) CHECK(rejected(golden, i) == 0);
    uint8_t b[GOLEM_ADAPTER_MSGPACK_MAX + 1];
    for (int type = 1; type <= 3; ++type) {
        golem_adapter_envelope e = sample((golem_adapter_message)type); size_t n;
        CHECK(golem_adapter_msgpack_encode(&e, b, sizeof(b), &n, NULL) == GOLEM_OK);
        for (size_t cut = 0; cut < n; ++cut) CHECK(rejected(b, cut) == 0);
    }
    CHECK(rejected(b, sizeof(b)) == 0);
    memcpy(b, golden, sizeof(golden)); b[sizeof(golden)] = 0;
    CHECK(rejected(b, sizeof(golden) + 1) == 0);
    memcpy(b, golden, sizeof(golden)); b[3] = 0; CHECK(rejected(b, sizeof(golden)) == 0);
    memcpy(b, golden, sizeof(golden)); b[3] = 31; CHECK(rejected(b, sizeof(golden)) == 0);
    memcpy(b, golden, sizeof(golden)); b[sizeof(golden) - 1] = 1; CHECK(rejected(b, sizeof(golden)) == 0);
    memcpy(b, golden, sizeof(golden)); b[7] = 0; CHECK(rejected(b, sizeof(golden)) == 0);
    memcpy(b, golden, sizeof(golden)); b[7] = 0xff; CHECK(rejected(b, sizeof(golden)) == 0);
    memcpy(b, golden, sizeof(golden)); b[0] = 0x87; b[sizeof(golden)] = 28; b[sizeof(golden) + 1] = 0;
    CHECK(rejected(b, sizeof(golden) + 2) == 0);
    const uint8_t bad[][10] = {
        {0xdf,0xff,0xff,0xff,0xff}, {0x81,0,0xcf}, {0x81,0,0xd0,1},
        {0x81,4,0xdb,0xff,0xff,0xff,0xff}, {0x81,11,0xc6,0xff,0xff,0xff,0xff},
        {0x81,0,0x91,1}, {0x81,0,0x81,0,1}, {0x81,0,0xca}, {0x81,0,0xc7}, {0x81,0,0xc0}
    };
    for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) CHECK(rejected(bad[i], sizeof(bad[i])) == 0);
    memcpy(b, golden, sizeof(golden)); b[4] = 2;
    golem_adapter_envelope out;
    CHECK(golem_adapter_msgpack_decode((golem_bytes){b, sizeof(golden)}, &out, NULL) == GOLEM_ERR_UNSUPPORTED_VERSION);
    return 0;
}
static int wide(void)
{
    /* Independently specified nonminimal map32, uint16 key, uint64 number,
     * str32 length and reordered members. Ordinary MessagePack encoders may
     * choose these widths; values still must have the right semantic type. */
    const uint8_t data[] = {0xdf,0,0,0,6, 16,0xc3, 15,1, 14,63,
        4,0xdb,0,0,0,10,'l','o','c','a','l','.','n','o','o','p',
        1,1, 0xcd,0,0, 0xcf,0,0,0,0,0,0,0,1};
    golem_adapter_envelope out, e = sample(GOLEM_ADAPTER_CAPABILITY);
    CHECK(golem_adapter_msgpack_decode((golem_bytes){data, sizeof(data)}, &out, NULL) == GOLEM_OK);
    CHECK(equivalent(&e, &out) == 0); return 0;
}
static int gateway(void)
{
    for (int encoding = GOLEM_ENCODING_JSON; encoding <= GOLEM_ENCODING_MSGPACK; ++encoding) {
        golem_adapter_envelope e = sample(GOLEM_ADAPTER_RUN_STAGE), out;
        uint8_t bytes[GOLEM_ADAPTER_JSON_MAX]; size_t n;
        if (encoding == GOLEM_ENCODING_JSON) {
            CHECK(golem_adapter_envelope_encode(&e, (char *)bytes, sizeof(bytes), &n, NULL) == GOLEM_OK); --n;
        } else CHECK(golem_adapter_msgpack_encode(&e, bytes, sizeof(bytes), &n, NULL) == GOLEM_OK);
        golem_gateway_envelope wrapper;
        CHECK(golem_gateway_envelope_prepare((golem_envelope_encoding)encoding, (golem_bytes){bytes, n}, &wrapper, NULL) == GOLEM_OK);
        CHECK(wrapper.payload.data == bytes && wrapper.payload.size == n && wrapper.signature_scheme == GOLEM_SIGNATURE_NONE);
        CHECK(golem_gateway_envelope_decode(&wrapper, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, &out, NULL) == GOLEM_OK && equivalent(&e, &out) == 0);
        CHECK(golem_gateway_envelope_decode(&wrapper, GOLEM_GATEWAY_REQUIRE_SIGNATURE, &out, NULL) == GOLEM_ERR_POLICY_DENIED);
        CHECK(golem_gateway_envelope_decode(&wrapper, (golem_gateway_trust)99, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(equivalent(&e, &out) == 0);
        golem_gateway_envelope forged = wrapper; forged.signature_scheme = GOLEM_SIGNATURE_ED25519_RESERVED;
        CHECK(golem_gateway_envelope_decode(&forged, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, &out, NULL) == GOLEM_ERR_POLICY_DENIED);
        forged = wrapper; forged.key_id[95] = 'x';
        CHECK(golem_gateway_envelope_decode(&forged, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, &out, NULL) == GOLEM_ERR_POLICY_DENIED);
        forged = wrapper; forged.signature = (golem_bytes){bytes, n};
        CHECK(golem_gateway_envelope_decode(&forged, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, &out, NULL) == GOLEM_ERR_POLICY_DENIED);
        forged = wrapper; forged.version = 2;
        CHECK(golem_gateway_envelope_decode(&forged, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, &out, NULL) == GOLEM_ERR_UNSUPPORTED_VERSION);
        forged = wrapper; forged.encoding = (golem_envelope_encoding)99;
        CHECK(golem_gateway_envelope_decode(&forged, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
        bytes[n - 1] ^= 1;
        CHECK(golem_gateway_envelope_decode(&wrapper, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, &out, NULL) == GOLEM_ERR_DIGEST_MISMATCH);
        CHECK(equivalent(&e, &out) == 0); bytes[n - 1] ^= 1;
        wrapper.version = 99;
        CHECK(golem_gateway_envelope_prepare((golem_envelope_encoding)99, (golem_bytes){bytes,n}, &wrapper, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(wrapper.version == 99);
        CHECK(golem_gateway_envelope_prepare((golem_envelope_encoding)encoding, (golem_bytes){NULL,n}, &wrapper, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_gateway_envelope_decode(NULL, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_gateway_envelope_decode(&wrapper, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    }
    return 0;
}
static int mutations(void)
{
    uint32_t random = 0x6a09e667u;
    for (int type = 1; type <= 3; ++type) {
        golem_adapter_envelope e = sample((golem_adapter_message)type);
        uint8_t seed[GOLEM_ADAPTER_MSGPACK_MAX], data[GOLEM_ADAPTER_MSGPACK_MAX]; size_t length;
        CHECK(golem_adapter_msgpack_encode(&e, seed, sizeof(seed), &length, NULL) == GOLEM_OK);
        for (size_t i = 0; i < 10000; ++i) {
            memcpy(data, seed, length); random = random * 1664525u + 1013904223u;
            size_t n = i % 4 == 0 ? random % length : length;
            for (size_t j = 0; j <= i % 4 && n != 0; ++j) {
                random = random * 1664525u + 1013904223u; data[random % n] = (uint8_t)(random >> 24);
            }
            golem_adapter_envelope decoded, again;
            if (golem_adapter_msgpack_decode((golem_bytes){data, n}, &decoded, NULL) == GOLEM_OK) {
                CHECK(golem_adapter_msgpack_encode(&decoded, data, sizeof(data), &n, NULL) == GOLEM_OK);
                CHECK(golem_adapter_msgpack_decode((golem_bytes){data, n}, &again, NULL) == GOLEM_OK);
                CHECK(equivalent(&decoded, &again) == 0);
            }
        }
    }
    return 0;
}
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    if (strcmp(argv[1], "roundtrip") == 0) return roundtrip();
    if (strcmp(argv[1], "limits") == 0) return limits();
    if (strcmp(argv[1], "buffers") == 0) return buffers();
    if (strcmp(argv[1], "malformed") == 0) return malformed();
    if (strcmp(argv[1], "wide") == 0) return wide();
    if (strcmp(argv[1], "gateway") == 0) return gateway();
    if (strcmp(argv[1], "mutations") == 0) return mutations();
    return EXIT_FAILURE;
}
