#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include "../agent_session/internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Inspect durable dispatch markers, never retry them. Every completed dispatch
 * must have a registered result, even when a later attempt passed. */
static golem_status attempts(golem_document_store *s, struct json_object *a, const char **action)
{
    int fd = -1;
    golem_status st = dw_dir(s->root, "execution-attempts", false, &fd);
    if (st == GOLEM_ERR_NOT_FOUND)
        return GOLEM_OK;
    if (st != GOLEM_OK)
        return st;
    int scan = openat(fd, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    DIR *dir = scan < 0 ? NULL : fdopendir(scan);
    if (!dir) {
        if (scan >= 0)
            close(scan);
        close(fd);
        return GOLEM_ERR_IO;
    }
    size_t count = 0;
    struct dirent *e;
    while (st == GOLEM_OK) {
        errno = 0;
        e = readdir(dir);
        if (!e) {
            if (errno)
                st = GOLEM_ERR_IO;
            break;
        }
        const char *name = e->d_name;
        size_t n = strlen(name);
        if (!strcmp(name, ".") || !strcmp(name, "..") || !strncmp(name, ".pending-", 9))
            continue;
        if (++count > 1024) {
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
            break;
        }
        bool started = n > 8 && !strcmp(name + n - 8, ".started"),
             done = n > 5 && !strcmp(name + n - 5, ".done");
        if (!started && !done) {
            if (n == 81 && !strncmp(name, "reentry-", 8) && !strcmp(name + 72, ".dispatch"))
                continue;
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        size_t len = n - (started ? 8 : 5);
        char id[GOLEM_DOCUMENT_ID_CAPACITY], other[96];
        if (len >= sizeof(id)) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        memcpy(id, name, len);
        id[len] = 0;
        if (!dw_id(id)) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        uint8_t *bytes = NULL;
        size_t size = 0;
        st = dw_read_at(fd, name, 32, &bytes, &size);
        free(bytes);
        bytes = NULL;
        if (st == GOLEM_OK && size != 32)
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        (void)snprintf(other, sizeof(other), "%s.%s", id, started ? "done" : "started");
        if (st != GOLEM_OK)
            break;
        golem_status counterpart = dw_read_at(fd, other, 32, &bytes, &size);
        if (counterpart == GOLEM_ERR_NOT_FOUND && !started)
            st = GOLEM_ERR_MISSING_RECORD;
        else if (counterpart != GOLEM_OK && counterpart != GOLEM_ERR_NOT_FOUND)
            st = counterpart;
        else if (counterpart == GOLEM_OK && size != 32)
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        if (st != GOLEM_OK || !started) {
            free(bytes);
            continue;
        }
        const char *state = "RECONCILE_EXECUTION";
        struct json_object *result = NULL;
        if (counterpart == GOLEM_OK) {
            golem_digest key;
            memcpy(key.bytes, bytes, 32);
            st = ex_load(s, &key, "qa", &result);
            /* A done marker without issuance is recoverable only by the
             * original execution call; completion cannot invent issuance. */
            if (st == GOLEM_ERR_NOT_FOUND) {
                st = GOLEM_OK;
                state = "RECOVER_EXECUTION_RECEIPT";
            } else if (st == GOLEM_OK) {
                if (strcmp(dw_text(result, "attempt_id"), id))
                    st = GOLEM_ERR_IDENTITY_MISMATCH;
                struct json_object *identity = json_object_new_object();
                golem_digest expected;
                if (!dw_add(identity, "checkpoint",
                            json_object_get(dw_get(result, "checkpoint"))) ||
                    !dw_add(identity, "manifest", json_object_get(dw_get(result, "manifest"))))
                    st = GOLEM_ERR_OUT_OF_MEMORY;
                if (st == GOLEM_OK)
                    st = ex_hash(identity, &expected);
                json_object_put(identity);
                uint8_t *start = NULL;
                size_t start_size = 0;
                if (st == GOLEM_OK)
                    st = dw_read_at(fd, name, 32, &start, &start_size);
                if (st == GOLEM_OK && (start_size != 32 || memcmp(start, expected.bytes, 32)))
                    st = GOLEM_ERR_IDENTITY_MISMATCH;
                free(start);
                bool submitted = false;
                for (size_t i = 0; i < s->count; ++i) {
                    golem_digest recorded;
                    if (!strcmp(dw_text(s->entries[i].meta, "kind"), "qa-result") &&
                        dw_digest(s->entries[i].meta, "execution_receipt", &recorded) &&
                        dw_equal(&key, &recorded))
                        submitted = true;
                }
                state = submitted ? "SUBMITTED" : "SUBMIT_RESULT";
            }
        }
        free(bytes);
        json_object_put(result);
        if (st == GOLEM_OK) {
            struct json_object *item = json_object_new_object();
            if (!ex_text(item, "attempt_id", id) || !ex_text(item, "state", state)) {
                json_object_put(item);
                st = GOLEM_ERR_OUT_OF_MEMORY;
            } else if (!wf_append(a, item))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (strcmp(state, "SUBMITTED"))
                *action = "RECONCILE_EXECUTION";
        }
    }
    if (closedir(dir) < 0 && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    close(fd);
    return st;
}
static int by_attempt(const void *a, const void *b)
{
    const struct json_object *const *x = a, *const *y = b;
    return strcmp(dw_text((struct json_object *)*x, "attempt_id"),
                  dw_text((struct json_object *)*y, "attempt_id"));
}
/* A recorded completion is also a lower bound on retained local execution
 * history. Deleting an entire side journal must not look like an empty Work. */
golem_status co_boundary_verify(golem_document_store *s, struct json_object *boundary)
{
    uint64_t seq = dw_uint(boundary, "session_sequence");
    int dir = -1;
    golem_status st = GOLEM_OK;
    if (seq) {
        st = dw_dir(s->root, "agent-events", false, &dir);
        char name[32];
        (void)snprintf(name, sizeof(name), "%08u.evt", (unsigned)seq);
        uint8_t *bytes = NULL;
        size_t size = 0;
        golem_digest actual, expected;
        if (st == GOLEM_OK)
            st = dw_read_at(dir, name, 80, &bytes, &size);
        if (st == GOLEM_OK && size != 80)
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        if (st == GOLEM_OK)
            st = golem_digest_bytes((golem_bytes){bytes, size}, &actual);
        if (st == GOLEM_OK &&
            (!dw_digest(boundary, "session_head", &expected) || !dw_equal(&actual, &expected)))
            st = GOLEM_ERR_DIGEST_MISMATCH;
        free(bytes);
        if (dir >= 0)
            close(dir);
        dir = -1;
    }
    struct json_object *a = dw_get(boundary, "attempts");
    if (st == GOLEM_OK && json_object_array_length(a))
        st = dw_dir(s->root, "execution-attempts", false, &dir);
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(a); ++i) {
        const char *id = dw_text(json_object_array_get_idx(a, i), "attempt_id");
        char name[96];
        uint8_t *bytes = NULL;
        size_t size = 0;
        golem_digest key, expected;
        (void)snprintf(name, sizeof(name), "%s.done", id);
        st = dw_read_at(dir, name, 32, &bytes, &size);
        if (st == GOLEM_OK && size != 32)
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        if (st == GOLEM_OK)
            memcpy(key.bytes, bytes, 32);
        free(bytes);
        bytes = NULL;
        struct json_object *result = NULL, *identity = json_object_new_object();
        if (st == GOLEM_OK)
            st = ex_load(s, &key, "qa", &result);
        if (st == GOLEM_OK && strcmp(dw_text(result, "attempt_id"), id))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        if (st == GOLEM_OK &&
            (!dw_add(identity, "checkpoint", json_object_get(dw_get(result, "checkpoint"))) ||
             !dw_add(identity, "manifest", json_object_get(dw_get(result, "manifest")))))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK)
            st = ex_hash(identity, &expected);
        (void)snprintf(name, sizeof(name), "%s.started", id);
        if (st == GOLEM_OK)
            st = dw_read_at(dir, name, 32, &bytes, &size);
        if (st == GOLEM_OK && (size != 32 || memcmp(bytes, expected.bytes, 32)))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        free(bytes);
        json_object_put(result);
        json_object_put(identity);
    }
    if (dir >= 0)
        close(dir);
    return st;
}
golem_status co_quiescent(golem_document_store *s, const char **action,
                          struct json_object **boundary)
{
    *action = NULL;
    as_log log = {.directory = -1};
    golem_status st = as_load(s, NULL, NULL, &log);
    if (st == GOLEM_OK && as_active(log.state)) {
        uint64_t now;
        golem_digest boot;
        st = as_clock_read(NULL, &now, &boot);
        if (st == GOLEM_OK)
            *action =
                as_live(&log, now, &boot) &&
                        strcmp(dw_text(dw_get(log.state, "active"), "state"), "RECOVERY_REQUIRED")
                    ? "WAIT"
                    : "RECONCILE_SESSION";
    }
    if (st == GOLEM_OK && !*action && log.state && as_unreceipted(s, &log) != GOLEM_OK)
        *action = "RECONCILE_SESSION";
    struct json_object *o = json_object_new_object(), *a = json_object_new_array();
    if (!o || !a)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = attempts(s, a, action);
    if (st == GOLEM_OK) {
        json_object_array_sort(a, by_attempt);
        if (!ex_uint(o, "session_sequence", log.sequence) ||
            !dw_add_digest(o, "session_head", &log.last) ||
            json_object_object_add(o, "session", json_object_get(log.state)) != 0 ||
            !dw_add(o, "attempts", json_object_get(a)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        *boundary = o;
    else
        json_object_put(o);
    json_object_put(a);
    as_close(&log);
    return st;
}
