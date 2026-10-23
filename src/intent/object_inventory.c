#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "object_inventory.h"
#include "schema.h"
#include "../common/json.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define OBJECT_ENTRIES 33792u
typedef struct entry {
    char path[192];
    uint64_t length;
    golem_digest digest;
    bool directory, raw, committed, final_seen, pending_seen;
    struct stat final, pending;
} entry;
typedef struct catalogue {
    entry *entries;
    size_t count;
    struct json_object *index;
    dev_t device;
    gi_object_inventory result;
} catalogue;

static struct json_object *member(struct json_object *o, const char *key)
{
    struct json_object *v = NULL; (void)json_object_object_get_ex(o, key, &v); return v;
}
static entry *lookup(catalogue *c, const char *path)
{
    struct json_object *v = NULL;
    return json_object_object_get_ex(c->index, path, &v) ? &c->entries[json_object_get_uint64(v)] : NULL;
}
static golem_status add(catalogue *c, const entry *e)
{
    if (c->count == OBJECT_ENTRIES) return GOLEM_ERR_OVERFLOW;
    if (lookup(c, e->path)) return GOLEM_ERR_INVALID_STATE;
    struct json_object *v = json_object_new_uint64(c->count);
    if (!v) return GOLEM_ERR_OUT_OF_MEMORY;
    if (json_object_object_add(c->index, e->path, v) != 0) {
        json_object_put(v); return GOLEM_ERR_OUT_OF_MEMORY;
    }
    c->entries[c->count++] = *e;
    return GOLEM_OK;
}
static bool stable(const struct stat *a, const struct stat *b)
{
#ifdef __APPLE__
    if (a->st_mtimespec.tv_nsec != b->st_mtimespec.tv_nsec || a->st_ctimespec.tv_nsec != b->st_ctimespec.tv_nsec) return false;
#else
    if (a->st_mtim.tv_nsec != b->st_mtim.tv_nsec || a->st_ctim.tv_nsec != b->st_ctim.tv_nsec) return false;
#endif
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino && a->st_mode == b->st_mode &&
        a->st_uid == b->st_uid && a->st_nlink == b->st_nlink && a->st_size == b->st_size &&
        a->st_mtime == b->st_mtime && a->st_ctime == b->st_ctime;
}
static golem_status plan(catalogue *c, const gi_object_manifest_input *inputs, size_t count)
{
    uint64_t previous = 0;
    for (size_t i = 0; i < count; ++i) {
        gi_object_preparation_result verified;
        golem_status st = gi_object_preparation_validate(inputs[i].bytes, &verified, NULL);
        if (st != GOLEM_OK) return st;
        if (verified.reservation.sequence <= previous || (!inputs[i].committed && i + 1 != count))
            return GOLEM_ERR_INVALID_STATE;
        previous = verified.reservation.sequence;
        if (!inputs[i].committed) c->result.pending = true;
        struct json_object *o = NULL;
        st = golem_json_parse(inputs[i].bytes, GI_CONTROL_MAX, &o);
        if (st != GOLEM_OK) return st;
        struct json_object *dirs = member(o, "new_directories"), *objects = member(o, "objects");
        for (size_t k = 0; st == GOLEM_OK && k < json_object_array_length(dirs); ++k) {
            entry e = {0}; e.directory = true; e.committed = inputs[i].committed;
            (void)snprintf(e.path, sizeof(e.path), "%s", json_object_get_string(json_object_array_get_idx(dirs, k)));
            st = add(c, &e);
        }
        for (size_t k = 0; st == GOLEM_OK && k < json_object_array_length(objects); ++k) {
            struct json_object *row = json_object_array_get_idx(objects, k);
            entry e = {0}; e.committed = inputs[i].committed;
            (void)snprintf(e.path, sizeof(e.path), "%s", json_object_get_string(member(row, "path")));
            e.length = json_object_get_uint64(member(row, "byte_length"));
            e.raw = !strcmp(json_object_get_string(member(row, "kind")), "raw");
            const char *digest = json_object_get_string(member(row, "digest"));
            st = golem_digest_parse((golem_string_view){digest, 64}, &e.digest);
            if (st != GOLEM_OK) break;
            entry *old = lookup(c, e.path);
            if (!strcmp(json_object_get_string(member(row, "disposition")), "reuse")) {
                if (!old || !old->committed || old->directory || old->raw != e.raw ||
                    old->length != e.length || memcmp(&old->digest, &e.digest, sizeof(e.digest)))
                    st = GOLEM_ERR_INVALID_STATE;
            } else st = add(c, &e);
        }
        json_object_put(o);
        if (st != GOLEM_OK) return st;
    }
    for (size_t i = 0; i < c->count; ++i) {
        char parent[192]; (void)snprintf(parent, sizeof(parent), "%s", c->entries[i].path);
        char *slash = strrchr(parent, '/');
        if (slash) {
            *slash = 0; entry *p = lookup(c, parent);
            if (!p || !p->directory) return GOLEM_ERR_INVALID_STATE;
        }
    }
    return GOLEM_OK;
}

