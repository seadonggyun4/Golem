#define _POSIX_C_SOURCE 200809L
#include "daemon_worker.h"
#include "work.h"
#include "../daemon/internal.h"
#include "../evidence/internal.h"
#include "golem/supervisor.h"
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

typedef struct invocation {
    cli_daemon_host *host;
    golem_runtime *runtime;
    uint64_t deadline, heartbeat, sequence;
    int dir;
    char store[GD_PATH];
    golem_adapter_capability capability;
} invocation;
static golem_status clock_now(uint64_t *out)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) < 0 || t.tv_sec < 0 ||
        (uint64_t)t.tv_sec > (UINT64_MAX - (uint64_t)t.tv_nsec) / 1000000000u) return GOLEM_ERR_IO;
    *out = (uint64_t)t.tv_sec * 1000000000u + (uint64_t)t.tv_nsec; return GOLEM_OK;
}
static golem_status pulse(void *context)
{
    invocation *i = context;
    if (*i->host->stop) return GOLEM_ERR_INCOMPLETE_WORK;
    golem_status s = golem_runtime_checkpoint(i->runtime); uint64_t now;
    if (s == GOLEM_OK) s = clock_now(&now);
    if (s == GOLEM_OK && now >= i->deadline) return GOLEM_ERR_INCOMPLETE_WORK;
    if (s == GOLEM_OK && now - i->heartbeat >= UINT64_C(1000000000)) {
        golem_lease_snapshot lease;
        s = golem_runtime_heartbeat(i->runtime, UINT64_C(60000000000), &lease);
        if (s == GOLEM_OK) i->heartbeat = now;
    }
    return s;
}
static golem_status save(invocation *i, const char *kind, golem_bytes bytes)
{
    char name[80]; (void)snprintf(name, sizeof(name), "%s-%020" PRIu64, kind, i->sequence);
    return gd_write(i->dir, name, bytes);
}
static golem_status launch(invocation *i, bool probe, golem_bytes input, golem_adapter_envelope *out)
{
    uint64_t now; golem_status s = pulse(i);
    if (s == GOLEM_OK) s = clock_now(&now);
    if (s != GOLEM_OK) return s;
    if (now >= i->deadline) return GOLEM_ERR_INCOMPLETE_WORK;
    char *argv[] = {(char *)i->host->worker, "adapter", "noop", probe ? "probe" : "run", probe ? NULL : i->store, NULL};
    golem_supervisor_result result = {0};
    s = golem_supervisor_run(i->host->worker, argv, input, i->deadline - now, pulse, i, &result);
    golem_status recorded = save(i, probe ? "probe.stdout" : "worker.stdout", (golem_bytes){result.output, result.output_size});
    if (recorded == GOLEM_OK) recorded = save(i, probe ? "probe.stderr" : "worker.stderr", (golem_bytes){result.error, result.error_size});
    if (recorded != GOLEM_OK) return recorded;
    if (s == GOLEM_OK) s = golem_adapter_envelope_decode((golem_bytes){result.output, result.output_size}, out, NULL);
    return s;
}
static golem_status probe(void *context, golem_adapter_capability *out, golem_diagnostic *diagnostic)
{
    invocation *i = context; (void)diagnostic; *out = i->capability; return GOLEM_OK;
}
static golem_status run_stage(void *context, const golem_adapter_request *request,
    golem_evidence_store *store, golem_adapter_result *out, golem_diagnostic *diagnostic)
{
    invocation *i = context; (void)store; (void)diagnostic;
    golem_adapter_envelope e = {.type = GOLEM_ADAPTER_RUN_STAGE, .data.request = *request};
    char bytes[GOLEM_ADAPTER_JSON_MAX]; size_t size;
    golem_status s = golem_adapter_envelope_encode(&e, bytes, sizeof(bytes), &size, NULL);
    if (s == GOLEM_OK) s = launch(i, false, (golem_bytes){(const uint8_t *)bytes, size - 1}, &e);
    if (s == GOLEM_OK && e.type != GOLEM_ADAPTER_STAGE_RESULT) s = GOLEM_ERR_PARSE;
    if (s == GOLEM_OK) *out = e.data.result;
    return s;
}
golem_status cli_daemon_execute(void *context, golem_runtime *runtime, golem_work_run *run,
    const char *directory, const golem_stage_snapshot *stage, uint64_t deadline, golem_runtime_result *out)
{
    invocation i = {.host = context, .runtime = runtime, .deadline = deadline, .sequence = stage->sequence, .dir = -1};
    golem_evidence_store *store = NULL; golem_adapter *adapter = NULL; gd_blob bytes = {0};
    golem_status s = clock_now(&i.heartbeat); char path[GD_PATH];
#define TRY(call) do { s = (call); if (s != GOLEM_OK) goto done; } while (0)
    if (s != GOLEM_OK) goto done;
    i.dir = golem_evidence_path_open(directory, true); if (i.dir < 0) { s = GOLEM_ERR_IO; goto done; }
    /* Durable no-overwrite dispatch marker precedes any child, including probe.
     * An orphan marker after a lost journal suffix prevents sequence reuse. */
    TRY(save(&i, "dispatch", (golem_bytes){(const uint8_t *)"local.noop\n", 11}));
    TRY(gd_path(directory, "evidence", i.store));
    if (mkdirat(i.dir, "evidence", 0700) < 0 && errno != EEXIST) { s = GOLEM_ERR_IO; goto done; }
    TRY(golem_evidence_open(i.store, true, NULL, &store, NULL));
    TRY(gd_path(directory, "context.bin", path)); TRY(gd_read(path, GOLEM_JOURNAL_MAX_PAYLOAD, &bytes));
    golem_receipt receipt; TRY(golem_evidence_put(store, (golem_bytes){bytes.data, bytes.size}, &receipt, NULL));
    free(bytes.data); bytes = (gd_blob){0};
    golem_digest predecessor = {{0}}; golem_adapter_envelope envelope;
    for (uint64_t sequence = 1; sequence < stage->sequence; ++sequence) {
        free(bytes.data); bytes = (gd_blob){0};
        char name[80]; (void)snprintf(name, sizeof(name), "result-%020" PRIu64, sequence);
        TRY(gd_path(directory, name, path)); TRY(gd_read(path, GOLEM_ADAPTER_JSON_MAX, &bytes));
        TRY(golem_adapter_envelope_decode((golem_bytes){bytes.data, bytes.size}, &envelope, NULL));
        if (envelope.type != GOLEM_ADAPTER_STAGE_RESULT) { s = GOLEM_ERR_PARSE; goto done; }
        const golem_adapter_result *r = &envelope.data.result;
        if (r->request.sequence != sequence || strcmp(r->request.run_id, golem_work_run_id_borrow(run)) != 0 ||
            strcmp(r->request.adapter_id, "local.noop") != 0 || !r->simulation ||
            r->request.context.size != receipt.size || memcmp(&r->request.context.digest, &receipt.digest, sizeof(receipt.digest)) != 0 ||
            r->request.has_predecessor != (sequence > 1) || memcmp(&r->request.predecessor, &predecessor, sizeof(predecessor)) != 0) { s = GOLEM_ERR_IDENTITY_MISMATCH; goto done; }
        uint64_t size; TRY(golem_evidence_verify(store, &r->evidence.digest, &size, NULL));
        if (size != r->evidence.size) { s = GOLEM_ERR_SIZE_MISMATCH; goto done; }
        predecessor = r->evidence.digest;
    }
    TRY(launch(&i, true, (golem_bytes){NULL, 0}, &envelope));
    if (envelope.type != GOLEM_ADAPTER_CAPABILITY || strcmp(envelope.data.capability.adapter_id, "local.noop") != 0 ||
        !envelope.data.capability.simulation || envelope.data.capability.effect != GOLEM_EFFECT_LOCAL) { s = GOLEM_ERR_POLICY_DENIED; goto done; }
    i.capability = envelope.data.capability;
    golem_adapter_ops ops = {probe, run_stage}; TRY(golem_adapter_create(&ops, &i, NULL, &adapter));
    char id[64]; (void)snprintf(id, sizeof(id), "stage-%" PRIu64, stage->sequence);
    golem_adapter_request request;
    TRY(golem_adapter_request_init(run, "local.noop", id, &receipt, stage->sequence > 1 ? &predecessor : NULL, &request));
    envelope.type = GOLEM_ADAPTER_STAGE_RESULT;
    TRY(golem_adapter_dispatch(adapter, run, &request, store, &envelope.data.result, NULL));
    if (!envelope.data.result.simulation) { s = GOLEM_ERR_POLICY_DENIED; goto done; }
    char encoded[GOLEM_ADAPTER_JSON_MAX]; size_t size;
    TRY(golem_adapter_envelope_encode(&envelope, encoded, sizeof(encoded), &size, NULL));
    TRY(save(&i, "result", (golem_bytes){(const uint8_t *)encoded, size - 1}));
    /* Simulation attestation only. Real acceptance requires a registered host. */
    *out = (golem_runtime_result){stage->sequence, envelope.data.result.outcome, envelope.data.result.failure,
        envelope.data.result.outcome == GOLEM_STAGE_PASSED};
done:
    free(bytes.data); golem_adapter_free(adapter);
    golem_status closed = golem_evidence_close(store); if (s == GOLEM_OK) s = closed;
    if (i.dir >= 0 && close(i.dir) < 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
    return s;
#undef TRY
}
