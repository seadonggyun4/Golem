#define _POSIX_C_SOURCE 200809L
#include "context_internal.h"
#include "../agent_session/internal.h"
#include "golem/system_error.h"
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

typedef struct digest_index {
    golem_digest digest;
    size_t index;
} digest_index;
typedef struct selection_walk {
    digest_index *map;
    size_t count, *queue, write;
    bool *selected;
} selection_walk;
static int compare_digest(const void *a, const void *b)
{
    return memcmp(((const digest_index *)a)->digest.bytes,
                  ((const digest_index *)b)->digest.bytes, GOLEM_DIGEST_SIZE);
}
static void retain(selection_walk *walk, size_t i)
{
    if (!walk->selected[i]) {
        walk->selected[i] = true;
        walk->queue[walk->write++] = i;
    }
}
/* Native schemas use digest strings for references. Unknown/complex structures
 * retain full metadata; authored prose is never scored for relevance. */
static bool references(selection_walk *walk, struct json_object *o, unsigned depth,
                       bool metadata_root)
{
    if (depth > 64)
        return false;
    if (json_object_is_type(o, json_type_string)) {
        const char *text = json_object_get_string(o);
        digest_index key;
        if (strlen(text) == 64 &&
            golem_digest_parse((golem_string_view){text, 64}, &key.digest) == GOLEM_OK) {
            digest_index *found = bsearch(&key, walk->map, walk->count,
                                          sizeof(*walk->map), compare_digest);
            if (found)
                retain(walk, found->index);
        }
    } else if (json_object_is_type(o, json_type_array)) {
        for (size_t i = 0; i < json_object_array_length(o); ++i)
            if (!references(walk, json_object_array_get_idx(o, i), depth + 1, false))
                return false;
    } else if (json_object_is_type(o, json_type_object)) {
        json_object_object_foreach(o, key, value) {
            if (metadata_root && !strcmp(key, "supersedes"))
                continue;
            if (!references(walk, value, depth + 1, false))
                return false;
        }
    }
    return true;
}
static bool archivable(dw_entry *e)
{
    uint64_t version = dw_uint(e->meta, "schema_version");
    const char *kind = dw_text(e->meta, "kind");
    return version == 4 &&
           (!strcmp(kind, "planning") || !strcmp(kind, "ux") ||
            !strcmp(kind, "publishing") || !strcmp(kind, "development-plan"));
}
golem_status cx_history_select(golem_document_store *s, struct json_object *facts,
                               wf_graph *graph, bool *selected, struct json_object **out)
{
    as_log log = {.directory = -1};
    golem_status st = as_load(s, NULL, NULL, &log);
    const char *fallback = NULL;
    uint8_t *memory = NULL;
    if (st == GOLEM_OK && as_active(log.state))
        fallback = "ACTIVE_ATTEMPT";
    if (st == GOLEM_OK && !fallback && log.state && as_unreceipted(s, &log) != GOLEM_OK)
        fallback = "UNSUBMITTED_OUTPUT";
    if (st == GOLEM_OK && !fallback && dw_get(log.state, "rejected_outputs"))
        fallback = "REJECTED_OUTPUT_HISTORY";
    if (!fallback && (s->reentry_count || s->completion_count || s->research_count ||
        s->runtime_profile_count || s->runtime_link_count || s->admission_link_count ||
        s->role_count || s->approval_count))
        fallback = "AUTHORITY_OR_NON_DOCUMENT_HISTORY";
    const char *directories[] = {"execution-policies", "execution-attempts", "execution-receipts"};
    for (size_t i = 0; st == GOLEM_OK && !fallback && i < 3; ++i) {
        struct stat info;
        if (fstatat(s->root, directories[i], &info, AT_SYMLINK_NOFOLLOW) == 0) {
            fallback = "EXECUTION_HISTORY";
            if (!S_ISDIR(info.st_mode))
                st = golem_system_error_note(GOLEM_ERR_INVALID_STATE, "context.selection", "directory_type", 0);
        } else if (errno != ENOENT)
            st = golem_system_error_note(GOLEM_ERR_IO, "context.selection", "fstatat", errno);
    }
    memset(selected, 0, s->count * sizeof(*selected));
    for (size_t i = 0; i < s->count; ++i)
        if (dw_uint(s->entries[i].meta, "schema_version") < 1 ||
            dw_uint(s->entries[i].meta, "schema_version") > 5)
            fallback = "UNKNOWN_METADATA_SCHEMA";
    if (st == GOLEM_OK && !fallback)
        st = dw_scratch(s, s->count * (sizeof(digest_index) + sizeof(size_t)), &memory);
    if (st == GOLEM_OK && !fallback) {
        selection_walk walk = {.map = (digest_index *)memory, .count = s->count,
            .queue = (size_t *)(memory + s->count * sizeof(digest_index)), .selected = selected};
        for (size_t i = 0; i < s->count; ++i) {
            walk.map[i] = (digest_index){s->entries[i].result.manifest_digest, i};
            if (graph->states[i] != GOLEM_DOCUMENT_SUPERSEDED || !archivable(&s->entries[i]))
                retain(&walk, i);
        }
        qsort(walk.map, walk.count, sizeof(*walk.map), compare_digest);
        bool complete = references(&walk, facts, 0, false);
        for (size_t read = 0; complete && read < walk.write; ++read) {
            size_t i = walk.queue[read];
            for (size_t p = 0; p < graph->nodes[i].parent_count; ++p)
                retain(&walk, graph->nodes[i].parents[p]);
            complete = references(&walk, s->entries[i].meta, 0, true);
        }
        if (!complete)
            fallback = "REFERENCE_COMPLEXITY";
    }
    dw_scratch_free(s, memory);
    if (fallback)
        for (size_t i = 0; i < s->count; ++i)
            selected[i] = true;
    struct json_object *summary = json_object_new_object(), *archived = json_object_new_array();
    if (st == GOLEM_OK && (!summary || !archived))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    size_t retained = 0;
    for (size_t i = 0; st == GOLEM_OK && i < s->count; ++i) {
        if (selected[i]) {
            ++retained;
            continue;
        }
        dw_entry *e = &s->entries[i];
        struct json_object *v = wf_ref(e);
        struct json_object *omitted = json_object_new_array();
        bool omitted_ok = omitted && wf_append(omitted, json_object_new_string("input_manifest"));
        if (v) {
            json_object_object_foreach(e->meta, key, value) {
                if (!strcmp(key, "input_manifest") || !strcmp(key, "document_id") || !strcmp(key, "revision"))
                    continue;
                if (!dw_add(v, key, json_object_get(value))) {
                    st = GOLEM_ERR_OUT_OF_MEMORY;
                    break;
                }
            }
        }
        if (!v || !omitted_ok || st != GOLEM_OK ||
            !dw_add_digest(v, "metadata_digest", &e->request_digest) ||
            !dw_add_digest(v, "body_digest", &e->result.body_digest) ||
            !dw_add(v, "omitted_fields", json_object_get(omitted)) ||
            !dw_add(v, "metadata_omitted", json_object_new_boolean(true))) {
            json_object_put(v);
            st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (!wf_append(archived, v))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(omitted);
    }
    if (st == GOLEM_OK &&
        (!dw_add(summary, "schema_version", json_object_new_int(1)) ||
         !dw_add(summary, "mode", json_object_new_string(fallback ? "FULL_FALLBACK" : "CURRENT_DEPENDENCIES")) ||
         !dw_add(summary, "reason", json_object_new_string(fallback ? fallback : "SUPERSEDED_NONDEPENDENCY_PLANS")) ||
         !dw_add(summary, "total_documents", json_object_new_uint64(s->count)) ||
         !dw_add(summary, "retained_metadata", json_object_new_uint64(retained)) ||
         !dw_add(summary, "agent_sequence", json_object_new_uint64(log.sequence)) ||
         !dw_add_digest(summary, "agent_head", &log.last) ||
         !(log.state ? dw_add(summary, "session_checkpoint", json_object_get(log.state))
                     : json_object_object_add(summary, "session_checkpoint", NULL) == 0) ||
         !dw_add(summary, "archived_documents", json_object_get(archived))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(archived);
    as_close(&log);
    if (st == GOLEM_OK)
        *out = summary;
    else
        json_object_put(summary);
    return st;
}
