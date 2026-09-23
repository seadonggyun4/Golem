#ifndef GOLEM_WORKFLOW_INTERNAL_H
#define GOLEM_WORKFLOW_INTERNAL_H
#include "golem/workflow.h"
#include "../document/internal.h"
typedef struct wf_graph {
    golem_dependency_node *nodes;
    size_t *edges;
    golem_document_freshness *states;
    void *memory;
} wf_graph;
golem_status wf_graph_make(golem_document_store *s, wf_graph *out);
void wf_graph_free(golem_document_store *s, wf_graph *g);
golem_status wf_metadata(struct json_object *m);
golem_status wf_preconditions(golem_document_store *s, struct json_object *m);
golem_status wf_selection(golem_document_store *s, struct json_object *m, wf_graph *g);
golem_status wf_manifest(golem_document_store *s, dw_entry *plan, const char *kind,
                         const golem_digest *source, uint64_t budget, wf_graph *g,
                         struct json_object **out);
struct json_object *wf_ref(dw_entry *e);
dw_entry *wf_resolve(golem_document_store *s, struct json_object *ref);
bool wf_reference(struct json_object *r);
bool wf_append(struct json_object *a, struct json_object *v);
int wf_kind(const char *kind);
int wf_stage(int kind);
extern const char *const wf_kinds[8];
extern const char *const wf_stages[6];
golem_status wf_integrity(golem_document_store *s, size_t index, uint64_t *size);
/* Collect the full selected, current dependency closure, without live I/O. */
golem_status wf_completed_documents(golem_document_store *s, const char *id,
                                    struct json_object **out);
golem_status wf_closure(golem_document_store *s, wf_graph *g, const size_t *roots, size_t count,
                        bool *selected);
/* Session adoption reconstructs a pinned input after its output was registered;
 * it must not confuse the next revision target with that historical input. */
golem_status wf_inputs(golem_document_store *s, const char *id, const char *kind,
                       const golem_digest *source, uint64_t budget, void *buffer, size_t capacity,
                       size_t *required, golem_diagnostic *d, bool enforce_reentry);
#endif
