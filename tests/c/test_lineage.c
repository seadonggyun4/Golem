#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/lineage.h"
#include "test.h"
#include <dirent.h>
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int make_run_spec(const char *id, const golem_graph_spec *override, golem_work_run **out)
{
    golem_graph_spec spec;
    golem_stage_graph *graph = NULL;
    golem_work_capsule *capsule = NULL;
    CHECK(golem_stage_graph_default_spec(&spec) == GOLEM_OK);
    if (override != NULL) spec = *override;
    CHECK(golem_stage_graph_create(&spec, &graph) == GOLEM_OK);
    const char *scope[] = {"local"}, *acceptance[] = {"tested"};
    golem_capsule_spec c = {0};
    c.id = "lineage-test"; c.goal = "Track execution evidence";
    c.scope = (golem_string_list){scope, 1}; c.acceptance = (golem_string_list){acceptance, 1};
    c.graph = graph;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) c.permissions[i] = GOLEM_AUTONOMY_AUTO_LOCAL;
    CHECK(golem_work_capsule_create(&c, &capsule) == GOLEM_OK);
    CHECK(golem_work_run_create(id, capsule, 2000, out) == GOLEM_OK);
    golem_work_capsule_free(capsule); golem_stage_graph_free(graph);
    return 0;
}
static int make_run(const char *id, golem_work_run **out) { return make_run_spec(id, NULL, out); }
static int receipt(golem_receipt *out)
{
    *out = (golem_receipt){1, 1, 3, {{0}}};
    CHECK(golem_digest_bytes((golem_bytes){(const uint8_t *)"abc", 3}, &out->digest) == GOLEM_OK);
    return 0;
}
static int finish(golem_work_run *run, golem_lineage *g, golem_failure failure)
{
    golem_stage_snapshot s;
    CHECK(golem_stage_run_snapshot_get(golem_work_run_stage_borrow(run), &s) == GOLEM_OK);
    CHECK(golem_work_run_finish(run, s.sequence, failure == GOLEM_FAILURE_NONE ? GOLEM_STAGE_PASSED : GOLEM_STAGE_FAILED,
        failure, failure == GOLEM_FAILURE_NONE) == GOLEM_OK);
    CHECK(golem_lineage_seal(g, run, NULL) == GOLEM_OK);
    return 0;
}
static int stage(golem_work_run *run, golem_lineage *g, const golem_receipt *r,
    const golem_lineage_id *parents, size_t count, golem_failure failure, golem_lineage_id *last)
{
    golem_stage_snapshot s;
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    golem_lineage_id input, context, tool, artifact, evidence;
    CHECK(golem_lineage_begin(g, run, r, parents, count, &input, NULL) == GOLEM_OK);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_CONTEXT_BLOCK, r, &input, 1, &context, NULL) == GOLEM_OK);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_TOOL_RESULT, r, &context, 1, &tool, NULL) == GOLEM_OK);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_ARTIFACT, r, &tool, 1, &artifact, NULL) == GOLEM_OK);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, r, &artifact, 1, &evidence, NULL) == GOLEM_OK);
    CHECK(finish(run, g, failure) == 0); *last = evidence; return 0;
}
static int single(golem_lineage **out, const golem_allocator *allocator)
{
    golem_work_run *run = NULL;
    CHECK(make_run("r", &run) == 0);
    CHECK(golem_lineage_create("r", NULL, allocator, out, NULL) == GOLEM_OK);
    golem_stage_snapshot s; golem_receipt r; CHECK(receipt(&r) == 0);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    golem_lineage_id input, evidence;
    CHECK(golem_lineage_begin(*out, run, &r, NULL, 0, &input, NULL) == GOLEM_OK);
    CHECK(golem_lineage_add(*out, GOLEM_LINEAGE_EVIDENCE, &r, &input, 1, &evidence, NULL) == GOLEM_OK);
    CHECK(finish(run, *out, GOLEM_FAILURE_NONE) == 0);
    golem_work_run_free(run); return 0;
}

