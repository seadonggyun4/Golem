#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static bool empty(struct json_object *o)
{
    return json_object_is_type(o, json_type_object) && json_object_object_length(o) == 0;
}
static bool number(struct json_object *o, const char *key)
{
    return json_object_is_type(dw_get(o, key), json_type_int) &&
           json_object_get_int64(dw_get(o, key)) >= 0 && dw_uint(o, key) <= INT64_MAX;
}
static bool shape(const char *action, struct json_object *data, size_t index)
{
    golem_digest digest;
    if (!strcmp(action, "DIFF")) {
        const char *keys[] = {"digest"};
        return dw_keys(data, keys, 1) && dw_digest(data, "digest", &digest);
    }
    if (!strcmp(action, "REVIEW")) {
        const char *keys[] = {"operation", "group_id", "candidate", "diff",
                              "qa",        "decision", "reviewer"};
        return dw_keys(data, keys, 7) && !strcmp(dw_text(data, "operation"), "review") &&
               dw_digest(data, "diff", &digest) && ws_id(dw_text(data, "reviewer")) &&
               strlen(dw_text(data, "reviewer")) <= 64 &&
               json_object_is_type(dw_get(data, "qa"), json_type_string) &&
               (!*dw_text(data, "qa") || dw_digest(data, "qa", &digest)) &&
               (!strcmp(dw_text(data, "decision"), "PASS") ||
                !strcmp(dw_text(data, "decision"), "FAIL"));
    }
    if (!strcmp(action, "RESERVE")) {
        const char *keys[] = {"namespace"};
        return dw_keys(data, keys, 1) && dw_digest(data, "namespace", &digest);
    }
    if (!strcmp(action, "TICKET")) {
        const char *keys[] = {"ticket", "epoch", "instance", "boot"};
        const char *hex = dw_text(data, "instance");
        return dw_keys(data, keys, 4) && number(data, "ticket") && dw_uint(data, "ticket") &&
               number(data, "epoch") && dw_uint(data, "epoch") && strlen(hex) == 32 &&
               strspn(hex, "0123456789abcdef") == 32 && dw_digest(data, "boot", &digest);
    }
    if (!strcmp(action, "ENROLL")) {
        const char *keys[] = {"identities", "workspace_receipt"};
        const char *roots[] = {"work", "tree", "build", "temp"};
        const char *fields[] = {"path", "device", "inode"};
        struct json_object *ids = dw_get(data, "identities");
        if (!dw_keys(data, keys, 2) || !dw_digest(data, "workspace_receipt", &digest) ||
            !dw_keys(ids, roots, 4))
            return false;
        for (size_t j = 0; j < 4; ++j) {
            struct json_object *id = dw_get(ids, roots[j]);
            if (!dw_keys(id, fields, 3) || dw_text(id, "path")[0] != '/' || !number(id, "device") ||
                !number(id, "inode"))
                return false;
        }
        return true;
    }
    if (!strcmp(action, "SETTLING")) {
        const char *keys[] = {"termination", "qa",     "cancelled", "tokens_known",
                              "cost_known",  "tokens", "nano_cost"};
        if (!dw_keys(data, keys, 7) || !dw_digest(data, "termination", &digest) ||
            !json_object_is_type(dw_get(data, "qa"), json_type_string) ||
            (*dw_text(data, "qa") && !dw_digest(data, "qa", &digest)))
            return false;
        for (size_t j = 2; j <= 4; ++j)
            if (!json_object_is_type(dw_get(data, keys[j]), json_type_boolean))
                return false;
        for (size_t j = 5; j <= 6; ++j)
            if (!number(data, keys[j]) ||
                (!json_object_get_boolean(dw_get(data, keys[j - 2])) && dw_uint(data, keys[j])))
                return false;
        return true;
    }
    if (!strcmp(action, "SELECT")) {
        const char *keys[] = {"candidate", "comparison", "requires_target_revalidation",
                              "merge_authorized", "push_authorized"};
        if (!dw_keys(data, keys, 5) || !number(data, "candidate") ||
            dw_uint(data, "candidate") != index || !dw_digest(data, "comparison", &digest))
            return false;
        for (size_t j = 2; j < 5; ++j)
            if (!json_object_is_type(dw_get(data, keys[j]), json_type_boolean) ||
                json_object_get_boolean(dw_get(data, keys[j])) != (j == 2))
                return false;
        return true;
    }
    if (!strcmp(action, "COHORT"))
        return json_object_is_type(data, json_type_object) &&
               dw_digest(data, "record_digest", &digest);
    return empty(data);
}
golem_status cf_apply(cf_context *c, const char *action, size_t i, struct json_object *data)
{
    if (!strcmp(action, "CREATE")) {
        if (i || c->manifest || c->sequence || cf_model(data) != GOLEM_OK)
            return GOLEM_ERR_CORRUPT_JOURNAL;
        c->manifest = json_object_get(data);
        return GOLEM_OK;
    }
    if (!c->manifest || i >= json_object_array_length(dw_get(c->manifest, "candidates")))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    if (!shape(action, data, i))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    if (!strcmp(action, "SELECT")) {
        if (c->selection || strcmp(cf_state(c, i), "FINISHED"))
            return GOLEM_ERR_INVALID_STATE;
        c->selection = json_object_get(data);
        return GOLEM_OK;
    }
    if (!strcmp(action, "COHORT")) {
        if (c->exported)
            return GOLEM_ERR_INVALID_STATE;
        c->exported = true;
        return GOLEM_OK;
    }
    const char *state = cf_state(c, i), *next = NULL, *field = NULL;
    if (!strcmp(action, "DIFF") && !strcmp(state, "FINISHED") && !c->selection) {
        golem_status st = cf_diff_validate(c, i, data);
        if (st != GOLEM_OK)
            return st;
        next = "FINISHED";
        field = "diff";
    } else if (!strcmp(action, "REVIEW") && !strcmp(state, "FINISHED")) {
        if (strcmp(dw_text(data, "group_id"), dw_text(c->manifest, "group_id")) ||
            strcmp(dw_text(data, "candidate"), dw_text(cf_spec(c, i), "id")) ||
            strcmp(dw_text(data, "diff"), dw_text(dw_get(c->members[i], "diff"), "digest")))
            return GOLEM_ERR_CORRUPT_JOURNAL;
        golem_digest digest;
        struct json_object *projection = NULL;
        if (!dw_digest(data, "diff", &digest))
            return GOLEM_ERR_CORRUPT_JOURNAL;
        golem_status st = dw_cas_json(c->parent, &digest, &projection);
        if (st == GOLEM_OK && !strcmp(dw_text(data, "decision"), "PASS") &&
            !json_object_get_boolean(dw_get(projection, "complete")))
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        json_object_put(projection);
        if (st != GOLEM_OK)
            return st;
        next = "FINISHED";
        field = "review";
    } else if (!strcmp(action, "ENROLL") && !strcmp(state, "PLANNED")) {
        next = "READY";
        field = "enrollment";
    } else if (!strcmp(action, "RESERVE") && !strcmp(state, "READY")) {
        if (cf_budget(c, i) != GOLEM_OK)
            return GOLEM_ERR_BUDGET_EXHAUSTED;
        next = "RESERVED";
        field = "reservation";
    } else if (!strcmp(action, "TICKET") && !strcmp(state, "RESERVED") &&
               !dw_get(c->members[i], "token")) {
        next = "RESERVED";
        field = "token";
    } else if (!strcmp(action, "START_INTENT") && !strcmp(state, "RESERVED") &&
               dw_get(c->members[i], "token"))
        next = "START_INTENT";
    else if (!strcmp(action, "RUNNING") && !strcmp(state, "START_INTENT"))
        next = "RUNNING";
    else if (!strcmp(action, "CANCEL_REQUESTED") && cf_held(state) && strcmp(state, "SETTLING") &&
             strcmp(state, "CANCEL_REQUESTED"))
        next = "CANCEL_REQUESTED";
    else if (!strcmp(action, "SETTLING") && cf_held(state) && strcmp(state, "SETTLING")) {
        next = "SETTLING";
        field = "result";
    } else if (!strcmp(action, "FINISHED") && !strcmp(state, "SETTLING"))
        next = "FINISHED";
    if (!next || (!field && !empty(data)) || !json_object_is_type(data, json_type_object))
        return GOLEM_ERR_INVALID_STATE;
    struct json_object *record = NULL;
    if (c->members[i]) {
        if (json_object_deep_copy(c->members[i], &record, NULL) != 0)
            return GOLEM_ERR_OUT_OF_MEMORY;
    } else
        record = json_object_new_object();
    if (!ex_text(record, "state", next) ||
        (field && !dw_add(record, field, json_object_get(data)))) {
        json_object_put(record);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (!strcmp(next, "START_INTENT") &&
        !dw_add(record, "dispatch_intent", json_object_new_boolean(true))) {
        json_object_put(record);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    json_object_put(c->members[i]);
    c->members[i] = record;
    return GOLEM_OK;
}

golem_status cf_append(cf_context *c, const char *action, size_t index, struct json_object *data)
{
    if (c->sequence >= CF_EVENTS)
        return GOLEM_ERR_OVERFLOW;
    golem_status st = cf_apply(c, action, index, data);
    if (st != GOLEM_OK)
        return st;
    struct json_object *event = json_object_new_object();
    if (!ex_uint(event, "schema_version", 1) || !ex_uint(event, "sequence", c->sequence + 1) ||
        !dw_add_digest(event, "previous", &c->last) || !ex_text(event, "action", action) ||
        !ex_uint(event, "candidate", index) || !dw_add(event, "data", json_object_get(data)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_digest digest;
    if (st == GOLEM_OK)
        st = dw_put_json(c->parent, event, &digest);
    char name[16], hex[65];
    size_t size;
    (void)snprintf(name, sizeof(name), "%04u", c->sequence + 1);
    if (st == GOLEM_OK)
        st = golem_digest_format(&digest, hex, sizeof(hex), &size);
    if (st == GOLEM_OK)
        st = dw_publish(c->dir, name, (golem_bytes){(const uint8_t *)hex, 64});
    if (st == GOLEM_OK) {
        ++c->sequence;
        c->last = digest;
    } else
        c->parent->poisoned = true;
    json_object_put(event);
    return st;
}

golem_status cf_load(cf_context *c)
{
    int fd = openat(c->dir, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0)
        return GOLEM_ERR_IO;
    DIR *dir = fdopendir(fd);
    if (!dir) {
        close(fd);
        return GOLEM_ERR_IO;
    }
    unsigned count = 0, max = 0, visited = 0;
    golem_status st = GOLEM_OK;
    for (;;) {
        errno = 0;
        struct dirent *e = readdir(dir);
        if (!e) {
            if (errno)
                st = GOLEM_ERR_IO;
            break;
        }
        if (++visited > 1024) {
            st = GOLEM_ERR_OVERFLOW;
            break;
        }
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..") ||
            !strncmp(e->d_name, ".pending-", 9))
            continue;
        unsigned n = 0;
        char end, expected[16];
        if (sscanf(e->d_name, "%4u%c", &n, &end) != 1 || n < 1 || n > CF_EVENTS) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        (void)snprintf(expected, sizeof(expected), "%04u", n);
        if (strcmp(expected, e->d_name)) {
            st = GOLEM_ERR_CORRUPT_JOURNAL;
            break;
        }
        ++count;
        if (n > max)
            max = n;
    }
    if (closedir(dir) != 0 && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && count != max)
        st = GOLEM_ERR_MISSING_RECORD;
    for (unsigned i = 1; st == GOLEM_OK && i <= max; ++i) {
        char name[16];
        uint8_t *bytes = NULL;
        size_t size = 0;
        struct json_object *event = NULL;
        golem_digest digest, previous;
        (void)snprintf(name, sizeof(name), "%04u", i);
        st = dw_read_at(c->dir, name, 64, &bytes, &size);
        if (st == GOLEM_OK)
            st = golem_digest_parse((golem_string_view){(const char *)bytes, size}, &digest);
        if (st == GOLEM_OK)
            st = dw_cas_json(c->parent, &digest, &event);
        const char *keys[] = {"schema_version", "sequence",  "previous",
                              "action",         "candidate", "data"};
        if (st == GOLEM_OK &&
            (!dw_keys(event, keys, 6) || dw_uint(event, "schema_version") != 1 ||
             !number(event, "schema_version") || !number(event, "sequence") ||
             !number(event, "candidate") || dw_uint(event, "sequence") != i ||
             !dw_digest(event, "previous", &previous) || !dw_equal(&previous, &c->last) ||
             dw_uint(event, "candidate") >= GOLEM_CANDIDATE_MAX))
            st = GOLEM_ERR_CORRUPT_JOURNAL;
        if (st == GOLEM_OK)
            st = cf_apply(c, dw_text(event, "action"), (size_t)dw_uint(event, "candidate"),
                          dw_get(event, "data"));
        if (st == GOLEM_OK) {
            const char *action = dw_text(event, "action");
            const char *reference = !strcmp(action, "SETTLING") ? "termination"
                                    : !strcmp(action, "SELECT") ? "comparison"
                                    : !strcmp(action, "COHORT") ? "record_digest"
                                                                : NULL;
            if (reference) {
                golem_digest source;
                uint64_t length;
                st = dw_digest(dw_get(event, "data"), reference, &source)
                         ? golem_evidence_verify(c->parent->cas, &source, &length, NULL)
                         : GOLEM_ERR_CORRUPT_JOURNAL;
            }
        }
        if (st == GOLEM_OK) {
            c->sequence = i;
            c->last = digest;
        }
        json_object_put(event);
        free(bytes);
    }
    return st;
}
