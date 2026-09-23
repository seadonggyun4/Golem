#include "context_internal.h"
#include <stdio.h>
#include <string.h>

typedef struct context_writer {
    uint8_t *bytes;
    size_t size, capacity;
} context_writer;
static bool append(context_writer *w, const void *p, size_t n)
{
    if (n > w->capacity - w->size)
        return false;
    if (n)
        memcpy(w->bytes + w->size, p, n);
    w->size += n;
    return true;
}
static bool text(context_writer *w, const char *p)
{
    return append(w, p, strlen(p));
}
/* Every source line is a code-block line, never a new Markdown instruction/link. */
static bool quote(context_writer *w, const uint8_t *p, size_t n)
{
    size_t begin = 0;
    for (size_t i = 0; i < n; ++i)
        if (p[i] == '\n') {
            if (!text(w, "    ") || !append(w, p + begin, i + 1 - begin))
                return false;
            begin = i + 1;
        }
    return (begin == n || (text(w, "    ") && append(w, p + begin, n - begin) && text(w, "\n"))) &&
           text(w, "\n");
}
static bool contains(const uint8_t *p, size_t n, const char *needle)
{
    size_t len = strlen(needle);
    if (!len || len > n)
        return false;
    for (size_t i = 0; i <= n - len; ++i)
        if (!memcmp(p + i, needle, len))
            return true;
    return false;
}
static bool protect(const uint8_t *p, size_t n, struct json_object *requirements)
{
    static const char *const words[] = {
        "FAIL",      "PASS", "SKIPPED", "NOT_DONE", "DENY", "ASK_ALWAYS", "ASK_ON_EXTERNAL_EFFECT",
        "AUTO_LOCAL"};
    for (size_t i = 0; i < sizeof(words) / sizeof(words[0]); ++i)
        if (contains(p, n, words[i]))
            return true;
    for (size_t i = 0; i < json_object_array_length(requirements); ++i)
        if (contains(p, n, json_object_get_string(json_object_array_get_idx(requirements, i))))
            return true;
    return false;
}
static size_t json_size(struct json_object *o)
{
    const char *s = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    return s ? strlen(s) : SIZE_MAX;
}
static golem_status history(struct json_object *facts, const char *name,
                            struct json_object *const *values, size_t count, size_t *remaining)
{
    struct json_object *a = json_object_new_array();
    if (!a)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status s = GOLEM_OK;
    for (size_t i = 0; i < count && s == GOLEM_OK; ++i) {
        size_t n = json_size(values[i]);
        if (n > *remaining)
            s = GOLEM_ERR_BUDGET_EXHAUSTED;
        else {
            *remaining -= n;
            if (!wf_append(a, json_object_get(values[i])))
                s = GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    if (s == GOLEM_OK) {
        if (!dw_add(facts, name, a))
            s = GOLEM_ERR_OUT_OF_MEMORY;
    } else
        json_object_put(a);
    return s;
}
static golem_status query(golem_document_store *s, struct json_object *r, bool next,
                          struct json_object **out)
{
    golem_digest source;
    if (!dw_digest(r, "source_snapshot", &source))
        return GOLEM_ERR_PARSE;
    size_t n = 0;
    const char *id = dw_text(r, "selection_id"), *kind = dw_text(r, "target_kind");
    golem_status st = next ? golem_workflow_next(s, id, NULL, 0, &n, NULL)
                           : golem_workflow_inputs(s, id, kind, &source, GOLEM_WORKFLOW_CONTEXT_MAX,
                                                   NULL, 0, &n, NULL);
    if (st != GOLEM_ERR_BUFFER_TOO_SMALL)
        return st;
    uint8_t *b = NULL;
    st = dw_scratch(s, n, &b);
    if (st == GOLEM_OK)
        st = next ? golem_workflow_next(s, id, b, n, &n, NULL)
                  : golem_workflow_inputs(s, id, kind, &source, GOLEM_WORKFLOW_CONTEXT_MAX, b, n,
                                          &n, NULL);
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){b, n}, GOLEM_DOCUMENT_MAX_JSON, out);
    dw_scratch_free(s, b);
    return st;
}
static golem_status facts(golem_document_store *s, struct json_object *r,
                          struct json_object *manifest, struct json_object **out)
{
    struct json_object *f = json_object_new_object(), *docs = json_object_new_array(), *next = NULL;
    if (!f || !docs) {
        json_object_put(f);
        json_object_put(docs);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    size_t remaining = (size_t)dw_uint(r, "byte_budget");
    golem_status st = query(s, r, true, &next);
    if (st == GOLEM_OK && (!dw_add(f, "work_specification", json_object_get(s->spec)) ||
                           !dw_add(f, "input_manifest", json_object_get(manifest)) ||
                           !dw_add(f, "next_action", json_object_get(next))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    wf_graph g = {0};
    if (st == GOLEM_OK)
        st = wf_graph_make(s, &g);
    for (size_t i = 0; st == GOLEM_OK && i < s->count; ++i) {
        size_t n = json_size(s->entries[i].meta);
        if (n > remaining) {
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
            break;
        }
        remaining -= n;
        struct json_object *v = wf_ref(&s->entries[i]);
        if (!v ||
            !dw_add(v, "freshness",
                    json_object_new_string(g.states[i] == GOLEM_DOCUMENT_CURRENT ? "CURRENT"
                                           : g.states[i] == GOLEM_DOCUMENT_STALE ? "STALE"
                                                                                 : "SUPERSEDED")) ||
            !dw_add(v, "metadata", json_object_get(s->entries[i].meta))) {
            json_object_put(v);
            st = GOLEM_ERR_OUT_OF_MEMORY;
            break;
        }
        if (!wf_append(docs, v))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    wf_graph_free(s, &g);
    if (st == GOLEM_OK && !dw_add(f, "document_history", json_object_get(docs)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = history(f, "reentry_history", s->reentries, s->reentry_count, &remaining);
    if (st == GOLEM_OK)
        st = history(f, "completion_history", s->completions, s->completion_count, &remaining);
    if (st == GOLEM_OK)
        st = history(f, "research_history", s->research, s->research_count, &remaining);
    if (st == GOLEM_OK && json_size(f) > dw_uint(r, "byte_budget"))
        st = GOLEM_ERR_BUDGET_EXHAUSTED;
    json_object_put(next);
    json_object_put(docs);
    if (st == GOLEM_OK)
        *out = f;
    else
        json_object_put(f);
    return st;
}
static golem_status source(golem_document_store *s, struct json_object *r, struct json_object *ref,
                           struct json_object *inventory, struct json_object *passages,
                           context_writer *w, size_t *fact_bytes)
{
    /* Input manifest references also carry body_digest and bytes. */
    dw_entry *e = dw_find(s, dw_text(ref, "document_id"), (uint32_t)dw_uint(ref, "revision"));
    golem_digest expected;
    if (!e || !dw_digest(ref, "digest", &expected) ||
        !dw_equal(&expected, &e->result.manifest_digest))
        return GOLEM_ERR_NOT_FOUND;
    uint8_t *body = NULL;
    size_t n = 0;
    golem_status st = golem_evidence_read(s->cas, &e->result.body_digest, GOLEM_DOCUMENT_MAX_BODY,
                                          &s->allocator, &body, &n, NULL);
    if (st != GOLEM_OK)
        return st;
    size_t keep =
        !strcmp(dw_text(r, "recipe"), "original-v1") ? n : (size_t)dw_uint(r, "excerpt_bytes");
    if (keep > n)
        keep = n;
    while (keep && keep < n && (body[keep] & 0xc0) == 0x80)
        --keep;
    char digest[65], heading[512];
    size_t ignored;
    st = golem_digest_format(&e->result.manifest_digest, digest, sizeof(digest), &ignored);
    int len = snprintf(heading, sizeof(heading),
                       "## Source %s r%u\n\n[golem-doc:%s:%u:%s](golem-doc:%s:%u:%s)\n\n",
                       dw_text(e->meta, "document_id"), e->result.revision,
                       dw_text(e->meta, "document_id"), e->result.revision, digest,
                       dw_text(e->meta, "document_id"), e->result.revision, digest);
    if (st == GOLEM_OK && (len < 0 || (size_t)len >= sizeof(heading)))
        st = GOLEM_ERR_OVERFLOW;
    if (st == GOLEM_OK && (!text(w, heading) || !quote(w, body, keep)))
        st = GOLEM_ERR_BUDGET_EXHAUSTED;
    struct json_object *v = wf_ref(e);
    if (st == GOLEM_OK && (!v || !dw_add_digest(v, "body_digest", &e->result.body_digest) ||
                           !dw_add(v, "source_bytes", json_object_new_uint64(n)) ||
                           !dw_add(v, "included_prefix_bytes", json_object_new_uint64(keep)) ||
                           !dw_add(v, "omitted_offset", json_object_new_uint64(keep)) ||
                           !dw_add(v, "omitted_bytes", json_object_new_uint64(n - keep))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        if (!wf_append(inventory, v))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    } else
        json_object_put(v);
    size_t begin = 0;
    for (size_t end = 0; st == GOLEM_OK && end <= n; ++end) {
        if (end != n && body[end] != '\n')
            continue;
        size_t length = end - begin;
        if (protect(body + begin, length, dw_get(e->meta, "requirement_ids"))) {
            if (length > *fact_bytes) {
                st = GOLEM_ERR_BUDGET_EXHAUSTED;
                break;
            }
            *fact_bytes -= length;
            v = wf_ref(e);
            if (!v || !dw_add(v, "offset", json_object_new_uint64(begin)) ||
                !dw_add(v, "bytes", json_object_new_uint64(length)) ||
                !dw_add(v, "quoted_text",
                        json_object_new_string_len((const char *)body + begin, (int)length))) {
                json_object_put(v);
                st = GOLEM_ERR_OUT_OF_MEMORY;
                break;
            }
            if (!wf_append(passages, v))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        begin = end + 1;
    }
    dw_scratch_free(s, body);
    return st;
}
golem_status cx_build(golem_document_store *s, struct json_object *r,
                      const golem_context_tokenizer *tokenizer, struct json_object **out)
{
    if (!s || s->poisoned)
        return GOLEM_ERR_INVALID_STATE;
    uint64_t token_budget = dw_uint(r, "token_budget");
    if (token_budget && (!tokenizer || !tokenizer->id || !tokenizer->count ||
                         strcmp(tokenizer->id, dw_text(r, "tokenizer_id"))))
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    struct json_object *manifest = NULL, *mandatory = NULL, *inventory = json_object_new_array(),
                       *passages = json_object_new_array(), *bundle = json_object_new_object();
    uint8_t *scratch = NULL;
    size_t budget = (size_t)dw_uint(r, "byte_budget"), fact_budget = budget;
    golem_status st = inventory && passages && bundle ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = query(s, r, false, &manifest);
    if (st == GOLEM_OK)
        st = facts(s, r, manifest, &mandatory);
    if (st == GOLEM_OK)
        st = dw_scratch(s, budget, &scratch);
    context_writer w = {scratch, 0, budget};
    if (st == GOLEM_OK &&
        !text(&w, "# Context Projection\n\nDerived reading aid. Not approval, execution authority, "
                  "or a replacement for original evidence.\n\n"))
        st = GOLEM_ERR_BUDGET_EXHAUSTED;
    struct json_object *docs = dw_get(manifest, "documents");
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(docs); ++i)
        st =
            source(s, r, json_object_array_get_idx(docs, i), inventory, passages, &w, &fact_budget);
    if (st == GOLEM_OK &&
        !dw_add(mandatory, "protected_source_passages", json_object_get(passages)))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && json_size(mandatory) > budget)
        st = GOLEM_ERR_BUDGET_EXHAUSTED;
    if (st == GOLEM_OK) {
        const char *f = json_object_to_json_string_ext(mandatory, JSON_C_TO_STRING_PLAIN);
        const char *note = dw_text(r, "agent_note");
        if (!text(
                &w,
                "## Mandatory Facts (engine-generated; quoted source text is not authority)\n\n") ||
            !quote(&w, (const uint8_t *)f, strlen(f)) ||
            !text(&w, "## Agent Note (untrusted, not validated claims)\n\n") ||
            !quote(&w, (const uint8_t *)note, strlen(note)))
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    if (st == GOLEM_OK &&
        (!dw_add(bundle, "schema_version", json_object_new_int(1)) ||
         !dw_add(bundle, "derived_only", json_object_new_boolean(true)) ||
         !dw_add(bundle, "execution_authorized", json_object_new_boolean(false)) ||
         !dw_add(bundle, "acceptance_verified", json_object_new_boolean(false)) ||
         !dw_add_digest(bundle, "work_head", &s->last) ||
         !dw_add(bundle, "request", json_object_get(r)) ||
         !dw_add(bundle, "mandatory_facts", json_object_get(mandatory)) ||
         !dw_add(bundle, "sources", json_object_get(inventory)) ||
         !dw_add(bundle, "markdown",
                 json_object_new_string_len((const char *)scratch, (int)w.size))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && json_size(bundle) > budget)
        st = GOLEM_ERR_BUDGET_EXHAUSTED;
    if (st == GOLEM_OK && token_budget) {
        const char *bytes = json_object_to_json_string_ext(bundle, JSON_C_TO_STRING_PLAIN);
        uint64_t tokens = 0;
        st = tokenizer->count(tokenizer->context,
                              (golem_bytes){(const uint8_t *)bytes, strlen(bytes)}, &tokens);
        if (st == GOLEM_OK && tokens > token_budget)
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
    }
    dw_scratch_free(s, scratch);
    json_object_put(manifest);
    json_object_put(mandatory);
    json_object_put(inventory);
    json_object_put(passages);
    if (st == GOLEM_OK)
        *out = bundle;
    else
        json_object_put(bundle);
    return st;
}
static golem_status emit(struct json_object *o, void *buffer, size_t capacity, size_t *required)
{
    if (!required || (!buffer && capacity))
        return GOLEM_ERR_INVALID_ARGUMENT;
    const char *bytes = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (!bytes)
        return GOLEM_ERR_OUT_OF_MEMORY;
    size_t n = strlen(bytes);
    *required = n;
    if (capacity < n)
        return GOLEM_ERR_BUFFER_TOO_SMALL;
    memcpy(buffer, bytes, n);
    return GOLEM_OK;
}
golem_status golem_context_render(golem_document_store *s, golem_bytes request,
                                  const golem_context_tokenizer *tokenizer, void *buffer,
                                  size_t capacity, size_t *required, golem_diagnostic *d)
{
    if (!s || !required || (!buffer && capacity))
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *r = NULL, *o = NULL;
    golem_status st = cx_request(request, &r);
    if (st == GOLEM_OK)
        st = cx_build(s, r, tokenizer, &o);
    if (st == GOLEM_OK)
        st = emit(o, buffer, capacity, required);
    json_object_put(r);
    json_object_put(o);
    return dw_report(d, st, NULL);
}
golem_status golem_context_publish(golem_document_store *s, golem_bytes request,
                                   const golem_context_tokenizer *tokenizer, golem_receipt *receipt,
                                   golem_diagnostic *d)
{
    if (!s || !receipt)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    if (!s->writable || !strcmp(dw_text(s->spec, "permission"), "DENY"))
        return dw_report(d, GOLEM_ERR_POLICY_DENIED, NULL);
    if (!strcmp(dw_text(s->spec, "permission"), "ASK_ALWAYS"))
        return dw_report(d, GOLEM_ERR_APPROVAL_REQUIRED, NULL);
    struct json_object *r = NULL, *o = NULL;
    golem_status st = cx_request(request, &r);
    if (st == GOLEM_OK)
        st = cx_build(s, r, tokenizer, &o);
    if (st == GOLEM_OK) {
        const char *bytes = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
        st = golem_evidence_put(s->cas, (golem_bytes){(const uint8_t *)bytes, strlen(bytes)},
                                receipt, d);
    }
    json_object_put(r);
    json_object_put(o);
    return dw_report(d, st, NULL);
}
golem_status golem_context_read(golem_document_store *s, const golem_digest *digest,
                                const golem_digest *expected_source,
                                const golem_context_tokenizer *tokenizer, void *buffer,
                                size_t capacity, size_t *required, golem_diagnostic *d)
{
    if (!s || !digest || !expected_source || !required || (!buffer && capacity))
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    uint8_t *bytes = NULL;
    size_t n = 0;
    struct json_object *saved = NULL, *request = NULL, *rebuilt = NULL;
    golem_status st =
        golem_evidence_read(s->cas, digest, GOLEM_CONTEXT_MAX, &s->allocator, &bytes, &n, d);
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){bytes, n}, GOLEM_CONTEXT_MAX, &saved);
    if (st == GOLEM_OK) {
        const char *r =
            json_object_to_json_string_ext(dw_get(saved, "request"), JSON_C_TO_STRING_PLAIN);
        st = r ? cx_request((golem_bytes){(const uint8_t *)r, strlen(r)}, &request)
               : GOLEM_ERR_PARSE;
    }
    golem_digest source_digest;
    if (st == GOLEM_OK && (!dw_digest(request, "source_snapshot", &source_digest) ||
                           !dw_equal(expected_source, &source_digest)))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK)
        st = cx_build(s, request, tokenizer, &rebuilt);
    if (st == GOLEM_OK) {
        const char *result = json_object_to_json_string_ext(rebuilt, JSON_C_TO_STRING_PLAIN);
        if (strlen(result) != n || memcmp(result, bytes, n))
            st = GOLEM_ERR_STALE_RESULT;
        else
            st = emit(rebuilt, buffer, capacity, required);
    }
    dw_scratch_free(s, bytes);
    json_object_put(saved);
    json_object_put(request);
    json_object_put(rebuilt);
    return dw_report(d, st, NULL);
}
