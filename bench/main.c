#define _POSIX_C_SOURCE 200809L
#include "workloads.h"
#include "golem/version.h"
#include <json-c/json.h>
#include <openssl/crypto.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static uint64_t now(void)
{
    struct timespec t; BENCH_CHECK(clock_gettime(CLOCK_MONOTONIC, &t) == 0);
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static bool iterations(const char *text, size_t *out)
{
    size_t n = 0;
    if (*text == '\0') return false;
    for (; *text != '\0'; ++text) {
        if (*text < '0' || *text > '9' || n > 1000000) return false;
        n = n * 10 + (size_t)(*text - '0');
    }
    if (n == 0 || n > 1000000) return false;
    *out = n; return true;
}
static void field(struct json_object *o, const char *name, struct json_object *value)
{
    BENCH_CHECK(value != NULL && json_object_object_add(o, name, value) == 0);
}
int main(int argc, char **argv)
{
    if (argc != 4) { fprintf(stderr, "usage: golem_bench METRIC ITERATIONS SCRATCH_DIRECTORY\n"); return 2; }
    size_t count, loops; const bench_case *all = bench_cases(&count), *selected = NULL;
    for (size_t i = 0; i < count; ++i) if (strcmp(all[i].name, argv[1]) == 0) selected = &all[i];
    if (selected == NULL || !iterations(argv[2], &loops) || (selected->durable && loops > 4096)) return 2;
    bench_state s; bench_init(&s);
    char path[4096] = {0};
    if (selected->durable) {
        int n = snprintf(path, sizeof(path), "%s/golem-bench-XXXXXX", argv[3]);
        BENCH_CHECK(n > 0 && (size_t)n < sizeof(path));
        int fd = mkstemp(path); BENCH_CHECK(fd >= 0 && close(fd) == 0);
        BENCH_CHECK(golem_journal_open(path, NULL, &s.journal, NULL) == GOLEM_OK);
    }
    selected->run(&s, 1); /* Warm caches/crypto dispatch outside the timed batch. */
    uint64_t start = now(); selected->run(&s, loops); uint64_t elapsed = now() - start;
    BENCH_CHECK(elapsed > 0);
    if (s.journal != NULL) {
        BENCH_CHECK(golem_journal_close(s.journal, NULL) == GOLEM_OK);
        BENCH_CHECK(golem_journal_open(path, NULL, &s.journal, NULL) == GOLEM_OK);
        BENCH_CHECK(golem_journal_close(s.journal, NULL) == GOLEM_OK);
        BENCH_CHECK(unlink(path) == 0); /* Only our unique scratch file. */
    }
    struct json_object *o = json_object_new_object(); BENCH_CHECK(o != NULL);
    field(o, "schema", json_object_new_int(1));
    field(o, "workload_version", json_object_new_int(1));
    field(o, "metric", json_object_new_string(selected->name));
    field(o, "iterations", json_object_new_uint64(loops));
    field(o, "elapsed_ns", json_object_new_uint64(elapsed));
    field(o, "bytes_per_op", json_object_new_uint64(selected->bytes_per_op));
    field(o, "events_per_op", json_object_new_int(selected->events_per_op));
    field(o, "durable", json_object_new_boolean(selected->durable));
    field(o, "compiler", json_object_new_string(GOLEM_BENCH_COMPILER));
    field(o, "build_flags", json_object_new_string(GOLEM_BENCH_FLAGS));
    field(o, "workload_sha256", json_object_new_string(GOLEM_BENCH_WORKLOAD));
    field(o, "configuration", json_object_new_string(GOLEM_BENCH_CONFIG));
    field(o, "sanitized", json_object_new_boolean(GOLEM_BENCH_SANITIZED));
    field(o, "openssl", json_object_new_string(OpenSSL_version(OPENSSL_VERSION)));
    field(o, "json_c", json_object_new_string(json_c_version()));
    field(o, "version", json_object_new_string(golem_version_string()));
    field(o, "sink", json_object_new_uint64(s.sink));
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    BENCH_CHECK(text != NULL && puts(text) >= 0);
    json_object_put(o); bench_free(&s); return 0;
}
