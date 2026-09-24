#define _POSIX_C_SOURCE 200809L
#include "golem/supervisor.h"
#include "test.h"
#include <string.h>
#include <unistd.h>

typedef struct sink {
    size_t bytes[2];
    bool fail;
} sink;
static golem_status receive(void *context, unsigned stream, golem_bytes b)
{
    sink *s = context;
    if (stream > 1 || !b.data || b.size > 4096)
        return GOLEM_ERR_INVALID_ARGUMENT;
    s->bytes[stream] += b.size;
    return s->fail ? GOLEM_ERR_IO : GOLEM_OK;
}
static golem_status cancel_after_reads(void *context)
{
    sink *s = context;
    return s->bytes[0] >= 65536 ? GOLEM_ERR_POLICY_DENIED : GOLEM_OK;
}
int main(int argc, char **argv)
{
    if (argc > 1) {
        if (!strcmp(argv[1], "bulk") || !strcmp(argv[1], "hot")) {
            unsigned char block[4096] = {0};
            for (unsigned i = 0; i < 128 || !strcmp(argv[1], "hot"); ++i)
                if (write(1, block, sizeof(block)) != (ssize_t)sizeof(block))
                    return 1;
            return 0;
        }
        const unsigned char bytes[] = {'a', 0, 255, 0xe2, 0x82, 0xac};
        return write(1, bytes, sizeof(bytes)) == (ssize_t)sizeof(bytes) && write(2, "err", 3) == 3
                   ? 0
                   : 1;
    }
    char *args[] = {argv[0], "child", NULL}, *env[] = {NULL};
    sink collected = {0};
    golem_supervisor_stream options = {sizeof(options), 1, receive, &collected};
    golem_supervisor_capture captured;
    golem_supervisor_result result = {.exit_code = 42};
    CHECK(golem_supervisor_run_streamed(argv[0], args, "/", env, (golem_bytes){NULL, 0},
                                        UINT64_C(3000000000), NULL, NULL, &result, &options,
                                        &captured) == GOLEM_OK);
    CHECK(captured.spawned && captured.reaped && captured.eof[0] && captured.eof[1]);
    CHECK(collected.bytes[0] == 6 && collected.bytes[1] == 3);
    CHECK(captured.observed_bytes[0] == 6 && captured.observed_bytes[1] == 3);
    CHECK(result.output_size == 6 && result.error_size == 3 && result.exit_code == 0);
    collected = (sink){.fail = true};
    CHECK(golem_supervisor_run_streamed(argv[0], args, "/", env, (golem_bytes){NULL, 0},
                                        UINT64_C(3000000000), NULL, NULL, &result, &options,
                                        &captured) == GOLEM_ERR_IO);
    CHECK(captured.spawned && captured.reaped);
    options.version = 99;
    result.exit_code = 42;
    CHECK(golem_supervisor_run_streamed(argv[0], args, "/", env, (golem_bytes){NULL, 0},
                                        UINT64_C(3000000000), NULL, NULL, &result, &options,
                                        &captured) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(!captured.spawned && result.exit_code == 42);
    options.version = 1;
    args[1] = "bulk";
    collected = (sink){0};
    uint64_t limits[2] = {524288, 16384};
    CHECK(golem_supervisor_run_bulk(argv[0], args, "/", env, (golem_bytes){NULL, 0},
                                    UINT64_C(3000000000), NULL, NULL, &result, &options, limits,
                                    &captured) == GOLEM_OK);
    CHECK(collected.bytes[0] == 524288 && captured.observed_bytes[0] == 524288);
    CHECK(captured.reaped && captured.eof[0] && captured.eof[1]);
    CHECK(result.output_size == 0 && result.error_size == 0);
    limits[0]--;
    collected = (sink){0};
    CHECK(golem_supervisor_run_bulk(argv[0], args, "/", env, (golem_bytes){NULL, 0},
                                    UINT64_C(3000000000), NULL, NULL, &result, &options, limits,
                                    &captured) == GOLEM_ERR_BUDGET_EXHAUSTED);
    CHECK(captured.reaped && collected.bytes[0] <= limits[0]);
    args[1] = "hot";
    collected = (sink){0};
    limits[0] = UINT64_C(67108864);
    CHECK(golem_supervisor_run_bulk(argv[0], args, "/", env, (golem_bytes){NULL, 0},
                                    UINT64_C(3000000000), cancel_after_reads, &collected, &result,
                                    &options, limits, &captured) == GOLEM_ERR_POLICY_DENIED);
    CHECK(captured.reaped && !result.timed_out);
    limits[0]++;
    result.exit_code = 42;
    CHECK(golem_supervisor_run_bulk(argv[0], args, "/", env, (golem_bytes){NULL, 0},
                                    UINT64_C(3000000000), NULL, NULL, &result, &options, limits,
                                    &captured) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(!captured.spawned && result.exit_code == 42);
    return 0;
}
