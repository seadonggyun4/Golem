#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "internal.h"
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char *const roots[] = {"work", "tree", "build", "temp"};
/* Resolve ancestry through descriptors, including the parent Work whose path
 * is intentionally not exposed by the document-store API. */
static golem_status disjoint_ancestor(int root, const struct stat *needle)
{
    int fd = openat(root, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0)
        return GOLEM_ERR_IO;
    golem_status st = GOLEM_ERR_OVERFLOW;
    for (unsigned depth = 0; depth < 1024; ++depth) {
        struct stat here, above;
        if (fstat(fd, &here) != 0) {
            st = GOLEM_ERR_IO;
            break;
        }
        if (here.st_dev == needle->st_dev && here.st_ino == needle->st_ino) {
            st = GOLEM_ERR_IDENTITY_MISMATCH;
            break;
        }
        int next = openat(fd, "..", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
        if (next < 0) {
            st = GOLEM_ERR_IO;
            break;
        }
        if (fstat(next, &above) != 0) {
            close(next);
            st = GOLEM_ERR_IO;
            break;
        }
        close(fd);
        fd = next;
        if (here.st_dev == above.st_dev && here.st_ino == above.st_ino) {
            st = GOLEM_OK;
            break;
        }
    }
    if (close(fd) != 0 && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    return st;
}
static bool overlap(struct json_object *a, struct json_object *b)
{
    if (dw_uint(a, "device") == dw_uint(b, "device") && dw_uint(a, "inode") == dw_uint(b, "inode"))
        return true;
    const char *x = dw_text(a, "path"), *y = dw_text(b, "path");
    size_t nx = strlen(x), ny = strlen(y);
    return (nx <= ny && !memcmp(x, y, nx) && (!y[nx] || y[nx] == '/')) ||
           (ny <= nx && !memcmp(x, y, ny) && (!x[ny] || x[ny] == '/'));
}
golem_status cf_enroll(cf_context *c, size_t i, struct json_object **out)
{
    golem_candidate_member m = {0};
    const char *id = dw_text(cf_spec(c, i), "id");
    golem_status st = c->host->resolve(c->host->context, id, &m);
    golem_digest environment;
    if (st == GOLEM_OK &&
        (!m.work || m.work == c->parent || !m.workspace ||
         !dw_digest(cf_spec(c, i), "environment_digest", &environment) ||
         !dw_equal(&environment, &m.environment) ||
         strcmp(dw_text(m.work->spec, "work_id"), dw_text(cf_spec(c, i), "work_id"))))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    golem_workspace_result workspace = {0};
    if (st == GOLEM_OK)
        st = golem_workspace_call(m.work, m.workspace, GOLEM_WORKSPACE_RESUME, id, NULL, NULL,
                                  &workspace, NULL);
    bool retained =
        !strcmp(cf_state(c, i), "FINISHED") &&
        (workspace.state == GOLEM_WORKSPACE_SEALED || workspace.state == GOLEM_WORKSPACE_RETAINED);
    if (st == GOLEM_OK && workspace.state != GOLEM_WORKSPACE_READY &&
        workspace.state != GOLEM_WORKSPACE_ACTIVE && !retained)
        st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && (!m.tree_root || strcmp(m.tree_root, workspace.path)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK && !c->members[i]) {
        ws_context ctx = {.store = m.work,
                          .host = m.workspace,
                          .operation = GOLEM_WORKSPACE_RESUME,
                          .candidate = id};
        char head[65];
        st = ws_head(&ctx, workspace.path, head);
        if (st == GOLEM_OK && strcmp(head, dw_text(c->manifest, "base_commit")))
            st = GOLEM_ERR_STALE_RESULT;
    }
    const char *paths[] = {m.work_root, workspace.path, m.build_root, m.temp_root};
    struct json_object *data = json_object_new_object(), *identities = json_object_new_object();
    for (size_t k = 0; st == GOLEM_OK && k < 4; ++k) {
        struct json_object *identity = NULL;
        st = paths[k] ? ws_identity(paths[k], &identity) : GOLEM_ERR_INVALID_ARGUMENT;
        if (st == GOLEM_OK && !dw_add(identities, roots[k], identity))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        else if (st != GOLEM_OK)
            json_object_put(identity);
    }
    struct stat actual, parent;
    if (st == GOLEM_OK &&
        (fstat(m.work->root, &actual) != 0 || fstat(c->parent->root, &parent) != 0))
        st = GOLEM_ERR_IO;
    struct json_object *work = dw_get(identities, "work");
    if (st == GOLEM_OK && (dw_uint(work, "device") != (uint64_t)actual.st_dev ||
                           dw_uint(work, "inode") != (uint64_t)actual.st_ino ||
                           (actual.st_dev == parent.st_dev && actual.st_ino == parent.st_ino)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    for (size_t k = 0; st == GOLEM_OK && k < 4; ++k) {
        int fd = -1;
        struct stat identity;
        st = ws_directory(paths[k], &fd);
        if (st == GOLEM_OK && fstat(fd, &identity) != 0)
            st = GOLEM_ERR_IO;
        if (st == GOLEM_OK)
            st = disjoint_ancestor(fd, &parent);
        if (st == GOLEM_OK)
            st = disjoint_ancestor(c->parent->root, &identity);
        if (fd >= 0 && close(fd) != 0 && st == GOLEM_OK)
            st = GOLEM_ERR_IO;
        for (size_t j = 0; j < k; ++j)
            if (overlap(dw_get(identities, roots[k]), dw_get(identities, roots[j])))
                st = GOLEM_ERR_IDENTITY_MISMATCH;
        for (size_t other = 0; other < json_object_array_length(dw_get(c->manifest, "candidates"));
             ++other) {
            if (other == i || !c->members[other])
                continue;
            struct json_object *old = dw_get(dw_get(c->members[other], "enrollment"), "identities");
            for (size_t j = 0; j < 4; ++j)
                if (overlap(dw_get(identities, roots[k]), dw_get(old, roots[j])))
                    st = GOLEM_ERR_IDENTITY_MISMATCH;
        }
    }
    if (st == GOLEM_OK && (!dw_add(data, "identities", json_object_get(identities)) ||
                           !dw_add_digest(data, "workspace_receipt", &workspace.receipt)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(identities);
    if (st == GOLEM_OK)
        *out = data;
    else
        json_object_put(data);
    return st;
}
golem_status cf_member(cf_context *c, size_t i, golem_candidate_member *out)
{
    if (!c->members[i])
        return GOLEM_ERR_INVALID_STATE;
    struct json_object *current = NULL;
    golem_status st = cf_enroll(c, i, &current);
    if (st == GOLEM_OK &&
        !json_object_equal(dw_get(current, "identities"),
                           dw_get(dw_get(c->members[i], "enrollment"), "identities")))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    json_object_put(current);
    if (st == GOLEM_OK)
        st = c->host->resolve(c->host->context, dw_text(cf_spec(c, i), "id"), out);
    return st;
}

golem_status cf_budget(cf_context *c, size_t next)
{
    const char *dims[] = {"workers", "cpu", "memory", "io", "tokens", "nano_cost"};
    struct json_object *limits = dw_get(c->manifest, "limits"),
                       *desired = dw_get(cf_spec(c, next), "resources");
    for (size_t k = 0; k < 6; ++k) {
        uint64_t used = k == 0 ? 1 : dw_uint(desired, dims[k]);
        uint64_t limit = dw_uint(limits, dims[k]);
        for (size_t i = 0; i < json_object_array_length(dw_get(c->manifest, "candidates")); ++i) {
            if (i == next || !c->members[i] || !strcmp(cf_state(c, i), "READY"))
                continue;
            struct json_object *r = dw_get(cf_spec(c, i), "resources");
            uint64_t value = 0;
            if (k < 4)
                value = cf_held(cf_state(c, i)) ? (k == 0 ? 1 : dw_uint(r, dims[k])) : 0;
            else {
                struct json_object *actual = dw_get(c->members[i], "result");
                const char *known = k == 4 ? "tokens_known" : "cost_known";
                value = actual && json_object_get_boolean(dw_get(actual, known))
                            ? dw_uint(actual, dims[k])
                            : dw_uint(r, dims[k]);
                if (value > dw_uint(r, dims[k]))
                    return GOLEM_ERR_BUDGET_EXHAUSTED;
            }
            if (used > limit || value > limit - used)
                return GOLEM_ERR_BUDGET_EXHAUSTED;
            used += value;
        }
        if (used > limit)
            return GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    return GOLEM_OK;
}
