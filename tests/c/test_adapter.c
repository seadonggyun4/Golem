#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/adapter_protocol.h"
#include "golem/journal.h"
#include "golem/optimization.h"
#include "test.h"
#include <dirent.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static golem_bytes bytes(const char *s) { return (golem_bytes){(const uint8_t *)s, strlen(s)}; }
static int cleanup(const char *path)
{
    struct stat info; CHECK(lstat(path, &info) == 0);
    if (!S_ISDIR(info.st_mode)) { CHECK(unlink(path) == 0); return 0; }
    DIR *dir = opendir(path); CHECK(dir != NULL); struct dirent *entry;
    while ((entry = readdir(dir)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
        char child[1024]; CHECK(snprintf(child, sizeof(child), "%s/%s", path, entry->d_name) < (int)sizeof(child));
        CHECK(cleanup(child) == 0);
    }
    CHECK(closedir(dir) == 0); CHECK(rmdir(path) == 0); return 0;
}
static int capsule(golem_autonomy mode, golem_work_capsule **out)
{
    golem_graph_spec gs; golem_stage_graph *g = NULL;
    CHECK(golem_stage_graph_default_spec(&gs) == GOLEM_OK);
    CHECK(golem_stage_graph_create(&gs, &g) == GOLEM_OK);
    const char *scope[] = {"local"}, *acceptance[] = {"verified"};
    golem_capsule_spec s = {0}; s.id = "adapter"; s.goal = "Exercise adapter boundary";
    s.scope = (golem_string_list){scope, 1}; s.acceptance = (golem_string_list){acceptance, 1}; s.graph = g;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) s.permissions[i] = mode;
    CHECK(golem_work_capsule_create(&s, out) == GOLEM_OK);
    golem_stage_graph_free(g); return 0;
}
typedef struct fixture {
    char root[128]; golem_work_run *run; golem_evidence_store *store;
    golem_adapter *adapter; golem_receipt context;
} fixture;
static int setup(fixture *f, golem_autonomy mode)
{
    *f = (fixture){0};
#ifdef __APPLE__
    strcpy(f->root, "/private/tmp/golem-adapter-XXXXXX");
#else
    strcpy(f->root, "/tmp/golem-adapter-XXXXXX");
#endif
    CHECK(mkdtemp(f->root) != NULL);
    CHECK(golem_evidence_open(f->root, true, NULL, &f->store, NULL) == GOLEM_OK);
    CHECK(golem_evidence_put(f->store, bytes("context"), &f->context, NULL) == GOLEM_OK);
    CHECK(golem_adapter_noop_create(NULL, &f->adapter) == GOLEM_OK);
    golem_work_capsule *c = NULL; CHECK(capsule(mode, &c) == 0);
    CHECK(golem_work_run_create("test-run", c, 3, &f->run) == GOLEM_OK);
    golem_work_capsule_free(c); return 0;
}
static int teardown(fixture *f)
{
    golem_adapter_free(f->adapter); golem_work_run_free(f->run);
    CHECK(golem_evidence_close(f->store) == GOLEM_OK); return cleanup(f->root);
}
static int begin(fixture *f, golem_adapter_request *r)
{
    golem_stage_snapshot stage;
    CHECK(golem_work_run_begin(f->run, false, false, &stage) == GOLEM_OK);
    CHECK(golem_adapter_request_init(f->run, "local.noop", "request-1", &f->context, NULL, r) == GOLEM_OK);
    return 0;
}
static int roundtrip(const golem_adapter_envelope *e)
{
    char encoded[GOLEM_ADAPTER_JSON_MAX], again[GOLEM_ADAPTER_JSON_MAX]; size_t n, m;
    CHECK(golem_adapter_envelope_encode(e, NULL, 0, &n, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    memset(encoded, 'x', sizeof(encoded));
    CHECK(golem_adapter_envelope_encode(e, encoded, n - 1, &m, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(encoded[0] == 'x' && m == n);
    CHECK(golem_adapter_envelope_encode(e, encoded, sizeof(encoded), &n, NULL) == GOLEM_OK);
    golem_adapter_envelope decoded;
    CHECK(golem_adapter_envelope_decode(bytes(encoded), &decoded, NULL) == GOLEM_OK);
    CHECK(golem_adapter_envelope_encode(&decoded, again, sizeof(again), &m, NULL) == GOLEM_OK);
    CHECK(n == m && strcmp(encoded, again) == 0);
    uint8_t packed[GOLEM_ADAPTER_MSGPACK_MAX]; size_t packed_size;
    CHECK(golem_adapter_msgpack_encode(&decoded, packed, sizeof(packed), &packed_size, NULL) == GOLEM_OK);
    CHECK(golem_adapter_msgpack_decode((golem_bytes){packed, packed_size}, &decoded, NULL) == GOLEM_OK);
    CHECK(golem_adapter_envelope_encode(&decoded, again, sizeof(again), &m, NULL) == GOLEM_OK);
    CHECK(n == m && strcmp(encoded, again) == 0); return 0;
}
static int lifecycle(void)
{
    fixture f; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL) == 0);
    golem_adapter_envelope e = {.type = GOLEM_ADAPTER_CAPABILITY};
    CHECK(golem_adapter_probe(f.adapter, &e.data.capability, NULL) == GOLEM_OK);
    CHECK(e.data.capability.simulation && e.data.capability.effect == GOLEM_EFFECT_LOCAL);
    CHECK(roundtrip(&e) == 0);
    golem_digest predecessor; bool has_predecessor = false;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) {
        golem_adapter_request r; CHECK(begin(&f, &r) == 0);
        CHECK(r.stage == (golem_stage)i && r.sequence == i + 1);
        if (has_predecessor) { r.has_predecessor = true; r.predecessor = predecessor; }
        e.type = GOLEM_ADAPTER_RUN_STAGE; e.data.request = r; CHECK(roundtrip(&e) == 0);
        golem_adapter_result result;
        CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &result, NULL) == GOLEM_OK);
        CHECK(result.simulation && result.outcome == GOLEM_STAGE_PASSED && result.usage.cost_known && result.usage.nano_cost == 0);
        golem_work_snapshot snapshot;
        CHECK(golem_work_run_snapshot_get(f.run, &snapshot) == GOLEM_OK && snapshot.status == GOLEM_WORK_RUNNING);
        golem_adapter_result repeated;
        CHECK(golem_adapter_noop_run_stage(&r, f.store, &repeated, NULL) == GOLEM_OK);
        CHECK(memcmp(&result.evidence.digest, &repeated.evidence.digest, sizeof(predecessor)) == 0);
        CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &repeated, NULL) == GOLEM_ERR_INVALID_STATE);
        e.type = GOLEM_ADAPTER_STAGE_RESULT; e.data.result = result; CHECK(roundtrip(&e) == 0);
        predecessor = result.evidence.digest; has_predecessor = true;
        /* Only this test host attests its own simulation acceptance. */
        CHECK(golem_work_run_finish(f.run, r.sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    }
    return teardown(&f);
}
static int codec_test(void)
{
    const char *golden = "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\",\"stages\":\"63\",\"effect\":\"1\",\"simulation\":\"1\"}";
    golem_adapter_envelope e;
    CHECK(golem_adapter_envelope_decode(bytes(golden), &e, NULL) == GOLEM_OK);
    char encoded[1024]; size_t n;
    CHECK(golem_adapter_envelope_encode(&e, encoded, sizeof(encoded), &n, NULL) == GOLEM_OK);
    CHECK(strcmp(encoded, golden) == 0);
    const char *bad[] = {
        "{}", "[]", "null", "{", "{\"type\":1}",
        "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\",\"stages\":\"63\",\"effect\":\"1\",\"simulation\":true}",
        "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\",\"stages\":\"63\",\"effect\":\"1\",\"simulation\":\"1\",\"version\":\"1\"}",
        "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\",\"stages\":\"63\",\"effect\":\"1\",\"simulation\":\"1\",\"vers\\u0069on\":\"1\"}",
        "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\\u0000hidden\",\"stages\":\"63\",\"effect\":\"1\",\"simulation\":\"1\"}",
        "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\",\"stages\":\"063\",\"effect\":\"1\",\"simulation\":\"1\"}",
        "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\",\"stages\":\"4294967296\",\"effect\":\"1\",\"simulation\":\"1\"}",
        "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\",\"stages\":\"63\",\"effect\":\"1\",\"simulation\":\"2\"}",
        "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\",\"stages\":\"63\",\"effect\":\"1\",\"simulation\":{},\"extra\":\"x\"}",
        "{\"type\":\"1\",\"version\":\"1\",\"adapter_id\":\"local.noop\",\"stages\":\"-1\",\"effect\":\"1\",\"simulation\":\"1\"}"
    };
    for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); ++i) {
        e.type = (golem_adapter_message)99;
        CHECK(golem_adapter_envelope_decode(bytes(bad[i]), &e, NULL) != GOLEM_OK && e.type == 99);
    }
    for (size_t i = 0; i < strlen(golden); ++i)
        CHECK(golem_adapter_envelope_decode((golem_bytes){(const uint8_t *)golden, i}, &e, NULL) != GOLEM_OK);
    strcpy(encoded, golden); strcat(encoded, " {}");
    CHECK(golem_adapter_envelope_decode(bytes(encoded), &e, NULL) != GOLEM_OK);
    strcpy(encoded, golden); strcat(encoded, " \r\n\t");
    CHECK(golem_adapter_envelope_decode(bytes(encoded), &e, NULL) == GOLEM_OK);
    CHECK(golem_adapter_envelope_decode((golem_bytes){(const uint8_t *)golden, strlen(golden) + 1}, &e, NULL) != GOLEM_OK);
    strcpy(encoded, golden); encoded[45] = (char)0xff;
    CHECK(golem_adapter_envelope_decode(bytes(encoded), &e, NULL) != GOLEM_OK);
    uint8_t large[GOLEM_ADAPTER_JSON_MAX + 1] = {0};
    CHECK(golem_adapter_envelope_decode((golem_bytes){large, sizeof(large)}, &e, NULL) != GOLEM_OK);
    fixture f; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL) == 0);
    e.type = GOLEM_ADAPTER_RUN_STAGE; CHECK(begin(&f, &e.data.request) == 0);
    e.data.request.sequence = UINT64_MAX; e.data.request.attempt = UINT32_MAX;
    e.data.request.context.size = UINT64_MAX; CHECK(roundtrip(&e) == 0);
    e.data.request.version = 2;
    CHECK(golem_adapter_envelope_encode(&e, encoded, sizeof(encoded), &n, NULL) == GOLEM_ERR_UNSUPPORTED_VERSION);
    return teardown(&f);
}
typedef struct fake { golem_effect effect; uint32_t stages; int mode, calls; } fake;
static golem_status fake_probe(void *context, golem_adapter_capability *out, golem_diagnostic *d)
{
    (void)d; fake *f = context;
    *out = (golem_adapter_capability){1, "local.noop", f->stages, f->effect, true}; return GOLEM_OK;
}
static golem_status fake_run(void *context, const golem_adapter_request *r, golem_evidence_store *store,
    golem_adapter_result *out, golem_diagnostic *d)
{
    fake *f = context; ++f->calls;
    if (f->mode == 1) return GOLEM_ERR_IO;
    golem_status s = golem_adapter_noop_run_stage(r, store, out, d);
    if (s != GOLEM_OK) return s;
    if (f->mode == 2) ++out->request.sequence;
    if (f->mode == 3) ++out->evidence.size;
    if (f->mode == 4) out->simulation = false;
    if (f->mode == 5) out->outcome = GOLEM_STAGE_RUNNING;
    if (f->mode == 6) memset(&out->evidence.digest, 0, sizeof(out->evidence.digest));
    return GOLEM_OK;
}
static int gates(void)
{
    fixture f; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL) == 0);
    golem_adapter_request r; CHECK(begin(&f, &r) == 0);
    fake state = {GOLEM_EFFECT_EXTERNAL, GOLEM_ADAPTER_ALL_STAGES, 0, 0};
    golem_adapter_ops ops = {fake_probe, fake_run}; golem_adapter *a = NULL;
    CHECK(golem_adapter_create(&ops, &state, NULL, &a) == GOLEM_OK);
    golem_adapter_result result = {0}; result.request.sequence = 999;
    CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_POLICY_DENIED);
    CHECK(state.calls == 0 && result.request.sequence == 999);
    state.effect = GOLEM_EFFECT_LOCAL; state.stages = 1u << GOLEM_STAGE_QA;
    CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_POLICY_DENIED);
    state.stages = 0;
    CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    state.stages = GOLEM_ADAPTER_ALL_STAGES;
    ++r.sequence;
    CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_STALE_RESULT); --r.sequence;
    strcpy(r.run_id, "other");
    CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_IDENTITY_MISMATCH);
    strcpy(r.run_id, "test-run"); ++r.context.size;
    CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_SIZE_MISMATCH); --r.context.size;
    r.has_predecessor = true;
    CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_NOT_FOUND); r.has_predecessor = false;
    CHECK(state.calls == 0);
    CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_OK && state.calls == 1);
    golem_adapter_free(a); CHECK(teardown(&f) == 0);
    CHECK(setup(&f, GOLEM_AUTONOMY_DENY) == 0);
    golem_stage_snapshot snap;
    CHECK(golem_work_run_begin(f.run, false, true, &snap) == GOLEM_ERR_POLICY_DENIED);
    CHECK(golem_adapter_request_init(f.run, "local.noop", "req", &f.context, NULL, &r) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &result, NULL) != GOLEM_OK);
    return teardown(&f);
}
static int failures(void)
{
    for (int mode = 1; mode <= 6; ++mode) {
        fixture f; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL) == 0);
        golem_adapter_request r; CHECK(begin(&f, &r) == 0);
        fake state = {GOLEM_EFFECT_LOCAL, GOLEM_ADAPTER_ALL_STAGES, mode, 0};
        golem_adapter_ops ops = {fake_probe, fake_run}; golem_adapter *a = NULL;
        CHECK(golem_adapter_create(&ops, &state, NULL, &a) == GOLEM_OK);
        golem_adapter_result result = {0}; result.request.sequence = 999;
        CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) != GOLEM_OK);
        CHECK(state.calls == 1 && result.request.sequence == 999);
        state.mode = 0;
        CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_INVALID_STATE);
        CHECK(state.calls == 1);
        CHECK(golem_work_run_finish(f.run, 1, GOLEM_STAGE_FAILED, GOLEM_FAILURE_TIMEOUT, false) == GOLEM_OK);
        CHECK(golem_work_run_reenter(f.run) == GOLEM_OK);
        CHECK(begin(&f, &r) == 0 && r.sequence == 2 && r.attempt == 2);
        CHECK(golem_adapter_dispatch(a, f.run, &r, f.store, &result, NULL) == GOLEM_OK && state.calls == 2);
        golem_adapter_free(a); CHECK(teardown(&f) == 0);
    }
    return 0;
}
static int replay(void)
{
    fixture f; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL) == 0);
    golem_work_capsule *c; CHECK(capsule(GOLEM_AUTONOMY_AUTO_LOCAL, &c) == 0);
    uint8_t payload[4096], journal[8192]; size_t length, first, second;
    CHECK(golem_journal_created_encode("test-run", c, 3, payload, sizeof(payload), &length, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){payload, length}, journal, sizeof(journal), &first, NULL) == GOLEM_OK);
    golem_work_capsule_free(c);
    golem_journal_event event = {0}; event.type = GOLEM_JOURNAL_STARTED;
    event.stage = GOLEM_STAGE_PLANNING; event.attempt = 1; event.attempt_sequence = 1; event.outcome = GOLEM_STAGE_RUNNING;
    CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &length, NULL) == GOLEM_OK);
    CHECK(golem_journal_record_encode(event.type, 2, (golem_bytes){payload, length}, journal + first, sizeof(journal) - first, &second, NULL) == GOLEM_OK);
    golem_work_run *restored = NULL;
    CHECK(golem_journal_replay((golem_bytes){journal, first + second}, NULL, &restored, NULL) == GOLEM_OK);
    golem_work_run_free(f.run); f.run = restored;
    golem_adapter_request r; golem_adapter_result result;
    CHECK(golem_adapter_request_init(f.run, "local.noop", "req", &f.context, NULL, &r) == GOLEM_OK);
    CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_work_run_finish(f.run, 1, GOLEM_STAGE_FAILED, GOLEM_FAILURE_TIMEOUT, false) == GOLEM_OK);
    CHECK(golem_work_run_reenter(f.run) == GOLEM_OK); CHECK(begin(&f, &r) == 0);
    CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &result, NULL) == GOLEM_OK);
    return teardown(&f);
}
static int optimized(void)
{
    fixture f; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL) == 0);
    golem_cost_options costs = {0}; costs.version = 1; strcpy(costs.currency, "USD");
    costs.entry_capacity = 8; costs.report_capacity = 8;
    CHECK(golem_work_run_cost_enable(f.run, &costs) == GOLEM_OK);
    golem_optimization_policy policy;
    CHECK(golem_optimization_policy_init(&policy) == GOLEM_OK);
    CHECK(golem_work_run_optimization_enable(f.run, &policy) == GOLEM_OK);
    golem_optimization_context context = {0};
    context.run_id = "test-run"; context.stage = GOLEM_STAGE_PLANNING; context.sequence = 1; context.attempt = 1;
    strcpy(context.currency, "USD"); context.context_digest = f.context.digest;
    context.requirements_digest = f.context.digest; context.baseline_available = true;
    strcpy(context.baseline.id, "local.noop"); context.baseline.effect = GOLEM_EFFECT_LOCAL;
    context.baseline.verified = true; context.baseline.requirements_digest = context.requirements_digest;
    context.baseline.estimate.usage_known = true; context.baseline.estimate.cost_known = true;
    context.overhead.usage_known = true; context.overhead.cost_known = true; context.advisor_effect = GOLEM_EFFECT_LOCAL;
    golem_optimization_approval approval = {0}; golem_stage_snapshot stage;
    CHECK(golem_work_run_begin_optimized(f.run, &context, NULL, &approval, &stage, NULL, NULL) == GOLEM_OK);
    golem_adapter_request r; golem_adapter_result result;
    CHECK(golem_adapter_request_init(f.run, "other-route", "req", &f.context, NULL, &r) == GOLEM_OK);
    CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_IDENTITY_MISMATCH);
    strcpy(r.adapter_id, "local.noop"); r.context.digest.bytes[0] ^= 1;
    CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_IDENTITY_MISMATCH);
    r.context = f.context; r.has_predecessor = true; r.predecessor = f.context.digest;
    CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_IDENTITY_MISMATCH);
    r.has_predecessor = false; memset(&r.predecessor, 0, sizeof(r.predecessor));
    CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &result, NULL) == GOLEM_OK);
    return teardown(&f);
}
static void *oom(void *context, size_t size) { (void)context; (void)size; return NULL; }
static void release(void *context, void *p) { (void)context; free(p); }
static void *tracked_alloc(void *context, size_t size)
{
    size_t *live = context; void *p = malloc(size); if (p != NULL) ++*live; return p;
}
static void tracked_free(void *context, void *p) { size_t *live = context; --*live; free(p); }
static int invalid(void)
{
    golem_adapter *a = NULL; golem_allocator allocator = {NULL, oom, release};
    CHECK(golem_adapter_noop_create(&allocator, &a) == GOLEM_ERR_OUT_OF_MEMORY && a == NULL);
    CHECK(golem_adapter_create(NULL, NULL, NULL, &a) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_adapter_noop_create(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_adapter_probe(NULL, NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_adapter_free(NULL);
    size_t live = 0; allocator = (golem_allocator){&live, tracked_alloc, tracked_free};
    fake state = {GOLEM_EFFECT_LOCAL, GOLEM_ADAPTER_ALL_STAGES, 0, 0};
    golem_adapter_ops ops = {fake_probe, fake_run};
    CHECK(golem_adapter_create(&ops, &state, &allocator, &a) == GOLEM_OK && live == 1);
    ops.probe = NULL; allocator.deallocate = NULL;
    golem_adapter_capability cap;
    CHECK(golem_adapter_probe(a, &cap, NULL) == GOLEM_OK);
    golem_adapter_free(a); CHECK(live == 0 && state.calls == 0);
    fixture f; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL) == 0);
    golem_adapter_request r; CHECK(begin(&f, &r) == 0);
    golem_adapter_result result;
    CHECK(golem_adapter_noop_run_stage(&r, f.store, &result, NULL) == GOLEM_OK);
    result.failure = GOLEM_FAILURE_TIMEOUT;
    CHECK(golem_adapter_result_validate(&r, &result) == GOLEM_ERR_INVALID_ARGUMENT);
    result.outcome = GOLEM_STAGE_FAILED;
    CHECK(golem_adapter_result_validate(&r, &result) == GOLEM_OK);
    result.failure = GOLEM_FAILURE_POLICY_DENIED;
    CHECK(golem_adapter_result_validate(&r, &result) == GOLEM_ERR_INVALID_ARGUMENT);
    result.outcome = GOLEM_STAGE_BLOCKED;
    CHECK(golem_adapter_result_validate(&r, &result) == GOLEM_OK);
    result.usage.usage_known = false; result.usage.usage.input_tokens = 1;
    CHECK(golem_adapter_result_validate(&r, &result) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_cancel(f.run) == GOLEM_OK);
    CHECK(golem_adapter_dispatch(f.adapter, f.run, &r, f.store, &result, NULL) == GOLEM_ERR_INVALID_STATE);
    memset(r.request_id, 'x', sizeof(r.request_id));
    CHECK(golem_adapter_noop_run_stage(&r, f.store, &result, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return teardown(&f);
}
static int mutations(void)
{
    fixture f; CHECK(setup(&f, GOLEM_AUTONOMY_AUTO_LOCAL) == 0);
    golem_adapter_request r; CHECK(begin(&f, &r) == 0);
    golem_adapter_envelope seeds[3] = {{0}};
    seeds[0].type = GOLEM_ADAPTER_CAPABILITY;
    CHECK(golem_adapter_probe(f.adapter, &seeds[0].data.capability, NULL) == GOLEM_OK);
    seeds[1].type = GOLEM_ADAPTER_RUN_STAGE; seeds[1].data.request = r;
    seeds[2].type = GOLEM_ADAPTER_STAGE_RESULT;
    CHECK(golem_adapter_noop_run_stage(&r, f.store, &seeds[2].data.result, NULL) == GOLEM_OK);
    uint32_t random = 0x6a09e667u;
    for (size_t seed = 0; seed < 3; ++seed) {
        char original[2048], input[2048]; size_t length;
        CHECK(golem_adapter_envelope_encode(&seeds[seed], original, sizeof(original), &length, NULL) == GOLEM_OK);
        for (size_t i = 0; i < 5000; ++i) {
            memcpy(input, original, length);
            random = random * 1664525u + 1013904223u;
            size_t n = i % 4 == 0 ? random % length : length - 1;
            for (size_t j = 0; j <= i % 4 && n != 0; ++j) {
                random = random * 1664525u + 1013904223u;
                input[random % n] = (char)(random >> 24);
            }
            golem_adapter_envelope decoded;
            if (golem_adapter_envelope_decode((golem_bytes){(const uint8_t *)input, n}, &decoded, NULL) == GOLEM_OK)
                CHECK(roundtrip(&decoded) == 0);
        }
    }
    return teardown(&f);
}
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    if (strcmp(argv[1], "lifecycle") == 0) return lifecycle();
    if (strcmp(argv[1], "codec") == 0) return codec_test();
    if (strcmp(argv[1], "gates") == 0) return gates();
    if (strcmp(argv[1], "failures") == 0) return failures();
    if (strcmp(argv[1], "replay") == 0) return replay();
    if (strcmp(argv[1], "invalid") == 0) return invalid();
    if (strcmp(argv[1], "optimized") == 0) return optimized();
    if (strcmp(argv[1], "mutations") == 0) return mutations();
    return EXIT_FAILURE;
}
