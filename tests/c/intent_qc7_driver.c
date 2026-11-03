/* Test-only native integration adapter. Never installed or used by MCP.
 * No predicate/approval stubs: only publication syscalls are intercepted.
 * Caller must hold its disposable D01 fixture flock before entering this process. */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "../../src/intent/qa_result.h"
#include "../../src/document/internal.h"
#include "../../src/execution/internal.h"
#include "golem/completion.h"
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
void qc7_completion_fault(const char *);
/* Committed payloads only; a pending journal is never traversed/repaired. */
static golem_status schema_payload(void *ctx, const golem_digest *op, const golem_digest *request,
                                   const gi_journal_operation *record, golem_bytes bytes)
{
    (void)op;
    (void)request;
    (void)record;
    struct json_object *value = NULL;
    golem_status st = golem_json_parse(bytes, GI_DISPATCH_MAX, &value);
    if (st != GOLEM_OK)
        return GOLEM_OK; /* Older opaque payload: no JSON shape claim. */
    if (json_object_array_add(ctx, value) != 0) {
        json_object_put(value);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    return GOLEM_OK;
}
static const char *fault = "";
static unsigned appends;
static void die_at(const char *point)
{
    if (!strcmp(fault, point))
        _exit(77);
}
typedef struct pending_guard {
    gi_journal_guard next;
    void *context;
    unsigned calls;
} pending_guard;
static golem_status pending_fault(void *opaque)
{
    pending_guard *g = opaque;
    golem_status st = g->next(g->context);
    ++g->calls;
    if (st == GOLEM_OK && g->calls == 2)
        die_at(appends == 1 ? "prepared-pending-crash" : "accepted-pending-crash");
    return st;
}
static golem_status append_fault(gi_journal *j, gi_quota_lane lane, const golem_digest *op,
                                 const golem_digest *req, uint64_t seq, const golem_digest *head,
                                 golem_bytes payload, gi_journal_guard guard, void *ctx,
                                 gi_journal_receipt *out)
{
    ++appends;
    die_at(appends == 1 ? "before-prepared" : "before-accepted");
    if (!strcmp(fault, appends == 1 ? "prepared-io" : "accepted-io"))
        return GOLEM_ERR_IO;
    pending_guard pg = {guard, ctx, 0};
    golem_status st =
        gi_journal_append(j, lane, op, req, seq, head, payload, pending_fault, &pg, out);
    if (st == GOLEM_OK)
        die_at(appends == 1 ? "after-prepared" : "after-accepted");
    return st;
}
static golem_status event_fault(golem_document_store *s, const golem_digest *p, golem_digest *f,
                                gi_journal_guard guard, void *ctx)
{
    die_at("before-observation");
    if (!strcmp(fault, "observation-io"))
        return GOLEM_ERR_IO;
    golem_status st = dw_event_write_guarded(s, p, f, guard, ctx);
    if (st == GOLEM_OK)
        die_at("after-observation");
    return st;
}
/* Same implementation as library, with test-local publication boundaries. */
#define gi_journal_append append_fault
#define dw_event_write_guarded event_fault
#include "../../src/intent/qa_acceptance.c"
#undef gi_journal_append
#undef dw_event_write_guarded
static golem_bytes text_at(struct json_object *o, const char *k)
{
    struct json_object *v = dw_get(o, k);
    return (golem_bytes){(const uint8_t *)json_object_get_string(v),
                         (size_t)json_object_get_string_len(v)};
}
static golem_status observed(void *ctx, golem_digest *r, golem_digest *p, golem_digest *b,
                             uint64_t *now)
{
    struct json_object *i = ctx;
    *now = 110;
    return dw_digest(i, "registration", r) && dw_digest(i, "policy_pin", p) &&
                   dw_digest(i, "bundle_pin", b)
               ? GOLEM_OK
               : GOLEM_ERR_PARSE;
}
static golem_status fixture_guard(void *ctx)
{
    int fd = *(int *)ctx;
    struct stat sb;
    return fstat(fd, &sb) == 0 && S_ISDIR(sb.st_mode) && sb.st_uid == geteuid() &&
                   !(sb.st_mode & 077)
               ? GOLEM_OK
               : GOLEM_ERR_POLICY_DENIED;
}
static golem_status inputs(struct json_object *i, gi_review_inputs *in, gi_source_input *source,
                           golem_bytes *definition)
{
    *source = (gi_source_input){text_at(i, "source"), text_at(i, "text")};
    *definition = text_at(i, "definition");
    *in = (gi_review_inputs){text_at(i, "baseline"), source, 1, definition, 1};
    gi_review_binding b;
    return gi_review_bind(in, &b, NULL);
}
int main(int argc, char **argv)
{
    if (argc != 2)
        return 2;
    fault = argv[1];
    qc7_completion_fault(fault);
    char *buf = malloc(GI_DISPATCH_MAX + 1);
    if (!buf)
        return 2;
    size_t n = fread(buf, 1, GI_DISPATCH_MAX + 1, stdin);
    struct json_object *i = NULL, *out = NULL;
    golem_status st = n <= GI_DISPATCH_MAX
                          ? golem_json_parse((golem_bytes){(uint8_t *)buf, n}, GI_DISPATCH_MAX, &i)
                          : GOLEM_ERR_OVERFLOW;
    const char *op = dw_text(i, "op");
    golem_digest d = {0};
    if (st == GOLEM_OK && !strcmp(op, "digest")) {
        const char *kind = dw_text(i, "kind");
        golem_bytes bytes = text_at(i, "bytes");
        if (!strcmp(kind, "domain"))
            st = gi_domain_digest(bytes, &d, NULL);
        else if (!strcmp(kind, "contract"))
            st = golem_execution_contract_validate(bytes, &d, NULL);
        else if (!strcmp(kind, "source"))
            st = gi_source_identity(bytes, text_at(i, "text"), &d, NULL);
        else {
            struct json_object *o = NULL;
            st = golem_json_parse(bytes, GI_DISPATCH_MAX, &o);
            if (st == GOLEM_OK)
                st = ex_hash(o, &d);
            json_object_put(o);
        }
        out = json_object_new_object();
        if (st == GOLEM_OK && !dw_add_digest(out, "digest", &d))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    } else if (st == GOLEM_OK) {
        int fd = open(dw_text(i, "authority"), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
        if (fd < 0)
            st = GOLEM_ERR_IO;
        else
            st = fixture_guard(&fd);
        gi_journal *j = NULL;
        golem_document_store *s = NULL;
        gi_review_host *h = NULL;
        gi_product_access *access = NULL;
        gi_source_input source;
        golem_bytes definition;
        gi_review_inputs in;
        gi_review_binding bound;
        golem_digest bo, br, operation, head, registration, pp, bp;
        gi_journal_receipt receipt;
        gi_journal_status js;
        golem_execution_reply reply = {0};
        if (st == GOLEM_OK && strcmp(op, "snapshot") && strcmp(op, "hold") &&
            strcmp(op, "hold-authority"))
            st = inputs(i, &in, &source, &definition);
        if (st == GOLEM_OK && strcmp(op, "snapshot") && strcmp(op, "hold") &&
            strcmp(op, "hold-authority"))
            st = gi_review_bind(&in, &bound, NULL);
        if (st == GOLEM_OK &&
            (!dw_digest(i, "baseline_operation", &bo) || !dw_digest(i, "baseline_request", &br)))
            st = GOLEM_ERR_PARSE;
        if (st == GOLEM_OK && strcmp(op, "baseline") && strcmp(op, "review") &&
            strcmp(op, "review-state"))
            st = golem_document_store_open(dw_text(i, "work"), true, NULL, &s, NULL);
        if (st == GOLEM_OK &&
            (!strcmp(op, "baseline") || !strcmp(op, "review") || !strcmp(op, "snapshot") ||
             !strcmp(op, "review-state") || !strcmp(op, "hold-authority")))
            st = gi_journal_open(fd, &j);
        if (st == GOLEM_OK && j)
            st = gi_journal_inspect(j, &js);
        if (st == GOLEM_OK && (!strcmp(op, "hold") || !strcmp(op, "hold-authority"))) {
            /* Native Work lock held; release pipe belongs only to this test process. */
            puts("READY");
            fflush(stdout);
            char token;
            if (read((int)dw_uint(i, "release_fd"), &token, 1) != 1)
                st = GOLEM_ERR_IO;
        } else if (st == GOLEM_OK && !strcmp(op, "review-state")) {
            out = json_object_new_object();
            dw_add_digest(out, "authority_head", &js.head);
            dw_add(out, "authority_sequence", json_object_new_uint64(js.committed));
        } else if (st == GOLEM_OK && !strcmp(op, "snapshot")) {
            out = json_object_new_object();
            dw_add_digest(out, "work_head", &s->last);
            dw_add(out, "work_sequence", json_object_new_uint64(s->event_count));
            dw_add_digest(out, "authority_head", &js.head);
            dw_add(out, "authority_sequence", json_object_new_uint64(js.committed));
            dw_add(out, "pending", json_object_new_boolean(js.pending));
            ex_hash(s->spec, &d);
            dw_add_digest(out, "work_spec", &d);
            dw_add(out, "observations", json_object_new_uint64(s->intent_qa_count));
            dw_add(out, "completions", json_object_new_uint64(s->completion_count));
            struct json_object *events = json_object_new_array(),
                               *payloads = json_object_new_array();
            if (!events || !payloads) {
                json_object_put(events);
                json_object_put(payloads);
                st = GOLEM_ERR_OUT_OF_MEMORY;
            } else {
                for (size_t k = 0; k < s->intent_qa_count; ++k)
                    if (json_object_array_add(events, json_object_get(s->intent_qa[k])) != 0)
                        st = GOLEM_ERR_OUT_OF_MEMORY;
                if (st == GOLEM_OK && !js.pending)
                    st = gi_journal_visit_payloads(j, schema_payload, payloads);
                dw_add(out, "intent_observation_events", events);
                dw_add(out, "authority_payloads", payloads);
                dw_add(out, "authority_payload_status",
                       json_object_new_string(js.pending ? "NOT_RUN_PENDING" : "OBSERVED"));
                if (s->intent_enrollment)
                    dw_add(out, "intent_enrollment_event", json_object_get(s->intent_enrollment));
            }
            if (s->intent_qa_count)
                dw_add_digest(out, "observation", &s->intent_qa_frames[s->intent_qa_count - 1]);
        } else if (st == GOLEM_OK && !strcmp(op, "baseline")) {
            golem_digest zero = {{0}};
            st = gi_journal_store_objects(j, &bo, &br, 0, &zero, in.baseline, &source, 1,
                                          fixture_guard, &fd, &receipt);
            out = json_object_new_object();
            dw_add_digest(out, "definitions", &bound.definitions);
        } else if (st == GOLEM_OK) {
            if (!dw_digest(i, "registration", &registration) || !dw_digest(i, "policy_pin", &pp) ||
                !dw_digest(i, "bundle_pin", &bp))
                st = GOLEM_ERR_PARSE;
            if (st == GOLEM_OK)
                st = gi_review_host_open(text_at(i, "policy"), &pp, text_at(i, "bundle"), &bp,
                                         text_at(i, "control"), &registration, observed, i, &h);
            if (st == GOLEM_OK && !strcmp(op, "review")) {
                if (!dw_digest(i, "operation", &operation))
                    st = GOLEM_ERR_PARSE;
                if (st == GOLEM_OK)
                    st = gi_review_host_publish(h, j, &bo, &br, &bound.baseline, &definition, 1,
                                                &operation, js.committed, &js.head, &receipt);
            } else if (st == GOLEM_OK && !strcmp(op, "enroll")) {
                struct json_object *e = NULL;
                golem_bytes bytes = text_at(i, "enrollment");
                st = golem_json_parse(bytes, GI_CONTROL_MAX, &e);
                if (st == GOLEM_OK &&
                    (!dw_digest(i, "operation", &operation) ||
                     !dw_digest(i, "authority_head", &head) || !dw_digest(i, "approval", &d)))
                    st = GOLEM_ERR_PARSE;
                if (st == GOLEM_OK)
                    st = gi_product_enroll(s, fd, &in, bytes, &d, &bo, &br, &operation,
                                           dw_uint(i, "authority_sequence"), &head, s->event_count,
                                           &s->last, gi_review_host_guard, h, &receipt);
                json_object_put(e);
            } else if (st == GOLEM_OK && !strcmp(op, "enrollment-digest")) {
                golem_digest request;
                st = golem_digest_bytes(text_at(i, "enrollment"), &request);
                if (st == GOLEM_OK && (!dw_digest(i, "operation", &operation) ||
                                       !dw_digest(i, "authority_head", &head)))
                    st = GOLEM_ERR_PARSE;
                if (st == GOLEM_OK)
                    st = gi_product_enrollment_approval(s, &request, &bo, &br, &operation,
                                                        dw_uint(i, "authority_sequence"), &head,
                                                        s->event_count, &s->last, &d);
                out = json_object_new_object();
                dw_add_digest(out, "digest", &d);
            } else if (st == GOLEM_OK && !strcmp(op, "native-inputs")) {
                struct json_object *contract = NULL;
                st = golem_json_parse(text_at(i, "contract"), GI_CONTROL_MAX, &contract);
                if (st == GOLEM_OK)
                    st = ex_inputs(s, contract, dw_text(i, "input_kind"), &out);
                json_object_put(contract);
            } else if (st == GOLEM_OK) {
                st = gi_product_access_open(s, fd, h, text_at(i, "control"), text_at(i, "material"),
                                            &access);
                if (st == GOLEM_OK) {
                    golem_bytes request = text_at(i, "request");
                    if (!strcmp(op, "execution")) {
                        if (!dw_digest(i, "approval", &d))
                            st = GOLEM_ERR_PARSE;
                        else
                            st = golem_execution_call(s, request, &d, &reply, NULL);
                    } else if (!strcmp(op, "accept"))
                        st = gi_qa_accept(s, request, &reply);
                    else if (!strcmp(op, "current"))
                        st = gi_qa_current(s, &reply);
                    else if (!strcmp(op, "assess"))
                        st = gi_qa_assess(s, request, &reply);
                    else if (!strcmp(op, "completion"))
                        st = golem_completion_call(s, request, &reply, NULL);
                    else
                        st = GOLEM_ERR_INVALID_ARGUMENT;
                }
            }
        }
        gi_journal_close(j);
        gi_product_access_close(access);
        golem_status closed = golem_document_store_close(s);
        if (st == GOLEM_OK)
            st = closed;
        gi_review_host_close(h);
        if (fd >= 0)
            close(fd);
        if (st == GOLEM_OK && reply.data)
            st = golem_json_parse((golem_bytes){reply.data, reply.size}, GI_DISPATCH_MAX, &out);
        golem_execution_reply_free(&reply);
    }
    if (st == GOLEM_OK) {
        die_at("response-lost");
        puts(out ? json_object_to_json_string_ext(out, JSON_C_TO_STRING_PLAIN) : "{}");
    } else
        fprintf(stderr, "qc7 native status=%s\n", golem_status_string(st));
    json_object_put(out);
    json_object_put(i);
    free(buf);
    return st == GOLEM_OK ? 0 : 1;
}
