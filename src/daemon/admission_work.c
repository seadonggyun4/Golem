#include "admission_internal.h"
#include "../runtime/profile_internal.h"
#include "../agent_session/internal.h"
#include <string.h>

static bool same_ticket(struct json_object *a, struct json_object *b)
{
    return !strcmp(dw_text(a, "namespace"), dw_text(b, "namespace")) &&
           dw_uint(a, "ticket") == dw_uint(b, "ticket");
}

static golem_status validate(golem_document_store *store, struct json_object *event)
{
    const char *keys[] = {
        "schema_version", "type",    "namespace",  "ticket",          "epoch", "instance",
        "operation",      "work_id", "session_id", "runtime_binding", "boot"};
    golem_digest binding, namespace_id, instance, boot;
    if (!dw_keys(event, keys, 11) || dw_uint(event, "schema_version") != 1 ||
        strcmp(dw_text(event, "type"), "admission-link") || !dw_uint(event, "ticket") ||
        dw_uint(event, "ticket") > GOLEM_ADMISSION_MAX_TICKETS || !dw_uint(event, "epoch") ||
        !dw_digest(event, "runtime_binding", &binding) ||
        !dw_digest(event, "namespace", &namespace_id) || !dw_digest(event, "instance", &instance) ||
        !dw_digest(event, "boot", &boot) || !ga_nonzero(&boot, 32) ||
        !ga_nonzero(&namespace_id, 32) || !ga_nonzero(&instance, 32) ||
        !dw_id(dw_text(event, "operation")) ||
        strcmp(dw_text(event, "work_id"), dw_text(store->spec, "work_id")))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    struct json_object *claim = NULL;
    golem_status s = rp_binding_claim(store, &binding, &claim);
    if (s == GOLEM_OK && strcmp(dw_text(claim, "session_id"), dw_text(event, "session_id")))
        s = GOLEM_ERR_IDENTITY_MISMATCH;
    json_object_put(claim);
    return s;
}

static void remember(golem_document_store *s, struct json_object *event,
                     const golem_digest *payload, const golem_digest *frame)
{
    size_t index = s->admission_link_count++;
    s->admission_links[index] = json_object_get(event);
    s->admission_link_digests[index] = *payload;
    ++s->event_count;
    s->last = *frame;
}

golem_status ga_work_apply(golem_document_store *s, struct json_object *event,
                           const golem_digest *payload, const golem_digest *frame)
{
    if (s->admission_link_count >= 256)
        return GOLEM_ERR_OVERFLOW;
    for (size_t i = 0; i < s->admission_link_count; ++i)
        if (same_ticket(s->admission_links[i], event))
            return GOLEM_ERR_CORRUPT_JOURNAL;
    golem_status status = validate(s, event);
    if (status == GOLEM_OK)
        remember(s, event, payload, frame);
    return status;
}

golem_status golem_admission_publish_work(golem_document_store *store,
                                          const golem_digest *namespace_id,
                                          const golem_admission_ticket *ticket,
                                          golem_digest *receipt)
{
    if (!store || !namespace_id || !ticket || !receipt ||
        ticket->state != GOLEM_ADMISSION_GRANTED ||
        !memchr(ticket->request.operation, 0, sizeof(ticket->request.operation)) ||
        !memchr(ticket->request.work, 0, sizeof(ticket->request.work)) ||
        !memchr(ticket->request.session, 0, sizeof(ticket->request.session)) ||
        !ga_nonzero(ticket->token.instance, sizeof(ticket->token.instance)))
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (store->poisoned)
        return GOLEM_ERR_INVALID_STATE;
    if (!store->writable || !strcmp(dw_text(store->spec, "permission"), "DENY"))
        return GOLEM_ERR_POLICY_DENIED;
    if (!strcmp(dw_text(store->spec, "permission"), "ASK_ALWAYS"))
        return GOLEM_ERR_APPROVAL_REQUIRED;
    as_log log = {.directory = -1};
    golem_status s = as_load(store, NULL, NULL, &log);
    struct json_object *active = dw_get(log.state, "active"), *manifest = NULL;
    uint64_t now;
    golem_digest boot, pinned, instance;
    if (s == GOLEM_OK)
        s = as_clock_read(NULL, &now, &boot);
    if (s == GOLEM_OK &&
        (!as_live(&log, now, &boot) || strcmp(dw_text(active, "state"), "RUNNING") ||
         !dw_equal(&boot, &ticket->token.boot) || !dw_digest(active, "runtime_binding", &pinned) ||
         !dw_equal(&pinned, &ticket->request.runtime_binding) ||
         strcmp(dw_text(active, "session_id"), ticket->request.session)))
        s = GOLEM_ERR_STALE_RESULT;
    if (s == GOLEM_OK)
        s = as_fresh(store, active, false, &manifest);
    if (s == GOLEM_OK)
        s = golem_digest_bytes(
            (golem_bytes){ticket->token.instance, sizeof(ticket->token.instance)}, &instance);
    struct json_object *event = s == GOLEM_OK ? json_object_new_object() : NULL;
    if (s == GOLEM_OK &&
        (!event || !dw_add(event, "schema_version", json_object_new_int(1)) ||
         !dw_add(event, "type", json_object_new_string("admission-link")) ||
         !dw_add_digest(event, "namespace", namespace_id) ||
         !dw_add(event, "ticket", json_object_new_uint64(ticket->token.ticket)) ||
         !dw_add(event, "epoch", json_object_new_uint64(ticket->token.epoch)) ||
         !dw_add_digest(event, "instance", &instance) ||
         !dw_add_digest(event, "boot", &ticket->token.boot) ||
         !dw_add(event, "operation", json_object_new_string(ticket->request.operation)) ||
         !dw_add(event, "work_id", json_object_new_string(ticket->request.work)) ||
         !dw_add(event, "session_id", json_object_new_string(ticket->request.session)) ||
         !dw_add_digest(event, "runtime_binding", &ticket->request.runtime_binding)))
        s = GOLEM_ERR_OUT_OF_MEMORY;
    if (s == GOLEM_OK)
        s = validate(store, event);
    bool duplicate = false;
    golem_digest payload = {0}, frame;
    if (s == GOLEM_OK)
        for (size_t i = 0; i < store->admission_link_count; ++i) {
            if (!same_ticket(store->admission_links[i], event))
                continue;
            if (!json_object_equal(store->admission_links[i], event))
                s = GOLEM_ERR_IDENTITY_MISMATCH;
            else {
                duplicate = true;
                payload = store->admission_link_digests[i];
            }
            break;
        }
    if (s == GOLEM_OK && !duplicate && store->admission_link_count >= 256)
        s = GOLEM_ERR_OVERFLOW;
    if (s == GOLEM_OK && !duplicate)
        s = dw_put_json(store, event, &payload);
    if (s == GOLEM_OK) {
        s = as_clock_read(NULL, &now, &boot);
        if (s == GOLEM_OK && !as_live(&log, now, &boot))
            s = GOLEM_ERR_STALE_LEASE;
    }
    if (s == GOLEM_OK && !duplicate)
        s = dw_event_write(store, &payload, &frame);
    if (s == GOLEM_OK && !duplicate)
        remember(store, event, &payload, &frame);
    if (s == GOLEM_OK)
        *receipt = payload;
    if (s == GOLEM_ERR_IO)
        store->poisoned = true;
    json_object_put(manifest);
    json_object_put(event);
    as_close(&log);
    return s;
}
