#include "review.h"
#include "../common/json.h"
#include "../document/internal.h"
#include <stdlib.h>
#include <string.h>

static bool eq(struct json_object *o, const char *key, const char *value)
{ return json_object_is_type(dw_get(o, key), json_type_string) && !strcmp(dw_text(o, key), value); }
static bool text(struct json_object *o, const char *key)
{
    struct json_object *v = dw_get(o, key);
    return json_object_is_type(v, json_type_string) && json_object_get_string_len(v) > 0 &&
        json_object_get_string_len(v) <= 4096;
}
static bool array(struct json_object *v, size_t min, size_t max)
{ return json_object_is_type(v, json_type_array) && json_object_array_length(v) >= min && json_object_array_length(v) <= max; }
static bool same(const golem_digest *a, const golem_digest *b)
{ return !memcmp(a->bytes, b->bytes, sizeof(a->bytes)); }
static bool uint_field(struct json_object *o, const char *key, uint64_t *n)
{
    struct json_object *v = dw_get(o, key);
    if (!json_object_is_type(v, json_type_int) || json_object_get_int64(v) < 0) return false;
    *n = json_object_get_uint64(v); return true;
}
static bool dig(struct json_object *v, golem_digest *out)
{
    return json_object_is_type(v, json_type_string) && json_object_get_string_len(v) == 64 &&
        golem_digest_parse((golem_string_view){json_object_get_string(v), 64}, out) == GOLEM_OK;
}
static bool strings(struct json_object *v, size_t min, bool digest)
{
    if (!array(v, min, GI_PARENT_MAX)) return false;
    for (size_t i = 0; i < json_object_array_length(v); ++i) {
        struct json_object *s = json_object_array_get_idx(v, i); golem_digest d;
        if (digest ? !dig(s, &d) : (!json_object_is_type(s, json_type_string) ||
            json_object_get_string_len(s) < 1 || json_object_get_string_len(s) > 4096)) return false;
        for (size_t j = 0; j < i; ++j)
            if (json_object_equal(s, json_object_array_get_idx(v, j))) return false;
    }
    return true;
}
static golem_status definition(const gi_review_inputs *in, struct json_object *base,
    size_t index, golem_digest *digest, struct json_object *ids)
{
    struct json_object *o = NULL;
    golem_status st = golem_json_parse(in->definitions[index], GI_CONTROL_MAX, &o);
    if (st != GOLEM_OK) return st;
    struct json_object *body = dw_get(o, "body"), *bb = dw_get(base, "body");
    size_t nr = json_object_array_length(dw_get(bb, "requirement_refs"));
    bool constraint = index >= nr;
    const char *root[] = {"schema", "project_id", "work_id", "created_by_assertion", "body"};
    const char *keys[] = {"id", "exact_text", "source_spans", "modality", "quantifier", "negative",
        "conditions", "acceptance_oracle_refs", "derivation_rationale", "scope", "applies_to", "exclusions"};
    st = GOLEM_ERR_PARSE;
    if (!dw_keys(o, root, 5) || !eq(o, "schema", constraint ? "golem.intent.constraint.v1" : "golem.intent.requirement.v1") ||
        !json_object_equal(dw_get(o, "project_id"), dw_get(base, "project_id")) ||
        !json_object_equal(dw_get(o, "work_id"), dw_get(base, "work_id")) || !text(o, "created_by_assertion") ||
        !dw_keys(body, keys, constraint ? 12 : 9) || !dw_id(dw_text(body, "id")) ||
        !text(body, "exact_text") || !text(body, "modality") || !text(body, "quantifier") ||
        !json_object_is_type(dw_get(body, "negative"), json_type_boolean) ||
        !strings(dw_get(body, "conditions"), 0, false) || !strings(dw_get(body, "acceptance_oracle_refs"), 0, true) ||
        !text(body, "derivation_rationale") || !array(dw_get(body, "source_spans"), 1, GI_PARENT_MAX)) goto done;
    if (constraint && ((!eq(body, "scope", "LOCAL") && !eq(body, "scope", "GLOBAL") && !eq(body, "scope", "UNSCOPED")) ||
        !strings(dw_get(body, "applies_to"), 0, false) || !strings(dw_get(body, "exclusions"), 0, false))) goto done;
    if (json_object_object_get_ex(ids, dw_text(body, "id"), NULL)) goto done;
    if (json_object_object_add(ids, dw_text(body, "id"), NULL)) { st = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    st = gi_domain_digest(in->definitions[index], digest, NULL);
    golem_digest expected;
    struct json_object *refs = dw_get(bb, constraint ? "constraint_refs" : "requirement_refs");
    if (st == GOLEM_OK && (!dig(json_object_array_get_idx(refs, constraint ? index - nr : index), &expected) ||
        !same(digest, &expected))) st = GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *spans = dw_get(body, "source_spans");
    for (size_t k = 0; st == GOLEM_OK && k < json_object_array_length(spans); ++k) {
        struct json_object *span = json_object_array_get_idx(spans, k);
        const char *sk[] = {"source_ref", "start", "end"};
        uint64_t start, end; golem_digest source;
        if (!dw_keys(span, sk, 3) || !dw_digest(span, "source_ref", &source) ||
            !uint_field(span, "start", &start) || !uint_field(span, "end", &end) || start >= end || end > SIZE_MAX) {
            st = GOLEM_ERR_PARSE; break;
        }
        for (size_t j = 0; j < k; ++j)
            if (json_object_equal(span, json_object_array_get_idx(spans, j))) st = GOLEM_ERR_PARSE;
        bool found = false;
        for (size_t j = 0; st == GOLEM_OK && j < in->source_count; ++j) {
            golem_digest source_id;
            st = gi_source_identity(in->sources[j].control, in->sources[j].text, &source_id, NULL);
            if (st != GOLEM_OK || !same(&source, &source_id)) continue;
            found = true;
            st = gi_span_validate(in->sources[j].text, (gi_span){(size_t)start, (size_t)end}, NULL);
            /* Every cited byte must be inside approved designation. Existing
             * coverage rows already cover designation, so require containment
             * in rows explicitly linking this exact definition. */
            struct json_object *manifest = dw_get(bb, "coverage_manifest");
            uint64_t cursor = start;
            while (st == GOLEM_OK && cursor < end) {
                uint64_t next = cursor;
                for (size_t m = 0; m < json_object_array_length(manifest); ++m) {
                    struct json_object *entry = json_object_array_get_idx(manifest, m); golem_digest sid;
                    if (!dw_digest(entry, "source_ref", &sid) || !same(&sid, &source)) continue;
                    struct json_object *rows = dw_get(entry, "rows");
                    for (size_t r = 0; r < json_object_array_length(rows); ++r) {
                        struct json_object *row = json_object_array_get_idx(rows, r);
                        uint64_t a = dw_uint(row, "start"), b = dw_uint(row, "end");
                        struct json_object *rr = dw_get(row, constraint ? "constraint_refs" : "requirement_refs");
                        for (size_t z = 0; a <= cursor && b > next && z < json_object_array_length(rr); ++z) {
                            golem_digest id;
                            if (dig(json_object_array_get_idx(rr, z), &id) && same(&id, digest)) next = b;
                        }
                    }
                }
                if (next == cursor) st = GOLEM_ERR_REQUIREMENTS_UNMET;
                cursor = next;
            }
        }
        if (st == GOLEM_OK && !found) st = GOLEM_ERR_NOT_FOUND;
    }
done:
    json_object_put(o); return st;
}
golem_status gi_review_bind(const gi_review_inputs *in, gi_review_binding *out, golem_diagnostic *d)
{
    if (!in || !out || (in->definition_count && !in->definitions)) return GOLEM_ERR_INVALID_ARGUMENT;
    gi_baseline_coverage_result coverage;
    golem_status st = gi_baseline_coverage_validate(in->baseline, in->sources, in->source_count, &coverage, d);
    if (st != GOLEM_OK) return st;
    if (coverage.baseline.requirements + coverage.baseline.constraints != in->definition_count ||
        !in->definition_count || in->definition_count > 256) return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *base = NULL, *ids = json_object_new_object();
    if (!ids) return GOLEM_ERR_OUT_OF_MEMORY;
    st = golem_json_parse(in->baseline, GI_CONTROL_MAX, &base);
    golem_digest *digests = calloc(in->definition_count, sizeof(*digests));
    if (!digests) st = GOLEM_ERR_OUT_OF_MEMORY;
    gi_review_binding result = {0};
    for (size_t i = 0; st == GOLEM_OK && i < in->definition_count; ++i)
        st = definition(in, base, i, &digests[i], ids);
    if (st == GOLEM_OK) st = gi_baseline_identity(in->baseline, &result.baseline, d);
    /* Fixed-size ordered digests; baseline fixes membership and order. */
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){(uint8_t *)digests,
        in->definition_count * sizeof(*digests)}, &result.definitions);
    if (st == GOLEM_OK) {
        result.requirements = coverage.baseline.requirements; result.constraints = coverage.baseline.constraints;
        result.has_questions = coverage.baseline.has_questions; *out = result;
    }
    free(digests); json_object_put(base); json_object_put(ids); return st;
}

