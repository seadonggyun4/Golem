#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "../../src/intent/object_inventory.h"
#include "../../src/intent/schema.h"
#include "../../src/common/json.h"
#include "test.h"
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>

static const char *dirs[] = {"objects", "objects/v1", "objects/v1/raw", "objects/v1/raw/sha256",
    "objects/v1/domain", "objects/v1/domain/golem.intent.baseline.v1"};
static golem_bytes bytes(const char *s) { return (golem_bytes){(const uint8_t *)s, strlen(s)}; }
static int put(int root, const char *path, const char *text)
{
    int fd = openat(root, path, O_WRONLY | O_CREAT | O_EXCL, 0600);
    CHECK(fd >= 0); CHECK(write(fd, text, strlen(text)) == (ssize_t)strlen(text));
    CHECK(fchmod(fd, 0400) == 0); CHECK(close(fd) == 0); return 0;
}
static int clean(int root)
{
    int fd = openat(root, ".", O_RDONLY | O_DIRECTORY); CHECK(fd >= 0);
    DIR *dir = fdopendir(fd); CHECK(dir != NULL);
    struct dirent *de;
    while ((de = readdir(dir))) {
        if (!strcmp(de->d_name, ".") || !strcmp(de->d_name, "..")) continue;
        struct stat sb; CHECK(fstatat(root, de->d_name, &sb, AT_SYMLINK_NOFOLLOW) == 0);
        if (S_ISDIR(sb.st_mode)) {
            int child = openat(root, de->d_name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW); CHECK(child >= 0);
            CHECK(clean(child) == 0); CHECK(close(child) == 0);
        }
        CHECK(unlinkat(root, de->d_name, S_ISDIR(sb.st_mode) ? AT_REMOVEDIR : 0) == 0);
    }
    CHECK(closedir(dir) == 0); return 0;
}
static int scenario(unsigned mode)
{
    char temp[] = "/tmp/golem-object-inventory-XXXXXX"; CHECK(mkdtemp(temp) != NULL);
    int root = open(temp, O_RDONLY | O_DIRECTORY); CHECK(root >= 0);
    /* Inventory verifies domain identity, not proposal semantics. */
    const char *body = mode == 16 ? "{\"schema\":\"golem.intent.source.v1\"}" :
        "{\"schema\":\"golem.intent.baseline.v1\"}";
    golem_digest raw, domain; char raw_hex[65], domain_hex[65]; size_t n;
    CHECK(golem_digest_bytes(bytes("abc"), &raw) == GOLEM_OK);
    CHECK(gi_domain_digest(bytes(body), &domain, NULL) == GOLEM_OK);
    CHECK(golem_digest_format(&raw, raw_hex, sizeof(raw_hex), &n) == GOLEM_OK);
    CHECK(golem_digest_format(&domain, domain_hex, sizeof(domain_hex), &n) == GOLEM_OK);
    char raw_path[192], domain_path[192], pending[208];
    (void)snprintf(raw_path, sizeof(raw_path), "objects/v1/raw/sha256/%s", raw_hex);
    (void)snprintf(domain_path, sizeof(domain_path), "objects/v1/domain/golem.intent.baseline.v1/%s", domain_hex);
    (void)snprintf(pending, sizeof(pending), "%s.pending", raw_path);
    char manifest[4096];
    const char *z = "0000000000000000000000000000000000000000000000000000000000000000";
    int length = snprintf(manifest, sizeof(manifest),
        "{\"schema\":\"golem.intent.object-preparation.v1\",\"operation_id\":\"%s\",\"request_digest\":\"%s\","
        "\"lane\":0,\"expected_sequence\":0,\"expected_head\":\"%s\",\"baseline_digest\":\"%s\","
        "\"objects\":[{\"path\":\"%s\",\"kind\":\"raw\",\"byte_length\":3,\"digest\":\"%s\",\"disposition\":\"new\"},"
        "{\"path\":\"%s\",\"kind\":\"domain\",\"byte_length\":%zu,\"digest\":\"%s\",\"disposition\":\"new\"}],"
        "\"new_directories\":[\"objects\",\"objects/v1\",\"objects/v1/raw\",\"objects/v1/raw/sha256\","
        "\"objects/v1/domain\",\"objects/v1/domain/golem.intent.baseline.v1\"]}",
        z, z, z, domain_hex, raw_path, raw_hex, domain_path, strlen(body), domain_hex);
    CHECK(length > 0 && (size_t)length < sizeof(manifest));
    gi_object_manifest_input inputs[2] = {{bytes(manifest), mode == 1 || mode == 8 || mode == 10 || mode == 11}, {0}};
    size_t count = 1; struct json_object *second = NULL;
    if (mode != 0) {
        for (size_t i = 0; i < 6; ++i) CHECK(mkdirat(root, dirs[i], 0700) == 0);
        CHECK(put(root, domain_path, body) == 0);
        if (mode != 6 && mode != 11 && mode != 13 && mode != 14 && mode != 15)
            CHECK(put(root, raw_path, mode == 5 ? "bad" : "abc") == 0);
    }
    switch (mode) {
    case 2: CHECK(linkat(root, raw_path, root, pending, 0) == 0); break;
    case 3: CHECK(put(root, pending, "abc") == 0); break;
    case 4: CHECK(put(root, "objects/unknown", "x") == 0); break;
    case 6: CHECK(symlinkat(domain_hex, root, raw_path) == 0); break;
    case 7: CHECK(fchmodat(root, "objects/v1", 0755, 0) == 0); break;
    case 8: case 9: case 10: {
        second = json_tokener_parse(manifest); CHECK(second != NULL);
        json_object_object_add(second, "expected_sequence", json_object_new_int(1));
        if (mode != 10) {
            json_object_object_add(second, "new_directories", json_object_new_array());
            struct json_object *objects = NULL; CHECK(json_object_object_get_ex(second, "objects", &objects));
            for (size_t i = 0; i < 2; ++i)
                json_object_object_add(json_object_array_get_idx(objects, i), "disposition", json_object_new_string("reuse"));
        }
        inputs[1] = (gi_object_manifest_input){bytes(json_object_to_json_string_ext(second, JSON_C_TO_STRING_PLAIN)), true};
        if (mode == 9) inputs[0] = inputs[1]; else count = 2;
        break;
    }
    case 12: CHECK(linkat(root, raw_path, root, "external-link", 0) == 0); break;
    case 13: CHECK(put(root, pending, "abc") == 0); break;
    case 14: CHECK(put(root, pending, "a") == 0); break;
    case 15: CHECK(put(root, pending, "abcd") == 0); break;
    case 17: CHECK(fchmodat(root, raw_path, 0600, 0) == 0); break;
    default: break;
    }
    gi_object_inventory out, sentinel; memset(&sentinel, 0xa5, sizeof(sentinel)); out = sentinel;
    bool valid = mode == 0 || mode == 1 || mode == 2 || mode == 8 || mode == 13 || mode == 14;
    golem_status st = gi_object_inventory_scan(root, inputs, count, &out);
    CHECK((st == GOLEM_OK) == valid);
    if (!valid) CHECK(memcmp(&out, &sentinel, sizeof(out)) == 0);
    else {
        CHECK(out.pending == (mode != 1 && mode != 8));
        CHECK(out.actual.directories == (mode == 0 ? 0u : 6u));
        CHECK(out.actual.files == (mode == 0 ? 0u : mode == 2 ? 3u : 2u));
        CHECK(out.actual.logical_bytes == (mode == 0 ? 0u : strlen(body) + (mode == 2 ? 6u : mode == 14 ? 1u : 3u)));
        CHECK(out.intake.value[GI_QUOTA_ENTRIES] == out.actual.files + out.actual.directories);
        CHECK(out.intake.value[GI_QUOTA_BYTES] == out.actual.logical_bytes);
        CHECK(out.intake.value[GI_QUOTA_EVENTS] == 0 && out.intake.value[GI_QUOTA_PAYLOAD] == 0);
    }
    json_object_put(second); CHECK(clean(root) == 0); CHECK(close(root) == 0); CHECK(rmdir(temp) == 0);
    return 0;
}
int main(void)
{
    for (unsigned i = 0; i < 18; ++i) CHECK(scenario(i) == 0);
    return 0;
}
