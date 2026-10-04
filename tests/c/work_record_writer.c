#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "../../src/document/internal.h"
#include "test.h"
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <json-c/printbuf.h>

static int serializations;
static int serialize_once(struct json_object *o, struct printbuf *pb, int level, int flags)
{
    (void)o; (void)level; (void)flags;
    ++serializations;
    return printbuf_memappend(pb, "{\"fixture\":true}", 16);
}

static int fault, publications, verifications, guards;
static golem_status injected_verify(golem_evidence_store *s, const golem_digest *key,
                                    uint64_t *size, golem_diagnostic *d)
{
    ++verifications;
    return golem_evidence_verify(s, key, size, d);
}
static golem_status deny(void *context)
{
    (void)context;
    ++guards;
    return verifications == 1 && publications == 0 ? GOLEM_ERR_STALE_LEASE : GOLEM_ERR_INVALID_STATE;
}
static golem_status injected_publish(int dir, const char *name, golem_bytes bytes)
{
    ++publications;
    if (fault == 1) return GOLEM_ERR_IO;
    golem_status st = dw_publish(dir, name, bytes);
    return st == GOLEM_OK && fault == 2 ? GOLEM_ERR_IO : st;
}
#define dw_publish injected_publish
#define golem_evidence_verify injected_verify
#include "../../src/document/record.c"
#undef golem_evidence_verify
#undef dw_publish

