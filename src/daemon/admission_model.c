#include "admission_internal.h"
#include <string.h>

bool ga_nonzero(const void *bytes, size_t size)
{
    const uint8_t *p = bytes;
    for (size_t i = 0; i < size; ++i)
        if (p[i])
            return true;
    return false;
}

static bool identifier(const char *s, size_t capacity)
{
    size_t n = 0;
    while (n < capacity && s[n]) {
        unsigned char c = (unsigned char)s[n++];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
              c == '-' || c == '_'))
            return false;
    }
    return n && n < capacity && strcmp(s, ".") && strcmp(s, "..");
}

bool ga_live(golem_admission_state s)
{
    return s >= GOLEM_ADMISSION_GRANTED && s <= GOLEM_ADMISSION_SETTLING;
}

bool ga_children(const ga_model *m, uint64_t parent)
{
    for (uint64_t i = 0; i < m->count; ++i)
        if (m->tickets[i].request.parent == parent &&
            (ga_live(m->tickets[i].state) || m->tickets[i].state == GOLEM_ADMISSION_QUEUED))
            return true;
    return false;
}

bool ga_request_equal(const golem_admission_request *a, const golem_admission_request *b)
{
    return !strcmp(a->operation, b->operation) && !strcmp(a->work, b->work) &&
           !strcmp(a->session, b->session) &&
           !memcmp(&a->runtime_binding, &b->runtime_binding, sizeof(a->runtime_binding)) &&
           a->cpu_millis == b->cpu_millis && a->memory_bytes == b->memory_bytes &&
           a->parent == b->parent && a->foreground == b->foreground;
}

static bool limits_valid(golem_admission_limits l)
{
    return l.slots && l.slots <= 32 && l.cpu_millis && l.memory_bytes && l.foreground_burst <= 32;
}

static bool fits(const ga_model *m, uint64_t index)
{
    const golem_admission_request *r = &m->tickets[index].request;
    uint64_t slots = 0, cpu = 0, memory = 0;
    if (r->parent) {
        const golem_admission_ticket *p = &m->tickets[r->parent - 1];
        if (p->state != GOLEM_ADMISSION_GRANTED)
            return false;
        for (uint64_t i = 0; i < m->count; ++i)
            if (m->tickets[i].request.parent == r->parent && ga_live(m->tickets[i].state))
                return false;
        return true; /* Child bounds and lineage checked on enqueue. */
    }
    for (uint64_t i = 0; i < m->count; ++i) {
        const golem_admission_ticket *t = &m->tickets[i];
        if (!ga_live(t->state) || t->request.parent)
            continue;
        if (!strcmp(t->request.work, r->work) || !strcmp(t->request.session, r->session))
            return false;
        if (UINT64_MAX - cpu < t->request.cpu_millis ||
            UINT64_MAX - memory < t->request.memory_bytes)
            return false;
        ++slots;
        cpu += t->request.cpu_millis;
        memory += t->request.memory_bytes;
    }
    return slots < m->limits.slots && cpu <= m->limits.cpu_millis &&
           memory <= m->limits.memory_bytes && r->cpu_millis <= m->limits.cpu_millis - cpu &&
           r->memory_bytes <= m->limits.memory_bytes - memory;
}

uint64_t ga_pick(const ga_model *m)
{
    uint64_t oldest = 0;
    /* Nested work never waits for another global slot; drain it before roots. */
    for (uint64_t i = 0; i < m->count; ++i)
        if (m->tickets[i].state == GOLEM_ADMISSION_QUEUED && m->tickets[i].request.parent &&
            fits(m, i))
            return i + 1;
    for (uint64_t i = 0; i < m->count; ++i) {
        if (m->tickets[i].state != GOLEM_ADMISSION_QUEUED || m->tickets[i].request.parent)
            continue;
        if (!oldest)
            oldest = i + 1;
        if (m->bypasses >= m->limits.foreground_burst)
            break;
        if (m->tickets[i].request.foreground && fits(m, i))
            return i + 1;
    }
    return oldest && fits(m, oldest - 1) ? oldest : 0;
}

