#include "../../src/intent/object.h"
#include "../../src/intent/schema.h"
#include "../../src/common/json.h"
#include "test.h"
#include <string.h>

#define Z "0000000000000000000000000000000000000000000000000000000000000000"
#define B "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
static const char prep[] = "{\"schema\":\"golem.intent.object-preparation.v1\","
    "\"operation_id\":\"" Z "\",\"request_digest\":\"" Z "\",\"lane\":0,"
    "\"expected_sequence\":0,\"expected_head\":\"" Z "\",\"baseline_digest\":\"" B "\","
    "\"objects\":[{\"path\":\"objects/v1/domain/golem.intent.baseline.v1/" B "\","
    "\"kind\":\"domain\",\"byte_length\":10,\"digest\":\"" B "\",\"disposition\":\"new\"}],"
    "\"new_directories\":[\"objects\",\"objects/v1\",\"objects/v1/domain\",\"objects/v1/domain/golem.intent.baseline.v1\"]}";
static struct json_object *get(struct json_object *o, const char *name)
{
    struct json_object *v = NULL; (void)json_object_object_get_ex(o, name, &v); return v;
}
static int preparation(void)
{
    for (unsigned mode = 0; mode < 18; ++mode) {
        struct json_object *o = json_tokener_parse(prep);
        struct json_object *objects = get(o, "objects"), *dirs = get(o, "new_directories");
        struct json_object *row = json_object_array_get_idx(objects, 0);
        bool valid = mode == 0 || mode == 16;
        switch (mode) {
        case 1: json_object_object_add(o, "lane", json_object_new_int(1)); break;
        case 2: json_object_object_add(o, "lane", json_object_new_int(2)); break;
        case 3: json_object_object_add(o, "expected_sequence", json_object_new_uint64(UINT64_MAX)); break;
        case 4: json_object_object_add(row, "path", json_object_new_string("../escape")); break;
        case 5: json_object_object_add(row, "digest", json_object_new_string(Z)); break;
        case 6: json_object_object_add(row, "kind", json_object_new_string("raw")); break;
        case 7: json_object_object_add(row, "byte_length", json_object_new_int(GI_CONTROL_MAX + 1)); break;
        case 8: json_object_object_add(row, "disposition", json_object_new_string("reuse")); break;
        case 9: json_object_array_add(objects, json_object_get(row)); break;
        case 10: json_object_array_add(dirs, json_object_new_string("objects")); break;
        case 11: json_object_array_put_idx(dirs, 0, json_object_new_string("objects/v1"));
                 json_object_array_put_idx(dirs, 1, json_object_new_string("objects")); break;
        case 12: json_object_array_add(dirs, json_object_new_string("objects/v1/raw")); break;
        case 13: json_object_array_add(dirs, json_object_new_string("objects/v2")); break;
        case 14: json_object_object_add(row, "extra", NULL); break;
        case 15: json_object_object_del(o, "operation_id"); break;
        case 16: json_object_object_add(o, "new_directories", json_object_new_array());
                 json_object_object_add(row, "disposition", json_object_new_string("reuse")); break;
        case 17: json_object_object_add(o, "objects", json_object_new_array()); break;
        default: break;
        }
        const char *wire = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
        gi_object_preparation_result result, sentinel;
        memset(&sentinel, 0xa5, sizeof(sentinel)); memcpy(&result, &sentinel, sizeof(result));
        golem_status st = gi_object_preparation_validate((golem_bytes){(const uint8_t *)wire, strlen(wire)}, &result, NULL);
        CHECK((st == GOLEM_OK) == valid);
        if (!valid) CHECK(memcmp(&result, &sentinel, sizeof(result)) == 0);
        else {
            CHECK(result.reservation.sequence == 1 && result.objects == 1);
            CHECK(result.new_objects == (mode == 0 ? 1u : 0u));
            CHECK(result.new_object_bytes == (mode == 0 ? 10u : 0u));
            CHECK(result.new_directories == (mode == 0 ? 4u : 0u));
            gi_object_publication pub = result.reservation.publication, roundtrip;
            char payload[GI_OBJECT_PUBLICATION_CAPACITY]; size_t size;
            CHECK(gi_object_publication_encode(&pub, payload, sizeof(payload), &size) == GOLEM_OK);
            CHECK(gi_object_publication_decode((golem_bytes){(uint8_t *)payload, size}, &roundtrip) == GOLEM_OK);
            CHECK(memcmp(&pub, &roundtrip, sizeof(pub)) == 0);
        }
        json_object_put(o);
    }
    return 0;
}