int main(int argc, char **argv)
{
    CHECK(argc == 3);
    golem_document_store s = {.root = -1, .events = -1, .writable = true};
    s.root = open(argv[1], O_RDONLY | O_DIRECTORY);
    CHECK(s.root >= 0);
    CHECK(golem_evidence_open(argv[1], true, NULL, &s.cas, NULL) == GOLEM_OK);
    CHECK(dw_dir(s.root, "events", true, &s.events) == GOLEM_OK);
    struct json_object *event = json_tokener_parse("{\"schema_version\":1,\"type\":\"fixture\",\"assessment\":{\"result\":\"FAIL\"}}");
    CHECK(event != NULL);
    golem_digest payload, frame, saved, previous = {{0}};
    memset(&saved, 0x55, sizeof(saved));
    payload = saved;
    if (!strcmp(argv[2], "serialize-once")) {
        json_object_set_serializer(event, serialize_once, NULL, NULL);
        CHECK(dw_record_prepare(&s, event, 16, &payload) == GOLEM_OK);
        CHECK(serializations == 1);
        serializations = 0;
        frame = saved;
        CHECK(dw_record_prepare(&s, event, 15, &frame) == GOLEM_ERR_BUDGET_EXHAUSTED);
        CHECK(serializations == 1 && !memcmp(&frame, &saved, sizeof(saved)));
    } else if (!strcmp(argv[2], "readonly")) {
        s.writable = false;
        CHECK(dw_record_prepare(&s, event, 262144, &payload) == GOLEM_ERR_POLICY_DENIED);
        CHECK(dw_event_write(&s, &saved, &frame) == GOLEM_ERR_POLICY_DENIED);
        CHECK(!memcmp(&payload, &saved, sizeof(saved)) && publications == 0);
    } else if (!strcmp(argv[2], "budget")) {
        CHECK(dw_record_prepare(&s, event, 1, &payload) == GOLEM_ERR_BUDGET_EXHAUSTED);
        CHECK(!memcmp(&payload, &saved, sizeof(saved)) && !s.poisoned && publications == 0);
    } else if (!strcmp(argv[2], "missing")) {
        frame = saved;
        CHECK(dw_event_write_guarded(&s, &saved, &frame, deny, NULL) != GOLEM_OK);
        CHECK(s.poisoned && !memcmp(&frame, &saved, sizeof(saved)) && publications == 0);
        CHECK(guards == 0);
    } else {
        CHECK(dw_record_prepare(&s, event, 262144, &payload) == GOLEM_OK);
        const char *raw = json_object_to_json_string_ext(event, JSON_C_TO_STRING_PLAIN);
        golem_digest expected;
        CHECK(golem_digest_bytes((golem_bytes){(const uint8_t *)raw, strlen(raw)}, &expected) == GOLEM_OK);
        CHECK(!memcmp(&expected, &payload, sizeof(payload)));
        golem_digest again;
        CHECK(dw_record_prepare(&s, event, 262144, &again) == GOLEM_OK);
        CHECK(!memcmp(&again, &payload, sizeof(payload)) && publications == 0);
        if (!strcmp(argv[2], "guard")) {
            frame = saved;
            CHECK(dw_event_write_guarded(&s, &payload, &frame, deny, NULL) == GOLEM_ERR_STALE_LEASE);
            CHECK(guards == 1 && !s.poisoned && publications == 0);
            CHECK(!memcmp(&frame, &saved, sizeof(saved)));
        } else if (!strcmp(argv[2], "invalid-name")) {
            CHECK(dw_record_reference(&s, s.events, "../escape", &payload, false) == GOLEM_ERR_INVALID_ARGUMENT);
            CHECK(!s.poisoned && publications == 0);
        } else if (!strcmp(argv[2], "corrupt")) {
            char hex[65], path[4096]; size_t required;
            CHECK(golem_digest_format(&payload, hex, sizeof(hex), &required) == GOLEM_OK);
            CHECK(snprintf(path, sizeof(path), "%s/objects/sha256/%.2s/%s", argv[1], hex, hex+2) < (int)sizeof(path));
            CHECK(chmod(path, 0600) == 0);
            int fd = open(path, O_WRONLY | O_TRUNC);
            CHECK(fd >= 0 && write(fd, "bad", 3) == 3 && close(fd) == 0);
            frame = saved;
            CHECK(dw_event_write(&s, &payload, &frame) == GOLEM_ERR_DIGEST_MISMATCH);
            CHECK(s.poisoned && publications == 0 && !memcmp(&frame, &saved, sizeof(saved)));
        } else if (!strcmp(argv[2], "fault-before") || !strcmp(argv[2], "fault-after")) {
            fault = !strcmp(argv[2], "fault-before") ? 1 : 2;
            frame = saved;
            CHECK(dw_event_write(&s, &payload, &frame) == GOLEM_ERR_IO);
            CHECK(!memcmp(&frame, &saved, sizeof(saved)) && s.poisoned && publications == 1);
            CHECK(dw_event_write(&s, &payload, &frame) == GOLEM_ERR_INVALID_STATE);
            CHECK(publications == 1);
            struct stat info;
            CHECK((fstatat(s.events, "00000001.evt", &info, 0) == 0) == (fault == 2));
        } else if (!strcmp(argv[2], "raw") || !strcmp(argv[2], "hex")) {
            bool hex = !strcmp(argv[2], "hex");
            CHECK(dw_record_reference(&s, s.events, "0001", &payload, hex) == GOLEM_OK);
            uint8_t *bytes = NULL; size_t size = 0;
            CHECK(dw_read_at(s.events, "0001", 64, &bytes, &size) == GOLEM_OK);
            char expected_hex[65]; size_t required;
            CHECK(golem_digest_format(&payload, expected_hex, sizeof(expected_hex), &required) == GOLEM_OK);
            CHECK(size == (hex ? 64u : 32u));
            CHECK(!memcmp(bytes, hex ? (const void *)expected_hex : (const void *)payload.bytes, size));
            free(bytes);
        } else {
            bool agent = !strcmp(argv[2], "agent");
            CHECK(dw_record_event(&s, s.events, agent, 1, &previous, &payload, &frame) == GOLEM_OK);
            uint8_t *bytes = NULL; size_t size = 0;
            CHECK(dw_read_at(s.events, "00000001.evt", 80, &bytes, &size) == GOLEM_OK);
            CHECK(size == 80 && !memcmp(bytes, agent ? "GWAGN001" : "GWDOC001", 8));
            CHECK(bytes[8] == 1 && !memcmp(bytes + 16, previous.bytes, 32) && !memcmp(bytes + 48, payload.bytes, 32));
            for (unsigned i = 9; i < 16; ++i) CHECK(bytes[i] == 0);
            CHECK(golem_digest_bytes((golem_bytes){bytes, size}, &expected) == GOLEM_OK);
            CHECK(!memcmp(&frame, &expected, sizeof(frame)));
            free(bytes);
            CHECK(dw_record_event(&s, s.events, agent, 1, &previous, &payload, &again) == GOLEM_OK);
            CHECK(!memcmp(&frame, &again, sizeof(frame)));
            CHECK(s.event_count == 0 && !memcmp(&s.last, &previous, sizeof(previous)));
            if (!strcmp(argv[2], "conflict")) {
                CHECK(json_object_object_add(event, "extra", json_object_new_int(1)) == 0);
                CHECK(dw_record_prepare(&s, event, 262144, &again) == GOLEM_OK);
                CHECK(dw_record_event(&s, s.events, agent, 1, &previous, &again, &expected) == GOLEM_ERR_DIGEST_MISMATCH);
                CHECK(s.poisoned);
            }
        }
    }
    json_object_put(event);
    CHECK(golem_evidence_close(s.cas) == GOLEM_OK);
    CHECK(close(s.events) == 0 && close(s.root) == 0);
    return 0;
}
