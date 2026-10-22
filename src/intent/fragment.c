#include "fragment.h"
#include "schema.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void put64(uint8_t *p, uint64_t v)
{
    for (unsigned i = 0; i < 8; ++i) p[i] = (uint8_t)(v >> (8 * i));
}

golem_status gi_quarantine_encode(const gi_fragment_binding *b, golem_bytes source,
    uint8_t **out, size_t *size)
{
    if (!b || !out || !size || !source.data || source.size > GI_CONTROL_MAX ||
        b->original.source.sequence == 0 || b->original.source.sequence > 6208 ||
        b->original.source.kind > 2 || !b->original.source.present ||
        b->original.source.bytes != source.size) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_digest digest;
    golem_status st = golem_digest_bytes(source, &digest);
    if (st != GOLEM_OK) return st;
    if (memcmp(digest.bytes, b->original.source.final_digest.bytes, 32)) return GOLEM_ERR_INVALID_STATE;
    size_t n = GI_FRAGMENT_HEADER + source.size;
    uint8_t *wire = calloc(1, n);
    if (!wire) return GOLEM_ERR_OUT_OF_MEMORY;
    const gi_journal_alias_plan *a = &b->original.source;
    memcpy(wire, "GIQUA001", 8);
    put64(wire + 8, a->sequence); put64(wire + 16, GI_QUOTA_INTAKE); put64(wire + 24, a->kind);
    put64(wire + 32, a->device); put64(wire + 40, a->inode); put64(wire + 48, source.size);
    memcpy(wire + 64, a->preparation.bytes, 32); memcpy(wire + 96, a->operation.bytes, 32);
    memcpy(wire + 128, a->request.bytes, 32); memcpy(wire + 160, digest.bytes, 32);
    memcpy(wire + 192, b->original_approval.bytes, 32);
    const char *kinds[] = {"prep", "payload", "event"};
    (void)snprintf((char *)wire + 224, 64, "%08llu.%s.pending",
                   (unsigned long long)a->sequence, kinds[a->kind]);
    memcpy(wire + GI_FRAGMENT_HEADER, source.data, source.size);
    st = golem_digest_bytes((golem_bytes){wire, n}, &digest);
    if (st == GOLEM_OK) {
        memcpy(wire + 288, digest.bytes, 32); *out = wire; *size = n;
    } else free(wire);
    return st;
}

golem_status gi_fragment_encode(const gi_fragment_binding *b, golem_bytes source,
    golem_bytes truncated, uint8_t **out, size_t *size)
{
    if (!out || !size || !truncated.data || truncated.size < GI_FRAGMENT_HEADER ||
        truncated.size > GI_CONTROL_MAX + GI_FRAGMENT_HEADER) return GOLEM_ERR_INVALID_ARGUMENT;
    uint8_t *complete = NULL; size_t complete_size = 0;
    golem_status st = gi_quarantine_encode(b, source, &complete, &complete_size);
    if (st != GOLEM_OK) return st;
    if (truncated.size >= complete_size || memcmp(truncated.data, complete, truncated.size)) {
        free(complete); return GOLEM_ERR_INVALID_STATE;
    }
    size_t n = GI_FRAGMENT_HEADER + truncated.size;
    uint8_t *wire = calloc(1, n);
    if (!wire) { free(complete); return GOLEM_ERR_OUT_OF_MEMORY; }
    memcpy(wire, "GIQFR001", 8);
    put64(wire + 8, b->original.source.sequence); put64(wire + 16, GI_QUOTA_INTAKE);
    put64(wire + 24, b->original.source.kind);
    put64(wire + 32, b->envelope_device); put64(wire + 40, b->envelope_inode);
    put64(wire + 48, truncated.size); put64(wire + 56, complete_size);
    memcpy(wire + 64, b->original.source.preparation.bytes, 32);
    memcpy(wire + 96, b->original_approval.bytes, 32);
    memcpy(wire + 128, b->preservation_approval.bytes, 32);
    golem_digest digest;
    st = golem_digest_bytes(truncated, &digest);
    if (st == GOLEM_OK) memcpy(wire + 160, digest.bytes, 32);
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){complete, complete_size}, &digest);
    if (st == GOLEM_OK) memcpy(wire + 192, digest.bytes, 32);
    const char *kinds[] = {"prep", "payload", "event"};
    (void)snprintf((char *)wire + 224, 64, "quarantine/%08llu.%s.pending",
        (unsigned long long)b->original.source.sequence, kinds[b->original.source.kind]);
    memcpy(wire + GI_FRAGMENT_HEADER, truncated.data, truncated.size);
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){wire, n}, &digest);
    if (st == GOLEM_OK) {
        memcpy(wire + 288, digest.bytes, 32); *out = wire; *size = n;
    } else free(wire);
    free(complete); return st;
}

