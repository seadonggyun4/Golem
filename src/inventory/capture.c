#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include <errno.h>
#include <dirent.h>
#include <fcntl.h>
#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

typedef struct in_entry {
    char path[GOLEM_INVENTORY_PATH_MAX + 1];
    char head_mode[7], index_mode[7], head_oid[65], index_oid[65];
} in_entry;
typedef struct in_scan {
    ws_context git;
    golem_workspace_host host;
    const in_policy *policy;
    in_entry *entries;
    size_t count;
    uint64_t deadline, bytes;
    char head[65];
    int root;
} in_scan;

static uint64_t now_ns(void)
{
    struct timespec t;
    return clock_gettime(CLOCK_MONOTONIC, &t)
               ? 0
               : (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}

static golem_status pulse(void *context)
{
    in_scan *s = context;
    uint64_t now = now_ns();
    return now && now < s->deadline ? GOLEM_OK : GOLEM_ERR_BUDGET_EXHAUSTED;
}

static golem_status readable(void *context, golem_workspace_operation op, const char *id)
{
    (void)op;
    (void)id;
    return pulse(context);
}

static bool same_file(const struct stat *a, const struct stat *b)
{
#ifdef __APPLE__
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino && a->st_mode == b->st_mode &&
           a->st_size == b->st_size && a->st_mtimespec.tv_sec == b->st_mtimespec.tv_sec &&
           a->st_mtimespec.tv_nsec == b->st_mtimespec.tv_nsec &&
           a->st_ctimespec.tv_sec == b->st_ctimespec.tv_sec &&
           a->st_ctimespec.tv_nsec == b->st_ctimespec.tv_nsec;
#else
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino && a->st_mode == b->st_mode &&
           a->st_size == b->st_size && a->st_mtim.tv_sec == b->st_mtim.tv_sec &&
           a->st_mtim.tv_nsec == b->st_mtim.tv_nsec && a->st_ctim.tv_sec == b->st_ctim.tv_sec &&
           a->st_ctim.tv_nsec == b->st_ctim.tv_nsec;
#endif
}

static golem_status entry(in_scan *s, const uint8_t *path, size_t size, in_entry **out)
{
    char text[GOLEM_INVENTORY_PATH_MAX + 1];
    if (!size || size > GOLEM_INVENTORY_PATH_MAX || memchr(path, 0, size))
        return GOLEM_ERR_INCOMPLETE_WORK;
    memcpy(text, path, size);
    text[size] = 0;
    if (!in_path(text))
        return GOLEM_ERR_INCOMPLETE_WORK;
    /* Protection wins over an exclusion for every observed path. */
    if (in_any(s->policy->excluded, s->policy->excluded_count, text) &&
        !in_any(s->policy->protected, s->policy->protected_count, text)) {
        *out = NULL;
        return GOLEM_OK;
    }
    for (size_t i = 0; i < s->count; ++i)
        if (!strcmp(text, s->entries[i].path)) {
            *out = &s->entries[i];
            return GOLEM_OK;
        }
    if (s->count >= GOLEM_INVENTORY_MAX_PATHS)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    *out = &s->entries[s->count++];
    memcpy((*out)->path, text, size + 1);
    return GOLEM_OK;
}

typedef struct in_listing {
    in_scan *scan;
    unsigned kind;
    uint8_t record[GOLEM_INVENTORY_PATH_MAX + 96];
    size_t used;
} in_listing;

static golem_status listing_chunk(void *context, unsigned stream, golem_bytes bytes)
{
    in_listing *listing = context;
    if (stream != 0)
        return GOLEM_OK;
    for (size_t pos = 0; pos < bytes.size; ++pos) {
        if (listing->used == sizeof(listing->record))
            return GOLEM_ERR_BUDGET_EXHAUSTED;
        listing->record[listing->used++] = bytes.data[pos];
        if (bytes.data[pos])
            continue;
        in_git_entry parsed;
        golem_status st = in_git_entry_parse(
            (golem_bytes){listing->record, listing->used}, listing->kind == 1, &parsed);
        if (st != GOLEM_OK)
            return st;
        in_entry *e = NULL;
        st = entry(listing->scan, (const uint8_t *)parsed.path, strlen(parsed.path), &e);
        if (st != GOLEM_OK)
            return st;
        if (st == GOLEM_OK && e) {
            const char *mode = parsed.mode, *oid = parsed.oid;
            if (strcmp(mode, "100644") && strcmp(mode, "100755") && strcmp(mode, "120000"))
                return GOLEM_ERR_INCOMPLETE_WORK;
            char *m = listing->kind ? e->index_mode : e->head_mode;
            char *o = listing->kind ? e->index_oid : e->head_oid;
            if (*m)
                return GOLEM_ERR_PARSE;
            memcpy(m, mode, strlen(mode) + 1);
            memcpy(o, oid, strlen(oid) + 1);
        }
        listing->used = 0;
    }
    return GOLEM_OK;
}

static golem_status listing(in_scan *s, unsigned kind)
{
    const char *head[] = {"ls-tree", "-r", "-z", "--full-tree", "HEAD", NULL};
    const char *index[] = {"ls-files", "--stage", "-z", "--full-name", NULL};
    in_listing listing = {.scan = s, .kind = kind};
    const golem_supervisor_stream stream = {
        .struct_size = sizeof(stream), .version = 1,
        .write = listing_chunk, .context = &listing};
    golem_status st = ws_git_bulk(&s->git, s->host.repository_root,
        kind == 0 ? head : index, &stream, UINT64_C(67108864));
    if (st == GOLEM_OK && listing.used)
        st = GOLEM_ERR_PARSE;
    return st;
}

static int order(const void *a, const void *b)
{
    return strcmp(((const in_entry *)a)->path, ((const in_entry *)b)->path);
}

static bool path_prefix(const char *parent, const char *path)
{
    size_t n = strlen(parent);
    return strlen(path) >= n && !memcmp(parent, path, n) &&
           (path[n] == 0 || path[n] == '/');
}

/* Only prune a whole excluded subtree when no protection can overlap it.
 * Globs are deliberately conservative: matching the directory alone does not
 * prove whether a protected descendant exists. */
static bool prunable(const in_policy *policy, const char *path)
{
    bool excluded = false;
    for (size_t i = 0; i < policy->excluded_count; ++i)
        if (policy->excluded[i].kind == 2 && in_matches(&policy->excluded[i], path))
            excluded = true;
    if (!excluded)
        return false;
    for (size_t i = 0; i < policy->protected_count; ++i) {
        const in_rule *rule = &policy->protected[i];
        if (rule->kind == 3 || path_prefix(path, rule->pattern) ||
            (rule->kind == 2 && path_prefix(rule->pattern, path)))
            return false;
    }
    return true;
}

/* Git omits untracked special files. Walk without following links so such
 * entries cannot disappear from the declared source observation. */
static golem_status walk(in_scan *s, int parent_fd, const char *prefix, unsigned depth,
                         size_t *visited)
{
    if (depth > 64 || ++*visited > 4096)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    int fd = openat(parent_fd, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0)
        return GOLEM_ERR_IO;
    DIR *dir = fdopendir(fd);
    if (!dir) {
        close(fd);
        return GOLEM_ERR_IO;
    }
    golem_status st = GOLEM_OK;
    struct dirent *item;
    while (st == GOLEM_OK) {
        errno = 0;
        item = readdir(dir);
        if (!item) {
            if (errno)
                st = GOLEM_ERR_IO;
            break;
        }
        if (!strcmp(item->d_name, ".") || !strcmp(item->d_name, "..") ||
            (!*prefix && !strcmp(item->d_name, ".git")))
            continue;
        if (++*visited > 4096 || pulse(s) != GOLEM_OK) {
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
            break;
        }
        char path[GOLEM_INVENTORY_PATH_MAX + 1];
        int n = snprintf(path, sizeof(path), "%s%s%s", prefix, *prefix ? "/" : "", item->d_name);
        if (n < 0 || (size_t)n >= sizeof(path)) {
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
            break;
        }
        struct stat info;
        if (fstatat(fd, item->d_name, &info, AT_SYMLINK_NOFOLLOW)) {
            st = GOLEM_ERR_STALE_RESULT;
            break;
        }
        if (S_ISDIR(info.st_mode)) {
            if (prunable(s->policy, path))
                continue;
            int child = openat(fd, item->d_name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
            if (child < 0)
                st = GOLEM_ERR_INCOMPLETE_WORK;
            else {
                st = walk(s, child, path, depth + 1, visited);
                close(child);
            }
        } else {
            in_entry *entry_out = NULL;
            st = entry(s, (const uint8_t *)path, (size_t)n, &entry_out);
        }
    }
    closedir(dir);
    return st;
}

static struct json_object *tracked(const char *mode, const char *oid)
{
    if (!*mode)
        return NULL;
    struct json_object *o = json_object_new_object();
    if (!o || !dw_add(o, "mode", json_object_new_string(mode)) ||
        !dw_add(o, "oid", json_object_new_string(oid))) {
        json_object_put(o);
        return NULL;
    }
    return o;
}

/* Open each parent component independently. An absent parent is a deletion;
 * a symlink/unsupported parent is incomplete, never followed outside the root. */
static golem_status parent(in_scan *s, const char *path, int *out, char leaf[1025])
{
    memcpy(leaf, path, strlen(path) + 1);
    int fd = openat(s->root, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0)
        return GOLEM_ERR_IO;
    char *p = leaf, *slash;
    while ((slash = strchr(p, '/'))) {
        *slash = 0;
        int next = openat(fd, p, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (next < 0) {
            golem_status st = errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_INCOMPLETE_WORK;
            close(fd);
            return st;
        }
        close(fd);
        fd = next;
        p = slash + 1;
    }
    memmove(leaf, p, strlen(p) + 1);
    *out = fd;
    return GOLEM_OK;
}

static golem_status content(in_scan *s, const char *path, struct json_object **out)
{
    int dir = -1, fd = -1;
    char leaf[1025];
    golem_status st = parent(s, path, &dir, leaf);
    if (st == GOLEM_ERR_NOT_FOUND) {
        *out = NULL;
        return GOLEM_OK;
    }
    struct stat before, after;
    if (st == GOLEM_OK && fstatat(dir, leaf, &before, AT_SYMLINK_NOFOLLOW) < 0)
        st = errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO;
    if (st == GOLEM_ERR_NOT_FOUND) {
        close(dir);
        *out = NULL;
        return GOLEM_OK;
    }
    bool link = st == GOLEM_OK && S_ISLNK(before.st_mode);
    if (st == GOLEM_OK && !link && !S_ISREG(before.st_mode))
        st = GOLEM_ERR_INCOMPLETE_WORK;
    if (st == GOLEM_OK &&
        (before.st_size < 0 || (uint64_t)before.st_size > UINT64_C(67108864) - s->bytes))
        st = GOLEM_ERR_BUDGET_EXHAUSTED;
    EVP_MD_CTX *sha = NULL, *git = NULL;
    if (st == GOLEM_OK) {
        sha = EVP_MD_CTX_new();
        git = EVP_MD_CTX_new();
        if (!sha || !git)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK &&
        (EVP_DigestInit_ex(sha, EVP_sha256(), NULL) != 1 ||
         EVP_DigestInit_ex(git, strlen(s->head) == 40 ? EVP_sha1() : EVP_sha256(), NULL) != 1))
        st = GOLEM_ERR_CRYPTO;
    char header[64];
    if (st == GOLEM_OK) {
        int n = snprintf(header, sizeof(header), "blob %llu", (unsigned long long)before.st_size);
        if (n < 0 || (size_t)n >= sizeof(header) ||
            EVP_DigestUpdate(git, header, (size_t)n + 1) != 1)
            st = GOLEM_ERR_CRYPTO;
    }
    if (st == GOLEM_OK && !link) {
        fd = openat(dir, leaf, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0 || fstat(fd, &after) < 0 || !same_file(&before, &after))
            st = GOLEM_ERR_STALE_RESULT;
    }
    uint64_t total = 0;
    uint8_t buffer[8192];
    while (st == GOLEM_OK) {
        st = pulse(s);
        if (st != GOLEM_OK)
            break;
        ssize_t n = link ? readlinkat(dir, leaf, (char *)buffer, sizeof(buffer))
                         : read(fd, buffer, sizeof(buffer));
        if (n < 0 && errno == EINTR)
            continue;
        if (n < 0) {
            st = GOLEM_ERR_IO;
            break;
        }
        if (!n && !link)
            break;
        if (total + (uint64_t)n > (uint64_t)before.st_size ||
            (link && (size_t)n == sizeof(buffer))) {
            st = GOLEM_ERR_STALE_RESULT;
            break;
        }
        if (EVP_DigestUpdate(sha, buffer, (size_t)n) != 1 ||
            EVP_DigestUpdate(git, buffer, (size_t)n) != 1)
            st = GOLEM_ERR_CRYPTO;
        total += (uint64_t)n;
        if (link)
            break;
    }
    if (st == GOLEM_OK &&
        (total != (uint64_t)before.st_size || fstatat(dir, leaf, &after, AT_SYMLINK_NOFOLLOW) < 0 ||
         !same_file(&before, &after)))
        st = GOLEM_ERR_STALE_RESULT;
    uint8_t digest[32], oid[32];
    unsigned n = 0, m = 0;
    if (st == GOLEM_OK && (EVP_DigestFinal_ex(sha, digest, &n) != 1 || n != 32 ||
                           EVP_DigestFinal_ex(git, oid, &m) != 1 || m * 2 != strlen(s->head)))
        st = GOLEM_ERR_CRYPTO;
    struct json_object *o = NULL;
    if (st == GOLEM_OK) {
        o = json_object_new_object();
        if (!o ||
            !dw_add(o, "mode",
                    json_object_new_string(link                       ? "120000"
                                           : before.st_mode & S_IXUSR ? "100755"
                                                                      : "100644")) ||
            !dw_add(o, "oid", in_hex(oid, m)) || !dw_add(o, "sha256", in_hex(digest, n)) ||
            !dw_add(o, "size", json_object_new_uint64(total)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (fd >= 0)
        close(fd);
    if (dir >= 0)
        close(dir);
    EVP_MD_CTX_free(sha);
    EVP_MD_CTX_free(git);
    if (st == GOLEM_OK) {
        s->bytes += total;
        *out = o;
    } else
        json_object_put(o);
    return st;
}

static golem_status scan(in_scan *s, struct json_object **out)
{
    s->count = 0;
    s->bytes = 0;
    memset(s->entries, 0, sizeof(*s->entries) * GOLEM_INVENTORY_MAX_PATHS);
    struct json_object *identity = NULL, *items = json_object_new_array(),
                       *o = json_object_new_object();
    golem_status st =
        items && o ? ws_identity(s->host.repository_root, &identity) : GOLEM_ERR_OUT_OF_MEMORY;
    struct stat root_stat;
    if (st == GOLEM_OK &&
        (fstat(s->root, &root_stat) || (uint64_t)root_stat.st_dev != dw_uint(identity, "device") ||
         (uint64_t)root_stat.st_ino != dw_uint(identity, "inode")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        st = ws_git_policy(&s->git);
    if (st == GOLEM_OK) {
        const char *args[] = {"rev-parse", "--show-prefix", NULL};
        golem_supervisor_result prefix = {0};
        st = ws_git(&s->git, s->host.repository_root, args, &prefix);
        if (st == GOLEM_OK && (prefix.output_size != 1 || prefix.output[0] != '\n'))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
    }
    if (st == GOLEM_OK)
        st = ws_head(&s->git, s->host.repository_root, s->head);
    /* The no-follow walk inventories untracked and ignored entries, including
     * special files that ls-files --others cannot represent. */
    for (unsigned kind = 0; st == GOLEM_OK && kind < 2; ++kind)
        st = listing(s, kind);
    size_t visited = 0;
    if (st == GOLEM_OK)
        st = walk(s, s->root, "", 0, &visited);
    qsort(s->entries, s->count, sizeof(*s->entries), order);
    for (size_t i = 0; st == GOLEM_OK && i < s->count; ++i) {
        in_entry *e = &s->entries[i];
        struct json_object *item = json_object_new_object(), *body = NULL;
        st = content(s, e->path, &body);
        struct json_object *head = tracked(e->head_mode, e->head_oid),
                           *index = tracked(e->index_mode, e->index_oid);
        if (st == GOLEM_OK && (!item || (*e->head_mode && !head) || (*e->index_mode && !index)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK &&
            (json_object_object_add(item, "head", json_object_get(head)) ||
             json_object_object_add(item, "index", json_object_get(index)) ||
             json_object_object_add(item, "worktree", json_object_get(body)) ||
             !dw_add(item, "path_hex", in_hex((const uint8_t *)e->path, strlen(e->path)))))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK && json_object_array_add(items, json_object_get(item)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(item);
        json_object_put(body);
        json_object_put(head);
        json_object_put(index);
    }
    if (st == GOLEM_OK && (!dw_add(o, "schema_version", json_object_new_int(1)) ||
                           !dw_add(o, "root", json_object_get(identity)) ||
                           !dw_add(o, "head", json_object_new_string(s->head)) ||
                           !dw_add_digest(o, "policy", &s->policy->digest) ||
                           !dw_add(o, "entries", json_object_get(items))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = in_snapshot_validate(o, s->policy);
    struct json_object *current_identity = NULL;
    if (st == GOLEM_OK)
        st = ws_identity(s->host.repository_root, &current_identity);
    if (st == GOLEM_OK && !json_object_equal(identity, current_identity))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    json_object_put(current_identity);
    if (st == GOLEM_OK)
        *out = o;
    else
        json_object_put(o);
    json_object_put(identity);
    json_object_put(items);
    return st;
}

golem_status in_capture(const char *root, const in_policy *policy, struct json_object **out)
{
    in_scan s = {.policy = policy, .deadline = now_ns() + UINT64_C(60000000000), .root = -1};
    s.host = (golem_workspace_host){
        .repository_root = root, .check = readable, .pulse = pulse, .context = &s};
    s.git.host = &s.host;
    golem_status st = ws_directory(root, &s.root);
    void *memory = NULL;
    if (st == GOLEM_OK)
        st = golem_allocator_alloc_zero(NULL, GOLEM_INVENTORY_MAX_PATHS, sizeof(in_entry), &memory);
    s.entries = memory;
    struct json_object *first = NULL, *second = NULL;
    if (st == GOLEM_OK)
        st = scan(&s, &first);
    if (st == GOLEM_OK)
        st = scan(&s, &second);
    if (st == GOLEM_OK && !json_object_equal(first, second))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK)
        *out = json_object_get(second);
    json_object_put(first);
    json_object_put(second);
    (void)golem_allocator_free(NULL, memory);
    if (s.root >= 0)
        close(s.root);
    return st;
}
