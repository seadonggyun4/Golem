#include "golem/types.h"
#include <string.h>

golem_status golem_bytes_slice(golem_bytes source, size_t offset, size_t size, golem_bytes *out)
{
    if (out == NULL || (source.data == NULL && source.size != 0) ||
        offset > source.size || size > source.size - offset) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = (golem_bytes){source.data == NULL ? NULL : source.data + offset, size};
    return GOLEM_OK;
}
golem_status golem_bytes_write(golem_bytes source, void *destination,
                                      size_t capacity, size_t *required)
{
    if (required == NULL || (source.data == NULL && source.size != 0) ||
        (destination == NULL && capacity != 0)) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (capacity < source.size) {
        *required = source.size;
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    }
    if (source.size != 0) {
        memmove(destination, source.data, source.size);
    }
    *required = source.size;
    return GOLEM_OK;
}
golem_status golem_string_view_init(golem_string_view *out, const char *data, size_t size)
{
    if (out == NULL || (data == NULL && size != 0)) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = (golem_string_view){data, size};
    return GOLEM_OK;
}
golem_status golem_string_view_from_cstr(const char *text, golem_string_view *out)
{
    if (text == NULL || out == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = (golem_string_view){text, strlen(text)};
    return GOLEM_OK;
}
golem_status golem_string_view_slice(golem_string_view source, size_t offset,
                                            size_t size, golem_string_view *out)
{
    if (out == NULL || (source.data == NULL && source.size != 0) ||
        offset > source.size || size > source.size - offset) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = (golem_string_view){source.data == NULL ? NULL : source.data + offset, size};
    return GOLEM_OK;
}
golem_status golem_string_view_write(golem_string_view source, char *destination,
                                            size_t capacity, size_t *required)
{
    if (required == NULL || (source.data == NULL && source.size != 0) ||
        (destination == NULL && capacity != 0)) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (source.size == SIZE_MAX) {
        return GOLEM_ERR_OVERFLOW;
    }
    size_t needed = source.size + 1;
    if (capacity < needed) {
        *required = needed;
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    }
    if (source.size != 0) {
        memmove(destination, source.data, source.size);
    }
    destination[source.size] = '\0';
    *required = needed;
    return GOLEM_OK;
}
golem_status golem_string_clone(golem_string_view source,
                                       const golem_allocator *allocator, char **out)
{
    if (out == NULL || (source.data == NULL && source.size != 0) ||
        golem_allocator_validate(allocator) != GOLEM_OK) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (source.size == SIZE_MAX) {
        return GOLEM_ERR_OVERFLOW;
    }
    void *memory;
    golem_status status = golem_allocator_alloc(allocator, source.size + 1, &memory);
    if (status != GOLEM_OK) {
        return status;
    }
    char *copy = memory;
    if (source.size != 0) {
        memcpy(copy, source.data, source.size);
    }
    copy[source.size] = '\0';
    *out = copy;
    return GOLEM_OK;
}
