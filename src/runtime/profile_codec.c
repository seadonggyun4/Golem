#include "profile_internal.h"
#include <stdlib.h>
#include <string.h>

static int compare_keys(const void *a, const void *b)
{
    return strcmp(*(const char *const *)a, *(const char *const *)b);
}

/* Schema-v1 canonical form: sorted ASCII object keys; array order preserved;
 * integer/string scalars only. Deliberately not a claim of general RFC 8785 JCS.
 * Only called after bounded schema validation. Existing digest codecs untouched. */
golem_status rp_canonical(struct json_object *object, struct json_object **out)
{
    struct json_object *copy = NULL;
    golem_status status = GOLEM_OK;
    if (json_object_is_type(object, json_type_object)) {
        const char *keys[32];
        size_t count = 0;
        json_object_object_foreach(object, key, value)
        {
            (void)value;
            if (count == sizeof(keys) / sizeof(*keys))
                return GOLEM_ERR_BUDGET_EXHAUSTED;
            keys[count++] = key;
        }
        qsort(keys, count, sizeof(*keys), compare_keys);
        copy = json_object_new_object();
        for (size_t i = 0; status == GOLEM_OK && i < count; ++i) {
            struct json_object *child = NULL;
            status = rp_canonical(dw_get(object, keys[i]), &child);
            if (status == GOLEM_OK && !dw_add(copy, keys[i], child))
                status = GOLEM_ERR_OUT_OF_MEMORY;
        }
    } else if (json_object_is_type(object, json_type_array)) {
        copy = json_object_new_array();
        for (size_t i = 0; status == GOLEM_OK && i < json_object_array_length(object); ++i) {
            struct json_object *child = NULL;
            status = rp_canonical(json_object_array_get_idx(object, i), &child);
            if (status == GOLEM_OK && (!copy || json_object_array_add(copy, child) != 0)) {
                json_object_put(child);
                status = GOLEM_ERR_OUT_OF_MEMORY;
            }
        }
    } else if (json_object_is_type(object, json_type_string))
        copy = json_object_new_string_len(json_object_get_string(object),
                                          json_object_get_string_len(object));
    else if (json_object_is_type(object, json_type_int))
        copy = json_object_new_uint64(json_object_get_uint64(object));
    else
        status = GOLEM_ERR_PARSE;
    if (status == GOLEM_OK && !copy)
        status = GOLEM_ERR_OUT_OF_MEMORY;
    if (status == GOLEM_OK)
        *out = copy;
    else
        json_object_put(copy);
    return status;
}
