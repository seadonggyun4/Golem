#ifndef GOLEM_DOCUMENT_INTERNAL_H
#define GOLEM_DOCUMENT_INTERNAL_H
#include "golem/document.h"
#include "../common/json.h"
#include "golem/research.h"
#define DW_FRAME 80
#define DW_PATH 4096
typedef struct dw_entry {
    struct json_object *meta;
    golem_document_result result;
    golem_digest request_digest;
    char key[GOLEM_DOCUMENT_ID_CAPACITY];
} dw_entry;
struct golem_document_store {
    golem_allocator allocator;
    int root, events;
    bool writable, poisoned;
    golem_evidence_store *cas;
    struct json_object *spec;
    dw_entry *entries;
    size_t count, edges;
    size_t event_count, reentry_count;
    struct json_object *reentries[64];
    golem_digest reentry_digests[64];
    size_t completion_count;
    struct json_object *completions[64];
    golem_digest completion_digests[64];
    size_t research_count;
    struct json_object *research[GOLEM_RESEARCH_MAX_EVENTS];
    golem_digest research_digests[GOLEM_RESEARCH_MAX_EVENTS];
    golem_digest research_frames[GOLEM_RESEARCH_MAX_EVENTS];
    size_t runtime_profile_count;
    struct json_object *runtime_profiles[64];
    size_t runtime_link_count;
    struct json_object *runtime_links[256];
    golem_digest runtime_link_digests[256];
    size_t admission_link_count;
    struct json_object *admission_links[256];
    golem_digest admission_link_digests[256];
    golem_digest last;
};
struct json_object *dw_get(struct json_object *o, const char *key);
const char *dw_text(struct json_object *o, const char *key);
uint64_t dw_uint(struct json_object *o, const char *key);
bool dw_id(const char *s);
bool dw_keys(struct json_object *o, const char *const *keys, size_t count);
bool dw_digest(struct json_object *o, const char *key, golem_digest *out);
bool dw_equal(const golem_digest *a, const golem_digest *b);
golem_status dw_report(golem_diagnostic *d, golem_status s, const char *message);
golem_status dw_spec(golem_bytes b, struct json_object **out);
golem_status dw_meta(golem_bytes b, struct json_object **out);
golem_status dw_markdown(struct json_object *meta, golem_bytes b);
golem_status dw_read_at(int dir, const char *name, size_t limit, uint8_t **out, size_t *size);
/* Store-scoped scratch memory never escapes into public reply buffers. */
golem_status dw_scratch(golem_document_store *store, size_t size, uint8_t **out);
void dw_scratch_free(golem_document_store *store, void *memory);
golem_status dw_dir(int parent, const char *name, bool create, int *out);
golem_status dw_publish(int dir, const char *name, golem_bytes bytes);
golem_status dw_event_write(golem_document_store *s, const golem_digest *payload,
                            golem_digest *frame);
golem_status dw_replay(golem_document_store *s);
golem_status dw_apply(golem_document_store *s, struct json_object *event,
                      const golem_digest *payload, const golem_digest *frame);
golem_status dw_preconditions(golem_document_store *s, struct json_object *meta);
dw_entry *dw_find(golem_document_store *s, const char *id, uint32_t revision);
golem_status dw_project(golem_document_store *s, dw_entry *entry, bool create);
golem_status dw_cas_json(golem_document_store *s, const golem_digest *key,
                         struct json_object **out);
golem_status dw_put_json(golem_document_store *s, struct json_object *o, golem_digest *out);
bool dw_add(struct json_object *o, const char *key, struct json_object *value);
bool dw_add_digest(struct json_object *o, const char *key, const golem_digest *digest);
golem_status ga_work_apply(golem_document_store *store, struct json_object *event,
                           const golem_digest *payload, const golem_digest *frame);
#endif
