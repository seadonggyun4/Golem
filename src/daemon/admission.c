#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE 1
#endif
#include "admission_internal.h"
#include "internal.h"
#include "../evidence/internal.h"
#include "../agent_session/internal.h"
#include <openssl/rand.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>

static golem_status open_error(golem_diagnostic *d, golem_status status,
                              const char *operation, int saved_errno)
{
    if (d) {
        char message[128];
        (void)snprintf(message, sizeof(message), "admission.%s errno=%d", operation,
                       saved_errno);
        (void)golem_diagnostic_set(d, status, GOLEM_DIAGNOSTIC_NO_OFFSET, message);
    }
    return status;
}

static golem_status ready(golem_admission *a)
{
    if (!a)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (a->busy || a->poisoned || a->owner != getpid())
        return GOLEM_ERR_INVALID_STATE;
    return GOLEM_OK;
}
static golem_status token_check(golem_admission *a, golem_admission_token token)
{
    if (token.epoch != a->model.epoch || memcmp(token.instance, a->model.instance, 16) ||
        memcmp(&token.boot, &a->model.boot, 32))
        return GOLEM_ERR_STALE_LEASE;
    return token.ticket && token.ticket <= a->model.count ? GOLEM_OK : GOLEM_ERR_NOT_FOUND;
}
static ga_event transition(golem_admission_token token, ga_operation op)
{
    ga_event e = {0};
    e.operation = op;
    e.ticket = token.ticket;
    e.epoch = token.epoch;
    e.boot = token.boot;
    memcpy(e.nonce, token.instance, 16);
    return e;
}
static ga_event limits_event(golem_admission_limits limits, ga_operation op)
{
    ga_event e = {0};
    e.operation = op;
    e.ticket = limits.slots;
    e.request.cpu_millis = limits.cpu_millis;
    e.request.memory_bytes = limits.memory_bytes;
    e.epoch = limits.foreground_burst;
    return e;
}

golem_status golem_admission_open(const char *root, const golem_admission_options *o,
                                  golem_admission **out)
{
    return golem_admission_open_diagnostic(root, o, out, NULL);
}

golem_status golem_admission_open_diagnostic(const char *root,
    const golem_admission_options *o, golem_admission **out, golem_diagnostic *diagnostic)
{
    if (diagnostic)
        (void)golem_diagnostic_clear(diagnostic);
    if (!root || root[0] != '/' || !o || !out || o->size != sizeof(*o))
        return open_error(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, "arguments", 0);
    if (o->version != GOLEM_ADMISSION_VERSION)
        return open_error(diagnostic, GOLEM_ERR_UNSUPPORTED_VERSION, "version", 0);
    golem_status s = golem_allocator_validate(o->allocator);
    if (s != GOLEM_OK)
        return open_error(diagnostic, s, "allocator", 0);
    golem_allocator allocator = o->allocator ? *o->allocator : golem_allocator_default();
    golem_admission *a = NULL;
    s = golem_allocator_alloc(&allocator, sizeof(*a), (void **)&a);
    if (s != GOLEM_OK)
        return open_error(diagnostic, s, "allocate", 0);
    *a =
        (golem_admission){.allocator = allocator, .directory = -1, .leader = -1, .owner = getpid()};
    const char *operation = "root_open";
    errno = 0;
    a->directory = golem_evidence_path_open(root, true);
    if (a->directory < 0) {
        s = GOLEM_ERR_IO;
        goto fail;
    }
    operation = "owner_lock";
    errno = 0;
    a->leader = gd_lock(a->directory, ".owner", o->create, true);
    if (a->leader < 0) {
        s = GOLEM_ERR_JOURNAL_BUSY;
        goto fail;
    }
    operation = "replay";
    errno = 0;
    s = ga_load(a, o->expected);
    if (s != GOLEM_OK)
        goto fail;
    /* Establish required host identity before publishing any new durable event. */
    if (!a->checkpoint.records && !o->create) {
        s = GOLEM_ERR_NOT_FOUND;
        goto fail;
    }
    ga_event boot = {.operation = GA_BOOT, .epoch = a->model.epoch + 1};
    uint64_t now;
    operation = "boot_identity_clock";
    errno = 0;
    s = as_clock_read(NULL, &now, &boot.boot);
    if (s != GOLEM_OK)
        goto fail;
    if (!a->checkpoint.records) {
        ga_event init = limits_event(o->limits, GA_INIT);
        operation = "random_namespace";
        errno = 0;
        if (RAND_bytes(init.request.runtime_binding.bytes, 32) != 1) {
            s = GOLEM_ERR_CRYPTO;
            goto fail;
        }
        operation = "initial_commit";
        errno = 0;
        s = ga_commit(a, &init);
        if (s != GOLEM_OK)
            goto fail;
    }
    operation = "random_instance";
    errno = 0;
    if (RAND_bytes(boot.nonce, 16) != 1) {
        s = GOLEM_ERR_CRYPTO;
        goto fail;
    }
    operation = "epoch_commit";
    errno = 0;
    s = ga_commit(a, &boot);
    if (s != GOLEM_OK)
        goto fail;
    *out = a;
    return GOLEM_OK;
fail:
    (void)open_error(diagnostic, s, operation, errno);
    (void)golem_admission_close(a);
    return s;
}

