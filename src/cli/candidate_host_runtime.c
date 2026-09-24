#include "candidate_host.h"
#include "../runtime/profile_internal.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static golem_candidate_current_binding *find_binding(ch_host *h, const char *id)
{
    for (size_t i = 0; i < h->options.count; ++i)
        if (!strcmp(h->bindings[i].candidate, id))
            return &h->bindings[i];
    return NULL;
}

static golem_status resolve_member(void *context, const char *id, golem_candidate_member *out)
{
    ch_host *h = context;
    if (!strcmp(id, "$target")) {
        struct json_object *target = dw_get(h->config, "target");
        if (!target)
            return GOLEM_ERR_NOT_FOUND;
        golem_status st = GOLEM_OK;
        if (!h->target)
            st = golem_document_store_open(dw_text(target, "work"), false, NULL, &h->target, NULL);
        if (st == GOLEM_OK) {
            *out =
                (golem_candidate_member){.work = h->target, .tree_root = dw_text(target, "tree")};
            (void)dw_digest(target, "environment", &out->environment);
        }
        return st;
    }
    golem_candidate_current_binding *b = find_binding(h, id);
    if (!b)
        return GOLEM_ERR_NOT_FOUND;
    golem_status st = GOLEM_OK;
    if (!b->member.work)
        st = golem_document_store_open(b->member.work_root, true, NULL, &b->member.work, NULL);
    if (st == GOLEM_OK)
        *out = b->member;
    return st;
}

static golem_status start_current(void *context, const char *id, golem_admission *admission,
                                  const char *operation)
{
    ch_host *h = context;
    golem_candidate_member member;
    golem_status st = resolve_member(h, id, &member);
    if (st != GOLEM_OK)
        return st;
    /* The synchronous connector borrows only this candidate for this call. */
    golem_candidate_current_options options = h->options;
    options.bindings = find_binding(h, id);
    options.count = 1;
    options.target = NULL;
    golem_candidate_host connector;
    st = golem_candidate_current_host(&options, &connector);
    return st == GOLEM_OK ? connector.start(connector.context, id, admission, operation) : st;
}

static golem_status close_children(ch_host *h)
{
    golem_status st = GOLEM_OK;
    for (size_t i = 0; i < h->options.count; ++i) {
        golem_status closed = golem_document_store_close(h->bindings[i].member.work);
        h->bindings[i].member.work = NULL;
        if (st == GOLEM_OK)
            st = closed;
    }
    golem_status closed = golem_document_store_close(h->target);
    h->target = NULL;
    if (st == GOLEM_OK)
        st = closed;
    return st;
}

static golem_status authorize(void *context, golem_bytes bytes)
{
    ch_host *h = context;
    golem_digest digest;
    golem_status st = golem_digest_bytes(bytes, &digest);
    if (st == GOLEM_OK && (!h->approved || !dw_equal(&digest, &h->authorized)))
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    if (st == GOLEM_OK && !strcmp(dw_text(h->request, "operation"), "finish")) {
        if (!h->attested)
            return GOLEM_ERR_APPROVAL_REQUIRED;
        golem_candidate_current_binding *b = find_binding(h, dw_text(h->request, "candidate"));
        golem_candidate_member member;
        st = resolve_member(h, dw_text(h->request, "candidate"), &member);
        if (st != GOLEM_OK)
            return st;
        as_log log = {.directory = -1};
        st = as_load(b->member.work, NULL, NULL, &log);
        /* Expiry is not termination. Even an expired/recovery claim must be
         * explicitly reconciled before the operator can settle this candidate. */
        if (st == GOLEM_OK && as_active(log.state))
            st = GOLEM_ERR_LEASE_BUSY;
        as_close(&log);
    }
    return st;
}

static golem_status workspace_check(void *context, golem_workspace_operation op, const char *id)
{
    ch_host *h = context;
    (void)op;
    return h->approved && find_binding(h, id) ? GOLEM_OK : GOLEM_ERR_APPROVAL_REQUIRED;
}
static golem_status pulse(void *context)
{
    return ((ch_host *)context)->approved ? GOLEM_OK : GOLEM_ERR_APPROVAL_REQUIRED;
}

