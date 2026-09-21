#include "golem/adapter_protocol.h"
#include <stdlib.h>
#include <string.h>

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    for (int format = 0; format < 2; ++format) {
        golem_adapter_envelope e, again;
        golem_status status = format == 0 ? golem_adapter_envelope_decode((golem_bytes){data, size}, &e, NULL) :
            golem_adapter_msgpack_decode((golem_bytes){data, size}, &e, NULL);
        if (status != GOLEM_OK) continue;
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
    }
    return 0;
}
