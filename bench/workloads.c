#include "workloads.h"
#include <string.h>

static void transition(bench_state *s, size_t count)
{
    for (size_t n = 0; n < count; ++n) {
        golem_work_run *run = NULL;
        BENCH_CHECK(golem_work_run_create("bench-run", s->capsule, 2, &run) == GOLEM_OK);
        for (unsigned stage = 0; stage < GOLEM_STAGE_COUNT; ++stage) {
            golem_stage_snapshot snapshot;
            BENCH_CHECK(golem_work_run_begin(run, false, false, &snapshot) == GOLEM_OK);
            BENCH_CHECK(snapshot.stage == (golem_stage)stage);
            BENCH_CHECK(golem_work_run_finish(run, snapshot.sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
        }
        golem_work_snapshot snapshot;
        BENCH_CHECK(golem_work_run_snapshot_get(run, &snapshot) == GOLEM_OK && snapshot.status == GOLEM_WORK_SUCCEEDED);
        s->sink += snapshot.passed_count;
        golem_work_run_free(run);
    }
}
static void replay(bench_state *s, size_t count)
{
    for (size_t n = 0; n < count; ++n) {
        golem_work_run *run = NULL; golem_work_snapshot snapshot;
        BENCH_CHECK(golem_journal_replay((golem_bytes){s->stream, s->stream_size}, NULL, &run, NULL) == GOLEM_OK);
        BENCH_CHECK(golem_work_run_snapshot_get(run, &snapshot) == GOLEM_OK && snapshot.status == GOLEM_WORK_SUCCEEDED);
        s->sink += snapshot.passed_count; golem_work_run_free(run);
    }
}
static void encode_frame(bench_state *s, size_t count)
{
    uint8_t out[128]; size_t required;
    for (size_t i = 0; i < count; ++i) {
        BENCH_CHECK(golem_journal_record_encode(GOLEM_JOURNAL_STARTED, 1,
            (golem_bytes){s->frame + GOLEM_JOURNAL_HEADER_SIZE, GOLEM_JOURNAL_EVENT_SIZE},
            out, sizeof(out), &required, NULL) == GOLEM_OK);
        BENCH_CHECK(required == s->frame_size && memcmp(out, s->frame, required) == 0);
        s->sink += required;
    }
}
static void decode_frame(bench_state *s, size_t count)
{
    for (size_t i = 0; i < count; ++i) {
        golem_journal_record record; size_t consumed;
        BENCH_CHECK(golem_journal_record_decode((golem_bytes){s->frame, s->frame_size}, &record, &consumed, NULL) == GOLEM_OK);
        BENCH_CHECK(consumed == s->frame_size && record.sequence == 1);
        s->sink += consumed;
    }
}
static void append(bench_state *s, size_t count)
{
    for (size_t i = 0; i < count; ++i) {
        uint64_t sequence;
        BENCH_CHECK(golem_journal_append(s->journal, GOLEM_JOURNAL_STARTED,
            (golem_bytes){s->frame + GOLEM_JOURNAL_HEADER_SIZE, GOLEM_JOURNAL_EVENT_SIZE}, &sequence, NULL) == GOLEM_OK);
        BENCH_CHECK(sequence == ++s->appended); s->sink += sequence;
    }
}
static void digest(bench_state *s, size_t count, size_t bytes, const golem_digest *expected)
{
    for (size_t i = 0; i < count; ++i) {
        golem_digest out;
        BENCH_CHECK(golem_digest_bytes((golem_bytes){s->blob, bytes}, &out) == GOLEM_OK);
        BENCH_CHECK(memcmp(&out, expected, sizeof(out)) == 0); s->sink += out.bytes[0];
    }
}
static void digest_small(bench_state *s, size_t n) { digest(s, n, 4096, &s->small_digest); }
static void digest_large(bench_state *s, size_t n) { digest(s, n, 1048576, &s->large_digest); }
static void json_encode(bench_state *s, size_t count)
{
    char out[GOLEM_ADAPTER_JSON_MAX + 1]; size_t n;
    for (size_t i = 0; i < count; ++i) {
        BENCH_CHECK(golem_adapter_envelope_encode(&s->envelope, out, sizeof(out), &n, NULL) == GOLEM_OK);
        BENCH_CHECK(n == s->json_size + 1 && memcmp(out, s->json, n) == 0); s->sink += n;
    }
}
static void json_decode(bench_state *s, size_t count)
{
    for (size_t i = 0; i < count; ++i) {
        golem_adapter_envelope out;
        BENCH_CHECK(golem_adapter_envelope_decode((golem_bytes){(const uint8_t *)s->json, s->json_size}, &out, NULL) == GOLEM_OK);
        BENCH_CHECK(out.type == GOLEM_ADAPTER_RUN_STAGE && out.data.request.sequence == 1); s->sink += out.data.request.sequence;
    }
}
static void msgpack_encode(bench_state *s, size_t count)
{
    uint8_t out[GOLEM_ADAPTER_MSGPACK_MAX]; size_t n;
    for (size_t i = 0; i < count; ++i) {
        BENCH_CHECK(golem_adapter_msgpack_encode(&s->envelope, out, sizeof(out), &n, NULL) == GOLEM_OK);
        BENCH_CHECK(n == s->packed_size && memcmp(out, s->packed, n) == 0); s->sink += n;
    }
}
static void msgpack_decode(bench_state *s, size_t count)
{
    for (size_t i = 0; i < count; ++i) {
        golem_adapter_envelope out;
        BENCH_CHECK(golem_adapter_msgpack_decode((golem_bytes){s->packed, s->packed_size}, &out, NULL) == GOLEM_OK);
        BENCH_CHECK(out.type == GOLEM_ADAPTER_RUN_STAGE && out.data.request.sequence == 1); s->sink += out.data.request.sequence;
    }
}
static bench_case cases[] = {
    {"transition_cycle", 0, 12, false, transition},
    {"transition_replay", 0, 13, false, replay},
    {"journal_encode", 64, 1, false, encode_frame},
    {"journal_decode", 64, 1, false, decode_frame},
    {"journal_append_fsync", 64, 1, true, append},
    {"digest_4k", 4096, 1, false, digest_small},
    {"digest_1m", 1048576, 1, false, digest_large},
    {"json_encode", 0, 1, false, json_encode},
    {"json_decode", 0, 1, false, json_decode},
    {"msgpack_encode", 0, 1, false, msgpack_encode},
    {"msgpack_decode", 0, 1, false, msgpack_decode}
};
const bench_case *bench_cases(size_t *count) { *count = sizeof(cases) / sizeof(cases[0]); return cases; }
static void add_frame(bench_state *s, golem_journal_type type, uint64_t seq, golem_bytes payload)
{
    size_t n;
    BENCH_CHECK(golem_journal_record_encode(type, seq, payload, s->stream + s->stream_size,
        sizeof(s->stream) - s->stream_size, &n, NULL) == GOLEM_OK);
    s->stream_size += n;
}
void bench_init(bench_state *s)
{
    *s = (bench_state){0};
    golem_graph_spec graph_spec; golem_stage_graph *graph = NULL;
    BENCH_CHECK(golem_stage_graph_default_spec(&graph_spec) == GOLEM_OK);
    BENCH_CHECK(golem_stage_graph_create(&graph_spec, &graph) == GOLEM_OK);
    const char *scope[] = {"synthetic benchmark"}, *accept[] = {"six stages passed"};
    golem_capsule_spec spec = {.id = "bench", .goal = "measure runtime", .scope = {scope, 1}, .acceptance = {accept, 1}, .graph = graph};
    for (unsigned i = 0; i < GOLEM_STAGE_COUNT; ++i) spec.permissions[i] = GOLEM_AUTONOMY_AUTO_LOCAL;
    BENCH_CHECK(golem_work_capsule_create(&spec, &s->capsule) == GOLEM_OK);
    golem_stage_graph_free(graph);
    uint8_t payload[4096]; size_t n;
    BENCH_CHECK(golem_journal_created_encode("bench-run", s->capsule, 2, payload, sizeof(payload), &n, NULL) == GOLEM_OK);
    add_frame(s, GOLEM_JOURNAL_CREATED, 1, (golem_bytes){payload, n});
    for (unsigned i = 0; i < GOLEM_STAGE_COUNT; ++i) {
        golem_journal_event event = {.type = GOLEM_JOURNAL_STARTED, .stage = (golem_stage)i,
            .attempt = 1, .attempt_sequence = i + 1, .outcome = GOLEM_STAGE_RUNNING};
        BENCH_CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &n, NULL) == GOLEM_OK);
        add_frame(s, event.type, 2 + 2 * i, (golem_bytes){payload, n});
        if (i == 0) BENCH_CHECK(golem_journal_record_encode(event.type, 1, (golem_bytes){payload, n}, s->frame, sizeof(s->frame), &s->frame_size, NULL) == GOLEM_OK);
        event.type = GOLEM_JOURNAL_FINISHED; event.outcome = GOLEM_STAGE_PASSED; event.requirements_met = true;
        BENCH_CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &n, NULL) == GOLEM_OK);
        add_frame(s, event.type, 3 + 2 * i, (golem_bytes){payload, n});
    }
    s->blob = malloc(1048576); BENCH_CHECK(s->blob != NULL);
    for (size_t i = 0; i < 1048576; ++i) s->blob[i] = (uint8_t)(i * 17u + 31u);
    BENCH_CHECK(golem_digest_bytes((golem_bytes){s->blob, 4096}, &s->small_digest) == GOLEM_OK);
    BENCH_CHECK(golem_digest_bytes((golem_bytes){s->blob, 1048576}, &s->large_digest) == GOLEM_OK);
    s->envelope.type = GOLEM_ADAPTER_RUN_STAGE;
    golem_adapter_request *r = &s->envelope.data.request;
    r->version = GOLEM_ADAPTER_VERSION; strcpy(r->request_id, "bench-request");
    strcpy(r->run_id, "bench-run"); strcpy(r->adapter_id, "local.noop");
    r->stage = GOLEM_STAGE_PLANNING; r->sequence = 1; r->attempt = 1;
    r->context = (golem_receipt){GOLEM_RECEIPT_VERSION, GOLEM_DIGEST_SHA256, 4096, s->small_digest};
    BENCH_CHECK(golem_adapter_envelope_encode(&s->envelope, s->json, sizeof(s->json), &n, NULL) == GOLEM_OK);
    s->json_size = n - 1;
    BENCH_CHECK(golem_adapter_msgpack_encode(&s->envelope, s->packed, sizeof(s->packed), &s->packed_size, NULL) == GOLEM_OK);
    cases[1].bytes_per_op = s->stream_size;
    cases[7].bytes_per_op = cases[8].bytes_per_op = s->json_size;
    cases[9].bytes_per_op = cases[10].bytes_per_op = s->packed_size;
}
void bench_free(bench_state *s) { golem_work_capsule_free(s->capsule); free(s->blob); }
