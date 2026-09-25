#ifndef GOLEM_CANDIDATE_INTERNAL_H
#define GOLEM_CANDIDATE_INTERNAL_H
#include "golem/candidate.h"
#include "../execution/internal.h"
#include "../workspace/internal.h"
#define CF_EVENTS 128u
typedef struct cf_context {
    golem_document_store *parent;
    const golem_candidate_host *host;
    golem_admission *admission;
    golem_bytes request_bytes;
    struct json_object *request, *manifest, *members[GOLEM_CANDIDATE_MAX], *selection;
    golem_digest last;
    unsigned sequence;
    int dir;
    bool exported;
} cf_context;
golem_status cf_model(struct json_object *manifest);
golem_status cf_load(cf_context *ctx);
golem_status cf_append(cf_context *ctx, const char *action, size_t index, struct json_object *data);
golem_status cf_apply(cf_context *ctx, const char *action, size_t index, struct json_object *data);
golem_status cf_enroll(cf_context *ctx, size_t index, struct json_object **out);
golem_status cf_member(cf_context *ctx, size_t index, golem_candidate_member *out);
golem_status cf_budget(cf_context *ctx, size_t index);
golem_status cf_report(cf_context *ctx, bool compare, struct json_object **out);
const char *cf_decision_v1(bool comparable, size_t passes);
golem_status cf_qa(golem_document_store *store, const golem_digest *qa, const char *root,
                   const char *base, golem_digest *gates, struct json_object **record);
golem_status cf_target(cf_context *ctx, size_t index, struct json_object **out);
golem_status cf_patch_identity(golem_document_store *selected_store, struct json_object *selected,
                               golem_document_store *target_store, struct json_object *target,
                               golem_digest *out);
golem_status cf_cohort(cf_context *ctx, struct json_object *report, struct json_object **out);
golem_status cf_cohort_check(golem_document_store *parent, struct json_object *manifest);
struct json_object *cf_spec(cf_context *ctx, size_t index);
const char *cf_state(cf_context *ctx, size_t index);
void cf_operation(cf_context *ctx, size_t index, char out[64]);
golem_status cf_ticket(cf_context *ctx, size_t index, golem_admission_ticket *out);
struct json_object *cf_token(const golem_admission_token *token);
bool cf_token_equal(struct json_object *object, const golem_admission_token *token);
bool cf_held(const char *state);
golem_status cf_diff_call(cf_context *ctx, size_t index, struct json_object **out);
golem_status cf_review_check(cf_context *ctx, size_t index);
golem_status cf_diff_validate(cf_context *ctx, size_t index, struct json_object *data);
golem_status cf_diff_inventory(golem_document_store *store, struct json_object *snapshot,
                               struct json_object **out);
golem_status cf_diff_content(cf_context *ctx, const golem_candidate_member *member,
                             const char *path_hex, struct json_object *entry, bool live,
                             size_t *remaining, struct json_object **out);
#endif
