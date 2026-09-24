#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Git status omits special files and empty directories. Before destructive
 * cleanup, independently reject entries whose preservation Git cannot promise.
 * The host must still quiesce writers: this is not an OS isolation primitive. */
static golem_status cleanup_scan(ws_context *ctx, int parent, unsigned depth, size_t *visited)
{
    if (depth > 64)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    int fd = openat(parent, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0)
        return GOLEM_ERR_IO;
    DIR *dir = fdopendir(fd);
    if (!dir) {
        close(fd);
        return GOLEM_ERR_IO;
    }
    golem_status st = GOLEM_OK;
    bool populated = false;
    while (st == GOLEM_OK) {
        errno = 0;
        struct dirent *entry = readdir(dir);
        if (!entry) {
            if (errno)
                st = GOLEM_ERR_IO;
            break;
        }
        const char *name = entry->d_name;
        if (!strcmp(name, ".") || !strcmp(name, "..") || (!depth && !strcmp(name, ".git")))
            continue;
        populated = true;
        if (++*visited > 4096) {
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
            break;
        }
        st = ctx->host->pulse(ctx->host->context);
        struct stat before, opened, after;
        if (st == GOLEM_OK && fstatat(fd, name, &before, AT_SYMLINK_NOFOLLOW))
            st = GOLEM_ERR_STALE_RESULT;
        if (st != GOLEM_OK)
            break;
        if (S_ISDIR(before.st_mode)) {
            int child = openat(fd, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
            if (child < 0)
                st = GOLEM_ERR_STALE_RESULT;
            else {
                if (fstat(child, &opened) || opened.st_dev != before.st_dev ||
                    opened.st_ino != before.st_ino)
                    st = GOLEM_ERR_STALE_RESULT;
                else
                    st = cleanup_scan(ctx, child, depth + 1, visited);
                if (close(child) && st == GOLEM_OK)
                    st = GOLEM_ERR_IO;
            }
        } else if (!S_ISREG(before.st_mode) && !S_ISLNK(before.st_mode))
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
        if (st == GOLEM_OK && (fstatat(fd, name, &after, AT_SYMLINK_NOFOLLOW) ||
            after.st_dev != before.st_dev || after.st_ino != before.st_ino ||
            after.st_mode != before.st_mode))
            st = GOLEM_ERR_STALE_RESULT;
    }
    if (closedir(dir) && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && depth && !populated)
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    return st;
}

golem_status ws_cleanup_inventory(ws_context *ctx)
{
    int fd = -1;
    size_t visited = 0;
    golem_status st = ws_directory(ctx->path, &fd);
    if (st == GOLEM_OK)
        st = cleanup_scan(ctx, fd, 0, &visited);
    if (fd >= 0 && close(fd) && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    return st;
}

static golem_status git_run(ws_context *ctx, const char *cwd, const char *const args[],
                    golem_supervisor_result *out, const golem_supervisor_stream *stream,
                    const uint64_t *limits, golem_supervisor_capture *capture)
{
    golem_status st = ctx->host->check(ctx->host->context, ctx->operation, ctx->candidate);
    if (st != GOLEM_OK)
        return st;
    char *argv[64] = {"/usr/bin/git", "--no-pager", "--no-optional-locks",
        "--literal-pathspecs", "--no-replace-objects",
        "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
        "-c", "core.untrackedCache=false", "-c", "submodule.recurse=false",
        "-c", "core.attributesFile=/dev/null", "-c", "core.excludesFile=/dev/null",
        "-c", "protocol.allow=never", "-c", "maintenance.auto=false",
        "-c", "gc.auto=0", "-c", "worktree.useRelativePaths=false", "-C", (char *)cwd};
    size_t n = 0;
    while (argv[n])
        ++n;
    for (size_t i = 0; args[i]; ++i) {
        if (n >= 63)
            return GOLEM_ERR_OVERFLOW;
        argv[n++] = (char *)args[i];
    }
    argv[n] = NULL;
    char *env[] = {"PATH=/usr/bin:/bin", "LANG=C", "LC_ALL=C",
        "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null", "GIT_TERMINAL_PROMPT=0",
        "GIT_NO_LAZY_FETCH=1", "GIT_LFS_SKIP_SMUDGE=1", NULL};
    if (stream)
        return golem_supervisor_run_bulk(argv[0], argv, cwd, env, (golem_bytes){NULL, 0},
            UINT64_C(60000000000), ctx->host->pulse, ctx->host->context, out,
            stream, limits, capture);
    return golem_supervisor_run_at(argv[0], argv, cwd, env, (golem_bytes){NULL, 0},
        UINT64_C(60000000000), ctx->host->pulse, ctx->host->context, out);
}

golem_status ws_git(ws_context *ctx, const char *cwd, const char *const args[],
                    golem_supervisor_result *out)
{
    return git_run(ctx, cwd, args, out, NULL, NULL, NULL);
}

golem_status ws_git_bulk(ws_context *ctx, const char *cwd, const char *const args[],
    const golem_supervisor_stream *stream, uint64_t stdout_limit)
{
    golem_supervisor_result result = {0};
    golem_supervisor_capture capture = {0};
    const uint64_t limits[2] = {stdout_limit, GOLEM_SUPERVISOR_OUTPUT_MAX};
    golem_status st = git_run(ctx, cwd, args, &result, stream, limits, &capture);
    if (st == GOLEM_OK && (!capture.reaped || !capture.eof[0] || !capture.eof[1]))
        st = GOLEM_ERR_INCOMPLETE_WORK;
    return st;
}

golem_status ws_git_policy(ws_context *ctx)
{
    const char *args[] = {"config", "--null", "--list", NULL};
    golem_supervisor_result result = {0};
    golem_status st = ws_git(ctx, ctx->host->repository_root, args, &result);
    if (st != GOLEM_OK)
        return st;
    /* Inspect effective keys, not values: includes are expanded by Git. Deny
     * all filter drivers rather than trying to enumerate executable dialects. */
    size_t pos = 0;
    while (pos < result.output_size) {
        const uint8_t *end = memchr(result.output + pos, 0, result.output_size - pos);
        if (!end)
            return GOLEM_ERR_PARSE;
        size_t size = (size_t)(end - result.output - pos);
        const uint8_t *nl = memchr(result.output + pos, '\n', size);
        size_t keysize = nl ? (size_t)(nl - result.output - pos) : size;
        const char *blocked[] = {"filter.", "extensions.worktreeconfig", "extensions.partialclone",
            "core.worktree", "core.sparsecheckout", "core.sparsecheckoutcone", NULL};
        for (size_t i = 0; blocked[i]; ++i) {
            size_t len = strlen(blocked[i]);
            if (keysize >= len && !memcmp(result.output + pos, blocked[i], len))
                return GOLEM_ERR_POLICY_DENIED;
        }
        /* Promisor remotes can turn object reads into network effects. */
        if (keysize >= 9 && !memcmp(result.output + pos + keysize - 9, ".promisor", 9))
            return GOLEM_ERR_POLICY_DENIED;
        pos += size + 1;
    }
    return GOLEM_OK;
}

golem_status ws_head(ws_context *ctx, const char *cwd, char out[65])
{
    const char *args[] = {"rev-parse", "--verify", "HEAD^{commit}", NULL};
    golem_supervisor_result result = {0};
    golem_status st = ws_git(ctx, cwd, args, &result);
    if (st != GOLEM_OK)
        return st;
    if ((result.output_size != 41 && result.output_size != 65) ||
        result.output[result.output_size - 1] != '\n')
        return GOLEM_ERR_PARSE;
    char oid[65];
    memcpy(oid, result.output, result.output_size - 1);
    oid[result.output_size - 1] = 0;
    if (!ws_oid(oid))
        return GOLEM_ERR_PARSE;
    memcpy(out, oid, result.output_size);
    return GOLEM_OK;
}

golem_status ws_clean(ws_context *ctx, const char *cwd, bool *clean,
                      golem_digest *status_digest)
{
    /* Git's normal status may hide assume-unchanged/skip-worktree entries.
     * Refuse those index modes rather than deleting apparently clean content. */
    const char *index[] = {"ls-files", "-v", "-z", NULL};
    golem_supervisor_result result = {0};
    golem_status st = ws_git(ctx, cwd, index, &result);
    if (st != GOLEM_OK)
        return st;
    size_t pos = 0;
    while (pos < result.output_size) {
        const uint8_t *end = memchr(result.output + pos, 0, result.output_size - pos);
        if (!end || result.output[pos] != 'H' ||
            (size_t)(end - result.output - pos) < 3 || result.output[pos + 1] != ' ')
            return GOLEM_ERR_POLICY_DENIED;
        pos = (size_t)(end - result.output) + 1;
    }
    const char *args[] = {"status", "--porcelain=v1", "-z", "--untracked-files=all",
        "--ignored", "--ignore-submodules=none", NULL};
    st = ws_git(ctx, cwd, args, &result);
    if (st == GOLEM_OK) {
        golem_receipt receipt;
        st = golem_evidence_put(ctx->store->cas,
            (golem_bytes){result.output, result.output_size}, &receipt, NULL);
        if (st == GOLEM_OK)
            *status_digest = receipt.digest;
    }
    if (st == GOLEM_OK)
        *clean = result.output_size == 0;
    return st;
}
