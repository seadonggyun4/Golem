#define _POSIX_C_SOURCE 200809L
#include "golem/admission.h"
#include "golem/candidate.h"
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
static golem_status deny_request(void *context, golem_bytes request)
{
    (void)context;
    (void)request;
    return GOLEM_ERR_APPROVAL_REQUIRED;
}
static golem_status deny_cancel(void *context, const char *candidate, const char *session)
{
    (void)context;
    (void)candidate;
    (void)session;
    return GOLEM_ERR_APPROVAL_REQUIRED;
}
/* Exercises only the trusted start connector, not approval or provider work. */
static golem_status current_start(host *h, golem_admission *admission,
                                  const golem_admission_ticket *ticket)
{
    golem_document_store *store = NULL;
    golem_status st = golem_document_store_open(h->work, true, NULL, &store, NULL);
    golem_workspace_host workspace = {0};
    golem_candidate_current_binding binding = {.candidate = "candidate-a",
                                               .session = "agent-a",
                                               .runtime_binding = ticket->request.runtime_binding,
                                               .member = {.work = store,
                                                          .workspace = &workspace,
                                                          .work_root = h->work,
                                                          .tree_root = "/",
                                                          .build_root = "/",
                                                          .temp_root = "/"}};
    golem_candidate_current_options options = {.size = sizeof(options),
                                               .version = 1,
                                               .bindings = &binding,
                                               .count = 1,
                                               .authorize = deny_request,
                                               .request_cancel = deny_cancel};
    golem_candidate_host connector;
    if (st == GOLEM_OK)
        st = golem_candidate_current_host(&options, &connector);
    if (st == GOLEM_OK &&
        connector.check(connector.context, (golem_bytes){NULL, 0}) != GOLEM_ERR_APPROVAL_REQUIRED)
        st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK)
        st = connector.start(connector.context, "candidate-a", admission, "bridge-1");
    if (st == GOLEM_OK && connector.start(connector.context, "candidate-a", admission,
                                          "bridge-1") != GOLEM_ERR_INVALID_STATE)
        st = GOLEM_ERR_INVALID_STATE;
    golem_admission_ticket current;
    if (st == GOLEM_OK)
        st = golem_admission_lookup(admission, "bridge-1", &current);
    if (st == GOLEM_OK)
        h->receipt = current.binding_receipt;
    golem_status closed = golem_document_store_close(store);
    return st == GOLEM_OK ? closed : st;
}
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
            s = !strcmp(h.mode, "current") ? current_start(&h, a, &t)
                                           : golem_admission_dispatch(a, t.token, &ops, &h);
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
