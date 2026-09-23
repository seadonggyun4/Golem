#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include "../agent_session/internal.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Escape authored prose as data; it cannot introduce Markdown headings/HTML. */
static void prose(FILE *f, const char *text)
{
    for (const unsigned char *p = (const unsigned char *)text; *p; ++p) {
        if (*p < 32 || *p == 127)
            fputc(' ', f);
        else {
            if (*p < 128 && ispunct(*p))
                fputc('\\', f);
            fputc(*p, f);
        }
    }
}
golem_status re_markdown(struct json_object *d, golem_execution_reply *out)
{
    char *data = NULL;
    size_t n = 0;
    FILE *f = open_memstream(&data, &n);
    if (!f)
        return GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *p = dw_get(d, "proposal");
    fprintf(f,
            "# Failure and Reentry %llu\n\n## Observation\n\nQA receipt: `%s`\n\nFailure "
            "signature: `%s`\n\nObserved source: `%s`\n\n",
            (unsigned long long)dw_uint(d, "sequence"), dw_text(d, "failure_receipt"),
            dw_text(d, "signature"), dw_text(d, "observed_source"));
    fprintf(f, "Overall QA: **%s**. Reason: `%s`.\n\n", dw_text(d, "qa_status"),
            dw_text(d, "qa_reason"));
    fputs("| Gate | Version | Status | Diagnostic |\n| --- | --- | --- | --- |\n", f);
    struct json_object *gates = dw_get(d, "observations");
    for (size_t i = 0; i < json_object_array_length(gates); ++i) {
        struct json_object *g = json_object_array_get_idx(gates, i);
        fprintf(f, "| %s | %llu | %s | %s |\n", dw_text(g, "gate_id"),
                (unsigned long long)dw_uint(g, "version"), dw_text(g, "status"),
                dw_text(g, "reason"));
    }
    fputc('\n', f);
    fprintf(
        f,
        "## Hypothesis\n\nClassification: %s. Confidence: %s (agent-declared, not calibrated).\n\n",
        dw_text(p, "classification"), dw_text(p, "confidence"));
    prose(f, dw_text(p, "hypothesis"));
    fputs("\n\n## Verification Method\n\n", f);
    prose(f, dw_text(p, "verification"));
    fprintf(f,
            "\n\n## Decision\n\nAction: **%s**. Target: `%s`. Reason: `%s`.\n\nExecution is not "
            "authorized by this report. Token/cost usage: UNKNOWN.\n\n",
            dw_text(d, "action"), dw_text(d, "target_kind"), dw_text(d, "reason"));
    const char *lists[] = {"invalidated", "reused"};
    const char *titles[] = {"Required Revisions", "Unchanged Inputs"};
    for (size_t j = 0; j < 2; ++j) {
        fprintf(f, "## %s\n\n", titles[j]);
        struct json_object *a = dw_get(d, lists[j]);
        if (!json_object_array_length(a))
            fputs("None.\n", f);
        for (size_t i = 0; i < json_object_array_length(a); ++i) {
            struct json_object *v = json_object_array_get_idx(a, i);
            fprintf(f, "- `%s` r%llu: `%s`\n", dw_text(v, "document_id"),
                    (unsigned long long)dw_uint(v, "revision"), dw_text(v, "digest"));
        }
        fputc('\n', f);
    }
    fputs("## Affected Requirements\n\n", f);
    struct json_object *a = dw_get(p, "affected_requirements");
    for (size_t i = 0; i < json_object_array_length(a); ++i)
        fprintf(f, "- `%s`\n", json_object_get_string(json_object_array_get_idx(a, i)));
    fputs("\n## Evidence\n\n", f);
    a = dw_get(p, "evidence_refs");
    for (size_t i = 0; i < json_object_array_length(a); ++i)
        fprintf(f, "- `%s`\n", json_object_get_string(json_object_array_get_idx(a, i)));
    fputs("\nOriginal revisions and QA results remain immutable. Dependency impact is structural, "
          "not a proven cause.\n",
          f);
    bool bad = ferror(f) != 0;
    if (fclose(f) != 0)
        bad = true;
    if (bad || n > GOLEM_DOCUMENT_MAX_BODY) {
        free(data);
        return bad ? GOLEM_ERR_IO : GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    *out = (golem_execution_reply){(uint8_t *)data, n};
    return GOLEM_OK;
}
golem_status re_apply(golem_document_store *s, struct json_object *event,
                      const golem_digest *payload, const golem_digest *frame)
{
    const char *keys[] = {"schema_version", "type", "request", "decision", "report_digest"};
    if (!dw_keys(event, keys, 5) || dw_uint(event, "schema_version") != 1 ||
        strcmp(dw_text(event, "type"), "reentry") || s->reentry_count >= RE_MAX_EVENTS)
        return GOLEM_ERR_CORRUPT_JOURNAL;
    struct json_object *d = dw_get(event, "decision"), *expected = NULL;
    golem_digest boot, report;
    if (!dw_digest(d, "boot", &boot) || !dw_digest(event, "report_digest", &report))
        return GOLEM_ERR_PARSE;
    golem_status st =
        re_decide(s, dw_get(event, "request"), dw_uint(d, "observed_ms"), &boot, &expected);
    if (st == GOLEM_OK && !json_object_equal(d, expected))
        st = GOLEM_ERR_CORRUPT_JOURNAL;
    golem_execution_reply md = {0};
    golem_digest digest;
    uint64_t size;
    if (st == GOLEM_OK)
        st = re_markdown(d, &md);
    if (st == GOLEM_OK)
        st = golem_digest_bytes((golem_bytes){md.data, md.size}, &digest);
    if (st == GOLEM_OK && !dw_equal(&digest, &report))
        st = GOLEM_ERR_DIGEST_MISMATCH;
    if (st == GOLEM_OK)
        st = golem_evidence_verify(s->cas, &report, &size, NULL);
    if (st == GOLEM_OK) {
        s->reentries[s->reentry_count] = json_object_get(event);
        s->reentry_digests[s->reentry_count++] = *payload;
        s->last = *frame;
        ++s->event_count;
    }
    golem_execution_reply_free(&md);
    json_object_put(expected);
    return st;
}
static golem_status reply(golem_document_store *s, size_t index, golem_execution_reply *out)
{
    struct json_object *o = json_object_new_object();
    golem_status st = GOLEM_OK;
    if (!ex_uint(o, "sequence", s->reentry_count) ||
        !dw_add_digest(o, "decision_digest", &s->reentry_digests[index]) ||
        !dw_add(o, "record", json_object_get(s->reentries[index])))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = ex_emit(o, out);
    json_object_put(o);
    return st;
}
golem_status golem_reentry_call(golem_document_store *s, golem_bytes b, golem_execution_reply *out,
                                golem_diagnostic *d)
{
    if (!s || !out || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *r = NULL, *decision = NULL, *event = NULL;
    golem_status st = golem_json_parse(b, GOLEM_DOCUMENT_MAX_JSON, &r);
    if (st == GOLEM_OK)
        st = re_validate(r);
    bool status = !strcmp(dw_text(r, "operation"), "status");
    if (st == GOLEM_OK && status) {
        if (s->reentry_count)
            st = reply(s, s->reentry_count - 1, out);
        else {
            struct json_object *o = json_object_new_object();
            if (!ex_uint(o, "sequence", 0))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK)
                st = ex_emit(o, out);
            json_object_put(o);
        }
        json_object_put(r);
        return dw_report(d, st, NULL);
    }
    for (size_t i = 0; st == GOLEM_OK && i < s->reentry_count; ++i) {
        struct json_object *old = dw_get(s->reentries[i], "request");
        if (strcmp(dw_text(old, "key"), dw_text(r, "key")))
            continue;
        st = json_object_equal(old, r) ? reply(s, i, out) : GOLEM_ERR_IDENTITY_MISMATCH;
        json_object_put(r);
        return dw_report(d, st, NULL);
    }
    if (st == GOLEM_OK && (!s->writable || !strcmp(dw_text(s->spec, "permission"), "DENY")))
        st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK && !strcmp(dw_text(s->spec, "permission"), "ASK_ALWAYS"))
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    as_log log = {.directory = -1};
    if (st == GOLEM_OK)
        st = as_load(s, NULL, NULL, &log);
    if (st == GOLEM_OK && as_active(log.state))
        st = GOLEM_ERR_JOURNAL_BUSY;
    as_close(&log);
    uint64_t now = 0;
    golem_digest boot;
    if (st == GOLEM_OK)
        st = as_clock_read(NULL, &now, &boot);
    if (st == GOLEM_OK)
        st = re_decide(s, r, now, &boot, &decision);
    golem_execution_reply md = {0};
    golem_receipt receipt;
    golem_digest payload, frame;
    if (st == GOLEM_OK)
        st = re_markdown(decision, &md);
    if (st == GOLEM_OK)
        st = golem_evidence_put(s->cas, (golem_bytes){md.data, md.size}, &receipt, NULL);
    if (st == GOLEM_OK) {
        event = json_object_new_object();
        if (!ex_uint(event, "schema_version", 1) || !ex_text(event, "type", "reentry") ||
            !dw_add(event, "request", json_object_get(r)) ||
            !dw_add(event, "decision", json_object_get(decision)) ||
            !dw_add_digest(event, "report_digest", &receipt.digest))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_execution_reply encoded = {0};
    if (st == GOLEM_OK)
        st = ex_emit(event, &encoded);
    golem_execution_reply_free(&encoded);
    if (st == GOLEM_OK)
        st = dw_put_json(s, event, &payload);
    if (st == GOLEM_OK)
        st = dw_event_write(s, &payload, &frame);
    if (st == GOLEM_OK) {
        /* All allocations precede commit; in-memory adoption cannot fail. */
        s->reentries[s->reentry_count] = json_object_get(event);
        s->reentry_digests[s->reentry_count++] = payload;
        s->last = frame;
        ++s->event_count;
        st = reply(s, s->reentry_count - 1, out);
    }
    if (st == GOLEM_ERR_IO)
        s->poisoned = true;
    golem_execution_reply_free(&md);
    json_object_put(r);
    json_object_put(decision);
    json_object_put(event);
    return dw_report(d, st, NULL);
}
golem_status golem_reentry_report(golem_document_store *s, uint32_t sequence, bool project,
                                  golem_execution_reply *out, golem_diagnostic *d)
{
    if (!s || !out || !sequence || sequence > s->reentry_count || s->poisoned)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (project && !s->writable)
        return dw_report(d, GOLEM_ERR_POLICY_DENIED, NULL);
    struct json_object *event = s->reentries[sequence - 1];
    golem_digest digest;
    if (!dw_digest(event, "report_digest", &digest))
        return dw_report(d, GOLEM_ERR_PARSE, NULL);
    uint8_t *bytes = NULL;
    size_t n = 0;
    int dir = -1;
    golem_status st =
        golem_evidence_read(s->cas, &digest, GOLEM_DOCUMENT_MAX_BODY, NULL, &bytes, &n, NULL);
    if (st == GOLEM_OK && project)
        st = dw_dir(s->root, "failures", true, &dir);
    if (st == GOLEM_OK && project) {
        char name[32];
        (void)snprintf(name, sizeof(name), "r%04u.md", sequence);
        st = dw_publish(dir, name, (golem_bytes){bytes, n});
    }
    if (dir >= 0)
        close(dir);
    if (st == GOLEM_OK)
        *out = (golem_execution_reply){bytes, n};
    else
        free(bytes);
    return dw_report(d, st, NULL);
}
