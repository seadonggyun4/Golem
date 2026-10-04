#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include "golem/system_error.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

golem_status dw_record_scan(int directory, unsigned limit, bool require_nonempty,
                            unsigned *out)
{
    if (directory < 0 || !limit || limit > 99999999 || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = openat(directory, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0)
        return golem_system_error_note(GOLEM_ERR_IO, "record.scan", "openat", errno);
    DIR *dir = fdopendir(fd);
    if (!dir) {
        (void)golem_system_error_note(GOLEM_ERR_IO, "record.scan", "fdopendir", errno);
        close(fd);
        return GOLEM_ERR_IO;
    }
    unsigned count = 0, maximum = 0;
    golem_status st = GOLEM_OK;
    for (;;) {
        errno = 0;
        struct dirent *item = readdir(dir);
        if (!item) {
            if (errno)
                st = golem_system_error_note(GOLEM_ERR_IO, "record.scan", "readdir", errno);
            break;
        }
        const char *name = item->d_name;
        if (!strcmp(name, ".") || !strcmp(name, "..") || !strncmp(name, ".pending-", 9))
            continue;
        unsigned sequence = 0;
        if (strlen(name) != 12 || strcmp(name + 8, ".evt")) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        for (unsigned i = 0; i < 8; ++i) {
            if (name[i] < '0' || name[i] > '9') {
                st = GOLEM_ERR_CORRUPT_JOURNAL;
                break;
            }
            sequence = sequence * 10 + (unsigned)(name[i] - '0');
        }
        if (st != GOLEM_OK || !sequence || sequence > limit) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        ++count;
        if (sequence > maximum) maximum = sequence;
    }
    if (closedir(dir) < 0 && st == GOLEM_OK)
        st = golem_system_error_note(GOLEM_ERR_IO, "record.scan", "closedir", errno);
    if (st == GOLEM_OK && ((require_nonempty && !count) || count != maximum))
        st = GOLEM_ERR_MISSING_RECORD;
    if (st == GOLEM_OK) *out = count;
    return st;
}

golem_status dw_record_read(golem_document_store *s, int directory, bool agent,
                            uint64_t sequence, const golem_digest *previous,
                            golem_digest *payload, golem_digest *frame,
                            struct json_object **event)
{
    if (!s || directory < 0 || !sequence || sequence > 99999999 ||
        !previous || !payload || !frame || !event)
        return GOLEM_ERR_INVALID_ARGUMENT;
    char name[32];
    (void)snprintf(name, sizeof(name), "%08u.evt", (unsigned)sequence);
    uint8_t *bytes = NULL, expected[DW_FRAME];
    size_t size = 0;
    golem_digest key, digest;
    struct json_object *value = NULL;
    golem_status st = dw_read_at(directory, name, DW_FRAME, &bytes, &size);
    if (st == GOLEM_OK && size != DW_FRAME) st = GOLEM_ERR_CORRUPT_JOURNAL;
    if (st == GOLEM_OK) {
        memcpy(key.bytes, bytes + 48, 32);
        dw_record_frame(expected, agent, sequence, previous, &key);
        if (memcmp(bytes, expected, DW_FRAME)) st = GOLEM_ERR_CORRUPT_JOURNAL;
    }
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){bytes, size}, &digest);
    if (st == GOLEM_OK) st = dw_cas_json(s, &key, &value);
    free(bytes);
    if (st == GOLEM_OK) {
        *payload = key;
        *frame = digest;
        *event = value;
    } else {
        json_object_put(value);
    }
    return st;
}
