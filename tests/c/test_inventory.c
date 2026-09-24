#include "../../src/inventory/internal.h"
#include "test.h"
#include <string.h>

int main(void)
{
    const char head[] = "100644 blob 0123456789012345678901234567890123456789\ta\tname\n";
    const char index[] = "100644 0123456789012345678901234567890123456789 0\ta";
    const char unmerged[] = "100644 0123456789012345678901234567890123456789 999999999999999999999\ta";
    in_git_entry git_entry = {0};
    CHECK(in_git_entry_parse((golem_bytes){(const uint8_t *)head, sizeof(head)}, false,
                             &git_entry) == GOLEM_OK);
    CHECK(!strcmp(git_entry.path, "a\tname\n"));
    CHECK(in_git_entry_parse((golem_bytes){(const uint8_t *)index, sizeof(index)}, true,
                             &git_entry) == GOLEM_OK);
    in_git_entry saved = git_entry;
    for (size_t n = 0; n < sizeof(head); ++n) {
        CHECK(in_git_entry_parse((golem_bytes){(const uint8_t *)head, n}, false,
                                 &git_entry) != GOLEM_OK);
        CHECK(!memcmp(&saved, &git_entry, sizeof(saved)));
    }
    CHECK(in_git_entry_parse((golem_bytes){(const uint8_t *)unmerged, sizeof(unmerged)}, true,
                             &git_entry) != GOLEM_OK);
    const char sha256[] = "120000 blob 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\tlink";
    CHECK(in_git_entry_parse((golem_bytes){(const uint8_t *)sha256, sizeof(sha256)}, false,
                             &git_entry) == GOLEM_OK);
    CHECK(strlen(git_entry.oid) == 64 && !strcmp(git_entry.mode, "120000"));
    const char *bad_records[] = {
        "100644 0123456789012345678901234567890123456789 +0\ta",
        "100644 0123456789012345678901234567890123456789 00\ta",
        "100644 0123456789012345678901234567890123456789 1\ta",
        "100644 0123456789012345678901234567890123456789 0\t../a",
        "100644 0123456789012345678901234567890123456789 0\t.git/config",
        "100644 012345678901234567890123456789012345678g 0\ta",
        "100644 0123456789012345678901234567890123456789 0\t",
        "999999 0123456789012345678901234567890123456789 0\ta"
    };
    saved = git_entry;
    for (size_t i = 0; i < sizeof(bad_records) / sizeof(bad_records[0]); ++i) {
        CHECK(in_git_entry_parse((golem_bytes){(const uint8_t *)bad_records[i],
                                 strlen(bad_records[i]) + 1}, true, &git_entry) != GOLEM_OK);
        CHECK(!memcmp(&saved, &git_entry, sizeof(saved)));
    }
    const char embedded[] = "100644 0123456789012345678901234567890123456789 0\ta\0hidden";
    CHECK(in_git_entry_parse((golem_bytes){(const uint8_t *)embedded, sizeof(embedded)}, true,
                             &git_entry) == GOLEM_ERR_PARSE);
    struct {
        const char *pattern, *path;
        bool expected;
    } cases[] = {{"a/*", "a/b", true},
                 {"a/*", "a/b/c", false},
                 {"**/test?.c", "test1.c", true},
                 {"**/test?.c", "a/b/test1.c", true},
                 {"**/test?.c", "a/test12.c", false},
                 {"a/**/b", "a/b", true},
                 {"a/**/b", "a/x/y/b", true},
                 {"a/**/b", "x/a/b", false},
                 {"**", "a/b", true},
                 {"a/?", "a//", false},
                 {"a*", "abc", true},
                 {"a*", "ba", false}};
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        in_rule rule = {.kind = 3};
        strcpy(rule.pattern, cases[i].pattern);
        CHECK(in_matches(&rule, cases[i].path) == cases[i].expected);
    }
    in_rule prefix = {.kind = 2, .pattern = "secret"};
    CHECK(in_matches(&prefix, "secret/key"));
    CHECK(!in_matches(&prefix, "secrets/key"));
    CHECK(!in_path("a/../b"));
    CHECK(!in_path(".git/config"));
    char bytes[10];
    CHECK(in_unhex("ff0a2d", bytes, sizeof(bytes)) == GOLEM_OK);
    CHECK((unsigned char)bytes[0] == 255 && bytes[1] == '\n');
    CHECK(in_unhex("00", bytes, sizeof(bytes)) == GOLEM_ERR_PARSE);
    const char *p = "{\"schema_version\":1,\"protected\":[],\"excluded\":[],"
                    "\"limit\":{\"mode\":\"BOUNDED\",\"max_changed_paths\":0}}";
    CHECK(golem_inventory_policy_validate((golem_bytes){(const uint8_t *)p, strlen(p)}, NULL) ==
          GOLEM_OK);
    const char *bad_patterns[] = {"../a",   "/a", "a//b",   "a/**b",
                                  "a/[bc]", "!a", "a/../b", ".git/x"};
    for (size_t i = 0; i < sizeof(bad_patterns) / sizeof(bad_patterns[0]); ++i) {
        struct json_object *object = json_tokener_parse(p), *rule = json_object_new_object();
        CHECK(dw_add(rule, "kind", json_object_new_string("SEGMENT_GLOB")));
        CHECK(dw_add(rule, "pattern", json_object_new_string(bad_patterns[i])));
        CHECK(json_object_array_add(dw_get(object, "protected"), rule) == 0);
        in_policy parsed;
        CHECK(in_policy_parse(object, &parsed) == GOLEM_ERR_PARSE);
        json_object_put(object);
    }
    golem_inventory_reply reply = {0};
    CHECK(golem_inventory_capture(NULL, (golem_bytes){0}, &reply, NULL) ==
          GOLEM_ERR_INVALID_ARGUMENT);
    golem_inventory_reply_free(&reply);
    uint8_t sentinel = 1;
    reply = (golem_inventory_reply){&sentinel, 1};
    CHECK(golem_inventory_capture("/not-a-golem-test-repository",
                                  (golem_bytes){(const uint8_t *)p, strlen(p)}, &reply,
                                  NULL) != GOLEM_OK);
    CHECK(reply.data == &sentinel && reply.size == 1);
    return 0;
}
