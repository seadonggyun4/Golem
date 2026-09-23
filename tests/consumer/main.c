#include <string.h>
#include "golem/core.h"
#include "golem/document.h"
#include "golem/discovery.h"
#include "golem/workflow.h"
#include "golem/agent_session.h"
#include "golem/execution.h"
#include "golem/reentry.h"
#include "golem/completion.h"
#include "golem/arena.h"
#include "golem/journal.h"
#include "golem/replay.h"
#include "golem/evidence.h"
#include "golem/lineage.h"
#include "golem/policy.h"
#include "golem/cost.h"
#include "golem/optimization.h"
#include "golem/types.h"
#include "golem/version.h"
#include "golem/adapter_protocol.h"
#include "golem/gateway.h"
#include "golem/runtime.h"
#include "golem/lease.h"
#include "golem/daemon.h"
#include "golem/supervisor.h"

static golem_status lease_sink(void *context, const golem_lease_event *event)
{
    (void)context; (void)event; return GOLEM_OK;
}
static golem_status lease_now(void *context, uint64_t *out)
{
    (void)context; *out = 0; return GOLEM_OK;
}

static golem_status runtime_sink(void *context, golem_journal_type type, golem_bytes payload)
{
    (void)type; (void)payload;
    ++*(unsigned *)context;
    return GOLEM_OK; /* Consumer smoke uses a test sink, not production storage. */
}
static golem_status runtime_execute(void *context, golem_work_run *run,
    const golem_stage_snapshot *stage, uint64_t deadline, golem_runtime_result *out)
{
    (void)context; (void)run; (void)deadline;
    *out = (golem_runtime_result){stage->sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true};
    return GOLEM_OK;
}
static int verify_runtime_api(const golem_work_capsule *capsule)
{
    unsigned records = 0;
    golem_runtime_options options = {GOLEM_RUNTIME_VERSION, 2, 16, 0};
    golem_runtime_ops ops = {runtime_sink, runtime_execute, lease_now};
    golem_runtime *runtime = NULL;
    if (golem_runtime_create("installed-runtime", capsule, &options, &ops, &records, NULL, &runtime) != GOLEM_OK) return 1;
    golem_lease *lease = NULL; golem_lease_ops lease_ops = {lease_sink}; golem_lease_snapshot owned;
    if (golem_lease_create("installed-runtime", &lease_ops, NULL, NULL, &lease) != GOLEM_OK ||
        golem_lease_acquire(lease, "consumer", 0, 10, &owned) != GOLEM_OK ||
        golem_runtime_lease_bind(runtime, lease, &owned.token) != GOLEM_OK ||
        golem_runtime_heartbeat(runtime, 20, &owned) != GOLEM_OK) {
        golem_runtime_free(runtime); golem_lease_free(lease); return 1;
    }
    golem_status status = golem_runtime_drive(runtime);
    golem_runtime_report report;
    int failed = status != GOLEM_OK || golem_runtime_report_get(runtime, &report) != GOLEM_OK ||
        report.work.status != GOLEM_WORK_SUCCEEDED || report.dispatched != 6 || records != 13;
    if (golem_lease_release(lease, &owned.token, 0) != GOLEM_OK) failed = 1;
    golem_runtime_free(runtime); golem_lease_free(lease); return failed;
}

