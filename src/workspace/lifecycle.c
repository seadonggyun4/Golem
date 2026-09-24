#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include <errno.h>
#include <fcntl.h>
#include <openssl/rand.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static golem_status registration(ws_context *ctx, struct json_object **out)
{
    struct json_object *o = json_object_new_object(), *repo = NULL, *root = NULL, *common = NULL;
    golem_status st = o ? ws_identity(ctx->host->repository_root, &repo) : GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ws_identity(ctx->host->worktree_root, &root);
    if (st == GOLEM_OK)
        st = ws_join(ctx->common, ctx->host->repository_root, ".git");
    if (st == GOLEM_OK)
        st = ws_identity(ctx->common, &common);
    if (st == GOLEM_OK && json_object_equal(repo, root))
        st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK) {
        size_t n = strlen(ctx->common);
        const char *path = ctx->host->worktree_root;
        if (!strncmp(path, ctx->common, n) && (path[n] == 0 || path[n] == '/'))
            st = GOLEM_ERR_POLICY_DENIED;
    }
    if (st == GOLEM_OK &&
        (!dw_add(o, "schema_version", json_object_new_int(1)) ||
         !dw_add(o, "repository_id", json_object_new_string(ctx->host->repository_id)) ||
         !dw_add(o, "repository", json_object_get(repo)) ||
         !dw_add(o, "root", json_object_get(root)) ||
         !dw_add(o, "common", json_object_get(common))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(repo);
    json_object_put(root);
    json_object_put(common);
    if (st == GOLEM_OK)
        *out = o;
    else
        json_object_put(o);
    return st;
}

static golem_status registered(ws_context *ctx, struct json_object *binding, bool create)
{
    int dir = -1;
    golem_status st = dw_dir(ctx->store->root, "workspace-repositories", create, &dir);
    const char *text = json_object_to_json_string_ext(binding, JSON_C_TO_STRING_PLAIN);
    if (!text && st == GOLEM_OK)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && create)
        st = dw_publish(dir, ctx->host->repository_id, (golem_bytes){(const uint8_t *)text, strlen(text)});
    else if (st == GOLEM_OK) {
        uint8_t *bytes = NULL;
        size_t size = 0;
        st = dw_read_at(dir, ctx->host->repository_id, GOLEM_DOCUMENT_MAX_JSON, &bytes, &size);
        if (st == GOLEM_OK && (size != strlen(text) || memcmp(bytes, text, size)))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        /* dw_read_at uses the documented standalone C heap. */
        (void)golem_allocator_free(NULL, bytes);
    }
    if (dir >= 0)
        close(dir);
    return st;
}