golem_status golem_admission_close(golem_admission *a)
{
    if (!a)
        return GOLEM_OK;
    if (a->busy)
        return GOLEM_ERR_INVALID_STATE;
    golem_status s = GOLEM_OK;
    if (a->leader >= 0 && close(a->leader) != 0)
        s = GOLEM_ERR_IO;
    if (a->directory >= 0 && close(a->directory) != 0)
        s = GOLEM_ERR_IO;
    golem_allocator allocator = a->allocator;
    (void)golem_allocator_free(&allocator, a);
    return s;
}

golem_status golem_admission_identity(golem_admission *a, golem_digest *id,
                                      golem_admission_checkpoint *checkpoint)
{
    golem_status s = ready(a);
    if (s != GOLEM_OK)
        return s;
    if (!id || !checkpoint)
        return GOLEM_ERR_INVALID_ARGUMENT;
    *id = a->model.namespace_id;
    *checkpoint = a->checkpoint;
    return GOLEM_OK;
}

golem_status golem_admission_enqueue(golem_admission *a, const golem_admission_request *r,
                                     uint64_t *out)
{
    golem_status s = ready(a);
    if (s != GOLEM_OK)
        return s;
    if (!r || !out || !memchr(r->operation, 0, sizeof(r->operation)) ||
        !memchr(r->work, 0, sizeof(r->work)) || !memchr(r->session, 0, sizeof(r->session)))
        return GOLEM_ERR_INVALID_ARGUMENT;
    for (uint64_t i = 0; i < a->model.count; ++i) {
        if (strcmp(r->operation, a->model.tickets[i].request.operation))
            continue;
        if (!ga_request_equal(r, &a->model.tickets[i].request))
            return GOLEM_ERR_IDENTITY_MISMATCH;
        *out = i + 1;
        return GOLEM_OK;
    }
    ga_event e = {.operation = GA_ENQUEUE, .ticket = a->model.count + 1};
    /* Copy semantic fields only, excluding uninitialized string suffixes/padding. */
    memcpy(e.request.operation, r->operation, strlen(r->operation));
    memcpy(e.request.work, r->work, strlen(r->work));
    memcpy(e.request.session, r->session, strlen(r->session));
    e.request.runtime_binding = r->runtime_binding;
    e.request.cpu_millis = r->cpu_millis;
    e.request.memory_bytes = r->memory_bytes;
    e.request.parent = r->parent;
    e.request.foreground = r->foreground;
    s = ga_commit(a, &e);
    if (s == GOLEM_OK)
        *out = e.ticket;
    return s;
}

