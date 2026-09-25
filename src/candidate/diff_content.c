#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "internal.h"
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Full-file replacement projection: byte-exact hex, never terminal control
 * sequences or an executable patch. No diff driver, textconv or shell runs. */
static int nibble(char c)
{
    return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1;
}

static golem_status live_bytes(const char *root, const char *hex, uint8_t *data, size_t capacity,
                               size_t *size)
{
    char path[4096];
    size_t n = strlen(hex);
    if (!n || n % 2 || n / 2 >= sizeof(path))
        return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < n / 2; ++i) {
        int a = nibble(hex[2 * i]), b = nibble(hex[2 * i + 1]);
        if (a < 0 || b < 0 || !(a * 16 + b))
            return GOLEM_ERR_PARSE;
        path[i] = (char)(a * 16 + b);
    }
    path[n / 2] = 0;
    if (path[0] == '/' || path[n / 2 - 1] == '/' || strstr(path, "//"))
        return GOLEM_ERR_PARSE;
    int dir = -1;
    golem_status st = ws_directory(root, &dir);
    char *part = path;
    while (st == GOLEM_OK) {
        char *slash = strchr(part, '/');
        if (slash)
            *slash = 0;
        if (!strcmp(part, ".") || !strcmp(part, "..") || !strcmp(part, ".git")) {
            st = GOLEM_ERR_POLICY_DENIED;
            break;
        }
        if (!slash)
            break;
        int next = openat(dir, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (next < 0)
            st = GOLEM_ERR_STALE_RESULT;
        if (close(dir) && st == GOLEM_OK)
            st = GOLEM_ERR_IO;
        dir = next;
        part = slash + 1;
    }
    struct stat info;
    if (st == GOLEM_OK && fstatat(dir, part, &info, AT_SYMLINK_NOFOLLOW))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK && S_ISLNK(info.st_mode)) {
        ssize_t got = readlinkat(dir, part, (char *)data, capacity);
        if (got < 0 || (size_t)got >= capacity)
            st = GOLEM_ERR_OVERFLOW;
        else
            *size = (size_t)got;
    } else if (st == GOLEM_OK && S_ISREG(info.st_mode)) {
        int fd = openat(dir, part, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
        struct stat opened;
        if (fd < 0 || fstat(fd, &opened) || !S_ISREG(opened.st_mode) ||
            opened.st_dev != info.st_dev || opened.st_ino != info.st_ino)
            st = GOLEM_ERR_STALE_RESULT;
        size_t used = 0;
        while (st == GOLEM_OK) {
            ssize_t got = read(fd, data + used, capacity - used);
            if (got < 0 && errno == EINTR)
                continue;
            if (got < 0)
                st = GOLEM_ERR_IO;
            else if (!got)
                break;
            else {
                used += (size_t)got;
                if (used == capacity)
                    st = GOLEM_ERR_OVERFLOW;
            }
        }
        if (fd >= 0 && close(fd) && st == GOLEM_OK)
            st = GOLEM_ERR_IO;
        *size = used;
    } else if (st == GOLEM_OK)
        st = GOLEM_ERR_POLICY_DENIED;
    if (dir >= 0 && close(dir) && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    return st;
}

golem_status cf_diff_content(cf_context *c, const golem_candidate_member *member, const char *path,
                             struct json_object *entry, bool live, size_t *remaining,
                             struct json_object **out)
{
    *out = NULL;
    struct json_object *worktree = dw_get(entry, "worktree");
    if (!worktree)
        return GOLEM_OK;
    if (dw_uint(worktree, "size") >= GOLEM_SUPERVISOR_OUTPUT_MAX ||
        dw_uint(worktree, "size") > *remaining)
        return GOLEM_ERR_OVERFLOW;
    size_t size = 0;
    golem_supervisor_result result = {0};
    golem_status st;
    if (live)
        st = live_bytes(member->tree_root, path, result.output, sizeof(result.output), &size);
    else {
        const char *oid = dw_text(worktree, "oid");
        if (!ws_oid(oid))
            return GOLEM_ERR_PARSE;
        ws_context git = {.store = member->work,
                          .host = member->workspace,
                          .operation = GOLEM_WORKSPACE_RESUME,
                          .candidate = dw_text(c->request, "candidate")};
        const char *args[] = {"cat-file", "blob", oid, NULL};
        st = ws_git(&git, member->tree_root, args, &result);
        size = result.output_size;
        if (result.timed_out)
            return GOLEM_ERR_BUDGET_EXHAUSTED;
        if (result.signal_number || (st == GOLEM_ERR_INCOMPLETE_WORK && result.exit_code != 128))
            return GOLEM_ERR_IO;
    }
    /* Missing historical dirty blobs and bounded captures are explicitly
     * incomplete. Permission, I/O and cancellation errors are never hidden. */
    if (st == GOLEM_ERR_OVERFLOW || size > *remaining)
        return GOLEM_ERR_OVERFLOW;
    if (st == GOLEM_ERR_INCOMPLETE_WORK)
        return GOLEM_ERR_INCOMPLETE_WORK;
    golem_digest actual, expected;
    if (st == GOLEM_OK)
        st = golem_digest_bytes((golem_bytes){result.output, size}, &actual);
    if (st == GOLEM_OK && (!dw_digest(worktree, "sha256", &expected) ||
                           !dw_equal(&actual, &expected) || dw_uint(worktree, "size") != size))
        st = GOLEM_ERR_STALE_RESULT;
    char *hex = NULL;
    if (st == GOLEM_OK)
        st = golem_allocator_alloc(&c->parent->allocator, size * 2 + 1, (void **)&hex);
    if (st == GOLEM_OK) {
        const char alphabet[] = "0123456789abcdef";
        for (size_t i = 0; i < size; ++i) {
            hex[2 * i] = alphabet[result.output[i] >> 4];
            hex[2 * i + 1] = alphabet[result.output[i] & 15];
        }
        hex[size * 2] = 0;
        *out = json_object_new_string_len(hex, (int)(size * 2));
        if (!*out)
            st = GOLEM_ERR_OUT_OF_MEMORY;
        else
            *remaining -= size;
    }
    dw_scratch_free(c->parent, hex);
    return st;
}
