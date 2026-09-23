#include "profile_internal.h"
#include "../agent_session/internal.h"
#include <string.h>

#define RP_JOURNAL_MAX (16u * 1024u * 1024u)

golem_status rp_binding_claim(golem_document_store *store, const golem_digest *digest,
                                  struct json_object **out)
{
    struct json_object *binding = NULL, *claim = json_object_new_object();
    golem_status status = claim ? dw_cas_json(store, digest, &binding) : GOLEM_ERR_OUT_OF_MEMORY;
    if (status == GOLEM_OK &&
        (!dw_add_digest(claim, "runtime_binding", digest) ||
         !dw_add(claim, "attempt_id", json_object_get(dw_get(binding, "attempt_id"))) ||
         !dw_add(claim, "session_id", json_object_get(dw_get(binding, "session_id"))) ||
         !dw_add(claim, "epoch", json_object_get(dw_get(binding, "claim_epoch"))) ||
         !dw_add(claim, "manifest_digest",
                 json_object_get(dw_get(binding, "input_manifest_digest")))))
        status = GOLEM_ERR_PARSE;
    if (status == GOLEM_OK)
        status = rp_validate_claim(store, claim);
    json_object_put(binding);
    if (status == GOLEM_OK)
        *out = claim;
    else
        json_object_put(claim);
    return status;
}

static golem_stage kind_stage(const char *kind)
{
    if (!strcmp(kind, "development-plan") || !strcmp(kind, "development-result"))
        return GOLEM_STAGE_DEVELOPMENT;
    if (!strcmp(kind, "qa-plan") || !strcmp(kind, "qa-result"))
        return GOLEM_STAGE_QA;
    if (!strcmp(kind, "completion"))
        return GOLEM_STAGE_AUDIT;
    for (int i = 0; i < GOLEM_STAGE_COUNT; ++i)
        if (!strcmp(kind, golem_stage_name((golem_stage)i)))
            return (golem_stage)i;
    return GOLEM_STAGE_NONE;
}

static golem_status check_journal(golem_document_store *store, struct json_object *claim,
                                  golem_bytes bytes, const char *run_id,
                                  const golem_journal_checkpoint *checkpoint,
                                  golem_replay_report *out)
{
    if (!bytes.data || !bytes.size || bytes.size > RP_JOURNAL_MAX || !run_id || !*run_id ||
        strlen(run_id) > 256 || !checkpoint || !checkpoint->records ||
        checkpoint->bytes != bytes.size)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_replay_options options = {.expected_run_id = run_id};
    golem_replay *replay = NULL;
    golem_work_run *run = NULL;
    golem_replay_report report;
    golem_status status = golem_replay_create(&options, &store->allocator, &replay, NULL);
    if (status == GOLEM_OK)
        status = golem_replay_expect_checkpoint(replay, checkpoint);
    if (status == GOLEM_OK)
        status = golem_replay_feed(replay, bytes, NULL);
    if (status == GOLEM_OK)
        status = golem_replay_finish(replay, &run, &report, NULL);
    golem_digest input;
    struct json_object *manifest = NULL;
    if (status == GOLEM_OK && !dw_digest(claim, "manifest_digest", &input))
        status = GOLEM_ERR_PARSE;
    if (status == GOLEM_OK)
        status = dw_cas_json(store, &input, &manifest);
    if (status == GOLEM_OK &&
        (!report.has_latest_attempt || report.latest_attempt.status != GOLEM_STAGE_RUNNING ||
         report.latest_attempt.stage != kind_stage(dw_text(manifest, "target_kind"))))
        status = GOLEM_ERR_IDENTITY_MISMATCH;
    if (status == GOLEM_OK)
        *out = report;
    json_object_put(manifest);
    golem_work_run_free(run);
    golem_replay_free(replay);
    return status;
}

static bool conflict(golem_document_store *store, struct json_object *event)
{
    for (size_t i = 0; i < store->runtime_link_count; ++i) {
        struct json_object *prior = store->runtime_links[i];
        if (!strcmp(dw_text(prior, "binding_digest"), dw_text(event, "binding_digest")) ||
            (!strcmp(dw_text(prior, "run_id"), dw_text(event, "run_id")) &&
             dw_uint(prior, "stage_sequence") == dw_uint(event, "stage_sequence")))
            return true;
    }
    return false;
}

golem_status rp_link_apply(golem_document_store *store, struct json_object *event,
                           const golem_digest *payload, const golem_digest *frame)
{
    const char *keys[] = {"schema_version", "type",  "binding_digest", "journal_digest", "run_id",
                          "records",        "bytes", "chain_head",     "stage_sequence"};
    golem_digest binding, journal;
    golem_journal_checkpoint checkpoint = {0};
    if (!dw_keys(event, keys, 9) || dw_uint(event, "schema_version") != 1 ||
        strcmp(dw_text(event, "type"), "runtime-link") ||
        !dw_digest(event, "binding_digest", &binding) ||
        !dw_digest(event, "journal_digest", &journal) ||
        !dw_digest(event, "chain_head", &checkpoint.chain_head) ||
        dw_uint(event, "bytes") > RP_JOURNAL_MAX || store->runtime_link_count >= 256 ||
        conflict(store, event))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    checkpoint.bytes = dw_uint(event, "bytes");
    checkpoint.records = dw_uint(event, "records");
    struct json_object *claim = NULL;
    golem_status status = rp_binding_claim(store, &binding, &claim);
    uint8_t *data = NULL;
    size_t size = 0;
    if (status == GOLEM_OK)
        status = golem_evidence_read(store->cas, &journal, RP_JOURNAL_MAX, &store->allocator, &data,
                                     &size, NULL);
    golem_replay_report report;
    if (status == GOLEM_OK)
        status = check_journal(store, claim, (golem_bytes){data, size}, dw_text(event, "run_id"),
                               &checkpoint, &report);
    if (status == GOLEM_OK && report.latest_attempt.sequence != dw_uint(event, "stage_sequence"))
        status = GOLEM_ERR_IDENTITY_MISMATCH;
    if (status == GOLEM_OK) {
        size_t index = store->runtime_link_count++;
        store->runtime_links[index] = json_object_get(event);
        store->runtime_link_digests[index] = *payload;
        ++store->event_count;
        store->last = *frame;
    }
    dw_scratch_free(store, data);
    json_object_put(claim);
    return status;
}

