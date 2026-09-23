#include "golem/adapter_protocol.h"
#include "golem/adapter_descriptor.h"
#include "check.h"

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
#ifndef GOLEM_FUZZ_MSGPACK
    golem_adapter_descriptor descriptor, decoded;
    memset(&descriptor, 0xa5, sizeof(descriptor));
    unsigned char descriptor_before[sizeof(descriptor)];
    memcpy(descriptor_before, &descriptor, sizeof(descriptor));
    golem_status descriptor_status = golem_adapter_descriptor_decode((golem_bytes){data, size}, &descriptor);
    if (descriptor_status == GOLEM_OK) {
        char encoded[GOLEM_DESCRIPTOR_MAX_BYTES], again[GOLEM_DESCRIPTOR_MAX_BYTES]; size_t n, m;
        REQUIRE(golem_adapter_descriptor_encode(&descriptor, encoded, sizeof(encoded), &n) == GOLEM_OK);
        REQUIRE(golem_adapter_descriptor_decode((golem_bytes){(uint8_t *)encoded, n}, &decoded) == GOLEM_OK);
        REQUIRE(golem_adapter_descriptor_encode(&decoded, again, sizeof(again), &m) == GOLEM_OK);
        REQUIRE(n == m && !memcmp(encoded, again, n));
    } else REQUIRE(!memcmp(descriptor_before, &descriptor, sizeof(descriptor)));
#endif
    {
        golem_adapter_envelope e, again;
        memset(&e, 0xa5, sizeof(e));
        unsigned char saved[sizeof(e)]; memcpy(saved, &e, sizeof(e));
#ifdef GOLEM_FUZZ_MSGPACK
        golem_status status = golem_adapter_msgpack_decode((golem_bytes){data, size}, &e, NULL);
#else
        golem_status status = golem_adapter_envelope_decode((golem_bytes){data, size}, &e, NULL);
#endif
        if (status != GOLEM_OK) { REQUIRE(memcmp(saved, &e, sizeof(e)) == 0); return 0; }
        char first[GOLEM_ADAPTER_JSON_MAX + 1], second[GOLEM_ADAPTER_JSON_MAX + 1];
        size_t n, m;
        if (golem_adapter_envelope_encode(&e, first, sizeof(first), &n, NULL) != GOLEM_OK ||
            golem_adapter_envelope_decode((golem_bytes){(const uint8_t *)first, n - 1}, &again, NULL) != GOLEM_OK ||
            golem_adapter_envelope_encode(&again, second, sizeof(second), &m, NULL) != GOLEM_OK ||
            n != m || memcmp(first, second, n) != 0) abort();
        uint8_t packed[GOLEM_ADAPTER_MSGPACK_MAX], canonical[GOLEM_ADAPTER_MSGPACK_MAX];
        if (golem_adapter_msgpack_encode(&e, packed, sizeof(packed), &n, NULL) != GOLEM_OK ||
            golem_adapter_msgpack_decode((golem_bytes){packed, n}, &again, NULL) != GOLEM_OK ||
            golem_adapter_msgpack_encode(&again, canonical, sizeof(canonical), &m, NULL) != GOLEM_OK ||
            n != m || memcmp(packed, canonical, n) != 0) abort();
        memset(second, 0xa5, sizeof(second));
        size_t required = 0;
        REQUIRE(golem_adapter_envelope_encode(&e, second, 1, &required, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
        REQUIRE((unsigned char)second[0] == 0xa5 && required > 1);
        REQUIRE(golem_adapter_msgpack_encode(&e, second, 1, &required, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
        REQUIRE((unsigned char)second[0] == 0xa5 && required > 1);
    }
    return 0;
}
