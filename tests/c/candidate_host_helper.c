#define _POSIX_C_SOURCE 200809L
#include "../../src/candidate/internal.h"
#include "golem/worker.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Synthetic, explicitly trusted fixture host. Not installed or usable as a
 * production approval broker. It starts only the fixed local fixture below. */
typedef struct host {
    struct json_object *config;
    golem_document_store *parent, *children[8], *target;
    golem_workspace_host workspace;
    golem_admission *admission;
    golem_worker_pool *pool;
    uint64_t jobs[8];
    bool deny, fail_start;
    unsigned starts;
} host;
static golem_status allow_workspace(void *v, golem_workspace_operation op, const char *id)
{
    (void)op;
    (void)id;
    return ((host *)v)->deny ? GOLEM_ERR_POLICY_DENIED : GOLEM_OK;
}
static golem_status pulse(void *v)
{
    return ((host *)v)->deny ? GOLEM_ERR_POLICY_DENIED : GOLEM_OK;
}
static size_t index_of(host *h, const char *id)
{
    struct json_object *a = dw_get(h->config, "members");
    for (size_t i = 0; i < json_object_array_length(a); ++i)
        if (!strcmp(dw_text(json_object_array_get_idx(a, i), "id"), id))
            return i;
    return 8;
}
static golem_status resolve(void *v, const char *id, golem_candidate_member *out)
{
    host *h = v;
    if (!strcmp(id, "$target")) {
        struct json_object *m = dw_get(h->config, "target");
        if (!m)
            return GOLEM_ERR_NOT_FOUND;
        golem_status st = golem_document_store_open(dw_text(m, "work"), false, NULL,
                                                   &h->target, NULL);
        if (st == GOLEM_OK) {
            *out = (golem_candidate_member){.work = h->target, .tree_root = dw_text(m, "tree")};
            if (!dw_digest(m, "environment", &out->environment))
                st = GOLEM_ERR_PARSE;
        }
        return st;
    }
    size_t i = index_of(h, id);
    if (i >= 8)
        return GOLEM_ERR_NOT_FOUND;
    struct json_object *m = json_object_array_get_idx(dw_get(h->config, "members"), i);
    golem_status st = GOLEM_OK;
    if (!h->children[i])
        st = golem_document_store_open(dw_text(m, "work"), true, NULL, &h->children[i], NULL);
    if (st == GOLEM_OK) {
        *out = (golem_candidate_member){.work = h->children[i],
                                        .workspace = &h->workspace,
                                        .work_root = dw_text(m, "work"),
                                        .tree_root = dw_text(m, "tree"),
                                        .build_root = dw_text(m, "build"),
                                        .temp_root = dw_text(m, "temp")};
        if (!dw_digest(m, "environment", &out->environment))
            st = GOLEM_ERR_PARSE;
    }
    return st;
}
static golem_status check(void *v, golem_bytes bytes)
{
    host *h = v;
    if (h->deny)
        return GOLEM_ERR_POLICY_DENIED;
    struct json_object *r = NULL;
    golem_status st = golem_json_parse(bytes, GOLEM_DOCUMENT_MAX_JSON, &r);
    if (st == GOLEM_OK && !strcmp(dw_text(r, "operation"), "finish")) {
        size_t i = index_of(h, dw_text(r, "candidate"));
        if (i < 8 && h->jobs[i]) {
            golem_worker_snapshot state;
            st = golem_worker_inspect(h->pool, h->jobs[i], &state);
            if (st == GOLEM_OK && state.state != GOLEM_WORKER_FINISHED)
                st = GOLEM_ERR_LEASE_BUSY;
        }
    }
    json_object_put(r);
    return st;
}
static golem_status publish(void *v, const golem_digest *ns, const golem_admission_ticket *t,
                            golem_digest *out)
{
    host *h = v;
    struct json_object *o = cf_token(&t->token);
    if (!dw_add_digest(o, "namespace", ns) || !ex_text(o, "work", t->request.work) ||
        !ex_text(o, "session", t->request.session) ||
        !dw_add_digest(o, "runtime_binding", &t->request.runtime_binding)) {
        json_object_put(o);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_status st = dw_put_json(h->parent, o, out);
    json_object_put(o);
    return st;
}
static golem_status start(void *v, const char *id, golem_admission *a, const char *operation)
{
    host *h = v;
    ++h->starts;
    if (h->fail_start)
        return GOLEM_ERR_IO;
    golem_admission_ticket ticket;
    golem_status st = golem_admission_lookup(a, operation, &ticket);
    if (st != GOLEM_OK)
        return st;
    if (!strcmp(dw_text(h->config, "mode"), "current"))
        return golem_admission_begin(a, ticket.token, publish, h, &ticket);
    golem_candidate_member m;
    st = resolve(h, id, &m);
    if (st != GOLEM_OK)
        return st;
    char temp[8192], build[8192];
    (void)snprintf(temp, sizeof(temp), "TMPDIR=%s", m.temp_root);
    (void)snprintf(build, sizeof(build), "GOLEM_BUILD_ROOT=%s", m.build_root);
    char *argv[] = {"/bin/sh", "-c",
                    "printf started > worker.started; while [ ! -f \"$TMPDIR/release\" ]; do sleep "
                    "0.01; done; printf done > worker.done",
                    NULL};
    char *env[] = {"PATH=/usr/bin:/bin", "LANG=C", temp, build, NULL};
    golem_worker_request request = {.executable = "/bin/sh",
                                    .cwd = m.tree_root,
                                    .argv = argv,
                                    .envp = env,
                                    .cpu_units = ticket.request.cpu_millis,
                                    .memory_bytes = ticket.request.memory_bytes,
                                    .timeout_ns = UINT64_C(15000000000),
                                    .lease_ns = UINT64_C(15000000000),
                                    .io_slots = 1,
                                    .resource_class = GOLEM_WORKER_BACKGROUND};
    size_t i = index_of(h, id);
    if (st == GOLEM_OK)
        st = golem_worker_submit(h->pool, &request, &h->jobs[i]);
    if (st == GOLEM_OK)
        st = golem_worker_start(h->pool, h->jobs[i], a, operation, publish, h);
    return st;
}
static golem_status cancel(void *v, const char *id)
{
    host *h = v;
    size_t i = index_of(h, id);
    return i < 8 && h->jobs[i] ? golem_worker_cancel(h->pool, h->jobs[i]) : GOLEM_OK;
}
static golem_status open_admission(host *h)
{
    golem_admission_options options = {
        .size = sizeof(options),
        .version = 1,
        .create = true,
        .limits = {.slots = 2, .cpu_millis = 2000, .memory_bytes = 8192}};
    return golem_admission_open(dw_text(h->config, "admission"), &options, &h->admission);
}
static void close_children(host *h)
{
    for (size_t i = 0; i < 8; ++i) {
        (void)golem_document_store_close(h->children[i]);
        h->children[i] = NULL;
    }
}
int main(int argc, char **argv)
{
    if (argc != 2)
        return 2;
    FILE *f = fopen(argv[1], "rb");
    if (!f)
        return 2;
    char buffer[65536];
    size_t n = fread(buffer, 1, sizeof(buffer), f);
    fclose(f);
    host h = {0};
    if (golem_json_parse((golem_bytes){(uint8_t *)buffer, n}, sizeof(buffer), &h.config) !=
            GOLEM_OK ||
        golem_document_store_open(dw_text(h.config, "parent"), true, NULL, &h.parent, NULL) !=
            GOLEM_OK ||
        open_admission(&h) != GOLEM_OK)
        return 2;
    h.workspace = (golem_workspace_host){.struct_size = sizeof(h.workspace),
                                         .version = 1,
                                         .repository_id = "fixture",
                                         .repository_root = dw_text(h.config, "repository"),
                                         .worktree_root = dw_text(h.config, "worktrees"),
                                         .check = allow_workspace,
                                         .pulse = pulse,
                                         .context = &h};
    golem_worker_options options = golem_worker_options_default();
    options.limits = (golem_worker_limits){.worker_slots = 2,
                                           .io_slots = 2,
                                           .cpu_units = 2000,
                                           .memory_bytes = 8192,
                                           .queue_bytes = 65536};
    if (golem_worker_open(&options, &h.pool) != GOLEM_OK)
        return 2;
    golem_candidate_host capabilities = {.size = sizeof(capabilities),
                                         .version = 1,
                                         .context = &h,
                                         .check = check,
                                         .resolve = resolve,
                                         .start = start,
                                         .cancel = cancel};
    char *line = NULL;
    size_t capacity = 0;
    ssize_t length;
    while ((length = getline(&line, &capacity, stdin)) > 0) {
        struct json_object *request = NULL, *result = NULL;
        golem_status st = golem_json_parse((golem_bytes){(uint8_t *)line, (size_t)length},
                                           GOLEM_DOCUMENT_MAX_JSON, &request);
        const char *op = dw_text(request, "operation");
        if (!strcmp(op, "$quit")) {
            json_object_put(request);
            break;
        }
        if (st == GOLEM_OK && !strcmp(op, "$provision")) {
            golem_candidate_member m;
            st = resolve(&h, dw_text(request, "candidate"), &m);
            golem_workspace_result r;
            if (st == GOLEM_OK)
                st = golem_workspace_call(m.work, m.workspace, GOLEM_WORKSPACE_CREATE,
                                          dw_text(request, "candidate"), dw_text(h.config, "base"),
                                          NULL, &r, NULL);
        } else if (st == GOLEM_OK && !strcmp(op, "$seal")) {
            golem_candidate_member m;
            st = resolve(&h, dw_text(request, "candidate"), &m);
            golem_workspace_result r;
            if (st == GOLEM_OK)
                st = golem_workspace_call(m.work, m.workspace, GOLEM_WORKSPACE_ACTIVATE,
                                          dw_text(request, "candidate"), NULL, NULL, &r, NULL);
            if (st == GOLEM_OK)
                st = golem_workspace_call(m.work, m.workspace, GOLEM_WORKSPACE_SEAL,
                                          dw_text(request, "candidate"), NULL, NULL, &r, NULL);
        } else if (st == GOLEM_OK && (!strcmp(op, "$grant") || !strcmp(op, "$token"))) {
            golem_admission_ticket t;
            st = !strcmp(op, "$grant")
                     ? golem_admission_grant(h.admission, &t)
                     : golem_admission_lookup(h.admission, dw_text(request, "key"), &t);
            if (st == GOLEM_OK)
                result = cf_token(&t.token);
        } else if (st == GOLEM_OK && !strcmp(op, "$proof")) {
            golem_receipt receipt;
            st = golem_evidence_put(h.parent->cas,
                                    (golem_bytes){(const uint8_t *)"fixture termination", 19},
                                    &receipt, NULL);
            result = json_object_new_object();
            if (st == GOLEM_OK && !dw_add_digest(result, "digest", &receipt.digest))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (st == GOLEM_OK && !strcmp(op, "$wait")) {
            size_t i = index_of(&h, dw_text(request, "candidate"));
            if (i >= 8 || !h.jobs[i])
                st = GOLEM_ERR_NOT_FOUND;
            else {
                struct json_object *m = json_object_array_get_idx(dw_get(h.config, "members"), i);
                char path[8192];
                int size = snprintf(path, sizeof(path), "%s/release", dw_text(m, "temp"));
                FILE *release = size > 0 && (size_t)size < sizeof(path) ? fopen(path, "wb") : NULL;
                if (!release || fclose(release) != 0)
                    st = GOLEM_ERR_IO;
                for (unsigned retry = 0; st == GOLEM_OK && retry < 1000; ++retry) {
                    golem_worker_snapshot snapshot;
                    st = golem_worker_inspect(h.pool, h.jobs[i], &snapshot);
                    if (st != GOLEM_OK || snapshot.state == GOLEM_WORKER_FINISHED)
                        break;
                    struct timespec delay = {0, 10000000};
                    nanosleep(&delay, NULL);
                    if (retry == 999)
                        st = GOLEM_ERR_LEASE_BUSY;
                }
            }
        } else if (st == GOLEM_OK && !strcmp(op, "$ack")) {
            size_t i = index_of(&h, dw_text(request, "candidate"));
            st = i < 8 ? golem_worker_acknowledge(h.pool, h.jobs[i], h.admission,
                                                  dw_text(request, "key"))
                       : GOLEM_ERR_NOT_FOUND;
            if (st == GOLEM_OK)
                h.jobs[i] = 0;
        } else if (st == GOLEM_OK && !strcmp(op, "$reopen")) {
            st = golem_admission_close(h.admission);
            h.admission = NULL;
            if (st == GOLEM_OK)
                st = open_admission(&h);
        } else if (st == GOLEM_OK && !strcmp(op, "$deny"))
            h.deny = json_object_get_boolean(dw_get(request, "value"));
        else if (st == GOLEM_OK && !strcmp(op, "$target")) {
            if (!dw_add(h.config, "target", json_object_get(dw_get(request, "binding"))))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (st == GOLEM_OK && !strcmp(op, "$fail-start"))
            h.fail_start = json_object_get_boolean(dw_get(request, "value"));
        else if (st == GOLEM_OK) {
            golem_execution_reply reply = {0};
            st = golem_candidate_call(h.parent, &capabilities, h.admission,
                                      (golem_bytes){(uint8_t *)line, (size_t)length}, &reply, NULL);
            if (st == GOLEM_OK)
                st = golem_json_parse((golem_bytes){reply.data, reply.size},
                                      GOLEM_DOCUMENT_MAX_JSON, &result);
            golem_execution_reply_free(&reply);
        }
        close_children(&h);
        if (h.target) {
            golem_status closed = golem_document_store_close(h.target);
            h.target = NULL;
            if (st == GOLEM_OK)
                st = closed;
        }
        struct json_object *response = json_object_new_object();
        ex_uint(response, "status", st);
        ex_uint(response, "starts", h.starts);
        dw_add(response, "result", result ? result : json_object_new_object());
        puts(json_object_to_json_string_ext(response, JSON_C_TO_STRING_PLAIN));
        fflush(stdout);
        json_object_put(response);
        json_object_put(request);
    }
    free(line);
    close_children(&h);
    golem_status closed = golem_worker_close(h.pool);
    (void)golem_admission_close(h.admission);
    (void)golem_document_store_close(h.parent);
    json_object_put(h.config);
    return closed == GOLEM_OK ? 0 : 2;
}
