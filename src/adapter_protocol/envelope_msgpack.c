#include "schema.h"
#include <string.h>

_Static_assert(W_FIELD_COUNT <= 32, "wire field masks require at most 32 IDs");
_Static_assert(GOLEM_ADAPTER_ID_CAPACITY <= 256, "writer uses str8 for long IDs");
_Static_assert(sizeof(golem_digest) == 32, "wire v1 requires SHA-256 digests");

/* Deliberately bounded schema profile, not a general MessagePack object tree. */
typedef struct fields {
    golem_wire_value values[W_FIELD_COUNT];
    uint32_t present, consumed;
    bool reading;
} fields;
static golem_status field(void *context, golem_wire_field id, golem_wire_value *v)
{
    fields *f = context; uint32_t bit = UINT32_C(1) << id;
    if (f->reading) {
        if ((f->present & bit) == 0 || f->values[id].kind != v->kind) return GOLEM_ERR_INVALID_ARGUMENT;
        *v = f->values[id]; f->consumed |= bit;
    } else { f->values[id] = *v; f->present |= bit; }
    return GOLEM_OK;
}
typedef struct writer { uint8_t data[GOLEM_ADAPTER_MSGPACK_MAX]; size_t size; bool failed; } writer;
static void put(writer *w, uint64_t n, size_t width)
{
    if (w->failed || width > sizeof(w->data) - w->size) { w->failed = true; return; }
    for (size_t i = width; i > 0; --i) w->data[w->size++] = (uint8_t)(n >> ((i - 1) * 8));
}
static void uint_put(writer *w, uint64_t n)
{
    if (n <= 127) put(w, n, 1);
    else {
        size_t width = n <= UINT8_MAX ? 1 : n <= UINT16_MAX ? 2 : n <= UINT32_MAX ? 4 : 8;
        put(w, width == 1 ? 0xcc : width == 2 ? 0xcd : width == 4 ? 0xce : 0xcf, 1); put(w, n, width);
    }
}
static void blob_put(writer *w, const void *data, size_t size)
{
    if (w->failed || size > sizeof(w->data) - w->size) { w->failed = true; return; }
    memcpy(w->data + w->size, data, size); w->size += size;
}
golem_status golem_adapter_msgpack_encode(const golem_adapter_envelope *e,
    void *buffer, size_t capacity, size_t *required, golem_diagnostic *d)
{
    if (required == NULL || (buffer == NULL && capacity != 0)) return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    golem_status s = golem_adapter_envelope_valid(e);
    if (s != GOLEM_OK) return golem_adapter_report(d, s);
    fields f = {0}; golem_wire_codec c = {&f, false, GOLEM_OK, field};
    golem_adapter_envelope copy = *e; golem_wire_visit(&c, &copy);
    if (c.status != GOLEM_OK) return golem_adapter_report(d, c.status);
    size_t count = 0;
    for (size_t i = 0; i < W_FIELD_COUNT; ++i) if ((f.present & (UINT32_C(1) << i)) != 0) ++count;
    writer w = {{0}, 0, false};
    if (count <= 15) put(&w, 0x80 | count, 1);
    else { put(&w, 0xde, 1); put(&w, count, 2); }
    for (size_t i = 0; i < W_FIELD_COUNT; ++i) {
        if ((f.present & (UINT32_C(1) << i)) == 0) continue;
        const golem_wire_value *v = &f.values[i]; uint_put(&w, i);
        switch (v->kind) {
        case W_UINT: uint_put(&w, v->number); break;
        case W_BOOL: put(&w, v->number ? 0xc3 : 0xc2, 1); break;
        case W_TEXT: {
            size_t n = strlen(v->text);
            if (n <= 31) put(&w, 0xa0 | n, 1);
            else { put(&w, 0xd9, 1); put(&w, n, 1); }
            blob_put(&w, v->text, n); break;
        }
        case W_DIGEST:
            put(&w, 0xc4, 1); put(&w, sizeof(v->digest.bytes), 1);
            blob_put(&w, v->digest.bytes, sizeof(v->digest.bytes)); break;
        }
    }
    if (w.failed) return golem_adapter_report(d, GOLEM_ERR_OVERFLOW);
    if (capacity < w.size) { *required = w.size; return golem_adapter_report(d, GOLEM_ERR_BUFFER_TOO_SMALL); }
    memcpy(buffer, w.data, w.size); *required = w.size;
    return golem_adapter_report(d, GOLEM_OK);
}
typedef struct reader { golem_bytes bytes; size_t offset; bool failed; } reader;
static uint64_t take(reader *r, size_t width)
{
    if (r->failed || width > r->bytes.size - r->offset) { r->failed = true; return 0; }
    uint64_t n = 0;
    for (size_t i = 0; i < width; ++i) n = (n << 8) | r->bytes.data[r->offset++];
    return n;
}
static uint64_t uint_take(reader *r, uint8_t tag)
{
    if (tag <= 127) return tag;
    if (tag >= 0xcc && tag <= 0xcf) return take(r, (size_t)1 << (tag - 0xcc));
    r->failed = true; return 0;
}
static void value_take(reader *r, golem_wire_value *v)
{
    uint8_t tag = (uint8_t)take(r, 1);
    if (tag <= 127 || (tag >= 0xcc && tag <= 0xcf)) { v->kind = W_UINT; v->number = uint_take(r, tag); return; }
    if (tag == 0xc2 || tag == 0xc3) { v->kind = W_BOOL; v->number = tag == 0xc3; return; }
    uint64_t size = 0;
    if ((tag & 0xe0) == 0xa0) { v->kind = W_TEXT; size = tag & 31; }
    else if (tag >= 0xd9 && tag <= 0xdb) { v->kind = W_TEXT; size = take(r, (size_t)1 << (tag - 0xd9)); }
    else if (tag >= 0xc4 && tag <= 0xc6) { v->kind = W_DIGEST; size = take(r, (size_t)1 << (tag - 0xc4)); }
    else { r->failed = true; return; }
    if (r->failed || size > r->bytes.size - r->offset) { r->failed = true; return; }
    const uint8_t *data = r->bytes.data + r->offset;
    if (v->kind == W_TEXT) {
        if (size == 0 || size >= sizeof(v->text) || memchr(data, 0, (size_t)size) != NULL) { r->failed = true; return; }
        memcpy(v->text, data, (size_t)size); v->text[size] = '\0';
        if (!golem_adapter_id_valid(v->text)) { r->failed = true; return; }
    } else {
        if (size != sizeof(v->digest.bytes)) { r->failed = true; return; }
        memcpy(v->digest.bytes, data, sizeof(v->digest.bytes));
    }
    r->offset += (size_t)size;
}
golem_status golem_adapter_msgpack_decode(golem_bytes bytes,
    golem_adapter_envelope *out, golem_diagnostic *d)
{
    if (out == NULL || bytes.data == NULL || bytes.size == 0 || bytes.size > GOLEM_ADAPTER_MSGPACK_MAX)
        return golem_adapter_report(d, GOLEM_ERR_INVALID_ARGUMENT);
    reader r = {bytes, 0, false}; uint8_t tag = (uint8_t)take(&r, 1); uint64_t count;
    if ((tag & 0xf0) == 0x80) count = tag & 15;
    else if (tag == 0xde || tag == 0xdf) count = take(&r, tag == 0xde ? 2 : 4);
    else return golem_adapter_report(d, GOLEM_ERR_PARSE);
    if (r.failed || count == 0 || count > W_FIELD_COUNT) return golem_adapter_report(d, GOLEM_ERR_PARSE);
    fields f = {0}; f.reading = true;
    for (uint64_t i = 0; i < count; ++i) {
        tag = (uint8_t)take(&r, 1); uint64_t id = uint_take(&r, tag);
        if (r.failed || id >= W_FIELD_COUNT || (f.present & (UINT32_C(1) << id)) != 0)
            return golem_adapter_report(d, GOLEM_ERR_PARSE);
        f.present |= UINT32_C(1) << id; value_take(&r, &f.values[id]);
        if (r.failed) return golem_adapter_report(d, GOLEM_ERR_PARSE);
    }
    if (r.offset != bytes.size) return golem_adapter_report(d, GOLEM_ERR_PARSE);
    golem_wire_codec c = {&f, true, GOLEM_OK, field}; golem_adapter_envelope e = {0};
    golem_wire_visit(&c, &e);
    if (c.status == GOLEM_OK && f.present != f.consumed) c.status = GOLEM_ERR_INVALID_ARGUMENT;
    if (c.status == GOLEM_OK) *out = e;
    return golem_adapter_report(d, c.status);
}