struct gi_review_state {
    gi_review_binding binding;
    gi_review_stage_status stages[7];
    struct json_object *base;
    uint64_t epoch;
    bool active, reviewed, busy;
    golem_digest review, activation_decision;
    char producer[GOLEM_DOCUMENT_ID_CAPACITY], reviewer[GOLEM_DOCUMENT_ID_CAPACITY];
    struct { golem_digest id, answer; bool answered; } questions[GI_OBLIGATION_MAX];
    size_t count, question_history_count, answer_history_count;
    golem_digest question_history[GI_OBLIGATION_MAX], answer_history[GI_OBLIGATION_MAX];
};
golem_status gi_review_create(const gi_review_inputs *in, gi_review_state **out)
{
    if (!out) return GOLEM_ERR_INVALID_ARGUMENT;
    gi_review_state *s = calloc(1, sizeof(*s)); if (!s) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = gi_review_bind(in, &s->binding, NULL);
    if (st == GOLEM_OK) st = golem_json_parse(in->baseline, GI_CONTROL_MAX, &s->base);
    /* Coverage questions become an unavoidable baseline-scoped obligation.
     * A trusted resolution review must explicitly cover all QUESTION_REQUIRED
     * spans; its closure does not modify the immutable source classification. */
    if (st == GOLEM_OK && s->binding.has_questions) {
        s->questions[0].id = s->binding.baseline; s->count = 1;
        s->question_history[0] = s->binding.baseline; s->question_history_count = 1;
    }
    if (st == GOLEM_OK) *out = s; else gi_review_free(s);
    return st;
}
void gi_review_free(gi_review_state *s)
{ if (s) { json_object_put(s->base); free(s); } }
golem_status gi_review_inspect(const gi_review_state *s, gi_review_status *out)
{
    if (!s || !out || s->busy) return GOLEM_ERR_INVALID_ARGUMENT;
    *out = (gi_review_status){s->epoch, s->count, s->active, s->reviewed, false, false, s->activation_decision}; return GOLEM_OK;
}
static const char *const stages[] = {"REQUIREMENTS", "DESIGN", "TASK_DECOMPOSITION", "IMPLEMENTATION",
    "TEST_DESIGN", "INTEGRATION", "FINAL_VALIDATION"};