static golem_status request_cancel(void *context, const char *id, const char *session)
{
    ch_host *h = context;
    golem_candidate_current_binding *b = find_binding(h, id);
    if (!b || strcmp(b->session, session))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    golem_candidate_member member;
    golem_status opened = resolve_member(h, id, &member);
    if (opened != GOLEM_OK)
        return opened;
    struct json_object *notice = json_object_new_object();
    const char *group = dw_text(h->request, "group_id");
    golem_status st = notice ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK &&
        (!ex_uint(notice, "schema_version", 1) ||
         !ex_text(notice, "type", "golem.candidate-cancel.v1") ||
         !ex_text(notice, "group_id", group) || !ex_text(notice, "candidate", id) ||
         !ex_text(notice, "session", session) ||
         !dw_add_digest(notice, "runtime_binding", &b->runtime_binding)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_digest digest;
    if (st == GOLEM_OK)
        st = dw_put_json(b->member.work, notice, &digest);
    int dir = -1;
    if (st == GOLEM_OK)
        st = dw_dir(b->member.work->root, "candidate-notifications", true, &dir);
    if (st == GOLEM_OK)
        st = dw_publish(dir, group, (golem_bytes){digest.bytes, sizeof(digest.bytes)});
    if (dir >= 0 && close(dir) && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    json_object_put(notice);
    return st;
}

static golem_status cancel_current(void *context, const char *id)
{
    golem_candidate_current_binding *b = find_binding(context, id);
    return b ? request_cancel(context, id, b->session) : GOLEM_ERR_NOT_FOUND;
}

golem_status ch_open(ch_host *h, struct json_object *config)
{
    *h = (ch_host){0};
    golem_status st = ch_validate(config);
    if (st != GOLEM_OK)
        return st;
    h->config = json_object_get(config);
    st = ex_hash(config, &h->config_digest);
    if (st == GOLEM_OK)
        st = golem_document_store_open(dw_text(config, "parent"), true, NULL, &h->parent, NULL);
    struct json_object *limits = dw_get(config, "limits");
    golem_admission_options options = {.size = sizeof(options),
                                       .version = 1,
                                       .create = true,
                                       .limits = {.slots = dw_uint(limits, "slots"),
                                                  .cpu_millis = dw_uint(limits, "cpu_millis"),
                                                  .memory_bytes = dw_uint(limits, "memory_bytes")}};
    if (st == GOLEM_OK)
        st = golem_admission_open(dw_text(config, "admission"), &options, &h->admission);
    h->workspace = (golem_workspace_host){.struct_size = sizeof(h->workspace),
                                          .version = 1,
                                          .repository_id = dw_text(config, "repository_id"),
                                          .repository_root = dw_text(config, "repository_root"),
                                          .worktree_root = dw_text(config, "worktree_root"),
                                          .check = workspace_check,
                                          .pulse = pulse,
                                          .context = h};
    struct json_object *bindings = dw_get(config, "bindings");
    h->options = (golem_candidate_current_options){.size = sizeof(h->options),
                                                   .version = 1,
                                                   .bindings = h->bindings,
                                                   .count = json_object_array_length(bindings),
                                                   .context = h,
                                                   .authorize = authorize,
                                                   .request_cancel = request_cancel};
    for (size_t i = 0; i < h->options.count; ++i) {
        struct json_object *b = json_object_array_get_idx(bindings, i);
        golem_candidate_current_binding *out = &h->bindings[i];
        out->candidate = dw_text(b, "candidate");
        out->session = dw_text(b, "session");
        (void)dw_digest(b, "runtime_binding", &out->runtime_binding);
        out->member = (golem_candidate_member){.workspace = &h->workspace,
                                               .work_root = dw_text(b, "work"),
                                               .tree_root = dw_text(b, "tree"),
                                               .build_root = dw_text(b, "build"),
                                               .temp_root = dw_text(b, "temp")};
        (void)dw_digest(b, "environment", &out->member.environment);
    }
    h->capabilities = (golem_candidate_host){.size = sizeof(h->capabilities),
                                             .version = 1,
                                             .context = h,
                                             .check = authorize,
                                             .resolve = resolve_member,
                                             .start = start_current,
                                             .cancel = cancel_current};
    return st;
}

golem_status ch_close(ch_host *h)
{
    golem_status st = close_children(h), closed = golem_admission_close(h->admission);
    if (st == GOLEM_OK)
        st = closed;
    closed = golem_document_store_close(h->parent);
    if (st == GOLEM_OK)
        st = closed;
    json_object_put(h->config);
    *h = (ch_host){0};
    return st;
}

static golem_status candidate_call(ch_host *h, struct json_object *request,
                                   struct json_object **out)
{
    const char *text = json_object_to_json_string_ext(request, JSON_C_TO_STRING_PLAIN);
    if (!text)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_execution_reply reply = {0};
    golem_status st =
        golem_candidate_call(h->parent, &h->capabilities, h->admission,
                             (golem_bytes){(const uint8_t *)text, strlen(text)}, &reply, NULL);
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){reply.data, reply.size}, GOLEM_DOCUMENT_MAX_JSON, out);
    golem_execution_reply_free(&reply);
    return st;
}