static int verify_memory_api(void)
{
    golem_policy_artifact artifact = {.revision = 1}, decoded_artifact;
    uint8_t policy_bytes[GOLEM_POLICY_ARTIFACT_SIZE]; size_t policy_size;
    if (golem_policy_spec_init(&artifact.policy) != GOLEM_OK ||
        golem_policy_artifact_encode(&artifact, policy_bytes, sizeof(policy_bytes), &policy_size) != GOLEM_OK ||
        golem_policy_artifact_decode((golem_bytes){policy_bytes, policy_size}, &decoded_artifact) != GOLEM_OK ||
        decoded_artifact.revision != 1 || decoded_artifact.policy.permissions[0] != GOLEM_AUTONOMY_DENY) return 1;
    bool worked = true;
    if (golem_daemon_tick(NULL, &worked) != GOLEM_ERR_INVALID_ARGUMENT || !worked ||
        golem_daemon_close(NULL) != GOLEM_OK ||
        golem_daemon_recover(NULL, NULL) != GOLEM_ERR_INVALID_ARGUMENT ||
        golem_runtime_recover(NULL, NULL, NULL, NULL, NULL, NULL) != GOLEM_ERR_INVALID_ARGUMENT ||
        golem_supervisor_run(NULL, NULL, (golem_bytes){NULL, 0}, 1, NULL, NULL, NULL) != GOLEM_ERR_INVALID_ARGUMENT) return 1;
    if (golem_runtime_step(NULL) != GOLEM_ERR_INVALID_ARGUMENT ||
        golem_runtime_run_borrow(NULL) != NULL) return 1;
    golem_adapter *adapter = NULL;
    golem_adapter_envelope envelope = {.type = GOLEM_ADAPTER_CAPABILITY}, decoded;
    char json[1024]; size_t json_size;
    if (golem_adapter_noop_create(NULL, &adapter) != GOLEM_OK) return 1;
    int adapter_result = golem_adapter_probe(adapter, &envelope.data.capability, NULL) != GOLEM_OK ||
        golem_adapter_envelope_encode(&envelope, json, sizeof(json), &json_size, NULL) != GOLEM_OK ||
        golem_adapter_envelope_decode((golem_bytes){(const uint8_t *)json, json_size - 1}, &decoded, NULL) != GOLEM_OK ||
        !decoded.data.capability.simulation;
    golem_adapter_free(adapter);
    if (adapter_result) return 1;
    uint8_t packed[GOLEM_ADAPTER_MSGPACK_MAX]; size_t packed_size;
    golem_gateway_envelope gateway;
    if (golem_adapter_msgpack_encode(&decoded, packed, sizeof(packed), &packed_size, NULL) != GOLEM_OK ||
        golem_gateway_envelope_prepare(GOLEM_ENCODING_MSGPACK, (golem_bytes){packed, packed_size}, &gateway, NULL) != GOLEM_OK ||
        golem_gateway_envelope_decode(&gateway, GOLEM_GATEWAY_REQUIRE_SIGNATURE, &decoded, NULL) != GOLEM_ERR_POLICY_DENIED ||
        golem_gateway_envelope_decode(&gateway, GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL, &decoded, NULL) != GOLEM_OK ||
        !decoded.data.capability.simulation) return 1;
    golem_policy_spec policy_spec;
    golem_policy *policy = NULL;
    golem_policy_request policy_request = {GOLEM_STAGE_PLANNING, GOLEM_EFFECT_LOCAL, GOLEM_AUTHORIZATION_GRANTED};
    golem_policy_decision policy_decision;
    if (golem_policy_spec_init(&policy_spec) != GOLEM_OK ||
        golem_policy_create(&policy_spec, NULL, &policy, NULL) != GOLEM_OK) return 1;
    int policy_result = golem_policy_evaluate(policy, &policy_request, &policy_decision) != GOLEM_OK ||
        policy_decision.verdict != GOLEM_POLICY_DENY;
    golem_policy_free(policy);
    if (policy_result) return 1;
    golem_lineage *lineage = NULL;
    golem_lineage_stats lineage_stats;
    if (golem_lineage_create("consumer", NULL, NULL, &lineage, NULL) != GOLEM_OK) return 1;
    int lineage_result = golem_lineage_stats_get(lineage, &lineage_stats) != GOLEM_OK ||
        lineage_stats.stages != 0 || strcmp(golem_lineage_run_id_borrow(lineage), "consumer") != 0;
    golem_lineage_free(lineage);
    if (lineage_result) return 1;
    golem_digest digest;
    char hex[GOLEM_DIGEST_HEX_CAPACITY];
    size_t hex_size;
    if (golem_digest_bytes((golem_bytes){(const uint8_t *)"abc", 3}, &digest) != GOLEM_OK ||
        golem_digest_format(&digest, hex, sizeof(hex), &hex_size) != GOLEM_OK ||
        strcmp(hex, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") != 0) {
        return 1;
    }
    uint32_t crc;
    if (golem_journal_crc32((golem_bytes){(const uint8_t *)"123456789", 9}, &crc) != GOLEM_OK ||
        crc != 0xcbf43926u) {
        return 1;
    }
    unsigned char storage[64];
    golem_arena arena;
    void *region;
    golem_diagnostic diagnostic;
    golem_string_view view;
    char *copy = NULL;
    if (golem_arena_init(&arena, storage, sizeof(storage)) != GOLEM_OK ||
        golem_arena_alloc(&arena, 8, _Alignof(max_align_t), &region) != GOLEM_OK ||
        golem_diagnostic_set(&diagnostic, GOLEM_ERR_PARSE, 7, "consumer") != GOLEM_OK ||
        golem_string_view_from_cstr("sample", &view) != GOLEM_OK ||
        golem_string_clone(view, NULL, &copy) != GOLEM_OK) {
        return 1;
    }
    size_t required;
    int result = golem_string_view_write(view, region, 8, &required) != GOLEM_OK ||
        required != 7 || strcmp(region, copy) != 0 || diagnostic.offset != 7;
    (void)golem_allocator_free(NULL, copy);
    return result;
}

static int verify_replay_api(const golem_work_capsule *capsule)
{
    uint8_t payload[1024], frame[2048];
    size_t payload_size, size;
    if (golem_journal_created_encode("consumer-run", capsule, 2, payload,
            sizeof(payload), &payload_size, NULL) != GOLEM_OK ||
        golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1,
            (golem_bytes){payload, payload_size}, frame, sizeof(frame), &size, NULL) != GOLEM_OK) {
        return 1;
    }
    golem_journal_inspection inspection = {0};
    if (golem_journal_inspect((golem_bytes){frame, size}, &inspection) != GOLEM_OK ||
        inspection.stream_status != GOLEM_OK || inspection.records != 1 ||
        inspection.valid_bytes != size) return 1;
    if (golem_journal_inspect((golem_bytes){NULL, 1}, &inspection) != GOLEM_ERR_INVALID_ARGUMENT ||
        inspection.valid_bytes != size || inspection.records != 1) return 1;
    golem_replay_options options = {"consumer-run", true, 1, size, false};
    golem_replay *engine = NULL;
    golem_work_run *recovered = NULL;
    golem_replay_report report;
    int result = 1;
    if (golem_replay_create(&options, NULL, &engine, NULL) == GOLEM_OK &&
        golem_replay_feed(engine, (golem_bytes){frame, 17}, NULL) == GOLEM_OK &&
        golem_replay_feed(engine, (golem_bytes){frame + 17, size - 17}, NULL) == GOLEM_OK &&
        golem_replay_finish(engine, &recovered, &report, NULL) == GOLEM_OK &&
        report.work.status == GOLEM_WORK_READY && report.action == GOLEM_RECOVERY_CHECK_POLICY) {
        result = 0;
    }
    golem_replay_free(engine);
    golem_work_run_free(recovered);
    return result;
}