static golem_status authorize(gi_review_state *s, gi_review_authorize fn, void *ctx,
    gi_review_purpose purpose, const golem_digest *evidence, const char *producer, const char *reviewer)
{
    return fn(ctx, purpose, &s->binding.baseline, evidence, dw_text(s->base, "project_id"),
        dw_text(s->base, "work_id"), producer, reviewer);
}
static golem_status apply(gi_review_state *s, struct json_object *o, gi_review_authorize fn, void *ctx)
{
    const char *keys[] = {"schema", "project_id", "work_id", "baseline_digest", "expected_epoch", "operation", "body"};
    golem_digest baseline; uint64_t epoch;
    if (!dw_keys(o, keys, 7) || !eq(o, "schema", "golem.intent.review-control.v1") ||
        !json_object_equal(dw_get(o, "project_id"), dw_get(s->base, "project_id")) ||
        !json_object_equal(dw_get(o, "work_id"), dw_get(s->base, "work_id")) ||
        !dw_digest(o, "baseline_digest", &baseline) || !same(&baseline, &s->binding.baseline) ||
        !uint_field(o, "expected_epoch", &epoch)) return GOLEM_ERR_PARSE;
    if (epoch != s->epoch || epoch == UINT64_MAX) return GOLEM_ERR_STALE_RESULT;
    const char *op = dw_text(o, "operation"); struct json_object *b = dw_get(o, "body");
    golem_status st = GOLEM_ERR_PARSE;
    if (!strcmp(op, "review")) {
        const char *bk[] = {"stage", "producer", "reviewer", "input_manifest", "definitions_digest", "verdict", "evidence_digest"};
        golem_digest input, defs, evidence;
        bool stage = false; for (size_t i = 0; i < 7; ++i) stage |= eq(b, "stage", stages[i]);
        if (!dw_keys(b, bk, 7) || !stage || !dw_id(dw_text(b, "producer")) || !dw_id(dw_text(b, "reviewer")) ||
            !strcmp(dw_text(b, "producer"), dw_text(b, "reviewer")) || !dw_digest(b, "input_manifest", &input) ||
            !dw_digest(b, "definitions_digest", &defs) || !same(&defs, &s->binding.definitions) ||
            !dw_digest(b, "evidence_digest", &evidence) ||
            (!eq(b, "verdict", "PASS") && !eq(b, "verdict", "REVISE") && !eq(b, "verdict", "QUESTION_REQUIRED") && !eq(b, "verdict", "INCONCLUSIVE"))) return st;
        if (eq(b, "verdict", "PASS") && s->count) return GOLEM_ERR_REQUIREMENTS_UNMET;
        /* The hook verifies exact control digest (outer wrapper) and authentic
         * delivery/subject provenance, not merely these model supplied labels. */
        st = authorize(s, fn, ctx, GI_REVIEW_STAGE, &evidence, dw_text(b, "producer"), dw_text(b, "reviewer"));
        if (st == GOLEM_OK) {
            for (unsigned i=0;i<7;++i) if(eq(b,"stage",stages[i])) {
                gi_review_stage_status *r=&s->stages[i];
                r->passed=eq(b,"verdict","PASS");r->evidence=evidence;r->input=input;r->definitions=defs;
                strcpy(r->producer,dw_text(b,"producer"));strcpy(r->reviewer,dw_text(b,"reviewer"));
                /* Upstream re-review invalidates downstream attestations. */
                for(unsigned j=i+1;j<7;++j)s->stages[j].passed=false;
            }
        }
        if (st == GOLEM_OK && eq(b, "stage", "REQUIREMENTS")) {
            s->reviewed = eq(b, "verdict", "PASS"); s->review = evidence;
            strcpy(s->producer, dw_text(b, "producer")); strcpy(s->reviewer, dw_text(b, "reviewer"));
        }
        if (st == GOLEM_OK && !eq(b, "verdict", "PASS")) {
            if (s->count == GI_OBLIGATION_MAX || s->question_history_count == GI_OBLIGATION_MAX) return GOLEM_ERR_OVERFLOW;
            for (size_t i = 0; i < s->question_history_count; ++i) if (same(&s->question_history[i], &evidence)) return GOLEM_ERR_INVALID_STATE;
            s->question_history[s->question_history_count++] = evidence;
            s->questions[s->count++].id = evidence;
        }
    } else if (!strcmp(op, "activate")) {
        const char *bk[] = {"decision_digest", "review_digest", "policy_digest"};
        golem_digest decision, review, policy, expected;
        if (!dw_keys(b, bk, 3) || !dw_digest(b, "decision_digest", &decision) || !dw_digest(b, "review_digest", &review) ||
            !dw_digest(b, "policy_digest", &policy) || !dw_digest(dw_get(s->base, "body"), "issuer_policy_ref", &expected) ||
            !same(&policy, &expected)) return st;
        if (s->active || !s->reviewed || !same(&review, &s->review)) return GOLEM_ERR_REQUIREMENTS_UNMET;
        st = authorize(s, fn, ctx, GI_REVIEW_STAGE, &s->review, s->producer, s->reviewer);
        if (st == GOLEM_OK) st = authorize(s, fn, ctx, GI_REVIEW_SOURCE_ADOPTION, &s->binding.baseline, "", "");
        if (st == GOLEM_OK) st = authorize(s, fn, ctx, GI_REVIEW_ACTIVATION, &decision, "", "");
        if (st == GOLEM_OK) { s->active = true; s->activation_decision = decision; }
    } else if (!strcmp(op, "question") || !strcmp(op, "answer")) {
        const char *bk[] = {"question_digest", "evidence_digest"}; golem_digest id, evidence;
        if (!dw_keys(b, bk, 2) || !dw_digest(b, "question_digest", &id) || !dw_digest(b, "evidence_digest", &evidence)) return st;
        size_t at = 0; while (at < s->count && !same(&id, &s->questions[at].id)) ++at;
        if (!strcmp(op, "question")) {
            if (at != s->count) return GOLEM_ERR_INVALID_STATE;
            if (s->count == GI_OBLIGATION_MAX || s->question_history_count == GI_OBLIGATION_MAX) return GOLEM_ERR_OVERFLOW;
            for (size_t i = 0; i < s->question_history_count; ++i) if (same(&s->question_history[i], &id)) return GOLEM_ERR_INVALID_STATE;
            s->question_history[s->question_history_count++] = id;
            s->questions[s->count++].id = id; st = GOLEM_OK;
        } else {
            if (at == s->count || s->questions[at].answered) return GOLEM_ERR_INVALID_STATE;
            if (s->answer_history_count == GI_OBLIGATION_MAX) return GOLEM_ERR_OVERFLOW;
            for (size_t i = 0; i < s->answer_history_count; ++i) if (same(&s->answer_history[i], &evidence)) return GOLEM_ERR_INVALID_STATE;
            st = authorize(s, fn, ctx, GI_REVIEW_ANSWER, &evidence, "", "");
            if (st == GOLEM_OK) {
                s->answer_history[s->answer_history_count++] = evidence;
                s->questions[at].answer = evidence; s->questions[at].answered = true;
            }
        }
    } else if (!strcmp(op, "resolve")) {
        const char *bk[] = {"close", "carry", "evidence_digest"}; golem_digest evidence;
        struct json_object *close = dw_get(b, "close"), *carry = dw_get(b, "carry");
        if (!dw_keys(b, bk, 3) || !array(close, 1, GI_OBLIGATION_MAX) || !array(carry, 0, GI_OBLIGATION_MAX) ||
            json_object_array_length(close) + json_object_array_length(carry) != s->count || !dw_digest(b, "evidence_digest", &evidence)) return st;
        bool closed[GI_OBLIGATION_MAX] = {false}, seen[GI_OBLIGATION_MAX] = {false};
        for (size_t k = 0; k < 2; ++k) {
            struct json_object *a = k ? carry : close;
            for (size_t i = 0; i < json_object_array_length(a); ++i) {
                golem_digest id; if (!dig(json_object_array_get_idx(a, i), &id)) return GOLEM_ERR_PARSE;
                size_t at = 0; while (at < s->count && !same(&id, &s->questions[at].id)) ++at;
                if (at == s->count || seen[at] || (!k && !s->questions[at].answered)) return GOLEM_ERR_REQUIREMENTS_UNMET;
                seen[at] = true; closed[at] = !k;
            }
        }
        st = GOLEM_OK;
        for (size_t i = 0; st == GOLEM_OK && i < s->count; ++i)
            if (closed[i]) st = authorize(s, fn, ctx, GI_REVIEW_ANSWER, &s->questions[i].answer, "", "");
        if (st == GOLEM_OK) st = authorize(s, fn, ctx, GI_REVIEW_RESOLUTION, &evidence, "", "");
        if (st == GOLEM_OK) {
            size_t n = 0;
            for (size_t i = 0; i < s->count; ++i) if (!closed[i]) s->questions[n++] = s->questions[i];
            memset(s->questions + n, 0, (s->count - n) * sizeof(s->questions[0])); s->count = n;
            s->reviewed = false; for(unsigned i=0;i<7;++i)s->stages[i].passed=false; /* Changed interpretation requires new review. */
        }
    }
    if (st == GOLEM_OK) ++s->epoch;
    return st;
}
golem_status gi_review_apply(gi_review_state *s, golem_bytes control, gi_review_authorize fn, void *ctx)
{
    if (!s || !fn || s->busy) return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = NULL; golem_status st = golem_json_parse(control, GI_CONTROL_MAX, &o);
    gi_review_state *next = malloc(sizeof(*next));
    if (!next) { json_object_put(o); return GOLEM_ERR_OUT_OF_MEMORY; }
    *next = *s; s->busy = true;
    golem_digest request;
    if (st == GOLEM_OK) st = golem_digest_bytes(control, &request);
    /* Exact entire control (including delivery and close/carry) is authorized
     * separately from evidence. No attacker-selected boolean grants authority. */
    if (st == GOLEM_OK) st = authorize(next, fn, ctx, GI_REVIEW_CONTROL, &request, "", "");
    if (st == GOLEM_OK) st = apply(next, o, fn, ctx);
    if (st == GOLEM_OK) *s = *next;
    s->busy = false; free(next); json_object_put(o); return st;
}

