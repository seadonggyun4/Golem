#include "schema.h"
#include "../common/json.h"
#include <stdlib.h>
#include <string.h>

static golem_status fail(golem_diagnostic *d, golem_status status, const char *code)
{
    if (d) (void)golem_diagnostic_set(d, status, GOLEM_DIAGNOSTIC_NO_OFFSET, code);
    return status;
}

golem_status gi_capacity_validate(const gi_capacity *c, golem_diagnostic *d)
{
    if (!c) return fail(d, GOLEM_ERR_INVALID_ARGUMENT, "intent.argument");
#define CAP(field, maximum) \
    if (c->field > maximum) return fail(d, GOLEM_ERR_OVERFLOW, "intent.limit." #field)
    CAP(control_bytes, GI_CONTROL_MAX);
    CAP(source_bytes, GI_SOURCE_MAX);
    CAP(baseline_source_bytes, GI_BASELINE_SOURCE_MAX);
    CAP(requirements, GI_REQUIREMENT_MAX);
    CAP(trace_nodes, GI_TRACE_NODE_MAX);
    CAP(trace_edges, GI_TRACE_EDGE_MAX);
    CAP(node_parents, GI_PARENT_MAX);
    CAP(unresolved, GI_OBLIGATION_MAX);
    CAP(observations, GI_OBSERVATION_MAX);
    CAP(dispatch_bytes, GI_DISPATCH_MAX);
#undef CAP
    return GOLEM_OK;
}

/* Reject overlong sequences, surrogates, out-of-range scalars and incomplete
 * tails. No normalization, BOM removal, newline conversion or implicit strlen. */
golem_status gi_text_validate(golem_bytes text, golem_diagnostic *d)
{
    if (!text.data && text.size) return fail(d, GOLEM_ERR_INVALID_ARGUMENT, "intent.argument");
    if (text.size > GI_SOURCE_MAX) return fail(d, GOLEM_ERR_OVERFLOW, "intent.limit.source_bytes");
    for (size_t i = 0; i < text.size;) {
        uint32_t scalar = text.data[i++], minimum;
        size_t tail;
        if (scalar < 0x80u) continue;
        if (scalar >= 0xc2u && scalar <= 0xdfu) { tail = 1; minimum = 0x80u; scalar &= 0x1fu; }
        else if (scalar >= 0xe0u && scalar <= 0xefu) { tail = 2; minimum = 0x800u; scalar &= 0x0fu; }
        else if (scalar >= 0xf0u && scalar <= 0xf4u) { tail = 3; minimum = 0x10000u; scalar &= 7u; }
        else return fail(d, GOLEM_ERR_PARSE, "intent.source.utf8");
        if (tail > text.size - i) return fail(d, GOLEM_ERR_PARSE, "intent.source.utf8");
        while (tail--) {
            unsigned char byte = text.data[i++];
            if ((byte & 0xc0u) != 0x80u) return fail(d, GOLEM_ERR_PARSE, "intent.source.utf8");
            scalar = (scalar << 6) | (byte & 0x3fu);
        }
        if (scalar < minimum || scalar > 0x10ffffu || (scalar >= 0xd800u && scalar <= 0xdfffu))
            return fail(d, GOLEM_ERR_PARSE, "intent.source.utf8");
    }
    return GOLEM_OK;
}

static bool boundary(golem_bytes text, size_t offset)
{
    return offset == text.size || (text.data[offset] & 0xc0u) != 0x80u;
}
static bool span_ok(golem_bytes text, gi_span span)
{
    return span.start < span.end && span.end <= text.size &&
        boundary(text, span.start) && boundary(text, span.end);
}
golem_status gi_span_validate(golem_bytes text, gi_span span, golem_diagnostic *d)
{
    golem_status status = gi_text_validate(text, d);
    if (status != GOLEM_OK) return status;
    return span_ok(text, span) ? GOLEM_OK : fail(d, GOLEM_ERR_PARSE, "intent.source.range");
}

golem_status gi_source_set_validate(const golem_bytes *sources, size_t count,
    size_t *total_bytes, golem_diagnostic *d)
{
    if (!sources || !count || !total_bytes) return fail(d, GOLEM_ERR_INVALID_ARGUMENT, "intent.argument");
    if (count > GI_CONTROL_MAX / sizeof(golem_bytes))
        return fail(d, GOLEM_ERR_OVERFLOW, "intent.limit.control_bytes");
    size_t total = 0;
    for (size_t i = 0; i < count; ++i) {
        if (sources[i].size > GI_BASELINE_SOURCE_MAX - total)
            return fail(d, GOLEM_ERR_OVERFLOW, "intent.limit.baseline_source_bytes");
        golem_status status = gi_text_validate(sources[i], d);
        if (status != GOLEM_OK) return status;
        total += sources[i].size;
    }
    *total_bytes = total;
    return GOLEM_OK;
}

static int compare_span(const void *a, const void *b)
{
    const gi_span *x = a, *y = b;
    if (x->start != y->start) return x->start < y->start ? -1 : 1;
    return x->end < y->end ? -1 : x->end != y->end;
}
static size_t merge_spans(gi_span *spans, size_t count)
{
    qsort(spans, count, sizeof(*spans), compare_span);
    size_t used = 0;
    for (size_t i = 0; i < count; ++i) {
        if (used && spans[i].start <= spans[used - 1].end) {
            if (spans[i].end > spans[used - 1].end) spans[used - 1].end = spans[i].end;
        } else spans[used++] = spans[i];
    }
    return used;
}

golem_status gi_coverage_validate(golem_bytes text, const gi_span *designated, size_t count,
    const gi_coverage_row *rows, size_t row_count, gi_coverage_result *out, golem_diagnostic *d)
{
    if (!designated || !count || !rows || !row_count || !out)
        return fail(d, GOLEM_ERR_INVALID_ARGUMENT, "intent.argument");
    /* Scratch is bounded by the approved control-byte ceiling, not a new
     * persistent row/event policy. Reject before multiplication/allocation. */
    if (count > GI_CONTROL_MAX / sizeof(gi_span) || row_count > GI_CONTROL_MAX / sizeof(gi_span))
        return fail(d, GOLEM_ERR_OVERFLOW, "intent.limit.control_bytes");
    golem_status status = gi_text_validate(text, d);
    if (status != GOLEM_OK) return status;
    gi_span *wanted = malloc(count * sizeof(*wanted));
    gi_span *covered = malloc(row_count * sizeof(*covered));
    if (!wanted || !covered) {
        free(wanted); free(covered);
        return fail(d, GOLEM_ERR_OUT_OF_MEMORY, "intent.memory");
    }
    gi_coverage_result result = {0, false, true};
    for (size_t i = 0; i < count; ++i) {
        wanted[i] = designated[i];
        if (!span_ok(text, wanted[i])) { status = fail(d, GOLEM_ERR_PARSE, "intent.source.range"); goto done; }
    }
    for (size_t i = 0; i < row_count; ++i) {
        covered[i] = rows[i].span;
        if (!span_ok(text, covered[i])) { status = fail(d, GOLEM_ERR_PARSE, "intent.source.range"); goto done; }
        if (rows[i].classification < GI_REQUIREMENT || rows[i].classification > GI_QUESTION_REQUIRED) {
            status = fail(d, GOLEM_ERR_PARSE, "intent.coverage.classification"); goto done;
        }
        result.has_questions |= rows[i].classification == GI_QUESTION_REQUIRED;
    }
    size_t wanted_count = merge_spans(wanted, count), covered_count = merge_spans(covered, row_count);
    if (wanted_count != covered_count) { status = fail(d, GOLEM_ERR_INVALID_STATE, "intent.coverage.mismatch"); goto done; }
    for (size_t i = 0; i < wanted_count; ++i) {
        if (wanted[i].start != covered[i].start || wanted[i].end != covered[i].end) {
            status = fail(d, GOLEM_ERR_INVALID_STATE, "intent.coverage.mismatch"); goto done;
        }
        result.designated_bytes += wanted[i].end - wanted[i].start;
    }
    *out = result;
done:
    free(wanted); free(covered);
    return status;
}

static struct json_object *get(struct json_object *o, const char *key)
{
    struct json_object *v = NULL;
    if (json_object_is_type(o, json_type_object)) (void)json_object_object_get_ex(o, key, &v);
    return v;
}
static bool keys(struct json_object *o, const char *const *names, size_t count)
{
    if (!json_object_is_type(o, json_type_object) || (size_t)json_object_object_length(o) != count) return false;
    for (size_t i = 0; i < count; ++i) if (!json_object_object_get_ex(o, names[i], NULL)) return false;
    return true;
}
static bool string(struct json_object *o)
{
    return json_object_is_type(o, json_type_string) && json_object_get_string_len(o) > 0;
}
static bool eq(struct json_object *o, const char *value)
{
    return string(o) && strcmp(json_object_get_string(o), value) == 0;
}
static bool identifier(struct json_object *o)
{
    if (!string(o) || json_object_get_string_len(o) > 64) return false;
    const unsigned char *s = (const unsigned char *)json_object_get_string(o);
    for (; *s; ++s)
        if (!((*s >= 'a' && *s <= 'z') || (*s >= 'A' && *s <= 'Z') ||
              (*s >= '0' && *s <= '9') || *s == '-' || *s == '_')) return false;
    return true;
}
static bool uint_value(struct json_object *o, uint64_t *out)
{
    if (!json_object_is_type(o, json_type_int) || json_object_get_int64(o) < 0) return false;
    *out = json_object_get_uint64(o);
    return true;
}
static bool digest(struct json_object *o, golem_digest *out)
{
    return string(o) && golem_digest_parse((golem_string_view){json_object_get_string(o),
        (size_t)json_object_get_string_len(o)}, out) == GOLEM_OK;
}

static int hex(unsigned char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
static bool escape_unit(golem_bytes b, size_t offset, unsigned *unit)
{
    if (b.size - offset < 6 || b.data[offset] != '\\' || b.data[offset + 1] != 'u') return false;
    unsigned value = 0;
    for (size_t i = 2; i < 6; ++i) {
        int digit = hex(b.data[offset + i]);
        if (digit < 0) return false;
        value = (value << 4) | (unsigned)digit;
    }
    *unit = value;
    return true;
}
/* json-c may replace unpaired surrogate escapes with U+FFFD. The source
 * boundary must reject that lossy interpretation, not normalize metadata. */
static bool scalar_escapes(golem_bytes b)
{
    for (size_t i = 0; i < b.size; ++i) {
        if (b.data[i] != '\\') continue;
        unsigned first;
        if (!escape_unit(b, i, &first)) { if (i + 1 < b.size) ++i; continue; }
        i += 5;
        if (first >= 0xdc00u && first <= 0xdfffu) return false;
        if (first >= 0xd800u && first <= 0xdbffu) {
            unsigned second;
            if (!escape_unit(b, i + 1, &second) || second < 0xdc00u || second > 0xdfffu) return false;
            i += 6;
        }
    }
    return true;
}

golem_status gi_domain_digest(golem_bytes control, golem_digest *out, golem_diagnostic *d)
{
    static const char *const registry[] = {"golem.intent.source.v1", "golem.intent.quota-preparation.v1"};
    if (!out || (!control.data && control.size)) return fail(d, GOLEM_ERR_INVALID_ARGUMENT, "intent.argument");
    if (control.size > GI_CONTROL_MAX) return fail(d, GOLEM_ERR_OVERFLOW, "intent.limit.control_bytes");
    if (!scalar_escapes(control)) return fail(d, GOLEM_ERR_PARSE, "intent.source.unicode_escape");
    struct json_object *o = NULL;
    golem_status status = golem_json_parse(control, GI_CONTROL_MAX, &o);
    if (status != GOLEM_OK) return fail(d, status, "intent.identity.json");
    const char *domain = NULL;
    for (size_t i = 0; i < sizeof(registry) / sizeof(*registry); ++i)
        if (eq(get(o, "schema"), registry[i])) domain = registry[i];
    json_object_put(o);
    if (!domain) return fail(d, GOLEM_ERR_UNSUPPORTED_VERSION, "intent.identity.unregistered_schema");
    size_t domain_size = strlen(domain) + 1;
    size_t size = domain_size + 8 + control.size;
    uint8_t *preimage = malloc(size);
    if (!preimage) return fail(d, GOLEM_ERR_OUT_OF_MEMORY, "intent.memory");
    memcpy(preimage, domain, domain_size);
    uint64_t length = (uint64_t)control.size;
    for (size_t i = 0; i < 8; ++i) preimage[domain_size + i] = (uint8_t)(length >> (8 * i));
    memcpy(preimage + domain_size + 8, control.data, control.size);
    status = golem_digest_bytes((golem_bytes){preimage, size}, out);
    free(preimage);
    return status;
}

golem_status gi_source_identity(golem_bytes control, golem_bytes text,
    golem_digest *out, golem_diagnostic *d)
{
    if (!out) return fail(d, GOLEM_ERR_INVALID_ARGUMENT, "intent.argument");
    gi_source_result source;
    golem_status status = gi_source_validate(control, text, &source, d);
    return status == GOLEM_OK ? gi_domain_digest(control, out, d) : status;
}

golem_status gi_source_validate(golem_bytes control, golem_bytes text,
    gi_source_result *out, golem_diagnostic *d)
{
    if (!out) return fail(d, GOLEM_ERR_INVALID_ARGUMENT, "intent.argument");
    gi_capacity capacity = {.control_bytes = control.size, .source_bytes = text.size};
    golem_status status = gi_capacity_validate(&capacity, d);
    if (status != GOLEM_OK) return status;
    if (!control.data && control.size) return fail(d, GOLEM_ERR_INVALID_ARGUMENT, "intent.argument");
    if (!scalar_escapes(control)) return fail(d, GOLEM_ERR_PARSE, "intent.source.unicode_escape");
    struct json_object *o = NULL;
    status = golem_json_parse(control, GI_CONTROL_MAX, &o);
    if (status != GOLEM_OK) return fail(d, status, "intent.source.json");
    const char *root_keys[] = {"schema", "project_id", "work_id", "created_by_assertion", "body"};
    const char *body_keys[] = {"body_cas", "byte_length", "media_type", "encoding", "origin",
        "capture_ref", "designation", "execution_authority"};
    const char *designation_keys[] = {"scope_id", "ranges", "purpose", "decision_ref"};
    const char *range_keys[] = {"start", "end"};
    struct json_object *body = get(o, "body"), *designation = get(body, "designation");
    struct json_object *ranges = get(designation, "ranges"), *work = get(o, "work_id");
    gi_source_result result = {0};
    golem_digest decision;
    uint64_t length;
    bool valid = keys(o, root_keys, 5) && eq(get(o, "schema"), "golem.intent.source.v1") &&
        identifier(get(o, "project_id")) && (!work || identifier(work)) &&
        string(get(o, "created_by_assertion")) && keys(body, body_keys, 8) &&
        digest(get(body, "body_cas"), &result.body_cas) && uint_value(get(body, "byte_length"), &length) &&
        eq(get(body, "encoding"), "UTF-8") && string(get(body, "capture_ref")) &&
        json_object_is_type(get(body, "execution_authority"), json_type_boolean) &&
        !json_object_get_boolean(get(body, "execution_authority")) &&
        keys(designation, designation_keys, 4) && identifier(get(designation, "scope_id")) &&
        string(get(designation, "purpose")) && digest(get(designation, "decision_ref"), &decision) &&
        json_object_is_type(ranges, json_type_array) && json_object_array_length(ranges) > 0;
    struct json_object *origin = get(body, "origin");
    valid = valid && (eq(origin, "TRUSTED_USER_INPUT") || eq(origin, "USER_DESIGNATED_DOCUMENT") ||
        eq(origin, "TOOL_OBSERVATION") || eq(origin, "EXTERNAL_REFERENCE") || eq(origin, "MODEL_DRAFT"));
    if (!valid) { status = fail(d, GOLEM_ERR_PARSE, "intent.source.schema"); goto done; }
    if (!eq(get(body, "media_type"), "text/plain") && !eq(get(body, "media_type"), "text/markdown")) {
        status = fail(d, GOLEM_ERR_UNSUPPORTED_VERSION, "intent.source.unsupported_media"); goto done;
    }
    if (length != text.size) { status = fail(d, GOLEM_ERR_PARSE, "intent.source.length"); goto done; }
    status = gi_text_validate(text, d);
    if (status != GOLEM_OK) goto done;
    golem_digest actual;
    status = golem_digest_bytes(text, &actual);
    if (status != GOLEM_OK) goto done;
    if (memcmp(&actual, &result.body_cas, sizeof(actual)) != 0) {
        status = fail(d, GOLEM_ERR_PARSE, "intent.source.body_cas"); goto done;
    }
    size_t count = json_object_array_length(ranges);
    if (count > GI_CONTROL_MAX / sizeof(gi_span)) {
        status = fail(d, GOLEM_ERR_OVERFLOW, "intent.limit.control_bytes"); goto done;
    }
    gi_span *spans = malloc(count * sizeof(*spans));
    if (!spans) { status = fail(d, GOLEM_ERR_OUT_OF_MEMORY, "intent.memory"); goto done; }
    for (size_t i = 0; i < count; ++i) {
        struct json_object *row = json_object_array_get_idx(ranges, i);
        uint64_t start, end;
        if (!keys(row, range_keys, 2) || !uint_value(get(row, "start"), &start) ||
            !uint_value(get(row, "end"), &end) || start > text.size || end > text.size ||
            !span_ok(text, (gi_span){(size_t)start, (size_t)end})) {
            status = fail(d, GOLEM_ERR_PARSE, "intent.source.range"); break;
        }
        spans[i] = (gi_span){(size_t)start, (size_t)end};
    }
    if (status == GOLEM_OK) {
        count = merge_spans(spans, count);
        result.byte_length = text.size;
        for (size_t i = 0; i < count; ++i) result.designated_bytes += spans[i].end - spans[i].start;
        *out = result;
    }
    free(spans);
done:
    json_object_put(o);
    return status;
}
