#define _POSIX_C_SOURCE 200809L
#include "proof_internal.h"
#include "../workspace/internal.h"
#include <dirent.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static golem_status close_directory(int fd, golem_status st)
{
    if (fd >= 0 && close(fd) != 0 && st == GOLEM_OK)
        return GOLEM_ERR_IO;
    return st;
}

static golem_status pack_directory(const char *parent, const golem_digest *digest, bool create,
                                   int *out)
{
    int root = -1, dir = -1;
    char hex[65];
    size_t needed;
    golem_status st = golem_digest_format(digest, hex, sizeof(hex), &needed);
    if (st == GOLEM_OK)
        st = ws_directory(parent, &root);
    if (st == GOLEM_OK)
        st = dw_dir(root, hex, create, &dir);
    st = close_directory(root, st);
    if (st == GOLEM_OK)
        *out = dir;
    else
        (void)close_directory(dir, st);
    return st;
}

/* Interrupted dw_publish may leave an unlinked-authority staging file.
 * Only its exact generated name is ignored; it is never consumed as evidence. */
static bool pending_name(const char *name)
{
    if (strlen(name) != 33 || strncmp(name, ".pending-", 9))
        return false;
    for (size_t i = 9; i < 33; ++i)
        if (!((name[i] >= '0' && name[i] <= '9') || (name[i] >= 'a' && name[i] <= 'f')))
            return false;
    return true;
}

static golem_status exact_inventory(int fd)
{
    int copy = dup(fd);
    if (copy < 0)
        return GOLEM_ERR_IO;
    DIR *dir = fdopendir(copy);
    if (!dir) {
        (void)close(copy);
        return GOLEM_ERR_IO;
    }
    golem_status st = GOLEM_OK;
    size_t visited = 0;
    for (;;) {
        errno = 0;
        struct dirent *entry = readdir(dir);
        if (!entry) {
            if (errno)
                st = GOLEM_ERR_IO;
            break;
        }
        const char *n = entry->d_name;
        if (!strcmp(n, ".") || !strcmp(n, ".."))
            continue;
        if (++visited > 1024) {
            st = GOLEM_ERR_OVERFLOW;
            break;
        }
        bool known = pending_name(n);
        for (size_t i = 0; i < PROOF_FILES; ++i)
            known = known || !strcmp(n, proof_names[i]);
        if (!known) {
            st = GOLEM_ERR_PARSE;
            break;
        }
    }
    if (closedir(dir) != 0 && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    return st;
}

golem_status golem_proof_publish(golem_bytes bytes, const char *parent, golem_digest *out,
                                 golem_diagnostic *d)
{
    if (!parent || !out)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *pack = NULL;
    golem_digest digest;
    int dir = -1;
    golem_status st = proof_parse(bytes, NULL, &pack, &digest);
    if (st == GOLEM_OK)
        st = pack_directory(parent, &digest, true, &dir);
    if (st == GOLEM_OK)
        st = exact_inventory(dir);
    struct json_object *files = dw_get(pack, "files");
    /* Each no-replace publication syncs its file and directory before the next
     * begins. A commit can only follow all payloads and their manifest. */
    for (size_t i = 0; st == GOLEM_OK && i < PROOF_FILES; ++i) {
        struct json_object *v = dw_get(files, proof_names[i]);
        st = dw_publish(dir, proof_names[i],
                        (golem_bytes){(const uint8_t *)json_object_get_string(v),
                                      (size_t)json_object_get_string_len(v)});
    }
    st = close_directory(dir, st);
    json_object_put(pack);
    if (st == GOLEM_OK)
        *out = digest;
    return dw_report(d, st, NULL);
}

golem_status golem_proof_verify_directory(const char *parent, const golem_digest *expected,
                                          golem_diagnostic *d)
{
    if (!parent || !expected)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    int dir = -1;
    golem_status st = pack_directory(parent, expected, false, &dir);
    if (st == GOLEM_OK)
        st = exact_inventory(dir);
    struct json_object *files = json_object_new_object(), *pack = json_object_new_object();
    if (st == GOLEM_OK && (!files || !pack))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    size_t total = 0;
    for (size_t i = 0; st == GOLEM_OK && i < PROOF_FILES; ++i) {
        uint8_t *data = NULL;
        size_t size = 0;
        st = dw_read_at(dir, proof_names[i], GOLEM_DOCUMENT_MAX_JSON - total, &data, &size);
        if (st == GOLEM_OK && memchr(data, 0, size))
            st = GOLEM_ERR_PARSE;
        if (st == GOLEM_OK && !dw_add(files, proof_names[i],
                                      json_object_new_string_len((const char *)data, (int)size)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        total += size;
        free(data);
    }
    if (st == GOLEM_OK &&
        (!ex_uint(pack, "schema_version", 1) || !dw_add(pack, "files", json_object_get(files))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_execution_reply reply = {0};
    if (st == GOLEM_OK)
        st = ex_emit(pack, &reply);
    if (st == GOLEM_OK)
        st = golem_proof_integrity((golem_bytes){reply.data, reply.size}, expected, NULL);
    golem_execution_reply_free(&reply);
    json_object_put(pack);
    json_object_put(files);
    st = close_directory(dir, st);
    return dw_report(d, st, NULL);
}
