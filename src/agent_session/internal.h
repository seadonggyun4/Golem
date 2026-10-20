#ifndef GOLEM_AGENT_SESSION_INTERNAL_H
#define GOLEM_AGENT_SESSION_INTERNAL_H
#include "golem/agent_session.h"
#include "../workflow/internal.h"
#define AS_EVENT_MAX 16384u
typedef struct as_log {
    int directory;
    uint64_t sequence, observed_ms;
    golem_digest last, boot;
    struct json_object *state, *duplicate, *history;
    bool key_conflict;
    const golem_agent_clock *publication_clock;
    uint64_t publication_observed_ms;
} as_log;
golem_status as_load(golem_document_store *s, const char *key, const golem_digest *request,
                     as_log *log);
void as_close(as_log *log);
golem_status as_reduce(struct json_object *prior, struct json_object *event,
                       struct json_object **out);
golem_status as_commit(golem_document_store *s, as_log *log, struct json_object *event,
                       const golem_agent_clock *clock, struct json_object **receipt);
struct json_object *as_receipt(struct json_object *event, struct json_object *state);
golem_status as_clock_read(const golem_agent_clock *clock, uint64_t *now, golem_digest *boot);
bool as_active(struct json_object *state);
golem_status as_unreceipted(golem_document_store *s, as_log *log);
bool as_token(struct json_object *active, struct json_object *token);
bool as_live(const as_log *log, uint64_t now, const golem_digest *boot);
golem_status as_publication_guard(void *log);
golem_status as_fresh(golem_document_store *s, struct json_object *active, bool output_allowed,
                      struct json_object **manifest);
bool as_rejected(struct json_object *state, const golem_digest *digest);
struct json_object *as_rejection_summary(struct json_object *data);
golem_status as_rejection_shape(struct json_object *state, struct json_object *data, uint64_t sequence);
golem_status as_rejection_validate(golem_document_store *store, struct json_object *state,
                                   struct json_object *data, uint64_t sequence);
golem_status as_rejection_prepare(golem_document_store *store, as_log *log,
                                  struct json_object *request, struct json_object *data);
golem_status as_rejection_graph(golem_document_store *store, wf_graph *graph);
golem_status as_registration_guard(golem_document_store *store, struct json_object *metadata);
#endif