golem_status golem_runtime_link_run(golem_document_store *store, const golem_digest *binding,
                                    golem_bytes journal, const char *run_id,
                                    const golem_journal_checkpoint *checkpoint,
                                    golem_digest *receipt, golem_diagnostic *diagnostic)
{
    if (!store || !binding || !receipt || !checkpoint)
        return dw_report(diagnostic, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (store->poisoned)
        return dw_report(diagnostic, GOLEM_ERR_INVALID_STATE, NULL);
    if (!store->writable || !strcmp(dw_text(store->spec, "permission"), "DENY"))
        return dw_report(diagnostic, GOLEM_ERR_POLICY_DENIED, NULL);
    if (!strcmp(dw_text(store->spec, "permission"), "ASK_ALWAYS"))
        return dw_report(diagnostic, GOLEM_ERR_APPROVAL_REQUIRED, NULL);
    as_log log = {.directory = -1};
    golem_status status = as_load(store, NULL, NULL, &log);
    struct json_object *active = dw_get(log.state, "active"), *manifest = NULL;
    uint64_t now = 0;
    golem_digest boot, pinned;
    if (status == GOLEM_OK)
        status = as_clock_read(NULL, &now, &boot);
    if (status == GOLEM_OK &&
        (!as_live(&log, now, &boot) || strcmp(dw_text(active, "state"), "RUNNING") ||
         !dw_digest(active, "runtime_binding", &pinned) || !dw_equal(binding, &pinned)))
        status = GOLEM_ERR_STALE_RESULT;
    if (status == GOLEM_OK)
        status = as_fresh(store, active, false, &manifest);
    golem_replay_report report;
    if (status == GOLEM_OK)
        status = check_journal(store, active, journal, run_id, checkpoint, &report);
    golem_receipt stored;
    struct json_object *event = status == GOLEM_OK ? json_object_new_object() : NULL;
    golem_digest journal_digest;
    if (status == GOLEM_OK)
        status = golem_digest_bytes(journal, &journal_digest);
    if (status == GOLEM_OK &&
        (!dw_add(event, "schema_version", json_object_new_int(1)) ||
         !dw_add(event, "type", json_object_new_string("runtime-link")) ||
         !dw_add_digest(event, "binding_digest", binding) ||
         !dw_add_digest(event, "journal_digest", &journal_digest) ||
         !dw_add(event, "run_id", json_object_new_string(run_id)) ||
         !dw_add(event, "records", json_object_new_uint64(checkpoint->records)) ||
         !dw_add(event, "bytes", json_object_new_uint64(checkpoint->bytes)) ||
         !dw_add_digest(event, "chain_head", &checkpoint->chain_head) ||
         !dw_add(event, "stage_sequence", json_object_new_uint64(report.latest_attempt.sequence))))
        status = GOLEM_ERR_OUT_OF_MEMORY;
    bool duplicate = false;
    golem_digest duplicate_receipt;
    if (status == GOLEM_OK)
        for (size_t i = 0; i < store->runtime_link_count; ++i)
            if (json_object_equal(event, store->runtime_links[i])) {
                duplicate_receipt = store->runtime_link_digests[i];
                duplicate = true;
                break;
            }
    if (status == GOLEM_OK && !duplicate && conflict(store, event))
        status = GOLEM_ERR_IDENTITY_MISMATCH;
    if (status == GOLEM_OK && !duplicate && store->runtime_link_count >= 256)
        status = GOLEM_ERR_BUDGET_EXHAUSTED;
    golem_digest payload, frame;
    if (status == GOLEM_OK && !duplicate)
        status = golem_evidence_put(store->cas, journal, &stored, NULL);
    if (status == GOLEM_OK && !duplicate)
        status = dw_put_json(store, event, &payload);
    /* Validate authority again after bounded replay/CAS work, before publication. */
    if (status == GOLEM_OK) {
        status = as_clock_read(NULL, &now, &boot);
        if (status == GOLEM_OK && !as_live(&log, now, &boot))
            status = GOLEM_ERR_STALE_LEASE;
    }
    if (status == GOLEM_OK && !duplicate)
        status = dw_event_write(store, &payload, &frame);
    if (status == GOLEM_OK && !duplicate) {
        size_t index = store->runtime_link_count++;
        store->runtime_links[index] = json_object_get(event);
        store->runtime_link_digests[index] = payload;
        store->last = frame;
        ++store->event_count;
        *receipt = payload;
    }
    if (status == GOLEM_OK && duplicate)
        *receipt = duplicate_receipt;
    if (status == GOLEM_ERR_IO)
        store->poisoned = true;
    json_object_put(manifest);
    json_object_put(event);
    as_close(&log);
    return dw_report(diagnostic, status, NULL);
}