static int lifecycle(void)
{
    golem_work_run *run = NULL; golem_lineage *g = NULL;
    CHECK(make_run("cycle", &run) == 0);
    char name[] = "cycle";
    CHECK(golem_lineage_create(name, NULL, NULL, &g, NULL) == GOLEM_OK);
    name[0] = 'x'; CHECK(strcmp(golem_lineage_run_id_borrow(g), "cycle") == 0);
    golem_receipt r; CHECK(receipt(&r) == 0);
    golem_lineage_id previous = 0;
    for (uint64_t sequence = 1; sequence <= 6; ++sequence) {
        CHECK(stage(run, g, &r, sequence == 1 ? NULL : &previous, sequence == 1 ? 0 : 1,
            GOLEM_FAILURE_NONE, &previous) == 0);
        golem_lineage_stage s;
        CHECK(golem_lineage_stage_get(g, sequence, &s) == GOLEM_OK);
        CHECK(s.execution.stage == (golem_stage)(sequence - 1) && s.execution.attempt == 1);
        CHECK(s.execution.sequence == sequence && s.execution.status == GOLEM_STAGE_PASSED);
        size_t count = 999; golem_lineage_id ids[8];
        CHECK(golem_lineage_predecessors(g, sequence, false, ids, 8, &count) == GOLEM_OK);
        CHECK(count == (sequence == 1 ? 0u : 1u));
        if (sequence > 1) CHECK(ids[0] == (sequence - 1) * 5);
        CHECK(golem_lineage_predecessors(g, sequence, true, ids, 8, &count) == GOLEM_OK && count == sequence - 1);
        for (size_t i = 0; i < count; ++i) CHECK(ids[i] == (i + 1) * 5);
        golem_lineage_node node;
        CHECK(golem_lineage_node_get(g, previous, &node) == GOLEM_OK);
        CHECK(node.stage_sequence == sequence && node.kind == GOLEM_LINEAGE_EVIDENCE);
        CHECK(memcmp(node.content.digest.bytes, r.digest.bytes, 32) == 0);
    }
    golem_lineage_stats stats;
    CHECK(golem_lineage_stats_get(g, &stats) == GOLEM_OK);
    CHECK(stats.stages == 6 && stats.nodes == 30 && stats.edges == 29 && !stats.has_open_stage);
    golem_lineage_id unused;
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, &previous, 1, &unused, NULL) == GOLEM_ERR_INVALID_STATE);
    golem_lineage_free(g); golem_work_run_free(run); return 0;
}

