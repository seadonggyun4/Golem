#include "internal.h"
#include <string.h>

static const golem_candidate_current_binding *
binding(const golem_candidate_current_options *options, const char *id)
{
    if (!id)
        return NULL;
    for (size_t i = 0; i < options->count; ++i)
        if (!strcmp(options->bindings[i].candidate, id))
            return &options->bindings[i];
    return NULL;
}

static golem_status check(void *context, golem_bytes request)
{
    const golem_candidate_current_options *options = context;
    return options->authorize(options->context, request);
}

static golem_status resolve(void *context, const char *id, golem_candidate_member *out)
{
    const golem_candidate_current_options *options = context;
    if (!id || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (!strcmp(id, "$target") && options->target) {
        *out = *options->target;
        return GOLEM_OK;
    }
    const golem_candidate_current_binding *b = binding(options, id);
    if (!b)
        return GOLEM_ERR_NOT_FOUND;
    *out = b->member;
    return GOLEM_OK;
}

static golem_status publish(void *context, const golem_digest *namespace_id,
                            const golem_admission_ticket *ticket, golem_digest *receipt)
{
    const golem_candidate_current_binding *b = context;
    if (strcmp(ticket->request.work, dw_text(b->member.work->spec, "work_id")) ||
        strcmp(ticket->request.session, b->session) ||
        !dw_equal(&ticket->request.runtime_binding, &b->runtime_binding))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    return golem_admission_publish_work(b->member.work, namespace_id, ticket, receipt);
}

static golem_status start(void *context, const char *id, golem_admission *admission,
                          const char *operation)
{
    const golem_candidate_current_options *options = context;
    const golem_candidate_current_binding *b = binding(options, id);
    if (!b || !admission || !operation)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_admission_ticket ticket;
    golem_status st = golem_admission_lookup(admission, operation, &ticket);
    if (st == GOLEM_OK && ticket.state != GOLEM_ADMISSION_GRANTED)
        st = GOLEM_ERR_INVALID_STATE;
    /* Reject misbinding before committing a STARTING intent. The publisher
     * repeats identity and checks the live claim immediately before publication. */
    if (st == GOLEM_OK && (strcmp(ticket.request.work, dw_text(b->member.work->spec, "work_id")) ||
                           strcmp(ticket.request.session, b->session) ||
                           !dw_equal(&ticket.request.runtime_binding, &b->runtime_binding)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK)
        st = golem_admission_begin(admission, ticket.token, publish, (void *)b, &ticket);
    return st;
}

static golem_status cancel(void *context, const char *id)
{
    const golem_candidate_current_options *options = context;
    const golem_candidate_current_binding *b = binding(options, id);
    if (!b)
        return GOLEM_ERR_NOT_FOUND;
    return options->request_cancel(options->context, id, b->session);
}

golem_status golem_candidate_current_host(const golem_candidate_current_options *options,
                                          golem_candidate_host *out)
{
    if (!options || !out || options->size != sizeof(*options) || options->version != 1 ||
        !options->bindings || !options->count || options->count > GOLEM_CANDIDATE_MAX ||
        !options->authorize || !options->request_cancel)
        return GOLEM_ERR_INVALID_ARGUMENT;
    for (size_t i = 0; i < options->count; ++i) {
        const golem_candidate_current_binding *b = &options->bindings[i];
        if (!b->candidate || !b->session || !dw_id(b->candidate) || !dw_id(b->session) ||
            !b->member.work || !b->member.workspace || !b->member.work_root ||
            !b->member.tree_root || !b->member.build_root || !b->member.temp_root)
            return GOLEM_ERR_INVALID_ARGUMENT;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(b->candidate, options->bindings[j].candidate) ||
                b->member.work == options->bindings[j].member.work)
                return GOLEM_ERR_IDENTITY_MISMATCH;
    }
    if (options->target && (!options->target->work || !options->target->tree_root))
        return GOLEM_ERR_INVALID_ARGUMENT;
    *out = (golem_candidate_host){.size = sizeof(*out),
                                  .version = 1,
                                  .context = (void *)options,
                                  .check = check,
                                  .resolve = resolve,
                                  .start = start,
                                  .cancel = cancel};
    return GOLEM_OK;
}
