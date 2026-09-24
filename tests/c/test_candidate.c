#include "../../src/candidate/internal.h"
#include "test.h"
#include <stdio.h>
#include <string.h>

static int patch_tests(void)
{
    const char *text =
        "{\"snapshot\":{\"repositories\":[{\"inventory\":{"
        "\"schema_version\":1,\"head\":\"0123456789012345678901234567890123456789\","
        "\"policy\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\","
        "\"root\":{\"path\":\"/"
        "candidate\"},\"entries\":[{\"path_hex\":\"61\",\"worktree\":{\"size\":1}}]}}]}}";
    struct json_object *a = json_tokener_parse(text), *b = json_tokener_parse(text);
    CHECK(a && b);
    struct json_object *inventory = dw_get(
        json_object_array_get_idx(dw_get(dw_get(b, "snapshot"), "repositories"), 0), "inventory");
    CHECK(ex_text(dw_get(inventory, "root"), "path", "/target"));
    golem_digest identity, same, sentinel = {{37}};
    CHECK(cf_patch_identity(NULL, a, NULL, b, &identity) == GOLEM_OK);
    CHECK(cf_patch_identity(NULL, a, NULL, a, &same) == GOLEM_OK && dw_equal(&identity, &same));
    CHECK(ex_uint(dw_get(json_object_array_get_idx(dw_get(inventory, "entries"), 0), "worktree"),
                  "size", 2));
    same = sentinel;
    CHECK(cf_patch_identity(NULL, a, NULL, b, &same) == GOLEM_ERR_REQUIREMENTS_UNMET);
    CHECK(dw_equal(&same, &sentinel));
    CHECK(cf_patch_identity(NULL, a, NULL, NULL, &same) == GOLEM_ERR_REQUIREMENTS_UNMET);
    json_object_put(a);
    json_object_put(b);
    return 0;
}

