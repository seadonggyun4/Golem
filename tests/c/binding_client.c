#include "golem/session_binding.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct fixture_clock {
    uint64_t now;
    unsigned boot;
} fixture_clock;
static golem_status clock_read(void *ctx, uint64_t *now, golem_digest *boot)
{
    fixture_clock *c = ctx;
    *now = c->now;
    memset(boot, 0, sizeof(*boot));
    boot->bytes[0] = (uint8_t)c->boot;
    return GOLEM_OK;
}
static golem_status observe(void *ctx, golem_bytes candidate, golem_digest *identity)
{
    const char *mode = ctx;
    if (!strcmp(mode, "deny"))
        return GOLEM_ERR_POLICY_DENIED;
    return golem_digest_bytes(candidate, identity);
}
/* Test-only host and clock; never installed or reachable through product CLI. */
int main(int argc, char **argv)
{
    if (argc != 6)
        return 2;
    FILE *f = fopen(argv[2], "rb");
    if (!f)
        return 2;
    uint8_t data[GOLEM_SESSION_BINDING_MAX_BYTES + 1];
    size_t n = fread(data, 1, sizeof(data), f);
    int bad = ferror(f);
    fclose(f);
    if (bad || n > GOLEM_SESSION_BINDING_MAX_BYTES)
        return 2;
    fixture_clock c = {strtoull(argv[3], NULL, 10), (unsigned)strtoul(argv[4], NULL, 10)};
    golem_agent_clock clock = {clock_read, &c};
    golem_session_binding_host host = {observe, argv[5]};
    bool fence = !strcmp(argv[5], "fence"), inspect = !strcmp(argv[5], "inspect");
    golem_document_store *s = NULL;
    golem_agent_reply reply = {0};
    golem_status st = golem_document_store_open(argv[1], !fence && !inspect, NULL, &s, NULL);
    if (st == GOLEM_OK)
        st = fence ? golem_session_fence_check(s, (golem_bytes){data, n}, &clock, NULL)
                   : golem_session_binding_call(
                         s, (golem_bytes){data, n}, &clock,
                         (!strcmp(argv[5], "host") || !strcmp(argv[5], "deny")) ? &host : NULL,
                         &reply, NULL);
    golem_status closed = golem_document_store_close(s);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK) {
        if (fence)
            puts("{}");
        else {
            (void)fwrite(reply.data, 1, reply.size, stdout);
            (void)fputc('\n', stdout);
        }
    } else
        fprintf(stderr, "%s\n", golem_status_string(st));
    golem_agent_reply_free(&reply);
    return st == GOLEM_OK ? 0 : 1;
}