static golem_status ticket_reply(const golem_admission_ticket *t, struct json_object **out)
{
    struct json_object *o = cf_token(&t->token);
    if (!o || !ex_uint(o, "state", t->state) || !ex_text(o, "operation_id", t->request.operation)) {
        json_object_put(o);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    *out = o;
    return GOLEM_OK;
}

static golem_status poll_agent(ch_host *h, struct json_object **out)
{
    const char *keys[] = {"operation", "group_id", "candidate", "session"};
    struct json_object *r = h->request;
    golem_candidate_current_binding *b = find_binding(h, dw_text(r, "candidate"));
    if (!dw_keys(r, keys, 4) || !b || strcmp(b->session, dw_text(r, "session")) ||
        !ws_id(dw_text(r, "group_id")) || strlen(dw_text(r, "group_id")) > 24)
        return GOLEM_ERR_PARSE;
    struct json_object *query = json_object_new_object(), *report = NULL;
    if (!query || !ex_text(query, "operation", "status") ||
        !ex_text(query, "group_id", dw_text(r, "group_id"))) {
        json_object_put(query);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_status st = candidate_call(h, query, &report);
    json_object_put(query);
    struct json_object *row = NULL, *rows = dw_get(report, "candidates");
    for (size_t i = 0; i < json_object_array_length(rows); ++i) {
        struct json_object *item = json_object_array_get_idx(rows, i);
        if (!strcmp(dw_text(item, "candidate"), b->candidate))
            row = item;
    }
    if (st == GOLEM_OK && !row)
        st = GOLEM_ERR_NOT_FOUND;
    golem_candidate_member member;
    if (st == GOLEM_OK)
        st = resolve_member(h, b->candidate, &member);
    char operation[64];
    (void)snprintf(operation, sizeof(operation), "cf-%s-%s", dw_text(r, "group_id"), b->candidate);
    golem_admission_ticket ticket;
    if (st == GOLEM_OK)
        st = golem_admission_lookup(h->admission, operation, &ticket);
    if (st == GOLEM_OK && (strcmp(ticket.request.work, dw_text(b->member.work->spec, "work_id")) ||
                           strcmp(ticket.request.session, b->session) ||
                           !dw_equal(&ticket.request.runtime_binding, &b->runtime_binding)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    as_log log = {.directory = -1};
    if (st == GOLEM_OK)
        st = as_load(b->member.work, NULL, NULL, &log);
    uint64_t now = 0;
    golem_digest boot;
    if (st == GOLEM_OK)
        st = as_clock_read(NULL, &now, &boot);
    struct json_object *active = dw_get(log.state, "active");
    bool live = st == GOLEM_OK && as_live(&log, now, &boot) &&
                !strcmp(dw_text(active, "state"), "RUNNING") &&
                !strcmp(dw_text(active, "session_id"), b->session);
    golem_digest binding;
    live = live && dw_digest(active, "runtime_binding", &binding);
    if (live) {
        struct json_object *original = NULL, *current = NULL, *manifest = NULL;
        st = rp_validate_claim(b->member.work, active);
        if (st == GOLEM_OK)
            st = dw_cas_json(b->member.work, &b->runtime_binding, &original);
        if (st == GOLEM_OK)
            st = dw_cas_json(b->member.work, &binding, &current);
        if (st == GOLEM_OK)
            st = as_fresh(b->member.work, active, false, &manifest);
        live = st == GOLEM_OK &&
               !strcmp(dw_text(original, "generation_digest"),
                       dw_text(current, "generation_digest")) &&
               json_object_equal(dw_get(original, "selection"), dw_get(current, "selection"));
        json_object_put(original);
        json_object_put(current);
        json_object_put(manifest);
    }
    bool cancelled = !strcmp(dw_text(row, "state"), "CANCEL_REQUESTED");
    bool proceed = live && !cancelled && !strcmp(dw_text(row, "state"), "RUNNING") &&
                   ticket.state == GOLEM_ADMISSION_RUNNING;
    struct json_object *o = json_object_new_object();
    if (st == GOLEM_OK &&
        (!o || !ex_text(o, "candidate", b->candidate) || !ex_text(o, "session", b->session) ||
         !dw_add(o, "may_continue", json_object_new_boolean(proceed)) ||
         !dw_add(o, "cancel_requested", json_object_new_boolean(cancelled)) ||
         !ex_text(o, "delivery", "COOPERATIVE_POLL") ||
         !dw_add(o, "ticket", cf_token(&ticket.token))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    as_close(&log);
    json_object_put(report);
    if (st == GOLEM_OK)
        *out = o;
    else
        json_object_put(o);
    return st;
}

static golem_status settle(ch_host *h, struct json_object **out)
{
    const char *keys[] = {"operation", "group_id",     "candidate",  "token",  "qa",
                          "cancelled", "tokens_known", "cost_known", "tokens", "nano_cost"};
    if (!h->attested || !dw_keys(h->request, keys, 10))
        return GOLEM_ERR_APPROVAL_REQUIRED;
    struct json_object *proof = json_object_new_object(), *finish = NULL;
    golem_status st = proof ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && (!ex_uint(proof, "schema_version", 1) ||
                           !ex_text(proof, "type", "golem.current-agent-termination.v1") ||
                           !ex_text(proof, "trust", "operator_attested") ||
                           !dw_add_digest(proof, "host_config", &h->config_digest) ||
                           !dw_add(proof, "request", json_object_get(h->request))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && json_object_deep_copy(h->request, &finish, NULL))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_digest receipt;
    if (st == GOLEM_OK)
        st = dw_put_json(h->parent, proof, &receipt);
    if (st == GOLEM_OK && (!ex_text(finish, "operation", "finish") ||
                           !dw_add_digest(finish, "termination", &receipt)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *original = h->request;
    h->request = finish;
    if (st == GOLEM_OK)
        st = ex_hash(finish, &h->authorized);
    if (st == GOLEM_OK)
        st = candidate_call(h, finish, out);
    h->request = original;
    json_object_put(finish);
    json_object_put(proof);
    return st;
}

golem_status ch_call(ch_host *h, struct json_object *envelope, struct json_object **out)
{
    const char *keys[] = {"schema_version", "request", "approval", "termination_attestation"};
    h->request = dw_get(envelope, "request");
    h->approved = h->attested = false;
    golem_status st =
        dw_keys(envelope, keys, 4) && dw_uint(envelope, "schema_version") == 1 &&
                json_object_is_type(h->request, json_type_object) &&
                json_object_is_type(dw_get(envelope, "approval"), json_type_string) &&
                json_object_is_type(dw_get(envelope, "termination_attestation"), json_type_string)
            ? GOLEM_OK
            : GOLEM_ERR_PARSE;
    if (st == GOLEM_OK) {
        const char *encoded = json_object_to_json_string_ext(h->request, JSON_C_TO_STRING_PLAIN);
        if (!encoded)
            st = GOLEM_ERR_OUT_OF_MEMORY;
        else if (strlen(encoded) > GOLEM_DOCUMENT_MAX_JSON)
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    if (st == GOLEM_OK)
        st = ex_hash(h->request, &h->authorized);
    golem_digest approved, attested;
    h->approved = st == GOLEM_OK && dw_digest(envelope, "approval", &approved) &&
                  dw_equal(&approved, &h->authorized);
    h->attested = st == GOLEM_OK && dw_digest(envelope, "termination_attestation", &attested) &&
                  dw_equal(&attested, &h->authorized);
    const char *op = dw_text(h->request, "operation");
    bool readonly = !strcmp(op, "status") || !strcmp(op, "ticket") || !strcmp(op, "poll");
    if (st == GOLEM_OK && !readonly && !h->approved)
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    if (st == GOLEM_OK && !readonly && !strcmp(dw_text(h->parent->spec, "permission"), "DENY"))
        st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK && !strcmp(op, "finish"))
        st = GOLEM_ERR_APPROVAL_REQUIRED; /* Use typed, operator-attested settle. */
    const char *only_op[] = {"operation"};
    if (st == GOLEM_OK && (!strcmp(op, "grant") || !strcmp(op, "shutdown"))) {
        if (!dw_keys(h->request, only_op, 1))
            st = GOLEM_ERR_PARSE;
        else if (!strcmp(op, "shutdown")) {
            h->stop = true;
            *out = json_object_new_object();
            if (!*out)
                st = GOLEM_ERR_OUT_OF_MEMORY;
        } else {
            golem_admission_ticket ticket;
            st = golem_admission_grant(h->admission, &ticket);
            if (st == GOLEM_OK)
                st = ticket_reply(&ticket, out);
        }
    } else if (st == GOLEM_OK && !strcmp(op, "ticket")) {
        const char *tk[] = {"operation", "operation_id"};
        golem_admission_ticket ticket;
        st =
            dw_keys(h->request, tk, 2) && dw_id(dw_text(h->request, "operation_id"))
                ? golem_admission_lookup(h->admission, dw_text(h->request, "operation_id"), &ticket)
                : GOLEM_ERR_PARSE;
        if (st == GOLEM_OK)
            st = ticket_reply(&ticket, out);
    } else if (st == GOLEM_OK) {
        if (st == GOLEM_OK && !strcmp(op, "workspace-create")) {
            const char *wk[] = {"operation", "candidate", "base_commit"};
            golem_candidate_current_binding *b = find_binding(h, dw_text(h->request, "candidate"));
            golem_workspace_result result;
            st = b && dw_keys(h->request, wk, 3) ? GOLEM_OK : GOLEM_ERR_PARSE;
            golem_candidate_member member;
            if (st == GOLEM_OK)
                st = resolve_member(h, b->candidate, &member);
            if (st == GOLEM_OK)
                st = golem_workspace_call(b->member.work, b->member.workspace,
                                          GOLEM_WORKSPACE_CREATE, b->candidate,
                                          dw_text(h->request, "base_commit"), NULL, &result, NULL);
            if (st == GOLEM_OK) {
                *out = json_object_new_object();
                if (!*out || !ex_text(*out, "path", result.path) ||
                    !dw_add_digest(*out, "receipt", &result.receipt))
                    st = GOLEM_ERR_OUT_OF_MEMORY;
            }
        } else if (st == GOLEM_OK && !strcmp(op, "poll"))
            st = poll_agent(h, out);
        else if (st == GOLEM_OK && !strcmp(op, "settle"))
            st = settle(h, out);
        else if (st == GOLEM_OK)
            st = candidate_call(h, h->request, out);
    }
    golem_status closed = close_children(h);
    if (st == GOLEM_OK)
        st = closed;
    h->request = NULL;
    h->approved = h->attested = false;
    return st;
}
