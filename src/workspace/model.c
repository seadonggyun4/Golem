#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#define _XOPEN_SOURCE 700
#include "internal.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static bool identifier(const char *s, size_t limit)
{
    if (!s || !*s || strlen(s) > limit)
        return false;
    for (; *s; ++s)
        if (!((*s >= 'a' && *s <= 'z') || (*s >= 'A' && *s <= 'Z') ||
              (*s >= '0' && *s <= '9') || *s == '_' || *s == '-'))
            return false;
    return true;
}

bool ws_id(const char *s)
{
    return identifier(s, 64);
}

bool ws_admin_id(const char *s)
{
    /* Git adds a numeric suffix when another Work uses the same basename. */
    return identifier(s, 255);
}

bool ws_oid(const char *s)
{
    if (!s || (strlen(s) != 40 && strlen(s) != 64))
        return false;
    for (; *s; ++s)
        if (!((*s >= '0' && *s <= '9') || (*s >= 'a' && *s <= 'f')))
            return false;
    return true;
}

golem_status ws_join(char out[4096], const char *parent, const char *child)
{
    int n = snprintf(out, 4096, "%s/%s", parent, child);
    return n < 0 || n >= 4096 ? GOLEM_ERR_OVERFLOW : GOLEM_OK;
}

golem_status ws_directory(const char *path, int *out)
{
    if (!path || path[0] != '/' || strlen(path) >= 4096 || !path[1])
        return GOLEM_ERR_INVALID_ARGUMENT;
    char copy[4096];
    memcpy(copy, path, strlen(path) + 1);
    int fd = open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0)
        return GOLEM_ERR_IO;
    char *part = copy + 1;
    golem_status st = GOLEM_OK;
    while (*part) {
        char *end = strchr(part, '/');
        if (end)
            *end = 0;
        if (!*part || !strcmp(part, ".") || !strcmp(part, "..")) {
            st = GOLEM_ERR_POLICY_DENIED;
            break;
        }
        int next = openat(fd, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (next < 0) {
            st = errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_POLICY_DENIED;
            break;
        }
        close(fd);
        fd = next;
        if (!end)
            break;
        part = end + 1;
        if (!*part)
            st = GOLEM_ERR_POLICY_DENIED;
    }
    char canonical[4096];
    if (st == GOLEM_OK && (!realpath(path, canonical) || strcmp(path, canonical)))
        st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK)
        *out = fd;
    else
        close(fd);
    return st;
}

golem_status ws_identity(const char *path, struct json_object **out)
{
    int fd = -1;
    golem_status st = ws_directory(path, &fd);
    struct stat statbuf;
    if (st == GOLEM_OK && fstat(fd, &statbuf) < 0)
        st = GOLEM_ERR_IO;
    if (fd >= 0)
        close(fd);
    if (st != GOLEM_OK)
        return st;
    struct json_object *o = json_object_new_object();
    if (!o || !dw_add(o, "path", json_object_new_string(path)) ||
        !dw_add(o, "device", json_object_new_uint64((uint64_t)statbuf.st_dev)) ||
        !dw_add(o, "inode", json_object_new_uint64((uint64_t)statbuf.st_ino))) {
        json_object_put(o);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    *out = o;
    return GOLEM_OK;
}
