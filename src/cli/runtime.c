#define _POSIX_C_SOURCE 200809L
#include "work.h"
#include "../adapter_protocol/internal.h"
#include <openssl/rand.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* The same deterministic transcript contract is used for publication and
 * read-only verification. No adapter callback is invoked during verification. */
typedef struct session {
    const char *root;
    int dir;
    bool writing;
    golem_journal *journal;
    golem_journal_reader reader;
    struct json_object *files;
} session;

static golem_status read_at(const char *root, const char *name, cli_blob *b)
{
    char path[CLI_PATH_MAX]; golem_status s = cli_path(root, name, path);
    return s == GOLEM_OK ? cli_read(path, CLI_BUNDLE_MAX, b) : s;
}
static golem_status file_record(session *s, const char *name, golem_bytes bytes)
{
    golem_digest digest; char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t required;
    golem_status status = golem_digest_bytes(bytes, &digest);
    if (status == GOLEM_OK) status = golem_digest_format(&digest, hex, sizeof(hex), &required);
    if (status == GOLEM_OK && !cli_json_add(s->files, name, json_object_new_string(hex))) status = GOLEM_ERR_OUT_OF_MEMORY;
    return status;
}
static golem_status publish(session *s, const char *name, golem_bytes bytes)
{
    golem_status status;
    if (s->writing) status = cli_write_new(s->dir, name, bytes);
    else {
        cli_blob b = {0}; status = read_at(s->root, name, &b);
        if (status == GOLEM_OK && (b.size != bytes.size || memcmp(b.data, bytes.data, b.size) != 0)) status = GOLEM_ERR_REPLAY_MISMATCH;
        free(b.data);
    }
    return status == GOLEM_OK && strcmp(name, "complete.json") != 0 ? file_record(s, name, bytes) : status;
}
static golem_status record(session *s, golem_journal_type type, golem_bytes bytes)
{
    if (s->writing) { uint64_t seq; return golem_journal_append(s->journal, type, bytes, &seq, NULL); }
    golem_journal_record r; bool has = false;
    golem_status status = golem_journal_reader_next(&s->reader, &r, &has, NULL);
    if (status == GOLEM_OK && (!has || r.type != type || r.payload.size != bytes.size || memcmp(r.payload.data, bytes.data, bytes.size) != 0)) status = GOLEM_ERR_REPLAY_MISMATCH;
    return status;
}
static golem_status event(session *s, const golem_stage_snapshot *stage, bool finished)
{
    golem_journal_event e = {.type = finished ? GOLEM_JOURNAL_FINISHED : GOLEM_JOURNAL_STARTED,
        .stage = stage->stage, .attempt = stage->attempt, .attempt_sequence = stage->sequence,
        .outcome = finished ? GOLEM_STAGE_PASSED : GOLEM_STAGE_RUNNING, .requirements_met = finished};
    uint8_t bytes[GOLEM_JOURNAL_EVENT_SIZE]; size_t size;
    golem_status status = golem_journal_event_encode(&e, bytes, sizeof(bytes), &size, NULL);
    return status == GOLEM_OK ? record(s, e.type, (golem_bytes){bytes, size}) : status;
}
static golem_status verify_receipt(golem_evidence_store *store, const golem_receipt *receipt)
{
    uint64_t size; golem_status s = golem_evidence_verify(store, &receipt->digest, &size, NULL);
    return s == GOLEM_OK && size != receipt->size ? GOLEM_ERR_SIZE_MISMATCH : s;
}

