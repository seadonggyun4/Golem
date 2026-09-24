#include "internal.h"
#include <string.h>

golem_status in_git_entry_parse(golem_bytes record, bool index, in_git_entry *out)
{
    if (!out || !record.data)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (!record.size || record.size > GOLEM_INVENTORY_PATH_MAX + 96 ||
        record.data[record.size - 1] != 0 || memchr(record.data, 0, record.size - 1))
        return GOLEM_ERR_PARSE;
    const uint8_t *tab = memchr(record.data, '\t', record.size - 1);
    if (!tab)
        return GOLEM_ERR_PARSE;
    size_t meta = (size_t)(tab - record.data), start = index ? 7 : 12;
    size_t suffix = index ? 2 : 0;
    if (meta < start + suffix || record.data[6] != ' ')
        return GOLEM_ERR_PARSE;
    in_git_entry parsed = {0};
    memcpy(parsed.mode, record.data, 6);
    if (strcmp(parsed.mode, "100644") && strcmp(parsed.mode, "100755") &&
        strcmp(parsed.mode, "120000") && strcmp(parsed.mode, "160000"))
        return GOLEM_ERR_INCOMPLETE_WORK;
    if (!index) {
        if (!strcmp(parsed.mode, "160000")) {
            start = 14;
            if (meta < start || memcmp(record.data + 7, "commit ", 7))
                return GOLEM_ERR_PARSE;
        } else if (memcmp(record.data + 7, "blob ", 5))
            return GOLEM_ERR_PARSE;
    } else if (record.data[meta - 2] != ' ' || record.data[meta - 1] != '0')
        return GOLEM_ERR_INCOMPLETE_WORK;
    size_t oid_size = meta - start - suffix;
    if (oid_size != 40 && oid_size != 64)
        return GOLEM_ERR_PARSE;
    memcpy(parsed.oid, record.data + start, oid_size);
    if (!ws_oid(parsed.oid))
        return GOLEM_ERR_PARSE;
    size_t path_size = record.size - meta - 2;
    if (!path_size || path_size > GOLEM_INVENTORY_PATH_MAX)
        return GOLEM_ERR_PARSE;
    memcpy(parsed.path, tab + 1, path_size);
    if (!in_path(parsed.path))
        return GOLEM_ERR_INCOMPLETE_WORK;
    *out = parsed;
    return GOLEM_OK;
}