golem_status gi_fragment_verify(const gi_fragment_binding *b, golem_bytes source,
    golem_bytes preserved)
{
    if (!preserved.data || preserved.size < 2 * GI_FRAGMENT_HEADER ||
        preserved.size > GI_CONTROL_MAX + 2 * GI_FRAGMENT_HEADER) return GOLEM_ERR_INVALID_ARGUMENT;
    uint8_t *wire = NULL; size_t n = 0;
    golem_status st = gi_fragment_encode(b, source,
        (golem_bytes){preserved.data + GI_FRAGMENT_HEADER, preserved.size - GI_FRAGMENT_HEADER}, &wire, &n);
    if (st == GOLEM_OK && (n != preserved.size || memcmp(wire, preserved.data, n))) st = GOLEM_ERR_INVALID_STATE;
    free(wire); return st;
}

golem_status gi_fragment_check_quota(const gi_quota_state *current, size_t truncated_bytes,
    bool final_present, bool pending_present)
{
    if (!current || truncated_bytes < GI_FRAGMENT_HEADER ||
        truncated_bytes >= GI_CONTROL_MAX + GI_FRAGMENT_HEADER) return GOLEM_ERR_INVALID_ARGUMENT;
    uint64_t bytes = GI_FRAGMENT_HEADER + truncated_bytes;
    gi_quota_usage retained = {{0}}, peak = {{0}};
    if (!final_present && !pending_present) {
        retained.value[GI_QUOTA_BYTES] = bytes; retained.value[GI_QUOTA_ENTRIES] = 1;
        peak.value[GI_QUOTA_BYTES] = 2 * bytes; peak.value[GI_QUOTA_ENTRIES] = 2;
    } else if (!final_present) {
        peak.value[GI_QUOTA_BYTES] = bytes; peak.value[GI_QUOTA_ENTRIES] = 1;
    }
    gi_quota_state checked;
    return gi_quota_project(current, GI_QUOTA_INTAKE, &retained, &peak, &checked);
}

