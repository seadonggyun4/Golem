#ifndef GOLEM_BENCH_WORKLOADS_H
#define GOLEM_BENCH_WORKLOADS_H
#include "golem/adapter_protocol.h"
#include "golem/journal.h"
#include <stdio.h>
#include <stdlib.h>
#define BENCH_CHECK(x) do { if (!(x)) { \
    fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); exit(EXIT_FAILURE); \
} } while (0)
typedef struct bench_state {
    golem_work_capsule *capsule;
    golem_adapter_envelope envelope;
    uint8_t stream[8192], frame[128], packed[GOLEM_ADAPTER_MSGPACK_MAX];
    char json[GOLEM_ADAPTER_JSON_MAX + 1];
    size_t stream_size, frame_size, packed_size, json_size;
    uint8_t *blob;
    golem_digest small_digest, large_digest;
    golem_journal *journal;
    uint64_t appended;
    volatile uint64_t sink;
} bench_state;
typedef struct bench_case {
    const char *name;
    size_t bytes_per_op;
    unsigned events_per_op;
    bool durable;
    void (*run)(bench_state *state, size_t iterations);
} bench_case;
void bench_init(bench_state *state);
void bench_free(bench_state *state);
const bench_case *bench_cases(size_t *count);
#endif
