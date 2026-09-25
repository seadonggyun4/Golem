#define _POSIX_C_SOURCE 200809L
#include "golem/approval.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
typedef struct fixture {
    const char *mode;
    unsigned checks;
    uint64_t now;
    unsigned boot;
} fixture;
static golem_status clock_read(void *ctx, uint64_t *now, golem_digest *boot)
{
    fixture *f = ctx;
    *now = f->now;
    memset(boot, 0, sizeof(*boot));
    boot->bytes[0] = (uint8_t)f->boot;
    return GOLEM_OK;
}
static golem_status decide(void *ctx, const golem_digest *action, const char *op,
                           golem_digest *issuer, uint64_t *epoch)
{
    (void)ctx;
    (void)action;
    (void)op;
    memset(issuer, 1, sizeof(*issuer));
    *epoch = 1;
    return GOLEM_OK;
}
static golem_status recheck(void *ctx, const golem_digest *action, const golem_digest *issuer,
                            uint64_t epoch)
{
    fixture *f = ctx;
    (void)action;
    ++f->checks;
    if (!strcmp(f->mode, "crash") && f->checks == 2)
        _exit(86);
    if (!strcmp(f->mode, "revoked") || (!strcmp(f->mode, "late-deny") && f->checks >= 2))
        return GOLEM_ERR_POLICY_DENIED;
    if (epoch != 1 || issuer->bytes[0] != 1)
        return GOLEM_ERR_IDENTITY_MISMATCH;
    return GOLEM_OK;
}
/* Synthetic host boundary and test clock. Never installed. */
int main(int argc, char **argv)
{
    if (argc != 8)
        return 2;
    FILE *f = fopen(argv[3], "rb");
    if (!f)
        return 2;
    uint8_t *data = malloc(GOLEM_DOCUMENT_MAX_JSON + 1);
    if (!data) {
        fclose(f);
        return 2;
    }
    size_t n = fread(data, 1, GOLEM_DOCUMENT_MAX_JSON + 1, f);
    int bad = ferror(f);
    fclose(f);
    if (bad || n > GOLEM_DOCUMENT_MAX_JSON) {
        free(data);
        return 2;
    }
    fixture ctx = {argv[4], 0, strtoull(argv[6], NULL, 10), (unsigned)strtoul(argv[7], NULL, 10)};
    golem_approval_host host = {sizeof(host), 1, decide, recheck, &ctx};
    golem_agent_clock clock = {clock_read, &ctx};
    golem_execution_reply out = {0};
    golem_document_store *s = NULL;
    bool describe = !strcmp(argv[1], "describe"), execute = !strcmp(argv[1], "execute");
    golem_status st = golem_document_store_open(argv[2], !describe, NULL, &s, NULL);
    golem_digest receipt, contract;
    if (st == GOLEM_OK && execute)
        st = golem_digest_parse((golem_string_view){argv[5], strlen(argv[5])}, &receipt);
    /* Execution approval digest is passed via a fixture-only adjacent file arg.
     * For the real API caller it remains a separate typed trusted input. */
    if (st == GOLEM_OK && execute)
        st = golem_digest_parse((golem_string_view){argv[6], strlen(argv[6])}, &contract);
    golem_execution_approval approval = {sizeof(approval), 1, &contract, NULL};
    if (st == GOLEM_OK) {
        if (describe)
            st = golem_approval_describe(s, (golem_bytes){data, n}, &out, NULL);
        else if (execute)
            st = golem_execution_call_receipted(s, (golem_bytes){data, n}, &receipt,
                                                !strcmp(argv[4], "no-host") ? NULL : &host,
                                                &approval, &out, NULL);
        else
            st = golem_approval_call(s, (golem_bytes){data, n},
                                     !strcmp(argv[4], "no-host") ? NULL : &host,
                                     ctx.boot ? &clock : NULL, &out, NULL);
    }
    golem_status closed = golem_document_store_close(s);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK) {
        (void)fwrite(out.data, 1, out.size, stdout);
        (void)fputc('\n', stdout);
    } else
        fprintf(stderr, "%s\n", golem_status_string(st));
    golem_execution_reply_free(&out);
    free(data);
    return st == GOLEM_OK ? 0 : 1;
}
