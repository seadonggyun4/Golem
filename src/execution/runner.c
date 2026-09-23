#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include "golem/supervisor.h"
#include "../agent_session/internal.h"
#include "../reentry/internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static struct json_object *find(struct json_object *a, const char *field, const char *value)
{
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *v = json_object_array_get_idx(a, i);
        if (strcmp(dw_text(v, field), value) == 0)
            return v;
    }
    return NULL;
}
static uint64_t clock_ms(void)
{
    struct timespec t;
    return clock_gettime(CLOCK_MONOTONIC, &t) == 0
               ? (uint64_t)t.tv_sec * 1000 + (uint64_t)t.tv_nsec / 1000000
               : 0;
}
static golem_status attempt_budget(int directory)
{
    int fd = openat(directory, ".", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (fd < 0)
        return GOLEM_ERR_IO;
    DIR *dir = fdopendir(fd);
    if (!dir) {
        close(fd);
        return GOLEM_ERR_IO;
    }
    size_t count = 0;
    struct dirent *entry;
    errno = 0;
    while ((entry = readdir(dir)) != NULL) {
        size_t n = strlen(entry->d_name);
        if (n > 8 && strcmp(entry->d_name + n - 8, ".started") == 0)
            ++count;
    }
    golem_status st = errno ? GOLEM_ERR_IO : count >= 256 ? GOLEM_ERR_BUDGET_EXHAUSTED : GOLEM_OK;
    closedir(dir);
    return st;
}
static golem_status result_budget(struct json_object *manifest, struct json_object *snapshot,
                                  struct json_object *gates)
{
    size_t bound = 4096;
    struct json_object *base[] = {manifest, snapshot};
    for (size_t i = 0; i < 2; ++i) {
        const char *p = json_object_to_json_string_ext(base[i], JSON_C_TO_STRING_PLAIN);
        if (!p)
            return GOLEM_ERR_OUT_OF_MEMORY;
        bound += strlen(p);
    }
    for (size_t i = 0; i < json_object_array_length(gates); ++i) {
        const char *p = json_object_to_json_string_ext(
            dw_get(json_object_array_get_idx(gates, i), "cases"), JSON_C_TO_STRING_PLAIN);
        if (!p)
            return GOLEM_ERR_OUT_OF_MEMORY;
        bound += 4096 + 2 * strlen(p);
    }
    return bound > GOLEM_DOCUMENT_MAX_JSON ? GOLEM_ERR_BUDGET_EXHAUSTED : GOLEM_OK;
}
static golem_status protected(golem_document_store *s, struct json_object *cp,
                              struct json_object *snapshot, struct json_object *manifest,
                              const golem_digest *key)
{
    struct json_object *c = dw_get(cp, "contract"), *gates = dw_get(c, "gates");
    struct json_object *base = dw_get(dw_get(cp, "baseline"), "repositories"),
                       *repos = dw_get(snapshot, "repositories");
    for (size_t i = 0; i < json_object_array_length(gates); ++i) {
        struct json_object *g = json_object_array_get_idx(gates, i),
                           *paths = dw_get(g, "protected_paths");
        struct json_object *old = find(base, "id", dw_text(g, "repository")),
                           *now = find(repos, "id", dw_text(g, "repository"));
        if (!old || !now)
            return GOLEM_ERR_STALE_RESULT;
        for (size_t j = 0; j < json_object_array_length(paths); ++j) {
            const char *path = json_object_get_string(json_object_array_get_idx(paths, j));
            if (!json_object_equal(find(dw_get(old, "files"), "path", path),
                                   find(dw_get(now, "files"), "path", path)))
                return GOLEM_ERR_POLICY_DENIED;
        }
        golem_receipt binary;
        golem_digest expected;
        const char *exe = json_object_get_string(json_object_array_get_idx(dw_get(g, "argv"), 0));
        golem_status st = golem_digest_file(exe, &binary, NULL);
        if (st != GOLEM_OK)
            return st;
        if (!dw_digest(json_object_array_get_idx(dw_get(cp, "executables"), i), "digest",
                       &expected) ||
            !dw_equal(&binary.digest, &expected))
            return GOLEM_ERR_STALE_RESULT;
    }
    /* A registered development result must describe these exact bytes and checkpoint. */
    struct json_object *docs = dw_get(manifest, "documents");
    bool found = false;
    for (size_t i = 0; i < json_object_array_length(docs); ++i) {
        struct json_object *ref = json_object_array_get_idx(docs, i);
        dw_entry *e = dw_find(s, dw_text(ref, "document_id"), (uint32_t)dw_uint(ref, "revision"));
        if (!e || strcmp(dw_text(e->meta, "kind"), "development-result"))
            continue;
        golem_digest receipt, checkpoint;
        struct json_object *r = NULL;
        if (dw_uint(e->meta, "schema_version") != 5 ||
            !dw_digest(e->meta, "execution_receipt", &receipt))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        golem_status st = ex_load(s, &receipt, "development", &r);
        if (st == GOLEM_OK &&
            (!dw_digest(r, "checkpoint", &checkpoint) || !dw_equal(&checkpoint, key) ||
             !json_object_equal(dw_get(r, "snapshot"), snapshot)))
            st = GOLEM_ERR_STALE_RESULT;
        json_object_put(r);
        if (st != GOLEM_OK)
            return st;
        found = true;
    }
    return found ? GOLEM_OK : GOLEM_ERR_REQUIREMENTS_UNMET;
}
static golem_status observations(struct json_object *gate, golem_supervisor_result *r,
                                 struct json_object **out, bool *passed)
{
    struct json_object *o = NULL, *actual = NULL, *expected = dw_get(gate, "cases");
    golem_status st =
        golem_json_parse((golem_bytes){r->output, r->output_size}, GOLEM_SUPERVISOR_OUTPUT_MAX, &o);
    const char *keys[] = {"schema_version", "cases"};
    if (st == GOLEM_OK && (!dw_keys(o, keys, 2) || dw_uint(o, "schema_version") != 1 ||
                           !ds_array(dw_get(o, "cases"), json_object_array_length(expected),
                                     json_object_array_length(expected))))
        st = GOLEM_ERR_PARSE;
    actual = dw_get(o, "cases");
    bool all = true;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(expected); ++i) {
        struct json_object *c = json_object_array_get_idx(actual, i),
                           *e = json_object_array_get_idx(expected, i);
        const char *ck[] = {"id", "status"}, *status = dw_text(c, "status");
        if (!dw_keys(c, ck, 2) || strcmp(dw_text(c, "id"), dw_text(e, "id")) ||
            (strcmp(status, "PASS") && strcmp(status, "FAIL")))
            st = GOLEM_ERR_PARSE;
        if (strcmp(status, "PASS"))
            all = false;
    }
    if (st == GOLEM_OK) {
        *out = json_object_get(actual);
        *passed = all;
    }
    json_object_put(o);
    return st;
}
typedef struct lease_guard {
    as_log *log;
    golem_document_store *store;
} lease_guard;
static golem_status pulse(void *context)
{
    lease_guard *guard = context;
    golem_status deadline = re_deadline(guard->store);
    if (deadline != GOLEM_OK)
        return deadline;
    if (!guard->log->state)
        return GOLEM_OK;
    uint64_t now;
    golem_digest boot;
    golem_status st = as_clock_read(NULL, &now, &boot);
    if (st == GOLEM_OK && !as_live(guard->log, now, &boot))
        st = GOLEM_ERR_STALE_RESULT;
    return st;
}
static golem_status gate_run(golem_document_store *s, struct json_object *gate,
                             struct json_object *plan, lease_guard *guard, struct json_object **out)
{
    struct json_object *args = dw_get(gate, "argv"),
                       *repo =
                           find(dw_get(plan, "repositories"), "id", dw_text(gate, "repository"));
    char *argv[33] = {0};
    for (size_t i = 0; i < json_object_array_length(args); ++i)
        argv[i] = (char *)json_object_get_string(json_object_array_get_idx(args, i));
    char *env[] = {"PATH=/usr/bin:/bin", "LANG=C", "LC_ALL=C", NULL};
    golem_supervisor_result r = {.exit_code = -1};
    uint64_t start = clock_ms();
    if (!start)
        return GOLEM_ERR_IO;
    golem_status execution =
        golem_supervisor_run_at(argv[0], argv, dw_text(repo, "root"), env, (golem_bytes){NULL, 0},
                                dw_uint(gate, "timeout_ms") * 1000000, pulse, guard, &r);
    uint64_t end = clock_ms();
    const char *status = "ERROR", *reason = "EXECUTION_ERROR";
    struct json_object *cases = NULL;
    bool passed = false;
    golem_status parsed = observations(gate, &r, &cases, &passed);
    if (r.timed_out)
        reason = "TIMEOUT";
    else if (execution == GOLEM_ERR_STALE_RESULT)
        reason = "LEASE_EXPIRED";
    else if (execution == GOLEM_ERR_BUDGET_EXHAUSTED)
        reason = "REENTRY_DEADLINE_EXHAUSTED";
    else if (execution == GOLEM_ERR_OVERFLOW)
        reason = "LOG_LIMIT";
    else if (r.signal_number)
        reason = "SIGNAL";
    else if (!end || end < start)
        reason = "CLOCK_ERROR";
    else if (r.exit_code > 0) {
        status = "FAIL";
        reason = "NONZERO_EXIT";
    } else if (execution == GOLEM_OK && parsed == GOLEM_OK) {
        status = passed ? "PASS" : "FAIL";
        reason = passed ? "DECLARED_CASES_PASSED" : "CASE_FAILED";
    } else if (execution == GOLEM_OK)
        reason = "INVALID_OR_MISSING_CASES";
    if (!cases)
        cases = json_object_new_array();
    struct json_object *o = json_object_new_object();
    golem_digest stdout_hash, stderr_hash, evidence;
    golem_status st = golem_digest_bytes((golem_bytes){r.output, r.output_size}, &stdout_hash);
    if (st == GOLEM_OK)
        st = golem_digest_bytes((golem_bytes){r.error, r.error_size}, &stderr_hash);
    if (st == GOLEM_OK &&
        (!ex_text(o, "gate_id", dw_text(gate, "id")) ||
         !ex_uint(o, "version", dw_uint(gate, "version")) || !ex_text(o, "status", status) ||
         !ex_text(o, "reason", reason) || !ex_uint(o, "started_ms", start) ||
         !ex_uint(o, "ended_ms", end) ||
         !dw_add(o, "exit_code", json_object_new_int(r.exit_code)) ||
         !ex_uint(o, "signal", (uint64_t)r.signal_number) ||
         !dw_add(o, "timed_out", json_object_new_boolean(r.timed_out)) ||
         !dw_add(o, "cases", json_object_get(cases)) ||
         !dw_add_digest(o, "stdout_digest", &stdout_hash) ||
         !dw_add_digest(o, "stderr_digest", &stderr_hash) ||
         !ex_uint(o, "stdout_size", r.output_size) || !ex_uint(o, "stderr_size", r.error_size) ||
         !ex_text(o, "log_policy", "summary-only; raw output discarded, truncated on overflow")))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    /* Only normalized IDs/statuses enter CAS. Raw logs may contain secrets. */
    if (st == GOLEM_OK)
        st = dw_put_json(s, o, &evidence);
    if (st == GOLEM_OK && !dw_add_digest(o, "observation_digest", &evidence))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        *out = o;
    else
        json_object_put(o);
    json_object_put(cases);
    return st;
}
golem_status ex_execute(golem_document_store *s, struct json_object *cp, const golem_digest *key,
                        struct json_object *manifest, const char *attempt,
                        struct json_object *token, struct json_object **out)
{
    int dir = -1;
    char started[80], done[80];
    (void)snprintf(started, sizeof(started), "%s.started", attempt);
    (void)snprintf(done, sizeof(done), "%s.done", attempt);
    golem_status st = dw_dir(s->root, "execution-attempts", true, &dir);
    struct json_object *identity = json_object_new_object();
    golem_digest request;
    if (!dw_add_digest(identity, "checkpoint", key) ||
        !dw_add(identity, "manifest", json_object_get(manifest)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ex_hash(identity, &request);
    json_object_put(identity);
    uint8_t *old = NULL;
    size_t n = 0;
    if (st == GOLEM_OK) {
        golem_status prior = dw_read_at(dir, started, 32, &old, &n);
        if (prior == GOLEM_OK) {
            if (n != 32 || memcmp(old, request.bytes, 32))
                st = GOLEM_ERR_IDENTITY_MISMATCH;
            free(old);
            old = NULL;
            if (st == GOLEM_OK)
                st = dw_read_at(dir, done, 32, &old, &n);
            golem_digest result;
            if (st == GOLEM_OK && n == 32) {
                memcpy(result.bytes, old, 32);
                st = dw_cas_json(s, &result, out);
            } else if (st == GOLEM_ERR_NOT_FOUND)
                st = GOLEM_ERR_INCOMPLETE_WORK;
            else if (st == GOLEM_OK)
                st = GOLEM_ERR_CORRUPT_JOURNAL;
            free(old);
            close(dir);
            return st;
        }
        if (prior != GOLEM_ERR_NOT_FOUND)
            st = prior;
        if (st == GOLEM_OK) {
            prior = dw_read_at(dir, done, 32, &old, &n);
            free(old);
            old = NULL;
            if (prior != GOLEM_ERR_NOT_FOUND)
                st = prior == GOLEM_OK ? GOLEM_ERR_MISSING_RECORD : prior;
        }
        if (st == GOLEM_OK)
            st = attempt_budget(dir);
    }
    struct json_object *snap = NULL, *after = NULL, *gates = NULL, *result = NULL;
    struct json_object *c = dw_get(cp, "contract"), *plan = dw_get(c, "snapshot_plan");
    if (st == GOLEM_OK)
        st = ex_snapshot(plan, &snap);
    if (st == GOLEM_OK)
        st = protected(s, cp, snap, manifest, key);
    if (st == GOLEM_OK)
        st = result_budget(manifest, snap, dw_get(c, "gates"));
    if (st == GOLEM_OK)
        st = ex_authorize(s, token, manifest);
    as_log log = {.directory = -1};
    lease_guard guard = {&log, s};
    if (st == GOLEM_OK)
        st = as_load(s, NULL, NULL, &log);
    if (st == GOLEM_OK && dw_get(manifest, "reentry")) {
        golem_digest decision, dispatch;
        char hex[65], slot[96];
        size_t ignored;
        if (!dw_digest(dw_get(manifest, "reentry"), "decision_digest", &decision))
            st = GOLEM_ERR_PARSE;
        if (st == GOLEM_OK)
            st = golem_digest_format(&decision, hex, sizeof(hex), &ignored);
        if (st == GOLEM_OK)
            st = golem_digest_bytes((golem_bytes){(const uint8_t *)attempt, strlen(attempt)},
                                    &dispatch);
        if (st == GOLEM_OK) {
            (void)snprintf(slot, sizeof(slot), "reentry-%s.dispatch", hex);
            st = dw_publish(dir, slot, (golem_bytes){dispatch.bytes, 32});
        }
    }
    if (st == GOLEM_OK)
        st = dw_publish(dir, started, (golem_bytes){request.bytes, 32});
    if (st == GOLEM_OK) {
        gates = json_object_new_array();
        if (!gates)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    struct json_object *definitions = dw_get(c, "gates");
    bool pass = true, error = false;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(definitions); ++i) {
        struct json_object *g = NULL;
        if (pulse(&guard) != GOLEM_OK) {
            st = GOLEM_ERR_STALE_RESULT;
            break;
        }
        st = gate_run(s, json_object_array_get_idx(definitions, i), plan, &guard, &g);
        if (st == GOLEM_OK && strcmp(dw_text(g, "status"), "PASS"))
            pass = false;
        if (st == GOLEM_OK && strcmp(dw_text(g, "status"), "ERROR") == 0)
            error = true;
        if (st == GOLEM_OK) {
            if (!wf_append(gates, g))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        } else
            json_object_put(g);
    }
    golem_status snapshot_status = st == GOLEM_OK ? ex_snapshot(plan, &after) : st;
    bool changed = snapshot_status != GOLEM_OK || !json_object_equal(snap, after);
    if (st == GOLEM_OK && !changed && protected(s, cp, after, manifest, key) != GOLEM_OK)
        changed = true;
    if (st == GOLEM_OK) {
        result = json_object_new_object();
        if (!ex_uint(result, "schema_version", 1) || !ex_text(result, "type", "qa") ||
            !ex_text(result, "work_id", dw_text(s->spec, "work_id")) ||
            !ex_text(result, "attempt_id", attempt) || !dw_add_digest(result, "checkpoint", key) ||
            !dw_add(result, "manifest", json_object_get(manifest)) ||
            !dw_add(result, "snapshot", json_object_get(snap)) ||
            !dw_add(result, "gates", json_object_get(gates)) ||
            !ex_text(result, "status",
                     changed || error ? "ERROR"
                     : pass           ? "PASS"
                                      : "FAIL") ||
            !ex_text(result, "reason",
                     changed ? "SNAPSHOT_CHANGED"
                     : pass  ? "DECLARED_GATES_PASSED"
                             : "GATE_NOT_PASSED"))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_digest result_digest;
    golem_execution_reply encoded = {0};
    if (st == GOLEM_OK)
        st = ex_emit(result, &encoded);
    golem_execution_reply_free(&encoded);
    if (st == GOLEM_OK)
        st = dw_put_json(s, result, &result_digest);
    if (st == GOLEM_OK)
        st = dw_publish(dir, done, (golem_bytes){result_digest.bytes, 32});
    if (st == GOLEM_OK)
        *out = result;
    else
        json_object_put(result);
    as_close(&log);
    json_object_put(snap);
    json_object_put(after);
    json_object_put(gates);
    if (dir >= 0)
        close(dir);
    return st;
}
