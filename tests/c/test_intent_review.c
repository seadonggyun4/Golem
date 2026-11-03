#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "../../src/intent/review.h"
#include "../../src/common/json.h"
#include "test.h"
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>

static golem_bytes bytes(const char *s)
{
    return (golem_bytes){(const uint8_t *)s, strlen(s)};
}
static struct json_object *get(struct json_object *o, const char *k)
{
    struct json_object *v = NULL;
    (void)json_object_object_get_ex(o, k, &v);
    return v;
}
static golem_bytes wire(struct json_object *o)
{
    return bytes(json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN));
}
static void put(struct json_object *o, const char *k, const char *v)
{
    (void)json_object_object_add(o, k, json_object_new_string(v));
}
static int hex(const golem_digest *d, char out[65])
{
    size_t n;
    CHECK(golem_digest_format(d, out, 65, &n) == GOLEM_OK);
    return 0;
}
static golem_status allowed(void *ctx, gi_review_purpose purpose, const golem_digest *base,
                            const golem_digest *evidence, const char *project, const char *work,
                            const char *producer, const char *reviewer)
{
    (void)base;
    (void)evidence;
    (void)producer;
    (void)reviewer;
    if (strcmp(project, "demo") || strcmp(work, "work"))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    int *deny = ctx;
    return *deny == (int)purpose + 1 ? GOLEM_ERR_POLICY_DENIED : GOLEM_OK;
}
static golem_status registered(void *ctx)
{
    return ctx ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED;
}
static int cleanup(int root)
{
    int fd = openat(root, ".", O_RDONLY | O_DIRECTORY);
    CHECK(fd >= 0);
    DIR *dir = fdopendir(fd);
    CHECK(dir != NULL);
    struct dirent *e;
    while ((e = readdir(dir))) {
        if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, ".."))
            continue;
        struct stat sb;
        CHECK(fstatat(root, e->d_name, &sb, AT_SYMLINK_NOFOLLOW) == 0);
        if (S_ISDIR(sb.st_mode)) {
            int child = openat(root, e->d_name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
            CHECK(child >= 0);
            CHECK(cleanup(child) == 0);
            CHECK(close(child) == 0);
        }
        CHECK(unlinkat(root, e->d_name, S_ISDIR(sb.st_mode) ? AT_REMOVEDIR : 0) == 0);
    }
    CHECK(closedir(dir) == 0);
    return 0;
}
static struct json_object *control(const char *base, uint64_t epoch, const char *op,
                                   struct json_object *body)
{
    struct json_object *o = json_object_new_object();
    put(o, "schema", "golem.intent.review-control.v1");
    put(o, "project_id", "demo");
    put(o, "work_id", "work");
    put(o, "baseline_digest", base);
    put(o, "operation", op);
    json_object_object_add(o, "expected_epoch", json_object_new_uint64(epoch));
    json_object_object_add(o, "body", body);
    return o;
}
static struct json_object *review(const char *defs, const char *evidence)
{
    struct json_object *b = json_object_new_object();
    put(b, "stage", "REQUIREMENTS");
    put(b, "producer", "author");
    put(b, "reviewer", "reviewer");
    put(b, "input_manifest", evidence);
    put(b, "definitions_digest", defs);
    put(b, "verdict", "PASS");
    put(b, "evidence_digest", evidence);
    return b;
}
int main(void)
{
    golem_digest raw, sd, rd, bd;
    char rh[65], sh[65], dh[65], bh[65], defs[65];
    CHECK(golem_digest_bytes(bytes("abc"), &raw) == GOLEM_OK);
    CHECK(hex(&raw, rh) == 0);
    char source[2048], definition[2048], baseline[4096];
    int n = snprintf(
        source, sizeof(source),
        "{\"schema\":\"golem.intent.source.v1\",\"project_id\":\"demo\",\"work_id\":\"work\","
        "\"created_by_assertion\":\"fixture\",\"body\":{\"body_cas\":\"%s\",\"byte_length\":3,"
        "\"media_type\":\"text/plain\",\"encoding\":\"UTF-8\",\"origin\":\"MODEL_DRAFT\","
        "\"capture_ref\":\"fixture\",\"designation\":{\"scope_id\":\"scope\",\"ranges\":[{\"start\":0,\"end\":3}],"
        "\"purpose\":\"PRODUCT_REQUIREMENT\",\"decision_ref\":\"%s\"},\"execution_authority\":false}}",
        rh, rh);
    CHECK(n > 0 && (size_t)n < sizeof(source));
    gi_source_input si = {bytes(source), bytes("abc")};
    CHECK(gi_source_identity(si.control, si.text, &sd, NULL) == GOLEM_OK);
    CHECK(hex(&sd, sh) == 0);
    n = snprintf(
        definition, sizeof(definition),
        "{\"schema\":\"golem.intent.requirement.v1\",\"project_id\":\"demo\",\"work_id\":\"work\","
        "\"created_by_assertion\":\"fixture\",\"body\":{\"id\":\"REQ-1\",\"exact_text\":\"abc\","
        "\"source_spans\":[{\"source_ref\":\"%s\",\"start\":0,\"end\":3}],\"modality\":\"MUST\","
        "\"quantifier\":\"ALL\",\"negative\":false,\"conditions\":[],\"acceptance_oracle_refs\":[],"
        "\"derivation_rationale\":\"fixture only\"}}",
        sh);
    CHECK(n > 0 && (size_t)n < sizeof(definition));
    CHECK(gi_domain_digest(bytes(definition), &rd, NULL) == GOLEM_OK);
    CHECK(hex(&rd, dh) == 0);
    n = snprintf(
        baseline, sizeof(baseline),
        "{\"schema\":\"golem.intent.baseline.v1\",\"project_id\":\"demo\",\"work_id\":\"work\","
        "\"created_by_assertion\":\"fixture\",\"body\":{\"source_refs\":[\"%s\"],\"previous_baseline_digest\":null,"
        "\"decision_refs\":[],\"requirement_refs\":[\"%s\"],\"constraint_refs\":[],\"issuer_policy_ref\":\"%s\","
        "\"coverage_manifest\":[{\"source_ref\":\"%s\",\"rows\":[{\"start\":0,\"end\":3,\"classification\":\"REQUIREMENT\","
        "\"requirement_refs\":[\"%s\"],\"constraint_refs\":[],\"rationale\":\"fixture\",\"review_refs\":[]}]}]}}",
        sh, dh, rh, sh, dh);
    CHECK(n > 0 && (size_t)n < sizeof(baseline));
    CHECK(gi_baseline_identity(bytes(baseline), &bd, NULL) == GOLEM_OK);
    CHECK(hex(&bd, bh) == 0);
    golem_bytes def = bytes(definition);
    gi_review_inputs in = {bytes(baseline), &si, 1, &def, 1};
    gi_review_binding binding;
    CHECK(gi_review_bind(&in, &binding, NULL) == GOLEM_OK);
    CHECK(hex(&binding.definitions, defs) == 0);
    gi_review_binding sentinel = binding;
    in.definition_count = 0;
    CHECK(gi_review_bind(&in, &binding, NULL) != GOLEM_OK);
    CHECK(!memcmp(&sentinel, &binding, sizeof(binding)));
    in.definition_count = 1;
    gi_source_input bad = si;
    bad.text = bytes("abd");
    in.sources = &bad;
    CHECK(gi_review_bind(&in, &binding, NULL) != GOLEM_OK);
    in.sources = &si;
    gi_review_state *stages_state = NULL;
    CHECK(gi_review_create(&in, &stages_state) == GOLEM_OK);
    const char *names[] = {"REQUIREMENTS", "DESIGN", "TASK_DECOMPOSITION"};
    int stage_deny = 0;
    for (unsigned i = 0; i < 3; ++i) {
        struct json_object *stage_body = review(defs, rh);
        put(stage_body, "stage", names[i]);
        struct json_object *stage_control = control(bh, i, "review", stage_body);
        CHECK(gi_review_apply(stages_state, wire(stage_control), allowed, &stage_deny) == GOLEM_OK);
        json_object_put(stage_control);
    }
    gi_review_stage_status observed_stage;
    CHECK(gi_review_stage_inspect(stages_state, 2, &observed_stage) == GOLEM_OK &&
          observed_stage.passed);
    struct json_object *new_requirements = control(bh, 3, "review", review(defs, rh));
    CHECK(gi_review_apply(stages_state, wire(new_requirements), allowed, &stage_deny) == GOLEM_OK);
    CHECK(gi_review_stage_inspect(stages_state, 2, &observed_stage) == GOLEM_OK &&
          !observed_stage.passed);
    CHECK(gi_review_stage_inspect(stages_state, 7, &observed_stage) == GOLEM_ERR_INVALID_ARGUMENT);
    json_object_put(new_requirements);
    gi_review_free(stages_state);
    gi_review_state *s = NULL;
    CHECK(gi_review_create(&in, &s) == GOLEM_OK);
    int deny = 0;
    gi_review_status status;
    struct json_object *r = control(bh, 0, "review", review(defs, rh));
    put(get(r, "body"), "reviewer", "author");
    CHECK(gi_review_apply(s, wire(r), allowed, &deny) != GOLEM_OK);
    put(get(r, "body"), "reviewer", "reviewer");
    deny = GI_REVIEW_STAGE + 1;
    CHECK(gi_review_apply(s, wire(r), allowed, &deny) == GOLEM_ERR_POLICY_DENIED);
    CHECK(gi_review_inspect(s, &status) == GOLEM_OK && status.epoch == 0);
    deny = 0;
    CHECK(gi_review_apply(s, wire(r), NULL, &deny) == GOLEM_ERR_INVALID_ARGUMENT);
    json_object_object_add(r, "unexpected", json_object_new_boolean(true));
    CHECK(gi_review_apply(s, wire(r), allowed, &deny) == GOLEM_ERR_PARSE);
    json_object_object_del(r, "unexpected");
    put(r, "work_id", "other");
    CHECK(gi_review_apply(s, wire(r), allowed, &deny) != GOLEM_OK);
    put(r, "work_id", "work");
    CHECK(gi_review_apply(s, bytes("{\"schema\":1,\"schema\":2}"), allowed, &deny) != GOLEM_OK);
    CHECK(gi_review_apply(s, wire(r), allowed, &deny) == GOLEM_OK);
    CHECK(gi_review_apply(s, wire(r), allowed, &deny) == GOLEM_ERR_STALE_RESULT);
    struct json_object *b = json_object_new_object();
    put(b, "decision_digest", rh);
    put(b, "review_digest", rh);
    put(b, "policy_digest", rh);
    struct json_object *a = control(bh, 1, "activate", b);
    deny = GI_REVIEW_ACTIVATION + 1;
    CHECK(gi_review_apply(s, wire(a), allowed, &deny) == GOLEM_ERR_POLICY_DENIED);
    deny = 0;
    CHECK(gi_review_apply(s, wire(a), allowed, &deny) == GOLEM_OK);
    CHECK(gi_review_inspect(s, &status) == GOLEM_OK && status.active &&
          !status.execution_authorized);
    b = json_object_new_object();
    put(b, "question_digest", dh);
    put(b, "evidence_digest", rh);
    struct json_object *q = control(bh, 2, "question", b);
    CHECK(gi_review_apply(s, wire(q), allowed, &deny) == GOLEM_OK);
    struct json_object *blocked = control(bh, 3, "review", review(defs, rh));
    CHECK(gi_review_apply(s, wire(blocked), allowed, &deny) == GOLEM_ERR_REQUIREMENTS_UNMET);
    b = json_object_new_object();
    put(b, "question_digest", dh);
    put(b, "evidence_digest", rh);
    struct json_object *answer = control(bh, 3, "answer", b);
    CHECK(gi_review_apply(s, wire(answer), allowed, &deny) == GOLEM_OK);
    b = json_object_new_object();
    put(b, "evidence_digest", rh);
    struct json_object *closed_ids = json_object_new_array(), *carry = json_object_new_array();
    json_object_array_add(closed_ids, json_object_new_string(dh));
    json_object_object_add(b, "close", closed_ids);
    json_object_object_add(b, "carry", carry);
    struct json_object *resolution = control(bh, 4, "resolve", b);
    json_object_array_add(carry, json_object_new_string(dh));
    CHECK(gi_review_apply(s, wire(resolution), allowed, &deny) != GOLEM_OK);
    CHECK(json_object_array_del_idx(carry, 0, 1) == 0);
    deny = GI_REVIEW_RESOLUTION + 1;
    CHECK(gi_review_apply(s, wire(resolution), allowed, &deny) == GOLEM_ERR_POLICY_DENIED);
    deny = 0;
    CHECK(gi_review_apply(s, wire(resolution), allowed, &deny) == GOLEM_OK);
    CHECK(gi_review_inspect(s, &status) == GOLEM_OK && status.open_questions == 0 &&
          !status.requirements_reviewed && !status.execution_authorized);
    json_object_object_add(q, "expected_epoch", json_object_new_uint64(5));
    CHECK(gi_review_apply(s, wire(q), allowed, &deny) ==
          GOLEM_ERR_INVALID_STATE); /* closed ID cannot reopen */
    gi_review_free(s);
    /* Durable control history uses existing journal/quota, never a live Work. */
    char path[] = "/tmp/golem-intent-review-XXXXXX";
    CHECK(mkdtemp(path) != NULL);
    int root = open(path, O_RDONLY | O_DIRECTORY);
    CHECK(root >= 0);
    gi_journal *j = NULL;
    CHECK(gi_journal_open(root, &j) == GOLEM_OK);
    golem_digest bo, br, op, zero = {{0}};
    CHECK(golem_digest_bytes(bytes("baseline-op"), &bo) == GOLEM_OK);
    CHECK(golem_digest_bytes(bytes("baseline-request"), &br) == GOLEM_OK);
    CHECK(golem_digest_bytes(bytes("review-op"), &op) == GOLEM_OK);
    gi_journal_receipt receipt;
    CHECK(gi_journal_store_objects(j, &bo, &br, 0, &zero, in.baseline, &si, 1, registered, &deny,
                                   &receipt) == GOLEM_OK);
    gi_journal_status js;
    CHECK(gi_journal_inspect(j, &js) == GOLEM_OK);
    CHECK(gi_review_publish(j, &bo, &br, &bd, &def, 1, wire(r), &op, js.committed, &js.head,
                            registered, allowed, &deny, &receipt) == GOLEM_OK);
    CHECK(gi_review_publish(j, &bo, &br, &bd, &def, 1, wire(r), &op, js.committed, &js.head,
                            registered, allowed, &deny, &receipt) != GOLEM_OK);
    CHECK(gi_review_load(j, &bo, &br, &bd, &def, 1, &s) == GOLEM_OK);
    CHECK(gi_review_inspect(s, &status) == GOLEM_OK && status.epoch == 1 &&
          status.requirements_reviewed && !status.active);
    gi_review_free(s);
    gi_journal_close(j);
    CHECK(gi_journal_open(root, &j) == GOLEM_OK);
    CHECK(gi_review_load(j, &bo, &br, &bd, &def, 1, &s) == GOLEM_OK);
    gi_review_free(s);
    gi_journal_close(j);
    CHECK(cleanup(root) == 0);
    CHECK(close(root) == 0);
    CHECK(rmdir(path) == 0);
    json_object_put(r);
    json_object_put(a);
    json_object_put(q);
    json_object_put(blocked);
    json_object_put(answer);
    json_object_put(resolution);
    return 0;
}
