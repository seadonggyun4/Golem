#include "golem/runtime_event.h"
#include <json-c/json.h>
#include <stdio.h>
#include <string.h>

static bool put(struct json_object *o, const char *key, struct json_object *v)
{
    if (o && v && json_object_object_add(o, key, v) == 0)
        return true;
    json_object_put(v);
    return false;
}
static bool str(struct json_object *o, const char *key, const char *v)
{
    return put(o, key, json_object_new_string(v));
}
static bool number(struct json_object *o, const char *key, uint64_t v)
{
    return put(o, key, json_object_new_uint64(v));
}
static bool push(struct json_object *a, struct json_object *v)
{
    if (a && v && json_object_array_add(a, v) == 0)
        return true;
    json_object_put(v);
    return false;
}
static struct json_object *metadata(const golem_runtime_event_page *p)
{
    struct json_object *o = json_object_new_object();
    char cursor[GOLEM_RUNTIME_CURSOR_MAX];
    size_t n;
    if (!o || !number(o, "schema_version", 1) || !str(o, "type", "runtime_event_page") ||
        !str(o, "authority", "DERIVED_ONLY") || !str(o, "privacy", "PRIVATE_REVIEW_REQUIRED") ||
        !number(o, "oldest", p->oldest) || !number(o, "newest", p->newest) ||
        !number(o, "dropped", p->dropped) || !number(o, "missed", p->missed) ||
        !number(o, "count", p->count))
        goto fail;
    if (p->next.sequence) {
        if (golem_runtime_cursor_format(&p->next, cursor, sizeof(cursor), &n) != GOLEM_OK ||
            !str(o, "next", cursor))
            goto fail;
    }
    return o;
fail:
    json_object_put(o);
    return NULL;
}
static struct json_object *record(const golem_runtime_event *e)
{
    struct json_object *o = json_object_new_object();
    char cursor[GOLEM_RUNTIME_CURSOR_MAX];
    size_t n;
    if (!o || golem_runtime_cursor_format(&e->cursor, cursor, sizeof(cursor), &n) != GOLEM_OK ||
        !number(o, "schema_version", e->version) || !str(o, "type", "runtime_event") ||
        !str(o, "authority", "DERIVED_ONLY") || !str(o, "cursor", cursor) ||
        !str(o, "event", golem_runtime_event_name(e->kind)) || !number(o, "event_id", e->kind) ||
        !str(o, "origin",
             e->origin == GOLEM_EVENT_ADMISSION_JOURNAL ? "ADMISSION_JOURNAL"
                                                        : "WORKER_OBSERVATION") ||
        !number(o, "subject", e->subject) || !number(o, "epoch", e->epoch) ||
        !put(o, "status_known", json_object_new_boolean(e->status_known)) ||
        !put(o, "elapsed_known", json_object_new_boolean(e->elapsed_known)))
        goto fail;
    if (e->status_known && !number(o, "status_code", e->status))
        goto fail;
    if (e->elapsed_known && !number(o, "coordinator_elapsed_ns", e->elapsed_ns))
        goto fail;
    return o;
fail:
    json_object_put(o);
    return NULL;
}
static struct json_object *otlp(struct json_object *lines)
{
    struct json_object *root = json_object_new_object(), *resources = json_object_new_array(),
                       *resource = json_object_new_object(), *scopes = json_object_new_array(),
                       *scope = json_object_new_object(), *logs = json_object_new_array();
    bool ok = root && resources && resource && scopes && scope && logs;
    for (size_t i = 0; ok && i < json_object_array_length(lines); ++i) {
        struct json_object *log = json_object_new_object(), *body = json_object_new_object();
        const char *bytes = json_object_to_json_string_ext(json_object_array_get_idx(lines, i),
                                                           JSON_C_TO_STRING_PLAIN);
        ok = log && body && bytes && str(body, "stringValue", bytes) &&
             put(log, "body", json_object_get(body)) &&
             str(log, "eventName", i ? "golem.runtime.diagnostic.v1" : "golem.runtime.page.v1");
        json_object_put(body);
        if (ok)
            ok = push(logs, log);
        else
            json_object_put(log);
    }
    if (ok)
        ok = put(scope, "logRecords", json_object_get(logs)) &&
             push(scopes, json_object_get(scope)) &&
             put(resource, "scopeLogs", json_object_get(scopes)) &&
             push(resources, json_object_get(resource)) &&
             put(root, "resourceLogs", json_object_get(resources));
    json_object_put(resources);
    json_object_put(resource);
    json_object_put(scopes);
    json_object_put(scope);
    json_object_put(logs);
    if (!ok) {
        json_object_put(root);
        return NULL;
    }
    return root;
}
static struct json_object *prov(const golem_runtime_event *events, size_t count,
                                struct json_object *lines, golem_status *status)
{
    *status = GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *root = json_object_new_object(), *prefix = json_object_new_object(),
                       *entities = json_object_new_object(), *relations = json_object_new_object();
    bool ok = root && prefix && entities && relations &&
              str(prefix, "golem", "urn:golem:runtime:") &&
              str(prefix, "prov", "http://www.w3.org/ns/prov#");
    for (size_t i = 0; ok && i <= count; ++i) {
        char key[96], content_digest[65];
        struct json_object *e = json_object_new_object();
        const char *bytes = json_object_to_json_string_ext(json_object_array_get_idx(lines, i),
                                                           JSON_C_TO_STRING_PLAIN);
        /* Content identity keeps overlapping pages mergeable without ordinal collisions. */
        if (e && bytes) {
            golem_digest digest;
            size_t n;
            golem_status st = golem_digest_bytes(
                (golem_bytes){(const uint8_t *)bytes, strlen(bytes)}, &digest);
            if (st == GOLEM_OK)
                st = golem_digest_format(&digest, content_digest, sizeof(content_digest), &n);
            if (st != GOLEM_OK) {
                *status = st;
                json_object_put(e);
                ok = false;
                break;
            }
            (void)snprintf(key, sizeof(key), "golem:projection_v1_%s", content_digest);
        }
        ok = e && bytes && str(e, "golem:authority", "DERIVED_ONLY") &&
             str(e, "golem:diagnostic", bytes);
        if (ok)
            ok = put(entities, key, e);
        else
            json_object_put(e);
        if (ok && i && events[i - 1].origin == GOLEM_EVENT_ADMISSION_JOURNAL) {
            char source[96], relation[96], digest[65];
            size_t n;
            (void)golem_digest_format(&events[i - 1].cursor.anchor, digest, sizeof(digest), &n);
            (void)snprintf(source, sizeof(source), "golem:journal_v1_%s", digest);
            (void)snprintf(relation, sizeof(relation), "golem:derivation_v1_%s", content_digest);
            struct json_object *src = json_object_new_object(), *r = json_object_new_object();
            ok = src && r &&
                 golem_digest_format(&events[i - 1].cursor.anchor, digest, sizeof(digest), &n) ==
                     GOLEM_OK &&
                 str(src, "golem:journalRecordDigest", digest) &&
                 str(src, "golem:verification", "VERIFY_ORIGINAL_JOURNAL_INDEPENDENTLY") &&
                 str(r, "prov:generatedEntity", key) && str(r, "prov:usedEntity", source) &&
                 put(entities, source, json_object_get(src)) &&
                 put(relations, relation, json_object_get(r));
            json_object_put(src);
            json_object_put(r);
        }
    }
    if (ok)
        ok = put(root, "prefix", json_object_get(prefix)) &&
             put(root, "entity", json_object_get(entities)) &&
             put(root, "wasDerivedFrom", json_object_get(relations));
    json_object_put(prefix);
    json_object_put(entities);
    json_object_put(relations);
    if (!ok) {
        json_object_put(root);
        return NULL;
    }
    *status = GOLEM_OK;
    return root;
}
golem_status golem_runtime_events_export(const golem_runtime_event *events,
                                         const golem_runtime_event_page *page,
                                         golem_runtime_event_format format, void *buffer,
                                         size_t capacity, size_t *required)
{
    if (!page || !required || (!buffer && capacity) || page->count > GOLEM_RUNTIME_EVENT_PAGE_MAX ||
        (page->count && !events) || format < GOLEM_RUNTIME_EVENTS_JSONL ||
        format > GOLEM_RUNTIME_EVENTS_PROV)
        return GOLEM_ERR_INVALID_ARGUMENT;
    for (size_t i = 0; i < page->count; ++i) {
        const golem_runtime_event *e = &events[i];
        if (e->version != 1 || !golem_runtime_event_name(e->kind) || !e->cursor.sequence ||
            e->cursor.sequence < page->oldest || e->cursor.sequence > page->newest ||
            memcmp(&e->cursor.stream, &page->next.stream, sizeof(e->cursor.stream)) ||
            (i && (events[i - 1].cursor.sequence == UINT64_MAX ||
                   e->cursor.sequence != events[i - 1].cursor.sequence + 1)) ||
            (e->origin != GOLEM_EVENT_ADMISSION_JOURNAL &&
             e->origin != GOLEM_EVENT_WORKER_OBSERVATION) ||
            (e->origin == GOLEM_EVENT_ADMISSION_JOURNAL && (e->elapsed_known || e->status_known)) ||
            (e->status_known && (e->status < GOLEM_OK || e->status > GOLEM_ERR_QUEUE_FULL)))
            return GOLEM_ERR_INVALID_ARGUMENT;
    }
    if (page->count && (events[page->count - 1].cursor.sequence != page->next.sequence ||
                        memcmp(&events[page->count - 1].cursor.anchor, &page->next.anchor,
                               sizeof(page->next.anchor))))
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *lines = json_object_new_array(), *mapped = NULL;
    bool ok = lines && push(lines, metadata(page));
    for (size_t i = 0; ok && i < page->count; ++i)
        ok = push(lines, record(&events[i]));
    golem_status mapping_status = GOLEM_ERR_OUT_OF_MEMORY;
    if (ok && format != GOLEM_RUNTIME_EVENTS_JSONL) {
        mapped = format == GOLEM_RUNTIME_EVENTS_OTLP
                     ? otlp(lines)
                     : prov(events, page->count, lines, &mapping_status);
        ok = mapped != NULL;
    }
    golem_status st = ok ? GOLEM_OK : mapping_status;
    size_t total = 0;
    if (st == GOLEM_OK) {
        size_t count = mapped ? 1 : json_object_array_length(lines);
        for (size_t i = 0; i < count; ++i) {
            const char *bytes = json_object_to_json_string_ext(
                mapped ? mapped : json_object_array_get_idx(lines, i), JSON_C_TO_STRING_PLAIN);
            if (!bytes) {
                st = GOLEM_ERR_OUT_OF_MEMORY;
                break;
            }
            total += strlen(bytes) + 1;
        }
        if (st == GOLEM_OK) {
            *required = total;
            if (capacity < total)
                st = GOLEM_ERR_BUFFER_TOO_SMALL;
            else {
                size_t offset = 0;
                for (size_t i = 0; i < count; ++i) {
                    const char *bytes = json_object_to_json_string_ext(
                        mapped ? mapped : json_object_array_get_idx(lines, i),
                        JSON_C_TO_STRING_PLAIN);
                    size_t n = strlen(bytes);
                    memcpy((uint8_t *)buffer + offset, bytes, n);
                    offset += n;
                    ((uint8_t *)buffer)[offset++] = '\n';
                }
            }
        }
    }
    json_object_put(mapped);
    json_object_put(lines);
    return st;
}
