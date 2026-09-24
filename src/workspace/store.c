#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

golem_status ws_append(ws_context *ctx, struct json_object *data)
{
    struct json_object *event = json_object_new_object();
    if (!event || !dw_add(event, "schema_version", json_object_new_int(1)) ||
        !dw_add(event, "sequence", json_object_new_int((int)ctx->sequence + 1)) ||
        !dw_add_digest(event, "previous", &ctx->last) ||
        !dw_add(event, "data", json_object_get(data))) {
        json_object_put(event);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_digest digest;
    golem_status st = dw_put_json(ctx->store, event, &digest);
    char name[16], hex[65];
    size_t size;
    (void)snprintf(name, sizeof(name), "%04u", ctx->sequence + 1);
    if (st == GOLEM_OK)
        st = golem_digest_format(&digest, hex, sizeof(hex), &size);
    if (st == GOLEM_OK)
        st = dw_publish(ctx->records, name, (golem_bytes){(uint8_t *)hex, 64});
    if (st == GOLEM_OK) {
        ctx->last = digest;
        ++ctx->sequence;
    } else
        ctx->store->poisoned = true;
    json_object_put(event);
    return st;
}

golem_status ws_load(ws_context *ctx)
{
    int fd = openat(ctx->records, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0)
        return GOLEM_ERR_IO;
    DIR *dir = fdopendir(fd);
    if (!dir) {
        close(fd);
        return GOLEM_ERR_IO;
    }
    unsigned count = 0, max = 0;
    struct dirent *entry;
    golem_status st = GOLEM_OK;
    errno = 0;
    while ((entry = readdir(dir))) {
        const char *name = entry->d_name;
        if (!strcmp(name, ".") || !strcmp(name, "..") || !strncmp(name, ".pending-", 9))
            continue;
        if (strlen(name) != 4 || memcmp(name, "000", 3) || name[3] < '1' || name[3] > '7') {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        unsigned seq = (unsigned)(name[3] - '0');
        ++count;
        if (seq > max)
            max = seq;
    }
    if (errno && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    closedir(dir);
    if (st == GOLEM_OK && count != max)
        st = GOLEM_ERR_MISSING_RECORD;
    for (unsigned i = 1; st == GOLEM_OK && i <= max; ++i) {
        char name[16];
        (void)snprintf(name, sizeof(name), "%04u", i);
        uint8_t *bytes = NULL;
        size_t size = 0;
        struct json_object *event = NULL;
        golem_digest digest, previous;
        st = dw_read_at(ctx->records, name, 64, &bytes, &size);
        if (st == GOLEM_OK)
            st = golem_digest_parse((golem_string_view){(char *)bytes, size}, &digest);
        if (st == GOLEM_OK)
            st = dw_cas_json(ctx->store, &digest, &event);
        const char *keys[] = {"schema_version", "sequence", "previous", "data"};
        if (st == GOLEM_OK && (!dw_keys(event, keys, 4) || dw_uint(event, "schema_version") != 1 ||
            dw_uint(event, "sequence") != i || !dw_digest(event, "previous", &previous) ||
            !dw_equal(&previous, &ctx->last) ||
            !json_object_is_type(dw_get(event, "data"), json_type_object)))
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        if (st == GOLEM_OK) {
            struct json_object *data = dw_get(event, "data");
            if (i == 1)
                ctx->intent = json_object_get(data);
            else if (i == 2)
                ctx->ready = json_object_get(data);
            else if (i == 5) {
                const char *retained[] = {"evidence"};
                golem_digest evidence;
                uint64_t n;
                if (!dw_keys(data, retained, 1) || !dw_digest(data, "evidence", &evidence))
                    st = GOLEM_ERR_CORRUPT_JOURNAL;
                else
                    st = golem_evidence_verify(ctx->store->cas, &evidence, &n, NULL);
            } else if (json_object_object_length(data) != 0)
                st = GOLEM_ERR_CORRUPT_JOURNAL;
            ctx->last = digest;
            ctx->sequence = i;
        }
        json_object_put(event);
        free(bytes);
    }
    return st;
}

static golem_status file_equals(int dir, const char *name, const char *expected)
{
    uint8_t *bytes = NULL;
    size_t size = 0;
    golem_status st = dw_read_at(dir, name, 8192, &bytes, &size);
    if (st == GOLEM_OK && (size != strlen(expected) || memcmp(bytes, expected, size)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    free(bytes);
    return st;
}

golem_status ws_verify(ws_context *ctx)
{
    const char *keys[] = {"tree", "gitdir"};
    if (!dw_keys(ctx->ready, keys, 2))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    const char *admin = dw_text(dw_get(ctx->ready, "gitdir"), "path");
    const char *nonce = dw_text(ctx->intent, "nonce");
    char parent[4096];
    if (!admin || !nonce || strlen(nonce) != 32 || ws_join(parent, ctx->common, "worktrees") != GOLEM_OK)
        return GOLEM_ERR_CORRUPT_JOURNAL;
    size_t len = strlen(parent);
    if (strncmp(admin, parent, len) || admin[len] != '/' || !ws_admin_id(admin + len + 1))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *tree = NULL, *gitdir = NULL;
    golem_status st = ws_identity(ctx->path, &tree);
    if (st == GOLEM_OK)
        st = ws_identity(admin, &gitdir);
    if (st == GOLEM_OK && (!json_object_equal(tree, dw_get(ctx->ready, "tree")) ||
        !json_object_equal(gitdir, dw_get(ctx->ready, "gitdir"))))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    int treefd = -1, adminfd = -1;
    if (st == GOLEM_OK)
        st = ws_directory(ctx->path, &treefd);
    if (st == GOLEM_OK)
        st = ws_directory(admin, &adminfd);
    char expected[8192];
    (void)snprintf(expected, sizeof(expected), "gitdir: %s\n", admin ? admin : "");
    if (st == GOLEM_OK)
        st = file_equals(treefd, ".git", expected);
    (void)snprintf(expected, sizeof(expected), "%s/.git\n", ctx->path);
    if (st == GOLEM_OK)
        st = file_equals(adminfd, "gitdir", expected);
    if (st == GOLEM_OK)
        st = file_equals(adminfd, "commondir", "../..\n");
    if (st == GOLEM_OK)
        st = file_equals(adminfd, "golem-owner", nonce);
    (void)snprintf(expected, sizeof(expected), "%s\n", nonce ? nonce : "");
    if (st == GOLEM_OK)
        st = file_equals(adminfd, "locked", expected);
    if (st == GOLEM_OK) {
        uint8_t *head = NULL;
        size_t size = 0;
        st = dw_read_at(adminfd, "HEAD", 65, &head, &size);
        if (st == GOLEM_OK) {
            if ((size != 41 && size != 65) || head[size - 1] != '\n')
                st = GOLEM_ERR_IDENTITY_MISMATCH;
            else {
                head[size - 1] = 0;
                if (!ws_oid((char *)head))
                    st = GOLEM_ERR_IDENTITY_MISMATCH;
            }
        }
        free(head);
    }
    if (treefd >= 0)
        close(treefd);
    if (adminfd >= 0)
        close(adminfd);
    json_object_put(tree);
    json_object_put(gitdir);
    return st;
}