golem_status golem_admission_lookup(golem_admission *a, const char *operation,
                                    golem_admission_ticket *out)
{
    golem_status s = ready(a);
    if (s != GOLEM_OK)
        return s;
    if (!operation || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    for (uint64_t i = 0; i < a->model.count; ++i)
        if (!strcmp(operation, a->model.tickets[i].request.operation)) {
            *out = a->model.tickets[i];
            return GOLEM_OK;
        }
    return GOLEM_ERR_NOT_FOUND;
}

golem_status golem_admission_grant(golem_admission *a, golem_admission_ticket *out)
{
    golem_status s = ready(a);
    if (s != GOLEM_OK)
        return s;
    if (!out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    uint64_t ticket = ga_pick(&a->model);
    if (!ticket)
        return GOLEM_ERR_NOT_FOUND;
    ga_event e = transition(a->model.tickets[ticket - 1].token, GA_GRANT);
    s = ga_commit(a, &e);
    if (s == GOLEM_OK)
        *out = a->model.tickets[ticket - 1];
    return s;
}

golem_status golem_admission_resize(golem_admission *a, golem_admission_limits limits)
{
    golem_status s = ready(a);
    if (s != GOLEM_OK)
        return s;
    ga_event e = limits_event(limits, GA_RESIZE);
    return ga_commit(a, &e);
}

static golem_status change(golem_admission *a, golem_admission_token token, ga_operation op,
                           golem_digest proof)
{
    golem_status s = ready(a);
    if (s == GOLEM_OK)
        s = token_check(a, token);
    if (s != GOLEM_OK)
        return s;
    ga_event e = transition(token, op);
    e.proof = proof;
    /* Exact repeat is successful without another durable event. */
    a->scratch = a->model;
    s = ga_apply(&a->scratch, &e);
    if (s != GOLEM_OK)
        return s;
    const golem_admission_ticket *before = &a->model.tickets[token.ticket - 1];
    const golem_admission_ticket *after = &a->scratch.tickets[token.ticket - 1];
    if (before->state == after->state &&
        !memcmp(&before->binding_receipt, &after->binding_receipt, sizeof(golem_digest)) &&
        !memcmp(&before->termination_receipt, &after->termination_receipt, sizeof(golem_digest)))
        return GOLEM_OK;
    return ga_commit(a, &e);
}

golem_status golem_admission_cancel(golem_admission *a, golem_admission_token t)
{
    return change(a, t, GA_CANCEL, (golem_digest){0});
}
golem_status golem_admission_settle(golem_admission *a, golem_admission_token t, golem_digest proof)
{
    return change(a, t, GA_SETTLE, proof);
}
golem_status golem_admission_release(golem_admission *a, golem_admission_token t)
{
    return change(a, t, GA_RELEASE, (golem_digest){0});
}

golem_status golem_admission_begin(golem_admission *a, golem_admission_token token,
    golem_status (*publish)(void *, const golem_digest *, const golem_admission_ticket *,
                           golem_digest *), void *context, golem_admission_ticket *out)
{
    golem_status s = ready(a);
    if (s == GOLEM_OK)
        s = token_check(a, token);
    if (s != GOLEM_OK)
        return s;
    if (!publish || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_admission_ticket ticket = a->model.tickets[token.ticket - 1];
    if (ticket.state != GOLEM_ADMISSION_GRANTED || ga_children(&a->model, token.ticket))
        return GOLEM_ERR_INVALID_STATE;
    golem_digest proof = {0};
    a->busy = true;
    s = publish(context, &a->model.namespace_id, &ticket, &proof);
    a->busy = false;
    if (s != GOLEM_OK)
        return s; /* Publisher is idempotent; execution intent not committed. */
    s = change(a, token, GA_BIND, proof);
    if (s == GOLEM_OK)
        s = change(a, token, GA_START, (golem_digest){0});
    if (s == GOLEM_OK)
        s = change(a, token, GA_RUN, (golem_digest){0});
    if (s != GOLEM_OK)
        return s;
    *out = a->model.tickets[token.ticket - 1];
    return GOLEM_OK;
}

golem_status golem_admission_dispatch(golem_admission *a, golem_admission_token token,
                                      const golem_admission_dispatch_ops *ops, void *context)
{
    if (!ops || !ops->publish || !ops->execute)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_admission_ticket ticket;
    golem_status s = golem_admission_begin(a, token, ops->publish, context, &ticket);
    if (s != GOLEM_OK)
        return s;
    golem_digest proof = {0};
    a->busy = true;
    s = ops->execute(context, &ticket, &proof);
    a->busy = false;
    if (s != GOLEM_OK)
        return s;
    s = golem_admission_settle(a, token, proof);
    if (s == GOLEM_OK)
        s = golem_admission_release(a, token);
    return s;
}