static golem_status optimized_start(golem_work_run *run,
    const golem_stage_permission_request *request, const golem_cost_amount *estimate, golem_stage_snapshot *out)
{
    golem_optimization_context c = {0};
    c.run_id = request->run_id; c.stage = request->stage; c.sequence = request->sequence; c.attempt = request->attempt;
    strcpy(c.currency, "USD"); c.context_digest.bytes[0] = 1; c.requirements_digest.bytes[0] = 2;
    strcpy(c.baseline.id, "baseline"); c.baseline.estimate = *estimate; c.baseline.effect = GOLEM_EFFECT_LOCAL;
    c.baseline.requirements_digest = c.requirements_digest; c.baseline.verified = true; c.baseline_available = true;
    c.candidate = c.baseline; strcpy(c.candidate.id, "cheaper-local"); c.candidate.estimate.nano_cost = 80;
    c.overhead.cost_known = true; c.overhead.usage_known = true; c.advisor_effect = GOLEM_EFFECT_LOCAL;
    golem_optimization_proposal p = {0}; p.version = GOLEM_OPTIMIZATION_VERSION;
    p.run_id = c.run_id; p.stage = c.stage; p.sequence = c.sequence; p.attempt = c.attempt;
    p.context_digest = c.context_digest; p.requirements_digest = c.requirements_digest;
    p.kind = GOLEM_OPTIMIZATION_ROUTE; strcpy(p.route_id, c.candidate.id);
    golem_optimization_approval approval = {0}; golem_optimization_decision decision;
    golem_status status = golem_work_run_begin_optimized(run, &c, &p, &approval, out, &decision, NULL);
    if (status == GOLEM_OK && (decision.verdict != GOLEM_OPTIMIZATION_APPLY || decision.expected.nano_cost != 80))
        return GOLEM_ERR_INVALID_STATE;
    return status;
}