static golem_status execute(session *s, const char *id, golem_bytes capsule_bytes,
    golem_work_capsule *capsule, struct json_object **summary, struct json_object **cost)
{
    golem_work_run *run = NULL; golem_adapter *adapter = NULL; golem_evidence_store *store = NULL;
    cli_blob journal = {0}; void *created = NULL; struct json_object *bill = NULL, *manifest = NULL, *result = NULL;
    char path[CLI_PATH_MAX]; int evidence_dir = -1; size_t required = 0;
    golem_status status = golem_work_run_create(id, capsule, 1, &run);
    golem_cost_options options = {.version = GOLEM_COST_VERSION, .currency = "USD", .entry_capacity = 6, .report_capacity = 6};
#define TRY(call) do { status = (call); if (status != GOLEM_OK) goto done; } while (0)
    if (status != GOLEM_OK) goto done;
    TRY(golem_work_run_cost_enable(run, &options));
    TRY(publish(s, "capsule.json", capsule_bytes));
    TRY(cli_path(s->root, "evidence", path));
    if (s->writing) { TRY(cli_mkdir_new(path, &evidence_dir)); if (close(evidence_dir) != 0) { evidence_dir = -1; status = GOLEM_ERR_IO; goto done; } evidence_dir = -1; }
    TRY(golem_evidence_open(path, s->writing, NULL, &store, NULL));
    golem_receipt context = {.version = GOLEM_RECEIPT_VERSION, .algorithm = GOLEM_DIGEST_SHA256, .size = capsule_bytes.size};
    TRY(golem_digest_bytes(capsule_bytes, &context.digest));
    if (s->writing) TRY(golem_evidence_put(store, capsule_bytes, &context, NULL));
    else TRY(verify_receipt(store, &context));
    TRY(cli_path(s->root, "journal.bin", path));
    if (s->writing) TRY(golem_journal_open(path, NULL, &s->journal, NULL));
    else { TRY(cli_read(path, CLI_BUNDLE_MAX, &journal)); TRY(golem_journal_reader_init(&s->reader, (golem_bytes){journal.data, journal.size})); }
    status = golem_journal_created_encode(id, capsule, 1, NULL, 0, &required, NULL);
    if (status != GOLEM_ERR_BUFFER_TOO_SMALL) goto done;
    created = malloc(required); if (created == NULL) { status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    TRY(golem_journal_created_encode(id, capsule, 1, created, required, &required, NULL));
    TRY(record(s, GOLEM_JOURNAL_CREATED, (golem_bytes){created, required}));
    if (s->writing) TRY(golem_adapter_noop_create(NULL, &adapter));
    golem_work_snapshot work; TRY(golem_work_run_snapshot_get(run, &work));
    golem_digest predecessor = {{0}};
    for (size_t i = 0; i < work.stage_count; ++i) {
        golem_cost_amount zero = {.usage_known = true, .cost_known = true};
        TRY(golem_work_run_cost_plan(run, i + 1, &zero));
        golem_stage_snapshot stage; TRY(golem_work_run_begin(run, false, false, &stage));
        TRY(event(s, &stage, false));
        char request_id[32], filename[48]; (void)snprintf(request_id, sizeof(request_id), "stage-%zu", i + 1);
        (void)snprintf(filename, sizeof(filename), "%s.json", request_id);
        golem_adapter_request request;
        TRY(golem_adapter_request_init(run, "local.noop", request_id, &context, i == 0 ? NULL : &predecessor, &request));
        golem_adapter_envelope envelope = {.type = GOLEM_ADAPTER_STAGE_RESULT};
        if (s->writing) TRY(golem_adapter_dispatch(adapter, run, &request, store, &envelope.data.result, NULL));
        else {
            cli_blob b = {0}; status = read_at(s->root, filename, &b);
            if (status == GOLEM_OK) status = golem_adapter_envelope_decode((golem_bytes){b.data, b.size}, &envelope, NULL);
            free(b.data); if (status != GOLEM_OK) goto done;
        }
        if (envelope.type != GOLEM_ADAPTER_STAGE_RESULT) { status = GOLEM_ERR_REPLAY_MISMATCH; goto done; }
        golem_adapter_result *r = &envelope.data.result;
        TRY(golem_adapter_result_validate(&request, r));
        if (!r->simulation || r->outcome != GOLEM_STAGE_PASSED || !r->usage.cost_known || !r->usage.usage_known ||
            r->usage.nano_cost || r->usage.usage.input_tokens || r->usage.usage.cached_input_tokens ||
            r->usage.usage.output_tokens || r->usage.usage.reasoning_tokens || r->usage.usage.tool_calls) { status = GOLEM_ERR_REPLAY_MISMATCH; goto done; }
        TRY(verify_receipt(store, &r->evidence));
        char encoded[GOLEM_ADAPTER_JSON_MAX]; TRY(golem_adapter_envelope_encode(&envelope, encoded, sizeof(encoded), &required, NULL));
        TRY(publish(s, filename, (golem_bytes){(const uint8_t *)encoded, required - 1}));
        golem_provider_usage usage = {.provider = "local", .model = "noop", .price_revision = "noop-v1", .currency = "USD", .actual = r->usage};
        memcpy(usage.request_id, request_id, strlen(request_id) + 1);
        TRY(golem_work_run_cost_report(run, stage.sequence, &usage));
        /* This attests only the simulation contract, never business acceptance. */
        TRY(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true));
        TRY(golem_work_run_cost_settle(run, stage.sequence));
        TRY(event(s, &stage, true)); predecessor = r->evidence.digest;
    }
    if (s->writing) {
        status = golem_journal_close(s->journal, NULL); s->journal = NULL; if (status != GOLEM_OK) goto done;
        TRY(read_at(s->root, "journal.bin", &journal));
    } else if (s->reader.offset != journal.size) { status = GOLEM_ERR_REPLAY_MISMATCH; goto done; }
    TRY(file_record(s, "journal.bin", (golem_bytes){journal.data, journal.size}));
    bill = cli_cost_projection(run); if (bill == NULL) { status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    const char *text = json_object_to_json_string_ext(bill, JSON_C_TO_STRING_PLAIN);
    TRY(publish(s, "cost.json", (golem_bytes){(const uint8_t *)text, strlen(text)}));
    manifest = json_object_new_object();
    if (!cli_json_add(manifest, "schema_version", json_object_new_int(1)) || !cli_json_add(manifest, "run_id", json_object_new_string(id)) ||
        !cli_json_add(manifest, "simulation", json_object_new_boolean(true)) || !cli_json_add(manifest, "files", json_object_get(s->files))) { status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    text = json_object_to_json_string_ext(manifest, JSON_C_TO_STRING_PLAIN);
    TRY(publish(s, "complete.json", (golem_bytes){(const uint8_t *)text, strlen(text)}));
    result = cli_run_projection(run, NULL, true); if (result == NULL) { status = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
done:
    if (evidence_dir >= 0) (void)close(evidence_dir);
    if (s->journal != NULL) { (void)golem_journal_close(s->journal, NULL); s->journal = NULL; }
    golem_status closed = golem_evidence_close(store); if (status == GOLEM_OK) status = closed;
    if (status == GOLEM_OK) { *summary = result; result = NULL; *cost = bill; bill = NULL; }
    golem_adapter_free(adapter); golem_work_run_free(run); free(created); free(journal.data);
    json_object_put(bill); json_object_put(manifest); json_object_put(result); return status;
#undef TRY
}

golem_status cli_noop_run(const char *capsule_path, const char *output, struct json_object **out)
{
    cli_blob b = {0}; golem_work_capsule *capsule = NULL; struct json_object *bill = NULL;
    session s = {.root = output, .dir = -1, .writing = true};
    golem_status status = cli_read(capsule_path, CLI_CAPSULE_MAX, &b);
    if (status == GOLEM_OK) status = cli_capsule_decode((golem_bytes){b.data, b.size}, &capsule);
    unsigned char random[16]; char id[37] = "run-";
    if (status == GOLEM_OK && RAND_bytes(random, sizeof(random)) != 1) status = GOLEM_ERR_CRYPTO;
    if (status == GOLEM_OK) for (size_t i = 0; i < sizeof(random); ++i) (void)snprintf(id + 4 + 2 * i, 3, "%02x", random[i]);
    if (status == GOLEM_OK) status = cli_mkdir_new(output, &s.dir);
    s.files = json_object_new_object(); if (s.files == NULL) status = GOLEM_ERR_OUT_OF_MEMORY;
    if (status == GOLEM_OK) status = execute(&s, id, (golem_bytes){b.data, b.size}, capsule, out, &bill);
    if (s.dir >= 0 && close(s.dir) != 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK) {
        json_object_put(*out); *out = NULL; json_object_put(bill); bill = NULL;
        status = cli_bundle_verify(output, out, &bill);
    }
    json_object_put(s.files); json_object_put(bill); golem_work_capsule_free(capsule); free(b.data); return status;
}
golem_status cli_bundle_verify(const char *root, struct json_object **summary, struct json_object **cost)
{
    cli_blob marker = {0}, capsule_bytes = {0}; struct json_object *manifest = NULL; golem_work_capsule *capsule = NULL;
    session s = {.root = root, .dir = -1};
    golem_status status = read_at(root, "complete.json", &marker);
    if (status == GOLEM_OK) status = cli_json_parse((golem_bytes){marker.data, marker.size}, &manifest);
    const char *id = cli_json_text(json_object_object_get(manifest, "run_id"));
    if (status == GOLEM_OK && !golem_adapter_id_valid(id)) status = GOLEM_ERR_INVALID_ARGUMENT;
    if (status == GOLEM_OK) status = read_at(root, "capsule.json", &capsule_bytes);
    if (status == GOLEM_OK) status = cli_capsule_decode((golem_bytes){capsule_bytes.data, capsule_bytes.size}, &capsule);
    s.files = json_object_new_object(); if (s.files == NULL) status = GOLEM_ERR_OUT_OF_MEMORY;
    if (status == GOLEM_OK) status = execute(&s, id, (golem_bytes){capsule_bytes.data, capsule_bytes.size}, capsule, summary, cost);
    json_object_put(s.files); json_object_put(manifest); golem_work_capsule_free(capsule); free(marker.data); free(capsule_bytes.data); return status;
}
