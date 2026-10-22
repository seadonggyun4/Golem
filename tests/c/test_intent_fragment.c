#include "../../src/intent/fragment.h"
#include "../../src/intent/schema.h"
#include "test.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void put64(uint8_t *p, uint64_t v)
{
    for (unsigned i = 0; i < 8; ++i) p[i] = (uint8_t)(v >> (8 * i));
}

static int damage_codec(gi_fragment_binding b, golem_bytes raw, golem_bytes envelope)
{
    gi_fragment_damage_binding d = {0}; d.fragment = b;
    d.device = 7; d.inode = 44; memset(d.approval.bytes, 6, 32);
    uint8_t *complete = NULL; size_t count = 0;
    CHECK(gi_fragment_encode(&b, raw, envelope, &complete, &count) == GOLEM_OK);
    for (size_t prefix = 320; prefix < count; ++prefix) {
        uint8_t *wire = NULL; size_t size = 0;
        CHECK(gi_fragment_damage_encode(&d, raw, envelope, (golem_bytes){complete, prefix},
                                       &wire, &size) == GOLEM_OK);
        CHECK(size == 384 + prefix && !memcmp(wire, "GIQFD001", 8));
        CHECK(!memcmp(wire + 384, complete, prefix));
        CHECK(!memcmp(wire + 256, "quarantine/00000001.payload.fragment.pending", 44));
        if (prefix == 320) {
            uint8_t expected[704] = {0}; golem_digest hash;
            memcpy(expected, "GIQFD001", 8);
            put64(expected + 8, 1); put64(expected + 24, 1);
            put64(expected + 32, 7); put64(expected + 40, 44);
            put64(expected + 48, prefix); put64(expected + 56, count);
            memset(expected + 64, 1, 32); memset(expected + 96, 4, 32);
            memset(expected + 128, 5, 32); memset(expected + 160, 6, 32);
            CHECK(golem_digest_bytes((golem_bytes){complete, prefix}, &hash) == GOLEM_OK);
            memcpy(expected + 192, hash.bytes, 32);
            CHECK(golem_digest_bytes((golem_bytes){complete, count}, &hash) == GOLEM_OK);
            memcpy(expected + 224, hash.bytes, 32);
            memcpy(expected + 256, "quarantine/00000001.payload.fragment.pending", 44);
            memcpy(expected + 384, complete, prefix);
            CHECK(golem_digest_bytes((golem_bytes){expected, sizeof(expected)}, &hash) == GOLEM_OK);
            memcpy(expected + 352, hash.bytes, 32);
            CHECK(size == sizeof(expected) && !memcmp(wire, expected, size));
        }
        CHECK(gi_fragment_damage_verify(&d, raw, envelope, (golem_bytes){wire, size}) == GOLEM_OK);
        /* Check every byte once at the longest prefix, including reserved bytes. */
        if (prefix + 1 == count) {
            for (size_t i = 0; i < size; ++i) {
                wire[i] ^= 1;
                CHECK(gi_fragment_damage_verify(&d, raw, envelope, (golem_bytes){wire, size}) != GOLEM_OK);
                wire[i] ^= 1;
            }
            for (size_t i = 0; i < size; ++i)
                CHECK(gi_fragment_damage_verify(&d, raw, envelope, (golem_bytes){wire, i}) != GOLEM_OK);
        }
        gi_fragment_damage_binding changed = d; changed.approval.bytes[0] ^= 1;
        CHECK(gi_fragment_damage_verify(&changed, raw, envelope, (golem_bytes){wire, size}) != GOLEM_OK);
        changed = d; changed.fragment.preservation_approval.bytes[0] ^= 1;
        CHECK(gi_fragment_damage_verify(&changed, raw, envelope, (golem_bytes){wire, size}) != GOLEM_OK);
        changed = d; changed.fragment.original_approval.bytes[0] ^= 1;
        CHECK(gi_fragment_damage_verify(&changed, raw, envelope, (golem_bytes){wire, size}) != GOLEM_OK);
        changed = d; changed.inode++;
        CHECK(gi_fragment_damage_verify(&changed, raw, envelope, (golem_bytes){wire, size}) != GOLEM_OK);
        uint8_t sentinel = 0, *out = &sentinel; size_t n = 99;
        CHECK(gi_fragment_damage_encode(&d, raw, envelope, (golem_bytes){wire, 320}, &out, &n) != GOLEM_OK);
        CHECK(out == &sentinel && n == 99); /* No recursive GIQFD001 container. */
        free(wire);
    }
    uint8_t sentinel = 0, *out = &sentinel; size_t n = 99;
    for (size_t i = 0; i < 320; ++i) {
        CHECK(gi_fragment_damage_encode(&d, raw, envelope, (golem_bytes){complete, i}, &out, &n) != GOLEM_OK);
        CHECK(out == &sentinel && n == 99);
    }
    CHECK(gi_fragment_damage_encode(&d, raw, envelope, (golem_bytes){complete, count}, &out, &n) != GOLEM_OK);
    complete[100] ^= 1;
    CHECK(gi_fragment_damage_encode(&d, raw, envelope, (golem_bytes){complete, 320}, &out, &n) != GOLEM_OK);
    CHECK(gi_fragment_damage_encode(NULL, raw, envelope, (golem_bytes){complete, 320}, &out, &n) != GOLEM_OK);
    CHECK(out == &sentinel && n == 99);
    free(complete);
    gi_quota_state usage = {0}, before; gi_quota_usage limit;
    CHECK(gi_quota_limit(GI_QUOTA_INTAKE, &limit) == GOLEM_OK);
    for (unsigned axis = GI_QUOTA_BYTES; axis <= GI_QUOTA_ENTRIES; ++axis) {
        uint64_t unit = axis == GI_QUOTA_BYTES ? 704 : 1;
        memset(&usage, 0, sizeof(usage)); usage.lane[0].value[axis] = limit.value[axis] - 2 * unit;
        before = usage;
        CHECK(gi_fragment_damage_check_quota(&usage, 320, false, false) == GOLEM_OK);
        CHECK(!memcmp(&usage, &before, sizeof(usage)));
        usage.lane[0].value[axis]++;
        CHECK(gi_fragment_damage_check_quota(&usage, 320, false, false) == GOLEM_ERR_OVERFLOW);
        usage.lane[0].value[axis] = limit.value[axis] - unit;
        CHECK(gi_fragment_damage_check_quota(&usage, 320, false, true) == GOLEM_OK);
        usage.lane[0].value[axis]++;
        CHECK(gi_fragment_damage_check_quota(&usage, 320, false, true) == GOLEM_ERR_OVERFLOW);
        usage.lane[0].value[axis] = limit.value[axis];
        CHECK(gi_fragment_damage_check_quota(&usage, 320, true, true) == GOLEM_OK);
        CHECK(gi_fragment_damage_check_quota(&usage, 320, true, false) == GOLEM_OK);
    }
    CHECK(gi_fragment_damage_check_quota(&usage, SIZE_MAX, false, false) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_fragment_damage_check_quota(NULL, 320, false, false) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}

int main(void)
{
    uint8_t source[17] = "original bytes!";
    gi_fragment_binding b = {0};
    b.original.source.sequence = 1; b.original.source.kind = 1;
    b.original.source.device = 7; b.original.source.inode = 42;
    b.original.source.present = true; b.original.source.bytes = sizeof(source);
    b.envelope_device = 7; b.envelope_inode = 43;
    memset(b.original.source.preparation.bytes, 1, 32);
    memset(b.original.source.operation.bytes, 2, 32);
    memset(b.original.source.request.bytes, 3, 32);
    memset(b.original_approval.bytes, 4, 32);
    memset(b.preservation_approval.bytes, 5, 32);
    golem_bytes raw = {source, sizeof(source)};
    CHECK(golem_digest_bytes(raw, &b.original.source.final_digest) == GOLEM_OK);
    /* Independent GIQUA001 wire fixture, including exact zero padding/hash. */
    uint8_t full[320 + sizeof(source)] = {0};
    memcpy(full, "GIQUA001", 8); put64(full + 8, 1); put64(full + 24, 1);
    put64(full + 32, 7); put64(full + 40, 42); put64(full + 48, sizeof(source));
    memcpy(full + 64, b.original.source.preparation.bytes, 32);
    memcpy(full + 96, b.original.source.operation.bytes, 32);
    memcpy(full + 128, b.original.source.request.bytes, 32);
    memcpy(full + 160, b.original.source.final_digest.bytes, 32);
    memcpy(full + 192, b.original_approval.bytes, 32);
    memcpy(full + 224, "00000001.payload.pending", 25);
    memcpy(full + 320, source, sizeof(source));
    golem_digest digest;
    CHECK(golem_digest_bytes((golem_bytes){full, sizeof(full)}, &digest) == GOLEM_OK);
    memcpy(full + 288, digest.bytes, 32);
    uint8_t *existing = NULL; size_t existing_size = 0;
    CHECK(gi_quarantine_encode(&b, raw, &existing, &existing_size) == GOLEM_OK);
    CHECK(existing_size == sizeof(full) && !memcmp(existing, full, sizeof(full)));
    free(existing);
    CHECK(damage_codec(b, raw, (golem_bytes){full, sizeof(full) - 1}) == 0);
    for (size_t prefix = 320; prefix < sizeof(full); ++prefix) {
        uint8_t *wire = NULL; size_t size = 0;
        CHECK(gi_fragment_encode(&b, raw, (golem_bytes){full, prefix}, &wire, &size) == GOLEM_OK);
        CHECK(size == prefix + 320 && !memcmp(wire, "GIQFR001", 8));
        CHECK(!memcmp(wire + 320, full, prefix));
        CHECK(gi_fragment_verify(&b, raw, (golem_bytes){wire, size}) == GOLEM_OK);
        /* Every byte participates in a verified exact binding or checksum. */
        for (size_t i = 0; i < size; ++i) {
            wire[i] ^= 1;
            CHECK(gi_fragment_verify(&b, raw, (golem_bytes){wire, size}) != GOLEM_OK);
            wire[i] ^= 1;
        }
        CHECK(gi_fragment_verify(&b, raw, (golem_bytes){wire, size - 1}) != GOLEM_OK);
        gi_fragment_binding changed = b;
        changed.preservation_approval.bytes[0] ^= 1;
        CHECK(gi_fragment_verify(&changed, raw, (golem_bytes){wire, size}) != GOLEM_OK);
        changed = b; changed.envelope_inode++;
        CHECK(gi_fragment_verify(&changed, raw, (golem_bytes){wire, size}) != GOLEM_OK);
        free(wire);
    }
    uint8_t sentinel = 0; uint8_t *out = &sentinel; size_t n = 99;
    for (size_t prefix = 0; prefix < 320; ++prefix) {
        CHECK(gi_fragment_encode(&b, raw, (golem_bytes){full, prefix}, &out, &n) != GOLEM_OK);
        CHECK(out == &sentinel && n == 99);
    }
    CHECK(gi_fragment_encode(&b, raw, (golem_bytes){full, sizeof(full)}, &out, &n) != GOLEM_OK);
    full[100] ^= 1;
    CHECK(gi_fragment_encode(&b, raw, (golem_bytes){full, 320}, &out, &n) != GOLEM_OK);
    full[100] ^= 1; source[0] ^= 1;
    CHECK(gi_fragment_encode(&b, raw, (golem_bytes){full, 320}, &out, &n) != GOLEM_OK);
    source[0] ^= 1;
    b.original.source.present = false;
    CHECK(gi_fragment_encode(&b, raw, (golem_bytes){full, 320}, &out, &n) != GOLEM_OK);
    b.original.source.present = true;
    CHECK(gi_fragment_encode(NULL, raw, (golem_bytes){full, 320}, &out, &n) != GOLEM_OK);
    CHECK(out == &sentinel && n == 99);
    gi_quota_state usage = {0}, original;
    gi_quota_usage limit;
    CHECK(gi_quota_limit(GI_QUOTA_INTAKE, &limit) == GOLEM_OK);
    for (unsigned axis = GI_QUOTA_BYTES; axis <= GI_QUOTA_ENTRIES; ++axis) {
        uint64_t unit = axis == GI_QUOTA_BYTES ? 640 : 1;
        memset(&usage, 0, sizeof(usage));
        usage.lane[0].value[axis] = limit.value[axis] - 2 * unit;
        original = usage;
        CHECK(gi_fragment_check_quota(&usage, 320, false, false) == GOLEM_OK);
        CHECK(!memcmp(&usage, &original, sizeof(usage)));
        usage.lane[0].value[axis]++;
        CHECK(gi_fragment_check_quota(&usage, 320, false, false) == GOLEM_ERR_OVERFLOW);
        usage.lane[0].value[axis] = limit.value[axis] - unit;
        CHECK(gi_fragment_check_quota(&usage, 320, false, true) == GOLEM_OK);
        usage.lane[0].value[axis]++;
        CHECK(gi_fragment_check_quota(&usage, 320, false, true) == GOLEM_ERR_OVERFLOW);
        usage.lane[0].value[axis] = limit.value[axis];
        CHECK(gi_fragment_check_quota(&usage, 320, true, true) == GOLEM_OK);
        CHECK(gi_fragment_check_quota(&usage, 320, true, false) == GOLEM_OK);
    }
    CHECK(gi_fragment_check_quota(&usage, SIZE_MAX, false, false) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
