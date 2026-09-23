#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "../src/daemon/events_internal.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <sys/resource.h>
#include <time.h>

static uint64_t now(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
        return 0;
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

int main(int argc, char **argv)
{
    if (argc != 2 || (strcmp(argv[1], "0") && strcmp(argv[1], "1") && strcmp(argv[1], "32")))
        return 2;
    unsigned observers = !strcmp(argv[1], "32") ? 32u : !strcmp(argv[1], "1") ? 1u : 0u;
    ge_ring ring = {.stream = {{1}}};
    golem_runtime_cursor cursors[32] = {0};
    golem_runtime_event records[64];
    const uint64_t iterations = 100000;
    /* Process startup, identity generation and serialization are not timed. */
    uint64_t start = now(), checksum = 0;
    if (!start)
        return 1;
    for (uint64_t i = 1; i <= iterations; ++i) {
        ge_append(&ring, (golem_runtime_event){.kind = GOLEM_EVENT_QUEUED,
                                             .origin = GOLEM_EVENT_WORKER_OBSERVATION,
                                             .subject = i});
        if (i % 16 == 0) {
            for (unsigned observer = 0; observer < observers; ++observer) {
                golem_runtime_event_page page;
                if (ge_read(&ring, cursors[observer].sequence ? &cursors[observer] : NULL,
                            records, 64, &page) != GOLEM_OK || page.count != 16)
                    return 1;
                cursors[observer] = page.next;
                checksum += records[page.count - 1].subject;
            }
        }
    }
    uint64_t end = now();
    struct rusage usage;
    if (end <= start || getrusage(RUSAGE_SELF, &usage) != 0 || ring.sequence != iterations)
        return 1;
    uint64_t rss = (uint64_t)usage.ru_maxrss;
#ifndef __APPLE__
    rss *= 1024;
#endif
    printf("{\"schema\":1,\"observers\":%u,\"iterations\":%" PRIu64
           ",\"elapsed_ns\":%" PRIu64 ",\"rss_bytes\":%" PRIu64
           ",\"checksum\":%" PRIu64 "}\n",
           observers, iterations, end - start, rss, checksum);
    return ferror(stdout) ? 1 : 0;
}