static golem_status content(int fd, const entry *e, const struct stat *sb, bool pending, uint8_t **loaded)
{
    if (sb->st_size < 0 || (uint64_t)sb->st_size > e->length ||
        (!pending && (uint64_t)sb->st_size != e->length)) return GOLEM_ERR_INVALID_STATE;
    /* An incomplete pending file remains attributable occupancy, never a
     * verified object. Full-length bytes must satisfy the planned identity. */
    if (pending && (uint64_t)sb->st_size < e->length) return GOLEM_OK;
    size_t n = (size_t)e->length, used = 0;
    uint8_t *bytes = malloc(n ? n : 1);
    if (!bytes) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = GOLEM_OK;
    while (used < n) {
        ssize_t got = read(fd, bytes + used, n - used);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0) { st = GOLEM_ERR_IO; break; }
        used += (size_t)got;
    }
    golem_digest actual;
    if (st == GOLEM_OK && !e->raw) {
        struct json_object *o = NULL;
        st = golem_json_parse((golem_bytes){bytes, n}, GI_CONTROL_MAX, &o);
        if (st == GOLEM_OK) {
            struct json_object *schema = member(o, "schema");
            if (!json_object_is_type(schema, json_type_string)) st = GOLEM_ERR_PARSE;
            else {
                char prefix[192]; int length = snprintf(prefix, sizeof(prefix), "objects/v1/domain/%s/",
                    json_object_get_string(schema));
                if (length < 0 || (size_t)length >= sizeof(prefix) || strncmp(e->path, prefix, (size_t)length))
                    st = GOLEM_ERR_INVALID_STATE;
            }
        }
        json_object_put(o);
    }
    if (st == GOLEM_OK) st = e->raw ? golem_digest_bytes((golem_bytes){bytes, n}, &actual) :
        gi_domain_digest((golem_bytes){bytes, n}, &actual, NULL);
    if (st == GOLEM_OK && memcmp(&actual, &e->digest, sizeof(actual))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && loaded) *loaded = bytes;
    else free(bytes);
    return st;
}

