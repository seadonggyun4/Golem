#ifndef GOLEM_WORKSPACE_INTERNAL_H
#define GOLEM_WORKSPACE_INTERNAL_H
#include "golem/workspace.h"
#include "golem/supervisor.h"
#include "../document/internal.h"

typedef struct ws_context {
    golem_document_store *store;
    const golem_workspace_host *host;
    golem_workspace_operation operation;
    const char *candidate;
    char path[4096], common[4096];
    int records;
    unsigned sequence;
    golem_digest last;
    struct json_object *intent, *ready;
} ws_context;
bool ws_id(const char *s);
bool ws_admin_id(const char *s);
bool ws_oid(const char *s);
golem_status ws_join(char out[4096], const char *parent, const char *child);
golem_status ws_directory(const char *path, int *out);
golem_status ws_identity(const char *path, struct json_object **out);
golem_status ws_git(ws_context *ctx, const char *cwd, const char *const args[],
                    golem_supervisor_result *out);
golem_status ws_git_policy(ws_context *ctx);
golem_status ws_git_bulk(ws_context *ctx, const char *cwd, const char *const args[],
    const golem_supervisor_stream *stream, uint64_t stdout_limit);
golem_status ws_head(ws_context *ctx, const char *cwd, char out[65]);
golem_status ws_clean(ws_context *ctx, const char *cwd, bool *clean,
                      golem_digest *status_digest);
golem_status ws_load(ws_context *ctx);
golem_status ws_append(ws_context *ctx, struct json_object *data);
golem_status ws_verify(ws_context *ctx);
golem_status ws_cleanup_inventory(ws_context *ctx);
#endif
