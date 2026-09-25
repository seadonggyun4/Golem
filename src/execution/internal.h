#ifndef GOLEM_EXECUTION_INTERNAL_H
#define GOLEM_EXECUTION_INTERNAL_H
#include "golem/execution.h"
#include "../workflow/internal.h"
#include "../discovery/internal.h"
#include "golem/supervisor.h"
typedef struct ex_log_capture {
    golem_document_store *store;
    struct evp_md_ctx_st *hash[2];
    uint8_t *retained[2];
    size_t size[2], cap;
    uint64_t observed[2];
    bool keep;
} ex_log_capture;
golem_status ex_retention(struct json_object *policy);
golem_status ex_logs_open(golem_document_store *store, struct json_object *policy,
                          ex_log_capture *out);
golem_status ex_logs_write(void *context, unsigned stream, golem_bytes chunk);
golem_status ex_logs_finish(ex_log_capture *capture, const golem_supervisor_capture *observed,
                            struct json_object **out, bool *complete);
void ex_logs_close(ex_log_capture *capture);
golem_status ex_logs_verify(golem_document_store *store, struct json_object *gate,
                            struct json_object *policy);
golem_status ex_bundle_build(golem_document_store *store, const golem_digest *key,
                             struct json_object *qa, struct json_object **out);
golem_status ex_bundle_check(golem_document_store *store, const golem_digest *key,
                             struct json_object *qa, bool publish);
golem_status ex_contract(struct json_object *o);
golem_status ex_command_validate(struct json_object *gate, struct json_object *repo);
golem_status ex_command_check(struct json_object *gate, struct json_object *plan);
golem_status ex_command_approve(struct json_object *contract, const golem_digest *shell);
golem_status ex_snapshot(golem_document_store *store, struct json_object *plan, bool publish,
                         struct json_object **out);
/* Typed, bounded CAS references. Read-only capture hashes without publishing. */
golem_status ex_object_ref(golem_document_store *store, struct json_object *object,
                           const char *type, size_t limit, bool publish, struct json_object **out);
golem_status ex_inventory_load(golem_document_store *store, struct json_object *repo,
                               struct json_object **out);
golem_status ex_snapshot_verify(golem_document_store *store, struct json_object *snapshot);
golem_status ex_inventory_check(golem_document_store *store, struct json_object *checkpoint,
                                struct json_object *snapshot, bool publish);
golem_status ex_inputs(golem_document_store *s, struct json_object *contract, const char *kind,
                       struct json_object **out);
golem_status ex_current(golem_document_store *s, struct json_object *manifest);
golem_status ex_load(golem_document_store *s, const golem_digest *key, const char *type,
                     struct json_object **out);
golem_status ex_markdown(golem_document_store *s, struct json_object *meta,
                         golem_execution_reply *out);
golem_status ex_document(golem_document_store *s, struct json_object *meta, golem_bytes body);
golem_status ex_live(golem_document_store *s, struct json_object *meta);
golem_status ex_pass(golem_document_store *s, struct json_object *meta);
golem_status ex_required(golem_document_store *s, struct json_object *meta);
golem_status ex_authorize(golem_document_store *s, struct json_object *token,
                          struct json_object *manifest);
struct ap_dispatch;
golem_status ex_execute(golem_document_store *s, struct json_object *checkpoint,
                        const golem_digest *checkpoint_digest, struct json_object *manifest,
                        const char *attempt, struct json_object *token,
                        struct ap_dispatch *approval, struct json_object **out);
bool ex_text(struct json_object *o, const char *key, const char *text);
bool ex_uint(struct json_object *o, const char *key, uint64_t n);
golem_status ex_emit(struct json_object *o, golem_execution_reply *out);
golem_status ex_hash(struct json_object *o, golem_digest *out);
#endif
