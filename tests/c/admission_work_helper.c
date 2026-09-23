#define _POSIX_C_SOURCE 200809L
#include "golem/admission.h"
#include "golem/document.h"
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef struct host {
    const char *work, *mode;
    golem_digest receipt;
    unsigned executions;
} host;
static golem_status publish(void *context, const golem_digest *id,
                            const golem_admission_ticket *ticket, golem_digest *receipt)
{
    host *h = context;
    golem_document_store *store = NULL;
    golem_status s = golem_document_store_open(h->work, true, NULL, &store, NULL);
    if (s == GOLEM_OK)
        s = golem_admission_publish_work(store, id, ticket, receipt);
    golem_digest duplicate;
    if (s == GOLEM_OK)
        s = golem_admission_publish_work(store, id, ticket, &duplicate);
    if (s == GOLEM_OK && memcmp(receipt, &duplicate, sizeof(duplicate)))
        s = GOLEM_ERR_IDENTITY_MISMATCH;
    golem_status closed = golem_document_store_close(store);
    if (s == GOLEM_OK)
        s = closed;
    if (s == GOLEM_OK)
        h->receipt = *receipt;
    if (s == GOLEM_OK && !strcmp(h->mode, "kill-publish"))
        (void)kill(getpid(), SIGKILL);
    return s;
}
static golem_status execute(void *context, const golem_admission_ticket *ticket,
                            golem_digest *receipt)
{
    host *h = context;
    (void)ticket;
    ++h->executions;
    golem_evidence_store *cas = NULL;
    golem_status s = golem_evidence_open(h->work, true, NULL, &cas, NULL);
    const char text[] = "Synthetic admission bridge terminated; not provider or QA evidence.";
    golem_receipt stored;
    if (s == GOLEM_OK)
        s = golem_evidence_put(cas, (golem_bytes){(const uint8_t *)text, sizeof(text) - 1}, &stored,
                               NULL);
    if (s == GOLEM_OK)
        *receipt = stored.digest;
    golem_status closed = golem_evidence_close(cas);
    if (s == GOLEM_OK)
        s = closed;
    if (s == GOLEM_OK && !strcmp(h->mode, "kill-execute"))
        (void)kill(getpid(), SIGKILL);
    return s;
}
int main(int argc, char **argv)
{
    if (argc != 7)
        return 2;
    golem_admission_options o = {.size = sizeof(o),
                                 .version = GOLEM_ADMISSION_VERSION,
                                 .create = true,
                                 .limits = {1, 1000, 1024, 0}};
    golem_admission *a = NULL;
    golem_status s = golem_admission_open(argv[1], &o, &a);
    host h = {.work = argv[2], .mode = argv[6]};
    golem_admission_ticket t = {0};
    if (!strcmp(h.mode, "inspect")) {
        if (s == GOLEM_OK)
            s = golem_admission_lookup(a, "bridge-1", &t);
    } else {
        golem_admission_request r = {.cpu_millis = 1000, .memory_bytes = 1024};
        (void)snprintf(r.operation, sizeof(r.operation), "bridge-1");
        (void)snprintf(r.work, sizeof(r.work), "%s", argv[4]);
        (void)snprintf(r.session, sizeof(r.session), "%s", argv[5]);
        if (s == GOLEM_OK)
            s = golem_digest_parse((golem_string_view){argv[3], strlen(argv[3])},
                                   &r.runtime_binding);
        uint64_t ticket;
        if (s == GOLEM_OK)
            s = golem_admission_enqueue(a, &r, &ticket);
        if (s == GOLEM_OK)
            s = golem_admission_grant(a, &t);
        const golem_admission_dispatch_ops ops = {publish, execute};
        if (s == GOLEM_OK)
            s = golem_admission_dispatch(a, t.token, &ops, &h);
        if (s == GOLEM_OK)
            s = golem_admission_lookup(a, "bridge-1", &t);
    }
    char digest[GOLEM_DIGEST_HEX_CAPACITY];
    size_t required;
    if (s == GOLEM_OK)
        s = golem_digest_format(&h.receipt, digest, sizeof(digest), &required);
    if (s == GOLEM_OK)
        printf("{\"state\":%u,\"executions\":%u,\"receipt\":\"%s\"}\n", (unsigned)t.state,
               h.executions, digest);
    else
        fprintf(stderr, "%s\n", golem_status_string(s));
    golem_status closed = golem_admission_close(a);
    return s == GOLEM_OK && closed == GOLEM_OK ? 0 : 1;
}