static golem_status scan(catalogue *c, int parent, const char *name, const char *path)
{
    char target[192]; size_t n = strlen(path);
    if (n >= sizeof(target)) return GOLEM_ERR_INVALID_STATE;
    memcpy(target, path, n + 1);
    bool pending = n > 8 && !strcmp(path + n - 8, ".pending");
    if (pending) target[n - 8] = 0;
    entry *e = lookup(c, target);
    if (!e || (pending && e->directory)) return GOLEM_ERR_INVALID_STATE;
    struct stat observed, opened, after, named;
    if (fstatat(parent, name, &observed, AT_SYMLINK_NOFOLLOW) < 0) return GOLEM_ERR_IO;
    if (observed.st_dev != c->device || observed.st_uid != geteuid() ||
        (e->directory ? !S_ISDIR(observed.st_mode) : !S_ISREG(observed.st_mode))) return GOLEM_ERR_INVALID_STATE;
    mode_t mode = observed.st_mode & 07777;
    if (e->directory ? mode != 0700 : (pending ? mode != 0600 && mode != 0400 : mode != 0400))
        return GOLEM_ERR_POLICY_DENIED;
    int fd = openat(parent, name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK |
        (e->directory ? O_DIRECTORY : 0));
    if (fd < 0) return GOLEM_ERR_IO;
    golem_status st = GOLEM_OK;
    if (fstat(fd, &opened) < 0 || !stable(&observed, &opened)) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && e->directory) {
        ++c->result.actual.directories;
        int listing = openat(fd, ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        DIR *dir = listing < 0 ? NULL : fdopendir(listing);
        if (!dir) { if (listing >= 0) close(listing); st = GOLEM_ERR_IO; }
        else {
            while (st == GOLEM_OK) {
                errno = 0; struct dirent *de = readdir(dir);
                if (!de) { if (errno) st = GOLEM_ERR_IO; break; }
                if (!strcmp(de->d_name, ".") || !strcmp(de->d_name, "..")) continue;
                char child[192]; int length = snprintf(child, sizeof(child), "%s/%s", path, de->d_name);
                if (length < 0 || (size_t)length >= sizeof(child)) { st = GOLEM_ERR_INVALID_STATE; break; }
                st = scan(c, fd, de->d_name, child);
            }
            if (closedir(dir) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
        }
    } else if (st == GOLEM_OK) {
        st = content(fd, e, &opened, pending, NULL);
        if (st == GOLEM_OK) {
            ++c->result.actual.files;
            c->result.actual.logical_bytes += (uint64_t)opened.st_size;
        }
    }
    if (st == GOLEM_OK && (fstat(fd, &after) < 0 || !stable(&opened, &after) ||
        fstatat(parent, name, &named, AT_SYMLINK_NOFOLLOW) < 0 || !stable(&opened, &named)))
        st = GOLEM_ERR_INVALID_STATE;
    if (close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK) {
        if (pending) { e->pending_seen = true; e->pending = opened; }
        else { e->final_seen = true; e->final = opened; }
    }
    return st;
}

golem_status gi_object_inventory_scan(int root, const gi_object_manifest_input *inputs, size_t count,
    gi_object_inventory *out)
{
    if (root < 0 || !out || (!inputs && count) || count > 6208) return GOLEM_ERR_INVALID_ARGUMENT;
    struct stat before, after, object;
    if (fstat(root, &before) < 0) return GOLEM_ERR_IO;
    if (!S_ISDIR(before.st_mode) || before.st_uid != geteuid() || (before.st_mode & 0077))
        return GOLEM_ERR_POLICY_DENIED;
    catalogue c = {0}; c.device = before.st_dev;
    c.entries = calloc(OBJECT_ENTRIES, sizeof(*c.entries)); c.index = json_object_new_object();
    golem_status st = c.entries && c.index ? plan(&c, inputs, count) : GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        if (fstatat(root, "objects", &object, AT_SYMLINK_NOFOLLOW) == 0) st = scan(&c, root, "objects", "objects");
        else if (errno != ENOENT) st = GOLEM_ERR_IO;
    }
    for (size_t i = 0; st == GOLEM_OK && i < c.count; ++i) {
        entry *e = &c.entries[i];
        if (e->committed && (!e->final_seen || e->pending_seen)) st = GOLEM_ERR_INVALID_STATE;
        if (!e->final_seen || e->pending_seen) c.result.pending = true;
        if (e->directory) continue;
        unsigned names = (unsigned)e->final_seen + (unsigned)e->pending_seen;
        if ((e->final_seen && e->final.st_nlink != names) ||
            (e->pending_seen && e->pending.st_nlink != names) ||
            (names == 2 && (e->final.st_dev != e->pending.st_dev || e->final.st_ino != e->pending.st_ino)))
            st = GOLEM_ERR_INVALID_STATE;
    }
    if (st == GOLEM_OK && (fstat(root, &after) < 0 || !stable(&before, &after))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) {
        c.result.intake.value[GI_QUOTA_BYTES] = c.result.actual.logical_bytes;
        c.result.intake.value[GI_QUOTA_ENTRIES] = c.result.actual.files + c.result.actual.directories;
        *out = c.result;
    }
    json_object_put(c.index); free(c.entries); return st;
}

