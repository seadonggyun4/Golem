#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "../../src/document/internal.h"
#include "test.h"
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    CHECK(argc == 3);
    const char *mode = argv[2];
    golem_document_store s = {.root = -1, .events = -1, .writable = true};
    s.allocator = golem_allocator_default();
    s.root = open(argv[1], O_RDONLY | O_DIRECTORY);
    CHECK(s.root >= 0);
    CHECK(golem_evidence_open(argv[1], true, NULL, &s.cas, NULL) == GOLEM_OK);
    CHECK(dw_dir(s.root, "events", true, &s.events) == GOLEM_OK);
    struct json_object *event = json_tokener_parse("{\"assessment\":{\"result\":\"FAIL\"}}");
    CHECK(event != NULL);
    golem_digest payload, previous = {{0}}, frame, saved;
    memset(&saved, 0x55, sizeof(saved));
    CHECK(dw_record_prepare(&s, event, GOLEM_DOCUMENT_MAX_JSON, &payload) == GOLEM_OK);
    unsigned count = 42;
    CHECK(dw_record_scan(s.events, 10, true, &count) == GOLEM_ERR_MISSING_RECORD);
    CHECK(count == 42);
    CHECK(dw_record_scan(s.events, 10, false, &count) == GOLEM_OK && count == 0);
    CHECK(dw_publish(s.events, ".pending-fixture", (golem_bytes){(const uint8_t *)"x", 1}) == GOLEM_OK);
    CHECK(dw_record_scan(s.events, 10, false, &count) == GOLEM_OK && count == 0);
    bool agent = !strcmp(mode, "agent");
    uint8_t bytes[DW_FRAME];
    dw_record_frame(bytes, agent, 1, &previous, &payload);
    size_t size = sizeof(bytes);
    const char *name = "00000001.evt";
    golem_status expected = GOLEM_OK, scan_expected = GOLEM_OK;
    if (!strcmp(mode, "magic")) { bytes[0] ^= 1; expected = GOLEM_ERR_CORRUPT_JOURNAL; }
    if (!strcmp(mode, "sequence")) { bytes[8] = 2; expected = GOLEM_ERR_CORRUPT_JOURNAL; }
    if (!strcmp(mode, "previous")) { bytes[16] = 1; expected = GOLEM_ERR_CORRUPT_JOURNAL; }
    if (!strcmp(mode, "truncated")) { --size; expected = GOLEM_ERR_CORRUPT_JOURNAL; }
    if (!strcmp(mode, "missing-cas")) { memcpy(bytes + 48, saved.bytes, 32); expected = GOLEM_ERR_NOT_FOUND; }
    if (!strcmp(mode, "gap")) { name = "00000002.evt"; scan_expected = GOLEM_ERR_MISSING_RECORD; }
    if (!strcmp(mode, "name")) { name = "1.evt"; scan_expected = GOLEM_ERR_CORRUPT_JOURNAL; }
    if (!strcmp(mode, "limit")) { name = "00000011.evt"; scan_expected = GOLEM_ERR_CORRUPT_JOURNAL; }
    if (!strcmp(mode, "symlink")) {
        CHECK(symlinkat(".pending-fixture", s.events, name) == 0);
        expected = GOLEM_ERR_IO;
    } else if (!strcmp(mode, "directory")) {
        CHECK(mkdirat(s.events, name, 0700) == 0);
        expected = GOLEM_ERR_IO;
    } else {
        CHECK(dw_publish(s.events, name, (golem_bytes){bytes, size}) == GOLEM_OK);
    }
    if (!strcmp(mode, "corrupt-cas")) {
        char hex[65], path[4096]; size_t required;
        CHECK(golem_digest_format(&payload, hex, sizeof(hex), &required) == GOLEM_OK);
        CHECK(snprintf(path, sizeof(path), "%s/objects/sha256/%.2s/%s", argv[1], hex, hex + 2) < (int)sizeof(path));
        CHECK(chmod(path, 0600) == 0);
        int fd = open(path, O_WRONLY | O_TRUNC);
        CHECK(fd >= 0 && write(fd, "bad", 3) == 3 && close(fd) == 0);
        expected = GOLEM_ERR_DIGEST_MISMATCH;
    }
    s.writable = false;
    count = 42;
    CHECK(dw_record_scan(s.events, 10, true, &count) == scan_expected);
    if (scan_expected != GOLEM_OK) {
        CHECK(count == 42);
    } else {
        CHECK(count == 1);
        struct json_object *read = event;
        golem_digest key = saved;
        frame = saved;
        CHECK(dw_record_read(&s, s.events, agent, 1, &previous, &key, &frame, &read) == expected);
        if (expected == GOLEM_OK) {
            CHECK(json_object_equal(event, read));
            CHECK(dw_equal(&key, &payload));
            golem_digest digest;
            CHECK(golem_digest_bytes((golem_bytes){bytes, size}, &digest) == GOLEM_OK);
            CHECK(dw_equal(&digest, &frame));
            json_object_put(read);
            read = event;
            key = saved;
            CHECK(dw_record_read(&s, s.events, !agent, 1, &previous, &key, &digest, &read) == GOLEM_ERR_CORRUPT_JOURNAL);
            CHECK(read == event && dw_equal(&key, &saved) && dw_equal(&digest, &frame));
            uint8_t other[DW_FRAME];
            dw_record_frame(other, !agent, 1, &previous, &payload);
            CHECK(!memcmp(other + 48, bytes + 48, 32) && memcmp(other, bytes, DW_FRAME));
        } else {
            CHECK(read == event && dw_equal(&key, &saved) && dw_equal(&frame, &saved));
        }
    }
    CHECK(!s.poisoned && s.event_count == 0 && dw_equal(&s.last, &previous));
    json_object_put(event);
    CHECK(golem_evidence_close(s.cas) == GOLEM_OK);
    CHECK(close(s.events) == 0 && close(s.root) == 0);
    return 0;
}
