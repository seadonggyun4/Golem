#include "object.h"
#include "../common/json.h"
#include <stdio.h>
#include <string.h>

golem_status gi_object_publication_encode(const gi_object_publication *p, char *out,
    size_t capacity, size_t *length)
{
    if (!p || !out || !length) return GOLEM_ERR_INVALID_ARGUMENT;
    char hex[4][GOLEM_DIGEST_HEX_CAPACITY]; size_t required;
    const golem_digest *values[] = {&p->preparation, &p->baseline, &p->operation, &p->request};
    for (size_t i = 0; i < 4; ++i) {
        golem_status st = golem_digest_format(values[i], hex[i], sizeof(hex[i]), &required);
        if (st != GOLEM_OK) return st;
    }
    char wire[GI_OBJECT_PUBLICATION_CAPACITY];
    int n = snprintf(wire, sizeof(wire), "{\"schema\":\"golem.intent.object-publication.v1\","
        "\"preparation_digest\":\"%s\",\"baseline_digest\":\"%s\","
        "\"operation_id\":\"%s\",\"request_digest\":\"%s\"}", hex[0], hex[1], hex[2], hex[3]);
    if (n < 0 || (size_t)n >= sizeof(wire) || (size_t)n >= capacity) return GOLEM_ERR_OVERFLOW;
    memcpy(out, wire, (size_t)n + 1); *length = (size_t)n;
    return GOLEM_OK;
}

golem_status gi_object_publication_decode(golem_bytes wire, gi_object_publication *out)
{
    if (!out) return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = NULL;
    golem_status st = golem_json_parse(wire, GI_OBJECT_PUBLICATION_CAPACITY - 1, &o);
    if (st != GOLEM_OK) return st;
    gi_object_publication p;
    golem_digest *values[] = {&p.preparation, &p.baseline, &p.operation, &p.request};
    const char *keys[] = {"preparation_digest", "baseline_digest", "operation_id", "request_digest"};
    for (size_t i = 0; i < 4 && st == GOLEM_OK; ++i) {
        struct json_object *v = NULL;
        if (!json_object_object_get_ex(o, keys[i], &v) || !json_object_is_type(v, json_type_string))
            st = GOLEM_ERR_PARSE;
        else st = golem_digest_parse((golem_string_view){json_object_get_string(v),
            (size_t)json_object_get_string_len(v)}, values[i]);
    }
    char canonical[GI_OBJECT_PUBLICATION_CAPACITY]; size_t length = 0;
    if (st == GOLEM_OK) st = gi_object_publication_encode(&p, canonical, sizeof(canonical), &length);
    /* Exact comparison also rejects unknown/missing schema, reordered members,
     * escaped spellings and whitespace without rewriting any supplied bytes. */
    if (st == GOLEM_OK && (length != wire.size || memcmp(canonical, wire.data, length))) st = GOLEM_ERR_PARSE;
    json_object_put(o);
    if (st == GOLEM_OK) *out = p;
    return st;
}

golem_status gi_object_reservation_project(const gi_quota_state *current,
    const gi_object_reservation *reservation, const gi_object_journal_binding *journal, gi_quota_state *out)
{
    if (!current || !reservation || !out || !reservation->sequence) return GOLEM_ERR_INVALID_ARGUMENT;
    char wire[GI_OBJECT_PUBLICATION_CAPACITY]; size_t length = 0;
    golem_status st = gi_object_publication_encode(&reservation->publication, wire, sizeof(wire), &length);
    if (st != GOLEM_OK) return st;
    gi_quota_usage added = {{1, length, 0, 0}};
    if (journal) {
        if (journal->lane != GI_QUOTA_INTAKE || journal->sequence != reservation->sequence ||
            memcmp(&journal->head, &reservation->head, sizeof(journal->head)) ||
            !journal->payload.data || journal->payload.size != length || memcmp(journal->payload.data, wire, length))
            return GOLEM_ERR_INVALID_STATE;
        /* current must contain the validated journal's reservation already. */
        if (!current->lane[GI_QUOTA_INTAKE].value[GI_QUOTA_EVENTS] ||
            current->lane[GI_QUOTA_INTAKE].value[GI_QUOTA_PAYLOAD] < length) return GOLEM_ERR_INVALID_STATE;
        memset(&added, 0, sizeof(added));
    }
    return gi_quota_project(current, GI_QUOTA_INTAKE, &added, &added, out);
}