/* The journal protects historical bytes, not current issuer credentials.
 * Replay reconstructs historical control state only. Every new transition
 * invokes live host authorization, and QC3 must revalidate current policy
 * before accepting any product effect. */
static golem_status historical(void *ctx, gi_review_purpose purpose, const golem_digest *baseline,
    const golem_digest *evidence, const char *project, const char *work, const char *producer, const char *reviewer)
{
    (void)ctx; (void)purpose; (void)baseline; (void)evidence;
    (void)project; (void)work; (void)producer; (void)reviewer;
    return GOLEM_OK;
}
static golem_status replay_control(void *ctx, const golem_digest *op, const golem_digest *request,
    const gi_journal_operation *record, golem_bytes payload)
{
    (void)op;
    gi_review_state *s = ctx; struct json_object *o = NULL;
    golem_status st = golem_json_parse(payload, GI_CONTROL_MAX, &o);
    /* Older D01 payloads are not necessarily JSON. Only this reserved schema
     * namespace is interpreted as QC1. Existing journal validation remains. */
    if (st != GOLEM_OK) return GOLEM_OK;
    const char *schema = dw_text(o, "schema");
    if (strncmp(schema, "golem.intent.review-control.", 28)) { json_object_put(o); return GOLEM_OK; }
    if (strcmp(schema, "golem.intent.review-control.v1")) { json_object_put(o); return GOLEM_ERR_UNSUPPORTED_VERSION; }
    golem_digest baseline, digest;
    if (!dw_digest(o, "baseline_digest", &baseline)) { json_object_put(o); return GOLEM_ERR_CORRUPT_JOURNAL; }
    if (!same(&baseline, &s->binding.baseline)) { json_object_put(o); return GOLEM_OK; }
    st = golem_digest_bytes(payload, &digest);
    /* All QC1 controls use intake; enabling resolution quota lanes is not
     * implied by naming an operation 'resolve'. */
    if (st == GOLEM_OK && (!same(&digest, request) || record->lane != GI_QUOTA_INTAKE)) st = GOLEM_ERR_CORRUPT_JOURNAL;
    json_object_put(o);
    if (st == GOLEM_OK) st = gi_review_apply(s, payload, historical, NULL);
    return st;
}
golem_status gi_review_load(gi_journal *journal, const golem_digest *operation,
    const golem_digest *request, const golem_digest *baseline,
    const golem_bytes *definitions, size_t count, gi_review_state **out)
{
    if (!journal || !operation || !request || !baseline || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    gi_baseline_read read = {0}; gi_review_state *state = NULL;
    golem_status st = gi_journal_read_baseline(journal, operation, request, baseline, &read);
    if (st == GOLEM_OK) {
        gi_review_inputs inputs = {read.graph.baseline, read.graph.sources, read.graph.source_count, definitions, count};
        st = gi_review_create(&inputs, &state);
    }
    if (st == GOLEM_OK) st = gi_journal_visit_payloads(journal, replay_control, state);
    gi_object_graph_dispose(&read.graph);
    if (st == GOLEM_OK) *out = state; else gi_review_free(state);
    return st;
}
typedef struct commit_guard {
    gi_review_state *state;
    golem_bytes control;
    gi_journal_guard registration;
    gi_review_authorize authority;
    void *context;
} commit_guard;
static golem_status recheck(void *opaque)
{
    commit_guard *g = opaque;
    golem_status st = g->registration(g->context);
    if (st != GOLEM_OK) return st;
    gi_review_state *candidate = malloc(sizeof(*candidate));
    if (!candidate) return GOLEM_ERR_OUT_OF_MEMORY;
    *candidate = *g->state;
    st = gi_review_apply(candidate, g->control, g->authority, g->context);
    free(candidate); return st;
}
golem_status gi_review_publish(gi_journal *journal, const golem_digest *baseline_operation,
    const golem_digest *baseline_request, const golem_digest *baseline,
    const golem_bytes *definitions, size_t count, golem_bytes control, const golem_digest *operation,
    uint64_t sequence, const golem_digest *head, gi_journal_guard guard,
    gi_review_authorize authority, void *context, gi_journal_receipt *out)
{
    if (!journal || !baseline_operation || !baseline_request || !baseline || !operation || !head || !guard || !authority || !out ||
        !control.data || !control.size || control.size > GI_CONTROL_MAX) return GOLEM_ERR_INVALID_ARGUMENT;
    /* Copy exact command bytes before callbacks to prevent accidental mutation
     * by a cooperative host between preflight and publication. */
    uint8_t *copy = malloc(control.size); if (!copy) return GOLEM_ERR_OUT_OF_MEMORY;
    memcpy(copy, control.data, control.size); control.data = copy;
    gi_review_state *state = NULL; golem_digest request;
    golem_status st = guard(context);
    if (st == GOLEM_OK) st = golem_digest_bytes(control, &request);
    gi_journal_operation prior;
    if (st == GOLEM_OK) {
        golem_status looked = gi_journal_lookup(journal, operation, &request, &prior);
        /* No implicit replay of an already used operation. Read-only lookup
         * remains available to the trusted host, without consuming callbacks. */
        if (looked == GOLEM_OK) st = GOLEM_ERR_INVALID_STATE;
        else if (looked != GOLEM_ERR_NOT_FOUND) st = looked;
    }
    if (st == GOLEM_OK) st = gi_review_load(journal, baseline_operation, baseline_request, baseline, definitions, count, &state);
    commit_guard g = {state, control, guard, authority, context};
    if (st == GOLEM_OK) st = recheck(&g);
    if (st == GOLEM_OK) st = gi_journal_append(journal, GI_QUOTA_INTAKE, operation, &request, sequence, head,
        control, recheck, &g, out);
    gi_review_free(state); free(copy); return st;
}

golem_status gi_review_stage_inspect(const gi_review_state *s,unsigned stage,gi_review_stage_status *out)
{
    if(!s||!out||stage>=7||s->busy)return GOLEM_ERR_INVALID_ARGUMENT;
    *out=s->stages[stage];return GOLEM_OK;
}