static golem_status enqueue(ga_model *m, const ga_event *e)
{
    const golem_admission_request *r = &e->request;
    if (!identifier(r->operation, sizeof(r->operation)) || !identifier(r->work, sizeof(r->work)) ||
        !identifier(r->session, sizeof(r->session)) || !ga_nonzero(&r->runtime_binding, 32) ||
        !r->cpu_millis || !r->memory_bytes)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (m->count == GOLEM_ADMISSION_MAX_TICKETS)
        return GOLEM_ERR_QUEUE_FULL;
    if (e->ticket != m->count + 1)
        return GOLEM_ERR_INVALID_STATE;
    for (uint64_t i = 0; i < m->count; ++i)
        if (!strcmp(r->operation, m->tickets[i].request.operation))
            return GOLEM_ERR_INVALID_STATE;
    if (r->parent) {
        if (r->parent > m->count)
            return GOLEM_ERR_INVALID_ARGUMENT;
        const golem_admission_ticket *p = &m->tickets[r->parent - 1];
        if (p->request.parent || p->state != GOLEM_ADMISSION_GRANTED ||
            strcmp(p->request.work, r->work) || strcmp(p->request.session, r->session) ||
            r->cpu_millis > p->request.cpu_millis || r->memory_bytes > p->request.memory_bytes)
            return GOLEM_ERR_INVALID_STATE;
    } else if (r->cpu_millis > m->limits.cpu_millis || r->memory_bytes > m->limits.memory_bytes) {
        return GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    golem_admission_ticket *t = &m->tickets[m->count++];
    *t = (golem_admission_ticket){0};
    t->request = *r;
    t->state = GOLEM_ADMISSION_QUEUED;
    t->token.ticket = e->ticket;
    t->token.epoch = m->epoch;
    t->token.boot = m->boot;
    memcpy(t->token.instance, m->instance, 16);
    return GOLEM_OK;
}

static golem_status boot(ga_model *m, const ga_event *e)
{
    if (m->epoch == UINT64_MAX || e->epoch != m->epoch + 1 || !ga_nonzero(e->nonce, 16) ||
        !ga_nonzero(&e->boot, 32) || !memcmp(e->nonce, m->instance, 16))
        return GOLEM_ERR_INVALID_STATE;
    ++m->epoch;
    m->boot = e->boot;
    memcpy(m->instance, e->nonce, 16);
    /* Unstarted roots with uncertain children must retain the shared reservation. */
    for (uint64_t i = m->count; i > 0; --i) {
        golem_admission_ticket *t = &m->tickets[i - 1];
        if (t->state == GOLEM_ADMISSION_GRANTED)
            t->state =
                ga_children(m, i) ? GOLEM_ADMISSION_RECONCILE_REQUIRED : GOLEM_ADMISSION_CANCELLED;
        else if (t->state == GOLEM_ADMISSION_QUEUED && t->request.parent)
            t->state = GOLEM_ADMISSION_CANCELLED;
        else if (ga_live(t->state) && t->state != GOLEM_ADMISSION_SETTLING)
            t->state = GOLEM_ADMISSION_RECONCILE_REQUIRED;
        t->token.epoch = m->epoch;
        t->token.boot = m->boot;
        memcpy(t->token.instance, m->instance, 16);
    }
    return GOLEM_OK;
}

golem_status ga_apply(ga_model *m, const ga_event *e)
{
    if (e->operation == GA_INIT || e->operation == GA_RESIZE) {
        golem_admission_limits l = {e->ticket, e->request.cpu_millis, e->request.memory_bytes,
                                    e->epoch};
        if (!limits_valid(l))
            return GOLEM_ERR_INVALID_ARGUMENT;
        if (e->operation == GA_INIT) {
            if (ga_nonzero(&m->namespace_id, 32) || !ga_nonzero(&e->request.runtime_binding, 32))
                return GOLEM_ERR_INVALID_STATE;
            m->namespace_id = e->request.runtime_binding;
        } else if (!m->epoch)
            return GOLEM_ERR_INVALID_STATE;
        m->limits = l;
        return GOLEM_OK;
    }
    if (!ga_nonzero(&m->namespace_id, 32))
        return GOLEM_ERR_INVALID_STATE;
    if (e->operation == GA_BOOT)
        return boot(m, e);
    if (!m->epoch)
        return GOLEM_ERR_INVALID_STATE;
    if (e->operation == GA_ENQUEUE)
        return enqueue(m, e);
    if (!e->ticket || e->ticket > m->count)
        return GOLEM_ERR_NOT_FOUND;
    golem_admission_ticket *t = &m->tickets[e->ticket - 1];
    if (e->epoch != m->epoch || memcmp(e->nonce, m->instance, 16) || memcmp(&e->boot, &m->boot, 32))
        return GOLEM_ERR_STALE_LEASE;
    switch (e->operation) {
    case GA_GRANT: {
        if (ga_pick(m) != e->ticket)
            return GOLEM_ERR_INVALID_STATE;
        if (!t->request.parent) {
            bool earlier = false;
            for (uint64_t i = 0; i + 1 < e->ticket; ++i)
                if (m->tickets[i].state == GOLEM_ADMISSION_QUEUED && !m->tickets[i].request.parent)
                    earlier = true;
            m->bypasses = earlier ? m->bypasses + 1 : 0;
        }
        t->state = GOLEM_ADMISSION_GRANTED;
        return GOLEM_OK;
    }
    case GA_BIND:
        if (t->state != GOLEM_ADMISSION_GRANTED || !ga_nonzero(&e->proof, 32) ||
            ga_children(m, e->ticket))
            return GOLEM_ERR_INVALID_STATE;
        if (ga_nonzero(&t->binding_receipt, 32) && memcmp(&t->binding_receipt, &e->proof, 32))
            return GOLEM_ERR_IDENTITY_MISMATCH;
        t->binding_receipt = e->proof;
        return GOLEM_OK;
    case GA_START:
        if (t->state != GOLEM_ADMISSION_GRANTED || !ga_nonzero(&t->binding_receipt, 32) ||
            ga_children(m, e->ticket))
            return GOLEM_ERR_INVALID_STATE;
        t->state = GOLEM_ADMISSION_STARTING;
        return GOLEM_OK;
    case GA_RUN:
        if (t->state != GOLEM_ADMISSION_STARTING)
            return GOLEM_ERR_INVALID_STATE;
        t->state = GOLEM_ADMISSION_RUNNING;
        return GOLEM_OK;
    case GA_CANCEL:
        if (ga_children(m, e->ticket))
            return GOLEM_ERR_INVALID_STATE;
        if (t->state == GOLEM_ADMISSION_QUEUED || t->state == GOLEM_ADMISSION_GRANTED)
            t->state = GOLEM_ADMISSION_CANCELLED;
        else if (t->state == GOLEM_ADMISSION_STARTING || t->state == GOLEM_ADMISSION_RUNNING)
            t->state = GOLEM_ADMISSION_CANCEL_REQUESTED;
        else if (t->state != GOLEM_ADMISSION_CANCEL_REQUESTED &&
                 t->state != GOLEM_ADMISSION_CANCELLED)
            return GOLEM_ERR_INVALID_STATE;
        return GOLEM_OK;
    case GA_SETTLE:
        if (!ga_nonzero(&e->proof, 32) || ga_children(m, e->ticket))
            return GOLEM_ERR_INVALID_STATE;
        if (t->state == GOLEM_ADMISSION_SETTLING || t->state == GOLEM_ADMISSION_RELEASED)
            return memcmp(&t->termination_receipt, &e->proof, 32) ? GOLEM_ERR_IDENTITY_MISMATCH
                                                                  : GOLEM_OK;
        if (t->state != GOLEM_ADMISSION_RUNNING && t->state != GOLEM_ADMISSION_STARTING &&
            t->state != GOLEM_ADMISSION_CANCEL_REQUESTED &&
            t->state != GOLEM_ADMISSION_RECONCILE_REQUIRED)
            return GOLEM_ERR_INVALID_STATE;
        t->termination_receipt = e->proof;
        t->state = GOLEM_ADMISSION_SETTLING;
        return GOLEM_OK;
    case GA_RELEASE:
        if (ga_children(m, e->ticket) ||
            (t->state != GOLEM_ADMISSION_SETTLING && t->state != GOLEM_ADMISSION_RELEASED))
            return GOLEM_ERR_INVALID_STATE;
        t->state = GOLEM_ADMISSION_RELEASED;
        return GOLEM_OK;
    default:
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
}