int main(int argc, char **argv)
{
    CHECK(argc == 2);
    golem_candidate_host host = {.version = 77};
    golem_candidate_current_options options = {.size = sizeof(options), .version = 1};
    CHECK(golem_candidate_current_host(NULL, &host) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_candidate_current_host(&options, &host) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(host.version == 77);
    CHECK(patch_tests() == 0);
    struct json_object *manifest = json_object_from_file(argv[1]);
    CHECK(manifest != NULL);
    const char *text = json_object_to_json_string_ext(manifest, JSON_C_TO_STRING_PLAIN);
    golem_digest digest, sentinel;
    memset(&sentinel, 0x37, sizeof(sentinel));
    digest = sentinel;
    CHECK(golem_candidate_validate((golem_bytes){(const uint8_t *)text, strlen(text)}, &digest,
                                   NULL) == GOLEM_OK);
    CHECK(!dw_equal(&digest, &sentinel));
    digest = sentinel;
    CHECK(golem_candidate_validate((golem_bytes){(const uint8_t *)"{}", 2}, &digest, NULL) !=
          GOLEM_OK);
    CHECK(dw_equal(&digest, &sentinel));
    CHECK(!strcmp(cf_decision_v1(false, 8), "INCOMPARABLE"));
    CHECK(!strcmp(cf_decision_v1(true, 0), "NO_ELIGIBLE"));
    CHECK(!strcmp(cf_decision_v1(true, 1), "SOLE_PASS"));
    CHECK(!strcmp(cf_decision_v1(true, 2), "TIE"));

    /* Eight cancelled candidates must fit the bounded replay schema, including
     * every start intent and termination acknowledgement (65 records). */
    struct json_object *members = dw_get(manifest, "candidates");
    CHECK(dw_add(manifest, "parallel_opt_in", json_object_new_boolean(true)));
    for (size_t i = 1; i < GOLEM_CANDIDATE_MAX; ++i) {
        struct json_object *member = NULL;
        CHECK(json_object_deep_copy(json_object_array_get_idx(members, 0), &member, NULL) == 0);
        char name[32];
        snprintf(name, sizeof(name), "candidate-%zu", i);
        CHECK(ex_text(member, "id", name) && ex_text(member, "work_id", name) &&
              ex_text(member, "session_id", name));
        CHECK(wf_append(members, member));
    }
    struct json_object *limits = dw_get(manifest, "limits");
    CHECK(ex_uint(limits, "workers", 8) && ex_uint(limits, "tokens", 800) &&
          ex_uint(limits, "nano_cost", 8000000));
    CHECK(cf_model(manifest) == GOLEM_OK);
    cf_context c = {0};
    CHECK(cf_apply(&c, "CREATE", 0, manifest) == GOLEM_OK);
    c.sequence = 1;
    struct json_object *enrollment = json_object_new_object(), *ids = json_object_new_object();
    const char *roots[] = {"work", "tree", "build", "temp"};
    for (size_t j = 0; j < 4; ++j) {
        struct json_object *id = json_object_new_object();
        CHECK(ex_text(id, "path", "/fixture") && ex_uint(id, "device", 1) &&
              ex_uint(id, "inode", j + 1));
        CHECK(dw_add(ids, roots[j], id));
    }
    CHECK(dw_add(enrollment, "identities", ids) &&
          dw_add_digest(enrollment, "workspace_receipt", &sentinel));
    struct json_object *reservation = json_object_new_object(), *empty = json_object_new_object(),
                       *result = json_object_new_object();
    CHECK(dw_add_digest(reservation, "namespace", &sentinel));
    CHECK(dw_add_digest(result, "termination", &sentinel) && ex_text(result, "qa", "") &&
          dw_add(result, "cancelled", json_object_new_boolean(true)) &&
          dw_add(result, "tokens_known", json_object_new_boolean(true)) &&
          dw_add(result, "cost_known", json_object_new_boolean(true)) &&
          ex_uint(result, "tokens", 0) && ex_uint(result, "nano_cost", 0));
    golem_admission_token t = {.ticket = 1, .epoch = 1};
    t.boot = sentinel;
    struct json_object *token = cf_token(&t);
    for (size_t i = 0; i < GOLEM_CANDIDATE_MAX; ++i) {
        CHECK(cf_apply(&c, "ENROLL", i, empty) != GOLEM_OK);
        CHECK(cf_apply(&c, "ENROLL", i, enrollment) == GOLEM_OK);
        CHECK(cf_apply(&c, "RESERVE", i, empty) != GOLEM_OK);
        CHECK(cf_apply(&c, "RESERVE", i, reservation) == GOLEM_OK);
        CHECK(cf_apply(&c, "TICKET", i, token) == GOLEM_OK);
        CHECK(cf_apply(&c, "START_INTENT", i, empty) == GOLEM_OK);
        CHECK(cf_apply(&c, "START_INTENT", i, empty) != GOLEM_OK);
        CHECK(cf_apply(&c, "RUNNING", i, empty) == GOLEM_OK);
        CHECK(cf_apply(&c, "CANCEL_REQUESTED", i, empty) == GOLEM_OK);
        CHECK(cf_apply(&c, "SETTLING", i, empty) != GOLEM_OK);
        CHECK(cf_apply(&c, "FINISHED", i, empty) != GOLEM_OK);
        CHECK(cf_apply(&c, "SETTLING", i, result) == GOLEM_OK);
        CHECK(cf_apply(&c, "FINISHED", i, empty) == GOLEM_OK);
        c.sequence += 8;
    }
    CHECK(c.sequence == 65 && c.sequence < CF_EVENTS);
    for (size_t i = 0; i < GOLEM_CANDIDATE_MAX; ++i)
        json_object_put(c.members[i]);
    json_object_put(c.manifest);
    json_object_put(manifest);
    json_object_put(enrollment);
    json_object_put(reservation);
    json_object_put(empty);
    json_object_put(result);
    json_object_put(token);
    return 0;
}