static int reentry(void)
{
    golem_work_run *run = NULL; golem_lineage *g = NULL;
    CHECK(make_run("retry", &run) == 0 && golem_lineage_create("retry", NULL, NULL, &g, NULL) == GOLEM_OK);
    golem_receipt r; CHECK(receipt(&r) == 0);
    golem_lineage_id previous = 0;
    for (size_t i = 0; i < 5; ++i) CHECK(stage(run, g, &r, i == 0 ? NULL : &previous, i == 0 ? 0 : 1,
        i == 4 ? GOLEM_FAILURE_IMPLEMENTATION_DEFECT : GOLEM_FAILURE_NONE, &previous) == 0);
    CHECK(golem_work_run_reenter(run) == GOLEM_OK);
    golem_lineage_id inputs[] = {20, 25};
    CHECK(stage(run, g, &r, inputs, 2, GOLEM_FAILURE_NONE, &previous) == 0);
    golem_lineage_stage old, current;
    CHECK(golem_lineage_stage_get(g, 4, &old) == GOLEM_OK);
    CHECK(golem_lineage_stage_get(g, 6, &current) == GOLEM_OK);
    CHECK(old.execution.stage == GOLEM_STAGE_DEVELOPMENT && old.execution.attempt == 1);
    CHECK(current.execution.stage == GOLEM_STAGE_DEVELOPMENT && current.execution.attempt == 2);
    CHECK(old.input == 16 && current.input == 26);
    size_t count; golem_lineage_id found[6];
    CHECK(golem_lineage_predecessors(g, 6, true, found, 6, &count) == GOLEM_OK && count == 5);
    for (size_t i = 0; i < count; ++i) CHECK(found[i] == (i + 1) * 5);
    CHECK(stage(run, g, &r, &previous, 1, GOLEM_FAILURE_NONE, &previous) == 0);
    CHECK(stage(run, g, &r, &previous, 1, GOLEM_FAILURE_NONE, &previous) == 0);
    size_t size;
    CHECK(golem_lineage_encode(g, NULL, 0, &size, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    uint8_t *data = malloc(size); CHECK(data != NULL);
    CHECK(golem_lineage_encode(g, data, size, &size, NULL) == GOLEM_OK);
    golem_lineage *copy = NULL;
    CHECK(golem_lineage_decode((golem_bytes){data, size}, NULL, &copy, NULL) == GOLEM_OK);
    CHECK(golem_lineage_predecessors(copy, 6, false, found, 6, &count) == GOLEM_OK && count == 2);
    CHECK(found[0] == 20 && found[1] == 25);
    golem_lineage_free(copy); free(data); golem_lineage_free(g); golem_work_run_free(run); return 0;
}

static int invalid(void)
{
    golem_lineage *g = NULL; golem_work_run *run = NULL, *wrong = NULL;
    CHECK(make_run("r", &run) == 0 && make_run("wrong", &wrong) == 0);
    CHECK(golem_lineage_create("r", NULL, NULL, &g, NULL) == GOLEM_OK);
    golem_receipt r; CHECK(receipt(&r) == 0);
    golem_lineage_id id = 999, input;
    CHECK(golem_lineage_begin(g, run, &r, NULL, 0, &id, NULL) == GOLEM_ERR_INVALID_STATE && id == 999);
    golem_stage_snapshot s;
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    CHECK(golem_work_run_begin(wrong, false, false, &s) == GOLEM_OK);
    CHECK(golem_lineage_begin(g, wrong, &r, NULL, 0, &id, NULL) == GOLEM_ERR_IDENTITY_MISMATCH);
    CHECK(golem_lineage_begin(g, run, &r, &id, 1, &input, NULL) == GOLEM_ERR_INVALID_GRAPH);
    CHECK(golem_lineage_begin(g, run, &r, NULL, 0, &input, NULL) == GOLEM_OK && input == 1);
    CHECK(golem_lineage_begin(g, run, &r, NULL, 0, &id, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_lineage_seal(g, run, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_ARTIFACT, &r, NULL, 1, &id, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_STAGE_INPUT, &r, &input, 1, &id, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_lineage_id duplicate[] = {1, 1}, future = 2, zero = 0;
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, duplicate, 2, &id, NULL) == GOLEM_ERR_INVALID_GRAPH);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, &future, 1, &id, NULL) == GOLEM_ERR_INVALID_GRAPH);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, &zero, 1, &id, NULL) == GOLEM_ERR_INVALID_GRAPH);
    CHECK(id == 999);
    CHECK(golem_work_run_finish(run, 1, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    CHECK(golem_lineage_seal(g, run, NULL) == GOLEM_ERR_REQUIREMENTS_UNMET);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, &input, 1, &id, NULL) == GOLEM_OK && id == 2);
    CHECK(golem_lineage_seal(g, run, NULL) == GOLEM_OK);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    CHECK(golem_lineage_begin(g, run, &r, NULL, 0, &input, NULL) == GOLEM_ERR_INVALID_GRAPH);
    golem_lineage_id not_evidence = 1;
    CHECK(golem_lineage_begin(g, run, &r, &not_evidence, 1, &input, NULL) == GOLEM_ERR_INVALID_GRAPH);
    CHECK(golem_lineage_begin(g, run, &r, &id, 1, &input, NULL) == GOLEM_OK && input == 3);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, &id, 1, &future, NULL) == GOLEM_ERR_INVALID_GRAPH);
    size_t required = 999; golem_lineage_id small = 777;
    CHECK(golem_lineage_predecessors(g, 2, true, &small, 0, &required) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(required == 1 && small == 777);
    CHECK(golem_lineage_predecessors(g, 2, false, NULL, 0, &required) == GOLEM_ERR_BUFFER_TOO_SMALL && required == 1);
    CHECK(golem_lineage_predecessors(g, 1, true, NULL, 0, &required) == GOLEM_OK && required == 0);
    CHECK(golem_lineage_encode(g, NULL, 0, &required, NULL) == GOLEM_ERR_INVALID_STATE && required == 0);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, &input, 1, &future, NULL) == GOLEM_OK);
    CHECK(golem_work_run_cancel(run) == GOLEM_OK && golem_lineage_seal(g, run, NULL) == GOLEM_OK);
    CHECK(golem_lineage_encode(g, NULL, 0, &required, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    golem_lineage_free(g); golem_work_run_free(run); golem_work_run_free(wrong); return 0;
}

#define ABC_DIGEST 0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23, \
    0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad
/* Independent wire fixture: run r, passed planning #1, input abc -> evidence abc. */
static const uint8_t golden[197] = {
    [0]='H','W','L','G',1,0,0,0,197,0,0,0,1,0,0,0,1,0,0,0,2,0,0,0,1,
    [32]='r', [37]=2, [45]=1, [49]=1, [57]=1, [61]=2,
    [65]=1, [69]=1, [81]='H','W','E','R',1,0,1,0,3, [97]=ABC_DIGEST,
    [129]=5, [133]=1, [141]=1, [145]='H','W','E','R',1,0,1,0,3, [161]=ABC_DIGEST,
    [193]=1
};

static int codec(void)
{
    golem_lineage *g = NULL; CHECK(single(&g, NULL) == 0);
    uint8_t data[sizeof(golden)]; memset(data, 0xaa, sizeof(data)); size_t size = 999;
    CHECK(golem_lineage_encode(g, data, sizeof(data) - 1, &size, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(size == sizeof(golden));
    for (size_t i = 0; i < sizeof(data); ++i) CHECK(data[i] == 0xaa);
    CHECK(golem_lineage_encode(g, data, sizeof(data), &size, NULL) == GOLEM_OK);
    CHECK(memcmp(data, golden, sizeof(golden)) == 0);
    golem_lineage *copy = NULL;
    CHECK(golem_lineage_decode((golem_bytes){golden, sizeof(golden)}, NULL, &copy, NULL) == GOLEM_OK);
    CHECK(golem_lineage_encode(copy, data, sizeof(data), &size, NULL) == GOLEM_OK);
    CHECK(memcmp(data, golden, sizeof(golden)) == 0);
    golem_lineage_free(copy); copy = NULL;
    for (size_t i = 0; i < sizeof(golden); ++i) {
        CHECK(golem_lineage_decode((golem_bytes){golden, i}, NULL, &copy, NULL) != GOLEM_OK && copy == NULL);
        memcpy(data, golden, sizeof(data)); data[i] ^= 0xff;
        golem_status status = golem_lineage_decode((golem_bytes){data, sizeof(data)}, NULL, &copy, NULL);
        if (status == GOLEM_OK) {
            uint8_t encoded[sizeof(data)];
            CHECK(golem_lineage_encode(copy, encoded, sizeof(encoded), &size, NULL) == GOLEM_OK);
            CHECK(memcmp(data, encoded, sizeof(data)) == 0);
            golem_lineage_free(copy); copy = NULL;
        } else CHECK(copy == NULL);
    }
    /* Explicit self-edge, dangling edge, duplicate input, wrong sequence/attempt. */
    const size_t fields[] = {193, 193, 129, 49, 45, 137, 133, 57, 61};
    const uint8_t values[] = {2, 255, 1, 2, 2, 1, 2, 2, 1};
    for (size_t i = 0; i < sizeof(fields) / sizeof(fields[0]); ++i) {
        memcpy(data, golden, sizeof(data)); data[fields[i]] = values[i];
        CHECK(golem_lineage_decode((golem_bytes){data, sizeof(data)}, NULL, &copy, NULL) == GOLEM_ERR_INVALID_GRAPH);
        CHECK(copy == NULL);
    }
    golem_lineage_free(g); return 0;
}

typedef struct tracker { size_t calls, fail_at, live; } tracker;
static void *allocate(void *context, size_t size)
{
    tracker *t = context;
    if (++t->calls == t->fail_at) return NULL;
    void *p = malloc(size); if (p != NULL) ++t->live; return p;
}
static void deallocate(void *context, void *pointer) { tracker *t = context; --t->live; free(pointer); }
static int ownership(void)
{
    for (size_t fail = 1; fail <= 6; ++fail) {
        tracker t = {0, fail, 0}; golem_allocator a = {&t, allocate, deallocate};
        golem_lineage *g = NULL;
        golem_status status = golem_lineage_create("r", NULL, &a, &g, NULL);
        CHECK(status == (fail <= 5 ? GOLEM_ERR_OUT_OF_MEMORY : GOLEM_OK));
        if (status != GOLEM_OK) CHECK(g == NULL);
        golem_lineage_free(g); CHECK(t.live == 0);
        t = (tracker){0, fail, 0}; g = NULL;
        status = golem_lineage_decode((golem_bytes){golden, sizeof(golden)}, &a, &g, NULL);
        CHECK(status == (fail <= 5 ? GOLEM_ERR_OUT_OF_MEMORY : GOLEM_OK));
        golem_lineage_free(g); CHECK(t.live == 0);
    }
    tracker t = {0, 0, 0}; golem_allocator a = {&t, allocate, deallocate};
    golem_lineage *g = NULL;
    CHECK(golem_lineage_create("r", NULL, &a, &g, NULL) == GOLEM_OK && t.calls == 5);
    t.fail_at = 6; a.allocate = NULL;
    golem_work_run *run = NULL; CHECK(make_run("r", &run) == 0);
    golem_receipt r; CHECK(receipt(&r) == 0); golem_lineage_id id;
    CHECK(stage(run, g, &r, NULL, 0, GOLEM_FAILURE_NONE, &id) == 0);
    size_t count; CHECK(golem_lineage_predecessors(g, 1, true, NULL, 0, &count) == GOLEM_OK);
    CHECK(t.calls == 5); golem_lineage_free(g); CHECK(t.live == 0);
    golem_work_run_free(run); return 0;
}

static int capacity(void)
{
    golem_lineage_limits limits = {1, 2, 1};
    golem_lineage *g = NULL; golem_work_run *run = NULL;
    CHECK(golem_lineage_create("r", &limits, NULL, &g, NULL) == GOLEM_OK);
    CHECK(make_run("r", &run) == 0);
    golem_stage_snapshot s; golem_receipt r; CHECK(receipt(&r) == 0);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    golem_lineage_id input, evidence, untouched = 999;
    CHECK(golem_lineage_begin(g, run, &r, NULL, 0, &input, NULL) == GOLEM_OK);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, &input, 1, &evidence, NULL) == GOLEM_OK);
    CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, &evidence, 1, &untouched, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(untouched == 999 && finish(run, g, GOLEM_FAILURE_NONE) == 0);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    CHECK(golem_lineage_begin(g, run, &r, &evidence, 1, &untouched, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    golem_lineage_stats stats;
    CHECK(golem_lineage_stats_get(g, &stats) == GOLEM_OK && stats.stages == 1 && stats.nodes == 2 && stats.edges == 1);
    CHECK(untouched == 999 && !stats.has_open_stage);
    golem_lineage_free(g); golem_work_run_free(run);
    limits.stages = GOLEM_LINEAGE_MAX_STAGES + 1; g = NULL;
    CHECK(golem_lineage_create("r", &limits, NULL, &g, NULL) == GOLEM_ERR_INVALID_ARGUMENT && g == NULL);
    return 0;
}

static int remove_tree(const char *path)
{
    struct stat st; CHECK(lstat(path, &st) == 0);
    if (!S_ISDIR(st.st_mode)) { CHECK(unlink(path) == 0); return 0; }
    DIR *dir = opendir(path); CHECK(dir != NULL);
    struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
        char child[1024]; CHECK(snprintf(child, sizeof(child), "%s/%s", path, entry->d_name) < (int)sizeof(child));
        CHECK(remove_tree(child) == 0);
    }
    CHECK(closedir(dir) == 0 && rmdir(path) == 0); return 0;
}
static int fixture(const char *root)
{
    golem_evidence_store *store = NULL;
    CHECK(golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_OK);
    golem_receipt r;
    CHECK(golem_evidence_put(store, (golem_bytes){(const uint8_t *)"abc", 3}, &r, NULL) == GOLEM_OK);
    golem_lineage *g = NULL; golem_work_run *run = NULL;
    CHECK(make_run("fixture", &run) == 0 && golem_lineage_create("fixture", NULL, NULL, &g, NULL) == GOLEM_OK);
    golem_lineage_id last;
    CHECK(stage(run, g, &r, NULL, 0, GOLEM_FAILURE_NONE, &last) == 0);
    CHECK(stage(run, g, &r, &last, 1, GOLEM_FAILURE_NONE, &last) == 0);
    CHECK(stage(run, g, &r, &last, 1, GOLEM_FAILURE_NONE, &last) == 0);
    golem_digest key; CHECK(golem_lineage_store(g, store, &key, NULL) == GOLEM_OK);
    char hex[65]; size_t required;
    CHECK(golem_digest_format(&key, hex, sizeof(hex), &required) == GOLEM_OK); puts(hex);
    golem_lineage_free(g); golem_work_run_free(run);
    CHECK(golem_evidence_close(store) == GOLEM_OK); return 0;
}
static int storage(void)
{
#ifdef __APPLE__
    char root[] = "/private/tmp/golem-lineage-XXXXXX";
#else
    char root[] = "/tmp/golem-lineage-XXXXXX";
#endif
    CHECK(mkdtemp(root) != NULL);
    golem_evidence_store *store = NULL;
    CHECK(golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_OK);
    golem_lineage *g = NULL, *loaded = NULL; CHECK(single(&g, NULL) == 0);
    size_t verified = 999; golem_digest key = {{0}}, untouched = {{0}};
    CHECK(golem_lineage_verify(g, store, &verified, NULL) == GOLEM_ERR_NOT_FOUND && verified == 999);
    CHECK(golem_lineage_store(g, store, &key, NULL) == GOLEM_ERR_NOT_FOUND);
    CHECK(memcmp(key.bytes, untouched.bytes, 32) == 0);
    golem_receipt r;
    CHECK(golem_evidence_put(store, (golem_bytes){(const uint8_t *)"abc", 3}, &r, NULL) == GOLEM_OK);
    CHECK(golem_lineage_verify(g, store, &verified, NULL) == GOLEM_OK && verified == 2);
    CHECK(golem_lineage_store(g, store, &key, NULL) == GOLEM_OK);
    CHECK(golem_lineage_load(store, &key, NULL, &loaded, NULL) == GOLEM_OK);
    CHECK(strcmp(golem_lineage_run_id_borrow(loaded), "r") == 0);
    golem_lineage_free(loaded); loaded = NULL;
    tracker owner = {0, 0, 0}; golem_allocator owner_allocator = {&owner, allocate, deallocate};
    golem_lineage *owned = NULL; CHECK(single(&owned, &owner_allocator) == 0);
    owner.fail_at = owner.calls + 1;
    golem_digest failed_key = {{0}};
    CHECK(golem_lineage_store(owned, store, &failed_key, NULL) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(memcmp(failed_key.bytes, untouched.bytes, 32) == 0);
    golem_lineage_free(owned); CHECK(owner.live == 0);
    uint8_t changed[sizeof(golden)]; memcpy(changed, golden, sizeof(changed)); changed[89] = 4;
    golem_receipt bad;
    CHECK(golem_evidence_put(store, (golem_bytes){changed, sizeof(changed)}, &bad, NULL) == GOLEM_OK);
    CHECK(golem_lineage_load(store, &bad.digest, NULL, &loaded, NULL) == GOLEM_ERR_SIZE_MISMATCH && loaded == NULL);
    changed[4] = 2;
    CHECK(golem_evidence_put(store, (golem_bytes){changed, sizeof(changed)}, &bad, NULL) == GOLEM_OK);
    CHECK(golem_lineage_load(store, &bad.digest, NULL, &loaded, NULL) == GOLEM_ERR_UNSUPPORTED_VERSION && loaded == NULL);
    for (size_t fail = 1; fail <= 7; ++fail) {
        tracker t = {0, fail, 0}; golem_allocator a = {&t, allocate, deallocate};
        golem_status status = golem_lineage_load(store, &key, &a, &loaded, NULL);
        CHECK(status == (fail <= 6 ? GOLEM_ERR_OUT_OF_MEMORY : GOLEM_OK));
        if (status != GOLEM_OK) CHECK(loaded == NULL);
        golem_lineage_free(loaded); loaded = NULL; CHECK(t.live == 0);
    }
    uint8_t *data = NULL; size_t length = 999;
    CHECK(golem_evidence_read(store, &key, 196, NULL, &data, &length, NULL) == GOLEM_ERR_OVERFLOW);
    CHECK(data == NULL && length == 999);
    CHECK(golem_evidence_read(store, &key, 197, NULL, &data, &length, NULL) == GOLEM_OK);
    CHECK(length == sizeof(golden) && memcmp(data, golden, length) == 0);
    CHECK(golem_allocator_free(NULL, data) == GOLEM_OK); data = NULL;
    char hex[65], path[512]; size_t required;
    CHECK(golem_digest_format(&r.digest, hex, sizeof(hex), &required) == GOLEM_OK);
    (void)snprintf(path, sizeof(path), "%s/objects/sha256/%.2s/%s", root, hex, hex + 2);
    CHECK(chmod(path, 0600) == 0);
    int fd = open(path, O_WRONLY); CHECK(fd >= 0 && write(fd, "abd", 3) == 3 && close(fd) == 0);
    verified = 999;
    CHECK(golem_lineage_verify(g, store, &verified, NULL) == GOLEM_ERR_DIGEST_MISMATCH && verified == 999);
    CHECK(golem_lineage_load(store, &key, NULL, &loaded, NULL) == GOLEM_ERR_DIGEST_MISMATCH && loaded == NULL);
    CHECK(golem_evidence_read(store, &r.digest, 3, NULL, &data, &length, NULL) == GOLEM_ERR_DIGEST_MISMATCH && data == NULL);
    CHECK(unlink(path) == 0);
    CHECK(golem_lineage_load(store, &key, NULL, &loaded, NULL) == GOLEM_ERR_NOT_FOUND && loaded == NULL);
    CHECK(golem_digest_format(&key, hex, sizeof(hex), &required) == GOLEM_OK);
    (void)snprintf(path, sizeof(path), "%s/objects/sha256/%.2s/%s", root, hex, hex + 2);
    CHECK(chmod(path, 0600) == 0);
    fd = open(path, O_WRONLY); CHECK(fd >= 0 && write(fd, "X", 1) == 1 && close(fd) == 0);
    CHECK(golem_lineage_load(store, &key, NULL, &loaded, NULL) == GOLEM_ERR_DIGEST_MISMATCH && loaded == NULL);
    CHECK(golem_evidence_put(store, (golem_bytes){NULL, 0}, &r, NULL) == GOLEM_OK);
    CHECK(golem_evidence_read(store, &r.digest, 0, NULL, &data, &length, NULL) == GOLEM_OK && length == 0 && data != NULL);
    CHECK(golem_allocator_free(NULL, data) == GOLEM_OK);
    golem_lineage_free(g); CHECK(golem_evidence_close(store) == GOLEM_OK);
    return remove_tree(root);
}

static int bounded(void)
{
    golem_lineage_limits limits = {GOLEM_LINEAGE_MAX_STAGES, GOLEM_LINEAGE_MAX_STAGES * 2,
        GOLEM_LINEAGE_MAX_STAGES * 2 - 1};
    golem_lineage *g = NULL; golem_work_run *run = NULL;
    CHECK(golem_lineage_create("long", &limits, NULL, &g, NULL) == GOLEM_OK && make_run("long", &run) == 0);
    golem_receipt r; CHECK(receipt(&r) == 0); golem_lineage_id previous = 0;
    for (uint32_t i = 0; i < limits.stages; ++i) {
        golem_stage_snapshot s; golem_lineage_id input, evidence;
        CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK && s.attempt == i + 1);
        CHECK(golem_lineage_begin(g, run, &r, i == 0 ? NULL : &previous, i == 0 ? 0 : 1, &input, NULL) == GOLEM_OK);
        CHECK(golem_lineage_add(g, GOLEM_LINEAGE_EVIDENCE, &r, &input, 1, &evidence, NULL) == GOLEM_OK);
        CHECK(finish(run, g, GOLEM_FAILURE_TIMEOUT) == 0); previous = evidence;
        if (i + 1 < limits.stages) CHECK(golem_work_run_reenter(run) == GOLEM_OK);
    }
    golem_lineage_id found[GOLEM_LINEAGE_MAX_STAGES]; size_t count;
    CHECK(golem_lineage_predecessors(g, limits.stages, true, found, limits.stages, &count) == GOLEM_OK);
    CHECK(count == limits.stages - 1);
    for (size_t i = 0; i < count; ++i) CHECK(found[i] == (i + 1) * 2);
    size_t size; CHECK(golem_lineage_encode(g, NULL, 0, &size, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    uint8_t *data = malloc(size); CHECK(data != NULL);
    CHECK(golem_lineage_encode(g, data, size, &size, NULL) == GOLEM_OK);
    golem_lineage *decoded = NULL;
    CHECK(golem_lineage_decode((golem_bytes){data, size}, NULL, &decoded, NULL) == GOLEM_OK);
    CHECK(golem_lineage_predecessors(decoded, limits.stages, true, found, limits.stages, &count) == GOLEM_OK);
    CHECK(count == limits.stages - 1);
    free(data); golem_lineage_free(decoded); golem_lineage_free(g); golem_work_run_free(run); return 0;
}

static int identity(void)
{
    golem_graph_spec spec;
    CHECK(golem_stage_graph_default_spec(&spec) == GOLEM_OK);
    spec.count = 3; spec.order[0] = GOLEM_STAGE_QA; spec.order[1] = GOLEM_STAGE_PLANNING; spec.order[2] = GOLEM_STAGE_AUDIT;
    for (size_t i = 0; i < GOLEM_FAILURE_COUNT; ++i) spec.reentry[i] = GOLEM_STAGE_NONE;
    golem_work_run *run = NULL; golem_lineage *g = NULL;
    CHECK(make_run_spec("custom", &spec, &run) == 0 && golem_lineage_create("custom", NULL, NULL, &g, NULL) == GOLEM_OK);
    golem_receipt r; CHECK(receipt(&r) == 0); golem_lineage_id previous;
    CHECK(stage(run, g, &r, NULL, 0, GOLEM_FAILURE_NONE, &previous) == 0);
    CHECK(stage(run, g, &r, &previous, 1, GOLEM_FAILURE_POLICY_DENIED, &previous) == 0);
    golem_lineage_stage record;
    CHECK(golem_lineage_stage_get(g, 1, &record) == GOLEM_OK && record.execution.stage == GOLEM_STAGE_QA);
    CHECK(golem_lineage_stage_get(g, 2, &record) == GOLEM_OK && record.execution.status == GOLEM_STAGE_BLOCKED);
    size_t size; CHECK(golem_lineage_encode(g, NULL, 0, &size, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    golem_lineage_free(g); golem_work_run_free(run); g = NULL; run = NULL;
    CHECK(make_run("r", &run) == 0 && golem_lineage_create("r", NULL, NULL, &g, NULL) == GOLEM_OK);
    CHECK(stage(run, g, &r, NULL, 0, GOLEM_FAILURE_NONE, &previous) == 0);
    golem_stage_snapshot s;
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    CHECK(golem_work_run_finish(run, s.sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    CHECK(golem_work_run_begin(run, false, false, &s) == GOLEM_OK);
    golem_lineage_id untouched = 999;
    CHECK(golem_lineage_begin(g, run, &r, &previous, 1, &untouched, NULL) == GOLEM_ERR_STALE_RESULT && untouched == 999);
    golem_lineage_free(g); golem_work_run_free(run); return 0;
}

static int nulls(void)
{
    golem_lineage *g = NULL;
    CHECK(golem_lineage_create(NULL, NULL, NULL, &g, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_lineage_create("", NULL, NULL, &g, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    char long_id[GOLEM_LINEAGE_MAX_RUN_ID + 2]; memset(long_id, 'x', sizeof(long_id)); long_id[sizeof(long_id) - 1] = '\0';
    CHECK(golem_lineage_create(long_id, NULL, NULL, &g, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_lineage_run_id_borrow(NULL) == NULL);
    golem_lineage_free(NULL);
    CHECK(single(&g, NULL) == 0);
    CHECK(golem_lineage_stats_get(g, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_lineage_node node; golem_lineage_stage s;
    CHECK(golem_lineage_node_get(g, 0, &node) == GOLEM_ERR_NOT_FOUND);
    CHECK(golem_lineage_stage_get(g, UINT64_MAX, &s) == GOLEM_ERR_NOT_FOUND);
    size_t required = 999;
    CHECK(golem_lineage_parents(g, 2, NULL, 1, &required) == GOLEM_ERR_INVALID_ARGUMENT && required == 999);
    CHECK(golem_lineage_parents(g, 0, NULL, 0, &required) == GOLEM_ERR_NOT_FOUND && required == 999);
    CHECK(golem_lineage_predecessors(g, 2, true, NULL, 0, &required) == GOLEM_ERR_NOT_FOUND && required == 999);
    CHECK(golem_lineage_encode(g, NULL, 1, &required, NULL) == GOLEM_ERR_INVALID_ARGUMENT && required == 999);
    golem_lineage *out = NULL;
    CHECK(golem_lineage_decode((golem_bytes){NULL, 1}, NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT && out == NULL);
    CHECK(golem_lineage_verify(g, NULL, &required, NULL) == GOLEM_ERR_INVALID_ARGUMENT && required == 999);
    CHECK(golem_lineage_store(g, NULL, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_lineage_load(NULL, NULL, NULL, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT && out == NULL);
    golem_lineage_free(g); return 0;
}

int main(int argc, char **argv)
{
    CHECK(argc >= 2);
    if (strcmp(argv[1], "lifecycle") == 0) return lifecycle();
    if (strcmp(argv[1], "reentry") == 0) return reentry();
    if (strcmp(argv[1], "invalid") == 0) return invalid();
    if (strcmp(argv[1], "codec") == 0) return codec();
    if (strcmp(argv[1], "ownership") == 0) return ownership();
    if (strcmp(argv[1], "capacity") == 0) return capacity();
    if (strcmp(argv[1], "storage") == 0) return storage();
    if (strcmp(argv[1], "bounded") == 0) return bounded();
    if (strcmp(argv[1], "identity") == 0) return identity();
    if (strcmp(argv[1], "nulls") == 0) return nulls();
    if (strcmp(argv[1], "fixture") == 0 && argc == 3) return fixture(argv[2]);
    return EXIT_FAILURE;
}
