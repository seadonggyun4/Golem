#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include <dirent.h>
#include <fcntl.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void frame(uint8_t b[80], uint64_t seq, const golem_digest *prev,
                  const golem_digest *payload)
{
    memcpy(b, "GWAGN001", 8);
    for (unsigned i = 0; i < 8; ++i)
        b[8 + i] = (uint8_t)(seq >> (8 * i));
    memcpy(b + 16, prev->bytes, 32);
    memcpy(b + 48, payload->bytes, 32);
}
static golem_status validate(golem_document_store *s, as_log *l, struct json_object *e)
{
    golem_digest boot;
    if (!dw_digest(e, "boot_id", &boot))
        return GOLEM_ERR_PARSE;
    golem_digest spec, expected;
    const char *spec_bytes = json_object_to_json_string_ext(s->spec, JSON_C_TO_STRING_PLAIN);
    if (!spec_bytes)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status identity =
        golem_digest_bytes((golem_bytes){(const uint8_t *)spec_bytes, strlen(spec_bytes)}, &spec);
    if (identity != GOLEM_OK)
        return identity;
    if (!dw_digest(e, "work_spec_digest", &expected) || !dw_equal(&spec, &expected))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    const char *op = dw_text(e, "operation");
    uint64_t now = dw_uint(e, "observed_ms");
    struct json_object *d = dw_get(e, "data"), *a = dw_get(l->state, "active");
    if (l->sequence && strcmp(op, "resume") != 0 &&
        (!dw_equal(&boot, &l->boot) || now < l->observed_ms))
        return GOLEM_ERR_STALE_RESULT;
    if (strcmp(op, "begin") == 0 || strcmp(op, "heartbeat") == 0 || strcmp(op, "submit") == 0 ||
        strcmp(op, "reconcile") == 0)
        if (!as_live(l, now, &boot))
            return GOLEM_ERR_STALE_RESULT;
    if (strcmp(op, "resume") == 0 && as_live(l, now, &boot) &&
        strcmp(dw_text(a, "session_id"), dw_text(d, "session_id")) != 0)
        return GOLEM_ERR_JOURNAL_BUSY;
    if (strcmp(op, "claim") == 0) {
        golem_digest key;
        struct json_object *m = NULL;
        if (!dw_digest(d, "manifest_digest", &key))
            return GOLEM_ERR_PARSE;
        if (!dw_digest(d, "policy_digest", &expected) || !dw_equal(&expected, &spec))
            return GOLEM_ERR_IDENTITY_MISMATCH;
        golem_status st = dw_cas_json(s, &key, &m);
        if (st == GOLEM_OK &&
            ((dw_uint(m, "schema_version") != 1 && dw_uint(m, "schema_version") != 2) ||
             dw_uint(m, "generation") != dw_uint(d, "input_generation") ||
             strcmp(dw_text(m, "work_id"), dw_text(s->spec, "work_id")) != 0 ||
             strcmp(dw_text(m, "target_kind"), dw_text(d, "kind")) != 0 ||
             strcmp(dw_text(m, "source_snapshot"), dw_text(d, "source_snapshot")) != 0))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        json_object_put(m);
        if (st != GOLEM_OK)
            return st;
    }
    if (strcmp(op, "submit") == 0 || strcmp(op, "reconcile") == 0) {
        if (dw_get(d, "output") && !wf_resolve(s, dw_get(d, "output")))
            return GOLEM_ERR_IDENTITY_MISMATCH;
        struct json_object *evidence = dw_get(d, "evidence");
        if (!json_object_is_type(evidence, json_type_array))
            return GOLEM_ERR_PARSE;
        for (size_t i = 0; i < json_object_array_length(evidence); ++i) {
            const char *v = json_object_get_string(json_object_array_get_idx(evidence, i));
            golem_digest key;
            uint64_t size;
            if (!v || golem_digest_parse((golem_string_view){v, strlen(v)}, &key) != GOLEM_OK)
                return GOLEM_ERR_PARSE;
            golem_status st = golem_evidence_verify(s->cas, &key, &size, NULL);
            if (st != GOLEM_OK)
                return st;
        }
    }
    return GOLEM_OK;
}
void as_close(as_log *l)
{
    if (l->directory >= 0)
        close(l->directory);
    json_object_put(l->state);
    json_object_put(l->duplicate);
    json_object_put(l->history);
    memset(l, 0, sizeof(*l));
    l->directory = -1;
}
golem_status as_load(golem_document_store *s, const char *key, const golem_digest *request,
                     as_log *l)
{
    memset(l, 0, sizeof(*l));
    l->directory = -1;
    l->history = json_object_new_array();
    if (!l->history)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = dw_dir(s->root, "agent-events", false, &l->directory);
    if (st == GOLEM_ERR_NOT_FOUND)
        return GOLEM_OK;
    if (st != GOLEM_OK)
        return st;
    int scan = openat(l->directory, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (scan < 0)
        return GOLEM_ERR_IO;
    DIR *dir = fdopendir(scan);
    if (!dir) {
        close(scan);
        return GOLEM_ERR_IO;
    }
    struct dirent *v;
    unsigned max = 0, count = 0;
    errno = 0;
    while ((v = readdir(dir)) != NULL) {
        if (strcmp(v->d_name, ".") == 0 || strcmp(v->d_name, "..") == 0 ||
            strncmp(v->d_name, ".pending-", 9) == 0)
            continue;
        unsigned n = 0;
        char tail, name[32];
        if (sscanf(v->d_name, "%8u.evt%c", &n, &tail) != 1 || n < 1 || n > GOLEM_AGENT_MAX_EVENTS) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        (void)snprintf(name, sizeof(name), "%08u.evt", n);
        if (strcmp(name, v->d_name) != 0) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        ++count;
        if (n > max)
            max = n;
    }
    if (errno && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    closedir(dir);
    if (st == GOLEM_OK && count != max)
        st = GOLEM_ERR_MISSING_RECORD;
    char (*keys)[GOLEM_DOCUMENT_ID_CAPACITY] =
        calloc(count ? count : 1, GOLEM_DOCUMENT_ID_CAPACITY);
    if (!keys)
        return GOLEM_ERR_OUT_OF_MEMORY;
    for (unsigned n = 1; st == GOLEM_OK && n <= max; ++n) {
        char name[32];
        (void)snprintf(name, sizeof(name), "%08u.evt", n);
        uint8_t *bytes = NULL, expected[80];
        size_t size = 0;
        golem_digest payload, digest, req;
        st = dw_read_at(l->directory, name, 80, &bytes, &size);
        if (st == GOLEM_OK && size != 80)
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        if (st == GOLEM_OK) {
            memcpy(payload.bytes, bytes + 48, 32);
            frame(expected, n, &l->last, &payload);
            if (memcmp(bytes, expected, 80) != 0)
                st = GOLEM_ERR_CORRUPT_JOURNAL;
        }
        if (st == GOLEM_OK)
            st = golem_digest_bytes((golem_bytes){bytes, size}, &digest);
        struct json_object *e = NULL, *state = NULL;
        if (st == GOLEM_OK)
            st = dw_cas_json(s, &payload, &e);
        if (st == GOLEM_OK)
            st = as_reduce(l->state, e, &state);
        if (st == GOLEM_OK)
            st = validate(s, l, e);
        if (st == GOLEM_OK) {
            const char *k = dw_text(e, "key");
            for (unsigned i = 0; i < n - 1; ++i)
                if (strcmp(keys[i], k) == 0)
                    st = GOLEM_ERR_CORRUPT_JOURNAL;
            if (st == GOLEM_OK)
                strcpy(keys[n - 1], k);
        }
        if (st == GOLEM_OK) {
            json_object_put(l->state);
            l->state = state;
            state = NULL;
            l->sequence = n;
            l->last = digest;
            l->observed_ms = dw_uint(e, "observed_ms");
            (void)dw_digest(e, "boot_id", &l->boot);
            (void)dw_digest(e, "request_digest", &req);
            if (n + 32 > max && !wf_append(l->history, json_object_get(e)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (key && strcmp(key, dw_text(e, "key")) == 0) {
                l->key_conflict = !dw_equal(request, &req);
                l->duplicate = as_receipt(e, l->state);
                if (!l->duplicate)
                    st = GOLEM_ERR_OUT_OF_MEMORY;
            }
        }
        json_object_put(state);
        json_object_put(e);
        free(bytes);
    }
    free(keys);
    return st;
}
golem_status as_commit(golem_document_store *s, as_log *l, struct json_object *e,
                       struct json_object **out)
{
    if (l->sequence >= GOLEM_AGENT_MAX_EVENTS)
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    struct json_object *state = NULL, *receipt = NULL;
    golem_status st = as_reduce(l->state, e, &state);
    if (st == GOLEM_OK)
        st = validate(s, l, e);
    if (st == GOLEM_OK) {
        receipt = as_receipt(e, state);
        if (!receipt)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    const char *serialized =
        st == GOLEM_OK ? json_object_to_json_string_ext(e, JSON_C_TO_STRING_PLAIN) : NULL;
    if (st == GOLEM_OK && (!serialized || strlen(serialized) > AS_EVENT_MAX))
        st = GOLEM_ERR_BUDGET_EXHAUSTED;
    golem_digest payload, digest;
    uint8_t bytes[80];
    char name[32];
    if (st == GOLEM_OK)
        st = dw_put_json(s, e, &payload);
    if (st == GOLEM_OK && l->directory < 0)
        st = dw_dir(s->root, "agent-events", true, &l->directory);
    if (st == GOLEM_OK) {
        frame(bytes, l->sequence + 1, &l->last, &payload);
        st = golem_digest_bytes((golem_bytes){bytes, 80}, &digest);
        (void)snprintf(name, sizeof(name), "%08u.evt", (unsigned)l->sequence + 1);
        if (st == GOLEM_OK)
            st = dw_publish(l->directory, name, (golem_bytes){bytes, 80});
        if (st != GOLEM_OK)
            s->poisoned = true;
    }
    if (st == GOLEM_OK) {
        *out = receipt;
        receipt = NULL;
    }
    json_object_put(receipt);
    json_object_put(state);
    return st;
}
