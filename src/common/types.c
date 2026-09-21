#include "golem/types.h"

golem_status golem_bytes_init(golem_bytes *out, const void *data, size_t size)
{
    if (out == NULL || (data == NULL && size != 0)) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    out->data = data;
    out->size = size;
    return GOLEM_OK;
}