golem_status gi_object_path(gi_object_kind kind, const golem_digest *digest, char *out, size_t cap)
{
    static const char *const prefixes[] = {"objects/v1/raw/sha256/", "objects/v1/domain/golem.intent.source.v1/",
        "objects/v1/domain/golem.intent.baseline.v1/"};
    if (!digest || !out || (unsigned)kind > GI_OBJECT_BASELINE) return GOLEM_ERR_INVALID_ARGUMENT;
    char hex[65], path[192]; size_t required;
    golem_status st = golem_digest_format(digest, hex, sizeof(hex), &required);
    if (st != GOLEM_OK) return st;
    int n = snprintf(path, sizeof(path), "%s%s", prefixes[kind], hex);
    if (n < 0 || (size_t)n >= cap || (size_t)n >= sizeof(path)) return GOLEM_ERR_OVERFLOW;
    memcpy(out, path, (size_t)n + 1); return GOLEM_OK;
}

golem_status gi_object_load(int root, gi_object_kind kind, const golem_digest *digest, size_t limit,
    uint8_t **out, size_t *size)
{
    if (root < 0 || !out || !size || !digest) return GOLEM_ERR_INVALID_ARGUMENT;
    entry e = {0}; e.raw = kind == GI_OBJECT_RAW; e.digest = *digest;
    golem_status st = gi_object_path(kind, digest, e.path, sizeof(e.path));
    if (st != GOLEM_OK) return st;
    struct stat base;
    if (fstat(root, &base) < 0) return GOLEM_ERR_IO;
    if (!S_ISDIR(base.st_mode) || base.st_uid != geteuid() || (base.st_mode & 0077)) return GOLEM_ERR_POLICY_DENIED;
    int parent = openat(root, ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent < 0) return GOLEM_ERR_IO;
    char path[192]; memcpy(path, e.path, strlen(e.path) + 1);
    char *part = path, *slash;
    while (st == GOLEM_OK && (slash = strchr(part, '/'))) {
        *slash = 0;
        int child = openat(parent, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        struct stat sb;
        if (child < 0) st = GOLEM_ERR_IO;
        else if (fstat(child, &sb) < 0 || sb.st_dev != base.st_dev || sb.st_uid != geteuid() ||
            (sb.st_mode & 07777) != 0700) st = GOLEM_ERR_INVALID_STATE;
        if (close(parent) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
        parent = child; part = slash + 1;
    }
    int fd = -1; struct stat before, after, named; uint8_t *loaded = NULL;
    if (st == GOLEM_OK) {
        fd = openat(parent, part, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
        if (fd < 0) st = GOLEM_ERR_IO;
        else if (fstat(fd, &before) < 0 || !S_ISREG(before.st_mode) || before.st_dev != base.st_dev ||
            before.st_uid != geteuid() || (before.st_mode & 07777) != 0400 || before.st_nlink != 1 ||
            before.st_size < 0 || (uint64_t)before.st_size > limit ||
            (uint64_t)before.st_size > (e.raw ? GI_SOURCE_MAX : GI_CONTROL_MAX)) st = GOLEM_ERR_INVALID_STATE;
    }
    if (st == GOLEM_OK) { e.length = (uint64_t)before.st_size; st = content(fd, &e, &before, false, &loaded); }
    if (st == GOLEM_OK && (fstat(fd, &after) < 0 || !stable(&before, &after) ||
        fstatat(parent, part, &named, AT_SYMLINK_NOFOLLOW) < 0 || !stable(&before, &named))) st = GOLEM_ERR_INVALID_STATE;
    if (fd >= 0 && close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (parent >= 0 && close(parent) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK) { *out = loaded; *size = (size_t)e.length; } else free(loaded);
    return st;
}