int main(void)
{
    static const char reentry_status[]="{\"schema_version\":1,\"operation\":\"status\"}";
    static const char completion_resume[]="{\"schema_version\":1,\"operation\":\"resume\",\"selection_id\":\"selection\"}";
    if(golem_completion_validate((golem_bytes){(const uint8_t *)completion_resume,sizeof(completion_resume)-1},NULL)!=GOLEM_OK) return 1;
    if(golem_reentry_validate((golem_bytes){(const uint8_t *)reentry_status,sizeof(reentry_status)-1},NULL)!=GOLEM_OK) return 1;
    golem_digest digest;
    if(golem_execution_contract_validate((golem_bytes){NULL,0},&digest,NULL)!=GOLEM_ERR_PARSE) return 1;
    const char *request="{\"schema_version\":1,\"operation\":\"status\",\"work_id\":\"work\"}";
    if(golem_agent_request_validate((golem_bytes){(const uint8_t *)request,strlen(request)},NULL)!=GOLEM_OK) return 1;
    golem_dependency_node node = {"work", "plan", 1, {{1}}, NULL, 0};
    golem_document_freshness state;
    if (golem_document_graph_evaluate(&node, 1, NULL, &state, 1, NULL) != GOLEM_OK ||
        state != GOLEM_DOCUMENT_CURRENT) return 1;
    if (golem_document_validate((golem_bytes){NULL, 0},
        (golem_bytes){NULL, 0}, NULL) != GOLEM_ERR_PARSE) return 1;
    if (verify_memory_api() != 0) {
        return 1;
    }
    golem_bytes bytes;
    if (golem_bytes_init(&bytes, NULL, 0) != GOLEM_OK) {
        return 1;
    }
    if (strcmp(golem_version_string(), GOLEM_VERSION_STRING) != 0) {
        return 1;
    }
    golem_graph_spec graph_spec;
    golem_stage_graph *graph = NULL;
    golem_work_capsule *capsule = NULL;
    golem_work_run *run = NULL;
    int result = 1;
    const char *scope[] = {"consumer"};
    const char *acceptance[] = {"six stages completed"};
    golem_capsule_spec spec = {0};
    spec.id = "consumer-capsule";
    spec.goal = "Verify installed core API";
    spec.scope = (golem_string_list){scope, 1};
    spec.acceptance = (golem_string_list){acceptance, 1};
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) {
        spec.permissions[i] = GOLEM_AUTONOMY_AUTO_LOCAL;
    }
    if (golem_stage_graph_default_spec(&graph_spec) != GOLEM_OK ||
        golem_stage_graph_create(&graph_spec, &graph) != GOLEM_OK) {
        goto cleanup;
    }
    spec.graph = graph;
    if (golem_work_capsule_create(&spec, &capsule) != GOLEM_OK ||
        golem_work_run_create("consumer-run", capsule, 2, &run) != GOLEM_OK) {
        goto cleanup;
    }
    if (verify_replay_api(capsule) != 0 || verify_runtime_api(capsule) != 0) {
        goto cleanup;
    }
    golem_cost_options cost_options = {0};
    cost_options.version = GOLEM_COST_VERSION;
    memcpy(cost_options.currency, "USD", 4);
    cost_options.entry_capacity = 6; cost_options.report_capacity = 6;
    cost_options.run_budget.enabled = GOLEM_BUDGET_COST;
    cost_options.run_budget.nano_cost_limit = 600;
    if (golem_work_run_cost_enable(run, &cost_options) != GOLEM_OK) goto cleanup;
    golem_optimization_policy optimization_policy;
    if (golem_optimization_policy_init(&optimization_policy) != GOLEM_OK) goto cleanup;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) optimization_policy.allowed[i] = GOLEM_OPTIMIZE_ROUTE;
    if (golem_work_run_optimization_enable(run, &optimization_policy) != GOLEM_OK) goto cleanup;
    for (size_t i = 0; i < graph_spec.count; ++i) {
        golem_stage_snapshot stage;
        golem_stage_permission_request request;
        golem_policy_decision decision;
        golem_cost_amount estimate = {{10, 0, 2, 0, 0}, 100, true, true};
        if (golem_work_run_cost_plan(run, i + 1, &estimate) != GOLEM_OK) goto cleanup;
        if (golem_work_run_permission_request(run, GOLEM_EFFECT_LOCAL, &request, NULL) != GOLEM_OK) goto cleanup;
        if (i % 2 == 0) {
            if (golem_work_run_begin_authorized(run, &request, &stage, &decision, NULL) != GOLEM_OK ||
                decision.verdict != GOLEM_POLICY_ALLOW) goto cleanup;
        } else if (optimized_start(run, &request, &estimate, &stage) != GOLEM_OK) goto cleanup;
        if (stage.stage != graph_spec.order[i] ||
            golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
                                     GOLEM_FAILURE_NONE, true) != GOLEM_OK) {
            goto cleanup;
        }
        golem_provider_usage report = {0};
        strcpy(report.request_id, "consumer-call"); strcpy(report.provider, "fixture");
        strcpy(report.model, "fixture-model"); strcpy(report.price_revision, "v1");
        strcpy(report.currency, "USD"); report.actual = estimate; report.actual.nano_cost = 80;
        if (golem_work_run_cost_report(run, stage.sequence, &report) != GOLEM_OK ||
            golem_work_run_cost_settle(run, stage.sequence) != GOLEM_OK) goto cleanup;
    }
    golem_cost_totals costs;
    if (golem_cost_ledger_totals_get(golem_work_run_cost_borrow(run), &costs) != GOLEM_OK ||
        costs.entries != 6 || costs.actual.nano_cost != 480 || !costs.actual.cost_known) goto cleanup;
    golem_work_snapshot work;
    if (golem_work_run_snapshot_get(run, &work) == GOLEM_OK &&
        work.status == GOLEM_WORK_SUCCEEDED && work.passed_count == 6) {
        result = 0;
    }
cleanup:
    golem_work_run_free(run);
    golem_work_capsule_free(capsule);
    golem_stage_graph_free(graph);
    return result;
}