golem_status gi_fragment_damage_encode(const gi_fragment_damage_binding *b,
    golem_bytes source, golem_bytes envelope, golem_bytes truncated,
    uint8_t **out, size_t *size)
{
    if (!b || !out || !size || !truncated.data || truncated.size < GI_FRAGMENT_HEADER ||
        truncated.size >= GI_CONTROL_MAX + 2 * GI_FRAGMENT_HEADER)
        return GOLEM_ERR_INVALID_ARGUMENT;
    uint8_t *complete = NULL; size_t complete_size = 0;
    golem_status st = gi_fragment_encode(&b->fragment, source, envelope, &complete, &complete_size);
    if (st != GOLEM_OK) return st;
    if (truncated.size >= complete_size || memcmp(truncated.data, complete, truncated.size)) {
        free(complete); return GOLEM_ERR_INVALID_STATE;
    }
    size_t n = GI_FRAGMENT_DAMAGE_HEADER + truncated.size;
    uint8_t *wire = calloc(1, n);
    if (!wire) { free(complete); return GOLEM_ERR_OUT_OF_MEMORY; }
    memcpy(wire, "GIQFD001", 8);
    put64(wire + 8, b->fragment.original.source.sequence);
    put64(wire + 16, GI_QUOTA_INTAKE);
    put64(wire + 24, b->fragment.original.source.kind);
    put64(wire + 32, b->device); put64(wire + 40, b->inode);
    put64(wire + 48, truncated.size); put64(wire + 56, complete_size);
    memcpy(wire + 64, b->fragment.original.source.preparation.bytes, 32);
    memcpy(wire + 96, b->fragment.original_approval.bytes, 32);
    memcpy(wire + 128, b->fragment.preservation_approval.bytes, 32);
    memcpy(wire + 160, b->approval.bytes, 32);
    golem_digest digest;
    st = golem_digest_bytes(truncated, &digest);
    if (st == GOLEM_OK) memcpy(wire + 192, digest.bytes, 32);
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){complete, complete_size}, &digest);
    if (st == GOLEM_OK) memcpy(wire + 224, digest.bytes, 32);
    const char *kinds[] = {"prep", "payload", "event"};
    (void)snprintf((char *)wire + 256, 64, "quarantine/%08llu.%s.fragment.pending",
        (unsigned long long)b->fragment.original.source.sequence,
        kinds[b->fragment.original.source.kind]);
    /* 320..351 is reserved zero; 352..383 is the whole-object checksum. */
    memcpy(wire + GI_FRAGMENT_DAMAGE_HEADER, truncated.data, truncated.size);
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){wire, n}, &digest);
    if (st == GOLEM_OK) {
        memcpy(wire + 352, digest.bytes, 32); *out = wire; *size = n;
    } else free(wire);
    free(complete); return st;
}

golem_status gi_fragment_damage_verify(const gi_fragment_damage_binding *b,
    golem_bytes source, golem_bytes envelope, golem_bytes preserved)
{
    if (!preserved.data || preserved.size < GI_FRAGMENT_DAMAGE_HEADER + GI_FRAGMENT_HEADER ||
        preserved.size >= GI_CONTROL_MAX + 2 * GI_FRAGMENT_HEADER + GI_FRAGMENT_DAMAGE_HEADER)
        return GOLEM_ERR_INVALID_ARGUMENT;
    uint8_t *wire = NULL; size_t n = 0;
    golem_status st = gi_fragment_damage_encode(b, source, envelope,
        (golem_bytes){preserved.data + GI_FRAGMENT_DAMAGE_HEADER,
                      preserved.size - GI_FRAGMENT_DAMAGE_HEADER}, &wire, &n);
    if (st == GOLEM_OK && (n != preserved.size || memcmp(wire, preserved.data, n)))
        st = GOLEM_ERR_INVALID_STATE;
    free(wire); return st;
}

golem_status gi_fragment_damage_check_quota(const gi_quota_state *current, size_t truncated_bytes,
    bool final_present, bool pending_present)
{
    if (!current || truncated_bytes < GI_FRAGMENT_HEADER ||
        truncated_bytes >= GI_CONTROL_MAX + 2 * GI_FRAGMENT_HEADER)
        return GOLEM_ERR_INVALID_ARGUMENT;
    uint64_t bytes = GI_FRAGMENT_DAMAGE_HEADER + truncated_bytes;
    gi_quota_usage retained = {{0}}, peak = {{0}};
    if (!final_present && !pending_present) {
        retained.value[GI_QUOTA_BYTES] = bytes; retained.value[GI_QUOTA_ENTRIES] = 1;
        peak.value[GI_QUOTA_BYTES] = 2 * bytes; peak.value[GI_QUOTA_ENTRIES] = 2;
    } else if (!final_present) {
        peak.value[GI_QUOTA_BYTES] = bytes; peak.value[GI_QUOTA_ENTRIES] = 1;
    }
    gi_quota_state checked;
    return gi_quota_project(current, GI_QUOTA_INTAKE, &retained, &peak, &checked);
}
