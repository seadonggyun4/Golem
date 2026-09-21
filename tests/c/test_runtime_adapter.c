#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/runtime.h"
#include "golem/adapter_protocol.h"
#include "golem/replay.h"
#include "test.h"
#include <dirent.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

typedef struct host {
    golem_journal *journal;
    golem_adapter *adapter;
    golem_evidence_store *store;
    golem_receipt context, evidence[32];
    size_t count;
    golem_failure failure;
    golem_lease *lease;
    uint64_t now, worker_calls;
    unsigned expiry_mode;
} host;
static golem_status lease_audit(void *context, const golem_lease_event *event)
{
    (void)context; (void)event;
    return GOLEM_OK; /* Test sink; production hosts durably serialize events. */
}
static golem_status lease_clock(void *context, uint64_t *out)
{
    *out = ((host *)context)->now; return GOLEM_OK;
}
static golem_status probe(void *context, golem_adapter_capability *out, golem_diagnostic *d)
{
    host *h = context; (void)d;
    if (h->expiry_mode == 1) h->now = 10;
    *out = (golem_adapter_capability){1, "local.test", GOLEM_ADAPTER_ALL_STAGES, GOLEM_EFFECT_LOCAL, true};
    return GOLEM_OK;
}
static golem_status worker(void *context, const golem_adapter_request *request,
    golem_evidence_store *store, golem_adapter_result *out, golem_diagnostic *d)
{
    host *h = context; char evidence[GOLEM_ADAPTER_JSON_MAX]; size_t size;
    ++h->worker_calls;
    if (h->expiry_mode == 2) h->now = 10;
    golem_adapter_envelope input = {.type = GOLEM_ADAPTER_RUN_STAGE, .data.request = *request};
    golem_status s = golem_adapter_envelope_encode(&input, evidence, sizeof(evidence), &size, d);
    if (s != GOLEM_OK) return s;
    bool fail = request->stage == GOLEM_STAGE_QA && request->attempt == 1;
    golem_adapter_result result = {.request = *request, .outcome = fail ? GOLEM_STAGE_FAILED : GOLEM_STAGE_PASSED,
        .failure = fail ? h->failure : GOLEM_FAILURE_NONE, .simulation = true,
        .usage = {.usage_known = true, .cost_known = true}};
    s = golem_evidence_put(store, (golem_bytes){(const uint8_t *)evidence, size - 1}, &result.evidence, d);
    if (s == GOLEM_OK) *out = result; return s;
}
static golem_status persist(void *context, golem_journal_type type, golem_bytes payload)
{
    host *h = context; uint64_t sequence;
    return golem_journal_append(h->journal, type, payload, &sequence, NULL);
}
static golem_status execute(void *context, golem_work_run *run,
    const golem_stage_snapshot *stage, uint64_t deadline, golem_runtime_result *out)
{
    host *h = context; (void)deadline;
    char id[32]; (void)snprintf(id, sizeof(id), "request-%zu", h->count + 1);
    golem_adapter_request request;
    golem_status s = golem_adapter_request_init(run, "local.test", id, &h->context,
        h->count == 0 ? NULL : &h->evidence[h->count - 1].digest, &request);
    golem_adapter_result result;
    if (s == GOLEM_OK) s = golem_adapter_dispatch(h->adapter, run, &request, h->store, &result, NULL);
    if (s != GOLEM_OK) return s;
    if (h->count >= 32) return GOLEM_ERR_OVERFLOW;
    h->evidence[h->count++] = result.evidence;
    /* Persist the complete result envelope too; execution evidence alone does
     * not record the reviewer's classified outcome. This is a test provider. */
    golem_adapter_envelope envelope = {.type = GOLEM_ADAPTER_STAGE_RESULT, .data.result = result};
    char bytes[GOLEM_ADAPTER_JSON_MAX]; size_t size; golem_receipt receipt;
    s = golem_adapter_envelope_encode(&envelope, bytes, sizeof(bytes), &size, NULL);
    if (s == GOLEM_OK) s = golem_evidence_put(h->store, (golem_bytes){(const uint8_t *)bytes, size - 1}, &receipt, NULL);
    if (s == GOLEM_OK) *out = (golem_runtime_result){stage->sequence, result.outcome, result.failure, result.outcome == GOLEM_STAGE_PASSED};
    return s;
}
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
int main(void)
{
    golem_graph_spec gs; CHECK(golem_stage_graph_default_spec(&gs) == GOLEM_OK);
    golem_stage_graph *graph = NULL; CHECK(golem_stage_graph_create(&gs, &graph) == GOLEM_OK);
    const char *texts[] = {"simulation"};
    golem_capsule_spec spec = {.id = "runtime-adapter", .goal = "Test provider and recovery", .scope = {texts, 1}, .acceptance = {texts, 1}, .graph = graph};
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) spec.permissions[i] = GOLEM_AUTONOMY_AUTO_LOCAL;
    golem_work_capsule *capsule = NULL; CHECK(golem_work_capsule_create(&spec, &capsule) == GOLEM_OK);
    golem_stage_graph_free(graph);
    for (int failure = GOLEM_FAILURE_PLANNING_GAP; failure <= GOLEM_FAILURE_QA_FLAKE + 2; ++failure) {
#ifdef __APPLE__
        char root[] = "/private/tmp/golem-runtime-XXXXXX";
#else
        char root[] = "/tmp/golem-runtime-XXXXXX";
#endif
        CHECK(mkdtemp(root) != NULL); char path[256]; (void)snprintf(path, sizeof(path), "%s/journal.bin", root);
        host h = {.failure = failure <= GOLEM_FAILURE_QA_FLAKE ? (golem_failure)failure : GOLEM_FAILURE_QA_FLAKE,
            .expiry_mode = failure <= GOLEM_FAILURE_QA_FLAKE ? 0u : (unsigned)(failure - GOLEM_FAILURE_QA_FLAKE)};
        CHECK(golem_journal_open(path, NULL, &h.journal, NULL) == GOLEM_OK);
        CHECK(golem_evidence_open(root, true, NULL, &h.store, NULL) == GOLEM_OK);
        const uint8_t input[] = "runtime integration context";
        CHECK(golem_evidence_put(h.store, (golem_bytes){input, sizeof(input) - 1}, &h.context, NULL) == GOLEM_OK);
        golem_adapter_ops adapter_ops = {probe, worker};
        CHECK(golem_adapter_create(&adapter_ops, &h, NULL, &h.adapter) == GOLEM_OK);
        golem_runtime_options options = {1, 3, 32, 60000000000u};
        golem_runtime_ops ops = {persist, execute, h.expiry_mode == 0 ? NULL : lease_clock}; golem_runtime *runtime = NULL;
        CHECK(golem_runtime_create("integration", capsule, &options, &ops, &h, NULL, &runtime) == GOLEM_OK);
        if (h.expiry_mode != 0) {
            golem_lease_ops lease_ops = {lease_audit}; golem_lease_snapshot owned;
            CHECK(golem_lease_create("integration", &lease_ops, &h, NULL, &h.lease) == GOLEM_OK);
            CHECK(golem_lease_acquire(h.lease, "worker", 0, 10, &owned) == GOLEM_OK);
            CHECK(golem_runtime_lease_bind(runtime, h.lease, &owned.token) == GOLEM_OK);
        }
        CHECK(golem_runtime_drive(runtime) == (h.expiry_mode == 0 ? GOLEM_OK : GOLEM_ERR_STALE_LEASE));
        golem_runtime_report report; CHECK(golem_runtime_report_get(runtime, &report) == GOLEM_OK);
        if (h.expiry_mode == 0) {
            CHECK(report.work.status == GOLEM_WORK_SUCCEEDED && report.reentries == 1 && report.dispatched == h.count);
        } else {
            CHECK(report.work.status == GOLEM_WORK_RUNNING && report.stopped && h.count == 0);
            CHECK(h.worker_calls == (h.expiry_mode == 1 ? 0u : 1u));
            CHECK(golem_runtime_drive(runtime) == GOLEM_ERR_STALE_LEASE);
        }
        CHECK(golem_journal_close(h.journal, NULL) == GOLEM_OK);
        CHECK(golem_journal_open(path, NULL, &h.journal, NULL) == GOLEM_OK);
        golem_work_run *replayed = NULL; golem_replay_report recovered;
        golem_replay_options replay_options = {.expected_run_id = "integration", .require_terminal = h.expiry_mode == 0};
        CHECK(golem_journal_recover(h.journal, &replay_options, &replayed, &recovered, NULL) == GOLEM_OK);
        CHECK(recovered.work.status == (h.expiry_mode == 0 ? GOLEM_WORK_SUCCEEDED : GOLEM_WORK_RUNNING));
        CHECK(recovered.verified_records == 2 + 2 * h.count);
        for (size_t i = 0; i < h.count; ++i) {
            uint64_t size; CHECK(golem_evidence_verify(h.store, &h.evidence[i].digest, &size, NULL) == GOLEM_OK);
            CHECK(size == h.evidence[i].size);
        }
        golem_work_run_free(replayed); golem_runtime_free(runtime); golem_adapter_free(h.adapter);
        golem_lease_free(h.lease);
        CHECK(golem_journal_close(h.journal, NULL) == GOLEM_OK);
        CHECK(golem_evidence_close(h.store) == GOLEM_OK); CHECK(cleanup(root) == 0);
    }
    golem_work_capsule_free(capsule); return 0;
}
