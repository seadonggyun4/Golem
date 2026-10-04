#include "internal.h"
#include <stdio.h>
#include <string.h>

static golem_status writable(golem_document_store *s)
{
    if (!s) return GOLEM_ERR_INVALID_ARGUMENT;
    if (!s->writable) return GOLEM_ERR_POLICY_DENIED;
    return s->poisoned ? GOLEM_ERR_INVALID_STATE : GOLEM_OK;
}

golem_status dw_record_prepare(golem_document_store *s, struct json_object *event,
                              size_t limit, golem_digest *out)
{
    if (!event || !out || !limit || limit > GOLEM_DOCUMENT_MAX_JSON)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status st = writable(s);
    if (st != GOLEM_OK) return st;
    st = dw_put_json_bounded(s, event, limit, out);
    if (st == GOLEM_ERR_IO) s->poisoned = true;
    return st;
}

void dw_record_frame(uint8_t bytes[DW_FRAME], bool agent, uint64_t sequence,
                     const golem_digest *previous, const golem_digest *payload)
{
    memcpy(bytes, agent ? "GWAGN001" : "GWDOC001", 8);
    for (unsigned i = 0; i < 8; ++i)
        bytes[8+i] = (uint8_t)(sequence >> (8*i));
    memcpy(bytes + 16, previous->bytes, 32);
    memcpy(bytes + 48, payload->bytes, 32);
}

/* CAS publication alone is not a committed record. Only this reference
 * publication makes the prepared evidence reachable from a record stream. */
static golem_status publish(golem_document_store *s, int directory, const char *name,
                            const golem_digest *payload, golem_bytes bytes,
                            golem_status (*guard)(void *), void *context)
{
    golem_status st = writable(s);
    if (st != GOLEM_OK) return st;
    if (directory < 0 || !name || !*name || !payload || strchr(name, '/') ||
        !strcmp(name, ".") || !strcmp(name, "..")) return GOLEM_ERR_INVALID_ARGUMENT;
    uint64_t size;
    st = golem_evidence_verify(s->cas, payload, &size, NULL);
    if (st == GOLEM_OK && guard) {
        golem_status checked = guard(context);
        if (checked != GOLEM_OK) return checked;
    }
    if (st == GOLEM_OK) st = dw_publish(directory, name, bytes);
    /* A missing/corrupt prepared object or any uncertain publication requires
     * reopening and replay, not a second append through this in-memory state. */
    if (st != GOLEM_OK) s->poisoned = true;
    return st;
}

static golem_status event_publish(golem_document_store *s, int directory, bool agent,
                            uint64_t sequence, const golem_digest *previous,
                            const golem_digest *payload, golem_digest *out,
                            golem_status (*guard)(void *), void *context)
{
    if (!previous || !payload || !out || !sequence || sequence > 99999999)
        return GOLEM_ERR_INVALID_ARGUMENT;
    uint8_t bytes[DW_FRAME];
    char name[32];
    golem_digest digest;
    dw_record_frame(bytes, agent, sequence, previous, payload);
    (void)snprintf(name, sizeof(name), "%08u.evt", (unsigned)sequence);
    golem_status st = golem_digest_bytes((golem_bytes){bytes, sizeof(bytes)}, &digest);
    if (st == GOLEM_OK) st = publish(s, directory, name, payload,
        (golem_bytes){bytes, sizeof(bytes)}, guard, context);
    if (st == GOLEM_OK) *out = digest;
    return st;
}
golem_status dw_record_event(golem_document_store *s, int directory, bool agent,
                            uint64_t sequence, const golem_digest *previous,
                            const golem_digest *payload, golem_digest *out)
{
    return event_publish(s, directory, agent, sequence, previous, payload, out, NULL, NULL);
}

golem_status dw_event_write(golem_document_store *s, const golem_digest *payload,
                            golem_digest *out)
{
    if (!s || s->event_count >= 99999999) return GOLEM_ERR_INVALID_ARGUMENT;
    return dw_record_event(s, s->events, false, s->event_count + 1, &s->last, payload, out);
}
golem_status dw_event_write_guarded(golem_document_store *s, const golem_digest *payload,
                                   golem_digest *out, golem_status (*guard)(void *), void *context)
{
    if (!s || !guard || s->event_count >= 99999999) return GOLEM_ERR_INVALID_ARGUMENT;
    return event_publish(s, s->events, false, s->event_count + 1, &s->last, payload, out, guard, context);
}

golem_status dw_record_reference(golem_document_store *s, int directory, const char *name,
                                const golem_digest *payload, bool hexadecimal)
{
    if (!payload) return GOLEM_ERR_INVALID_ARGUMENT;
    char hex[GOLEM_DIGEST_HEX_CAPACITY];
    size_t required;
    golem_status st = GOLEM_OK;
    if (hexadecimal) st = golem_digest_format(payload, hex, sizeof(hex), &required);
    if (st == GOLEM_OK) st = publish(s, directory, name, payload,
        hexadecimal ? (golem_bytes){(const uint8_t *)hex, 64} : (golem_bytes){payload->bytes, 32}, NULL, NULL);
    return st;
}