static golem_status initialize(ws_context *ctx, struct json_object *binding, const char *base)
{
    struct stat sb;
    if (lstat(ctx->path, &sb) == 0 || errno != ENOENT)
        return GOLEM_ERR_IDENTITY_MISMATCH;
    bool clean;
    golem_digest status;
    golem_status st = ws_clean(ctx, ctx->host->repository_root, &clean, &status);
    struct json_object *intent = json_object_new_object();
    unsigned char random[16];
    char nonce[33];
    if (st == GOLEM_OK && RAND_bytes(random, sizeof(random)) != 1)
        st = GOLEM_ERR_CRYPTO;
    if (st == GOLEM_OK) {
        for (size_t i = 0; i < sizeof(random); ++i)
            (void)snprintf(nonce + 2 * i, 3, "%02x", random[i]);
        if (!intent || !dw_add(intent, "registration", json_object_get(binding)) ||
            !dw_add(intent, "work_id", json_object_get(dw_get(ctx->store->spec, "work_id"))) ||
            !dw_add(intent, "candidate", json_object_new_string(ctx->candidate)) ||
            !dw_add(intent, "base_commit", json_object_new_string(base)) ||
            !dw_add(intent, "nonce", json_object_new_string(nonce)) ||
            !dw_add(intent, "main_dirty", json_object_new_boolean(!clean)) ||
            !dw_add_digest(intent, "main_status", &status) ||
            !dw_add(intent, "runtime_generation", json_object_new_uint64(ctx->store->runtime_profile_count)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        st = ws_append(ctx, intent);
    if (st == GOLEM_OK)
        ctx->intent = json_object_get(intent);
    json_object_put(intent);
    return st;
}

static golem_status create_tree(ws_context *ctx)
{
    int root = -1, work = -1;
    const char *work_id = dw_text(ctx->store->spec, "work_id");
    golem_status st = ws_directory(ctx->host->worktree_root, &root);
    if (st == GOLEM_OK)
        st = dw_dir(root, work_id, true, &work);
    if (work >= 0)
        close(work);
    if (root >= 0)
        close(root);
    const char *args[] = {"worktree", "add", "--detach", "--no-checkout", "--lock", "--reason",
        dw_text(ctx->intent, "nonce"), ctx->path, dw_text(ctx->intent, "base_commit"), NULL};
    golem_supervisor_result result = {0};
    if (st == GOLEM_OK)
        st = ws_git(ctx, ctx->host->repository_root, args, &result);
    /* There is no adoption path after an interrupted add. Only this invocation
     * can establish the nonce and metadata binding for the successful add. */
    const char *metadata[] = {"rev-parse", "--absolute-git-dir", NULL};
    if (st == GOLEM_OK)
        st = ws_git(ctx, ctx->path, metadata, &result);
    char admin[4096];
    if (st == GOLEM_OK) {
        if (!result.output_size || result.output_size >= sizeof(admin) ||
            result.output[result.output_size - 1] != '\n' ||
            memchr(result.output, 0, result.output_size))
            st = GOLEM_ERR_PARSE;
        else {
            memcpy(admin, result.output, result.output_size - 1);
            admin[result.output_size - 1] = 0;
        }
    }
    struct json_object *tree = NULL, *gitdir = NULL, *ready = json_object_new_object();
    if (st == GOLEM_OK)
        st = ws_identity(ctx->path, &tree);
    if (st == GOLEM_OK)
        st = ws_identity(admin, &gitdir);
    if (st == GOLEM_OK && (!ready || !dw_add(ready, "tree", json_object_get(tree)) ||
        !dw_add(ready, "gitdir", json_object_get(gitdir))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    int fd = -1;
    char parent[4096];
    if (st == GOLEM_OK)
        st = ws_join(parent, ctx->common, "worktrees");
    if (st == GOLEM_OK && (strncmp(admin, parent, strlen(parent)) ||
        admin[strlen(parent)] != '/' || !ws_admin_id(admin + strlen(parent) + 1)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        st = ws_directory(admin, &fd);
    if (st == GOLEM_OK) {
        const char *nonce = dw_text(ctx->intent, "nonce");
        st = dw_publish(fd, "golem-owner", (golem_bytes){(const uint8_t *)nonce, strlen(nonce)});
    }
    if (fd >= 0)
        close(fd);
    if (st == GOLEM_OK) {
        ctx->ready = json_object_get(ready);
        st = ws_verify(ctx);
    }
    const char *checkout[] = {"read-tree", "-m", "-u", "HEAD", NULL};
    if (st == GOLEM_OK)
        st = ws_git_policy(ctx);
    if (st == GOLEM_OK)
        st = ws_git(ctx, ctx->path, checkout, &result);
    char head[65];
    if (st == GOLEM_OK)
        st = ws_head(ctx, ctx->path, head);
    if (st == GOLEM_OK && strcmp(head, dw_text(ctx->intent, "base_commit")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        st = ws_append(ctx, ready);
    json_object_put(tree);
    json_object_put(gitdir);
    json_object_put(ready);
    return st;
}

static golem_status remove_tree(ws_context *ctx)
{
    bool clean;
    golem_digest digest;
    char head[65];
    golem_status st = ws_clean(ctx, ctx->path, &clean, &digest);
    if (st == GOLEM_OK && !clean)
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK)
        st = ws_head(ctx, ctx->path, head);
    if (st == GOLEM_OK && strcmp(head, dw_text(ctx->intent, "base_commit")))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK)
        st = ws_cleanup_inventory(ctx);
    struct json_object *empty = json_object_new_object();
    if (st == GOLEM_OK && !empty)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ws_append(ctx, empty);
    golem_supervisor_result result = {0};
    const char *unlock[] = {"worktree", "unlock", ctx->path, NULL};
    const char *remove[] = {"worktree", "remove", ctx->path, NULL};
    if (st == GOLEM_OK)
        st = ws_git(ctx, ctx->host->repository_root, unlock, &result);
    if (st == GOLEM_OK)
        st = ws_git(ctx, ctx->host->repository_root, remove, &result);
    struct stat sb;
    if (st == GOLEM_OK && (lstat(ctx->path, &sb) == 0 || errno != ENOENT))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        st = ws_append(ctx, empty);
    json_object_put(empty);
    return st;
}

golem_status golem_workspace_call(golem_document_store *store,
    const golem_workspace_host *host, golem_workspace_operation operation,
    const char *candidate, const char *base, const golem_digest *evidence,
    golem_workspace_result *out, golem_diagnostic *diagnostic)
{
    if (!store || !host || host->struct_size != sizeof(*host) || host->version != 1 ||
        !host->check || !host->pulse || !ws_id(host->repository_id) || !ws_id(candidate) || !out ||
        !host->repository_root || !host->worktree_root ||
        operation < GOLEM_WORKSPACE_CREATE || operation > GOLEM_WORKSPACE_REMOVE ||
        (operation == GOLEM_WORKSPACE_CREATE ? !ws_oid(base) : base != NULL) ||
        (operation == GOLEM_WORKSPACE_RETAIN ? evidence == NULL : evidence != NULL))
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (!store->writable || store->poisoned)
        return GOLEM_ERR_INVALID_STATE;
    if (!strcmp(dw_text(store->spec, "permission"), "DENY"))
        return GOLEM_ERR_POLICY_DENIED;
    const char *work_id = dw_text(store->spec, "work_id");
    if (!ws_id(work_id))
        return GOLEM_ERR_POLICY_DENIED;
    ws_context ctx = {.store = store, .host = host, .operation = operation,
        .candidate = candidate, .records = -1};
    golem_status st = host->check(host->context, operation, candidate);
    struct json_object *binding = NULL;
    if (st == GOLEM_OK)
        st = registration(&ctx, &binding);
    char parent[4096];
    if (st == GOLEM_OK)
        st = ws_join(parent, host->worktree_root, work_id);
    if (st == GOLEM_OK)
        st = ws_join(ctx.path, parent, candidate);
    if (st == GOLEM_OK)
        st = registered(&ctx, binding, operation == GOLEM_WORKSPACE_CREATE);
    int dir = -1;
    if (st == GOLEM_OK)
        st = dw_dir(store->root, "workspaces", operation == GOLEM_WORKSPACE_CREATE, &dir);
    if (st == GOLEM_OK)
        st = dw_dir(dir, candidate, operation == GOLEM_WORKSPACE_CREATE, &ctx.records);
    if (dir >= 0)
        close(dir);
    if (st == GOLEM_OK)
        st = ws_load(&ctx);
    if (st == GOLEM_OK && ctx.sequence) {
        const char *keys[] = {"registration", "work_id", "candidate", "base_commit", "nonce",
            "main_dirty", "main_status", "runtime_generation"};
        golem_digest status;
        if (!dw_keys(ctx.intent, keys, 8) || !dw_text(ctx.intent, "work_id") ||
            !dw_text(ctx.intent, "candidate") || !ws_oid(dw_text(ctx.intent, "base_commit")) ||
            !dw_text(ctx.intent, "nonce") || strlen(dw_text(ctx.intent, "nonce")) != 32 ||
            strcmp(dw_text(ctx.intent, "work_id"), work_id) ||
            strcmp(dw_text(ctx.intent, "candidate"), candidate) ||
            !json_object_is_type(dw_get(ctx.intent, "main_dirty"), json_type_boolean) ||
            !dw_digest(ctx.intent, "main_status", &status) ||
            dw_uint(ctx.intent, "runtime_generation") > store->runtime_profile_count ||
            !json_object_equal(binding, dw_get(ctx.intent, "registration")))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        if (st == GOLEM_OK) {
            uint64_t size;
            st = golem_evidence_verify(store->cas, &status, &size, NULL);
        }
    }
    if (st == GOLEM_OK && operation == GOLEM_WORKSPACE_CREATE && ctx.sequence)
        st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && operation != GOLEM_WORKSPACE_CREATE && !ctx.sequence)
        st = GOLEM_ERR_INCOMPLETE_WORK;
    if (st == GOLEM_OK && operation == GOLEM_WORKSPACE_CREATE) {
        st = ws_git_policy(&ctx);
        if (st == GOLEM_OK)
            st = initialize(&ctx, binding, base);
        if (st == GOLEM_OK)
            st = create_tree(&ctx);
    } else if (st == GOLEM_OK && (ctx.sequence == 1 || ctx.sequence == 6)) {
        if (operation != GOLEM_WORKSPACE_RESUME)
            st = GOLEM_ERR_INCOMPLETE_WORK;
    } else if (st == GOLEM_OK && ctx.sequence != 7) {
        st = ws_verify(&ctx);
        if (st == GOLEM_OK)
            st = ws_git_policy(&ctx);
        if (st == GOLEM_OK && operation != GOLEM_WORKSPACE_RESUME) {
            unsigned target = operation == GOLEM_WORKSPACE_ACTIVATE ? 3 :
                operation == GOLEM_WORKSPACE_SEAL ? 4 : operation == GOLEM_WORKSPACE_RETAIN ? 5 : 7;
            if (ctx.sequence + 1 != target && !(target == 7 && ctx.sequence == 5))
                st = GOLEM_ERR_INVALID_STATE;
            if (st == GOLEM_OK && operation == GOLEM_WORKSPACE_REMOVE)
                st = remove_tree(&ctx);
            else if (st == GOLEM_OK) {
                struct json_object *data = json_object_new_object();
                if (!data)
                    st = GOLEM_ERR_OUT_OF_MEMORY;
                if (st == GOLEM_OK && evidence) {
                    uint64_t size;
                    st = golem_evidence_verify(store->cas, evidence, &size, NULL);
                    if (st == GOLEM_OK && !dw_add_digest(data, "evidence", evidence))
                        st = GOLEM_ERR_OUT_OF_MEMORY;
                }
                if (st == GOLEM_OK)
                    st = ws_append(&ctx, data);
                json_object_put(data);
            }
        }
    } else if (st == GOLEM_OK && operation != GOLEM_WORKSPACE_RESUME)
        st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) {
        golem_workspace_result result = {.receipt = ctx.last};
        result.state = ctx.sequence == 1 || ctx.sequence == 6 ? GOLEM_WORKSPACE_ATTENTION :
            (golem_workspace_state)ctx.sequence;
        memcpy(result.path, ctx.path, strlen(ctx.path) + 1);
        *out = result;
    }
    if (ctx.records >= 0)
        close(ctx.records);
    json_object_put(ctx.intent);
    json_object_put(ctx.ready);
    json_object_put(binding);
    return dw_report(diagnostic, st, st == GOLEM_OK ? "workspace receipt verified" :
        "workspace refused; preserve paths and receipts, reopen before recovery");
}