int main(void)
{
    CHECK(preparation() == 0);
    gi_object_publication p = {0}, decoded, saved;
    memset(&p.preparation, 0xaa, sizeof(p.preparation));
    memset(&p.baseline, 0xbb, sizeof(p.baseline));
    memset(&p.operation, 0xcc, sizeof(p.operation));
    memset(&p.request, 0xdd, sizeof(p.request));
    char wire[GI_OBJECT_PUBLICATION_CAPACITY], copy[GI_OBJECT_PUBLICATION_CAPACITY]; size_t n = 0;
    CHECK(gi_object_publication_encode(&p, wire, sizeof(wire), &n) == GOLEM_OK);
    CHECK(n == strlen(wire) && n < sizeof(wire));
    CHECK(strchr(wire, ' ') == NULL && strchr(wire, '\n') == NULL);
    CHECK(strstr(wire, "preparation_digest") < strstr(wire, "baseline_digest"));
    CHECK(strstr(wire, "baseline_digest") < strstr(wire, "operation_id"));
    CHECK(strstr(wire, "operation_id") < strstr(wire, "request_digest"));
    CHECK(gi_object_publication_decode((golem_bytes){(uint8_t *)wire, n}, &decoded) == GOLEM_OK);
    CHECK(memcmp(&p, &decoded, sizeof(p)) == 0);
    golem_digest ignored;
    CHECK(gi_domain_digest((golem_bytes){(uint8_t *)wire, n}, &ignored, NULL) == GOLEM_ERR_UNSUPPORTED_VERSION);
    size_t unchanged = 123;
    memset(copy, 'x', sizeof(copy));
    CHECK(gi_object_publication_encode(&p, copy, n, &unchanged) == GOLEM_ERR_OVERFLOW);
    CHECK(unchanged == 123);
    for (size_t i = 0; i < sizeof(copy); ++i) CHECK(copy[i] == 'x');
    CHECK(gi_object_publication_encode(&p, copy, n + 1, &unchanged) == GOLEM_OK && unchanged == n);
    CHECK(memcmp(copy, wire, n + 1) == 0);
    memset(&saved, 0x5a, sizeof(saved));
    for (size_t i = 0; i < n; ++i) {
        decoded = saved;
        CHECK(gi_object_publication_decode((golem_bytes){(uint8_t *)wire, i}, &decoded) != GOLEM_OK);
        CHECK(memcmp(&saved, &decoded, sizeof(saved)) == 0);
    }
    memcpy(copy, wire, n); copy[n] = '\n'; decoded = saved;
    CHECK(gi_object_publication_decode((golem_bytes){(uint8_t *)copy, n + 1}, &decoded) != GOLEM_OK);
    CHECK(memcmp(&saved, &decoded, sizeof(saved)) == 0);
    memcpy(copy, wire, n + 1); *strstr(copy, "aaaa") = 'A';
    CHECK(gi_object_publication_decode((golem_bytes){(uint8_t *)copy, n}, &decoded) != GOLEM_OK);
    memcpy(copy, wire, n + 1); *strstr(copy, "golem") = 'G';
    CHECK(gi_object_publication_decode((golem_bytes){(uint8_t *)copy, n}, &decoded) != GOLEM_OK);

    gi_quota_state current = {0}, output, sentinel;
    memset(&sentinel, 0xa5, sizeof(sentinel));
    gi_object_reservation reservation = {.sequence = 1, .publication = p};
    CHECK(gi_object_reservation_project(&current, &reservation, NULL, &output) == GOLEM_OK);
    CHECK(output.lane[0].value[GI_QUOTA_EVENTS] == 1 && output.lane[0].value[GI_QUOTA_PAYLOAD] == n);
    CHECK(output.lane[0].value[GI_QUOTA_BYTES] == 0 && output.lane[0].value[GI_QUOTA_ENTRIES] == 0);
    gi_object_journal_binding journal = {.lane = GI_QUOTA_INTAKE, .sequence = 1,
        .payload = {(uint8_t *)wire, n}};
    current = output;
    CHECK(gi_object_reservation_project(&current, &reservation, &journal, &output) == GOLEM_OK);
    CHECK(memcmp(&current, &output, sizeof(output)) == 0);
    for (unsigned mode = 0; mode < 7; ++mode) {
        gi_object_journal_binding bad = journal;
        switch (mode) {
        case 0: bad.lane = GI_QUOTA_RECOVERY; break;
        case 1: bad.lane = GI_QUOTA_RESOLUTION; break;
        case 2: bad.sequence = 2; break;
        case 3: bad.head.bytes[0] = 1; break;
        case 4: bad.payload.size--; break;
        case 5: bad.payload.data = NULL; break;
        case 6: bad.payload.data = (uint8_t *)copy; break;
        }
        output = sentinel;
        CHECK(gi_object_reservation_project(&current, &reservation, &bad, &output) != GOLEM_OK);
        CHECK(memcmp(&output, &sentinel, sizeof(output)) == 0);
    }
    gi_quota_usage limit;
    CHECK(gi_quota_limit(GI_QUOTA_INTAKE, &limit) == GOLEM_OK);
    current.lane[0] = limit; output = sentinel;
    CHECK(gi_object_reservation_project(&current, &reservation, NULL, &output) == GOLEM_ERR_OVERFLOW);
    CHECK(memcmp(&output, &sentinel, sizeof(output)) == 0);
    CHECK(gi_object_reservation_project(&current, &reservation, &journal, &output) == GOLEM_OK);
    CHECK(memcmp(&current, &output, sizeof(output)) == 0);
    current.lane[0].value[GI_QUOTA_EVENTS]--;
    current.lane[0].value[GI_QUOTA_PAYLOAD] -= n;
    CHECK(gi_object_reservation_project(&current, &reservation, NULL, &output) == GOLEM_OK);
    CHECK(memcmp(&output.lane[0], &limit, sizeof(limit)) == 0);
    memset(&current, 0, sizeof(current));
    CHECK(gi_object_reservation_project(&current, &reservation, &journal, &output) == GOLEM_ERR_INVALID_STATE);
    CHECK(gi_object_publication_encode(NULL, wire, sizeof(wire), &n) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_object_publication_decode((golem_bytes){NULL, 0}, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
