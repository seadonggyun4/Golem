#include "../workflow/role_internal.h"
#include <string.h>

static const char *state(golem_status st)
{
    if (st == GOLEM_OK)
        return "SATISFIED";
    if (st == GOLEM_ERR_NOT_FOUND || st == GOLEM_ERR_MISSING_RECORD)
        return "MISSING";
    if (st == GOLEM_ERR_STALE_RESULT)
        return "STALE";
    if (st == GOLEM_ERR_APPROVAL_REQUIRED || st == GOLEM_ERR_POLICY_DENIED ||
        st == GOLEM_ERR_UNSUPPORTED_VERSION)
        return "BLOCKED";
    return "INVALID";
}

/* Keep the roles.v1 predicate independent from future changes to the legacy
 * completion evaluator. An issued PASS must still cover each expected case. */
golem_status rc_qa_cases(struct json_object *receipt, struct json_object *checkpoint)
{
    struct json_object *gates = dw_get(receipt, "gates");
    struct json_object *definitions = dw_get(dw_get(checkpoint, "contract"), "gates");
    if (strcmp(dw_text(receipt, "status"), "PASS") || !ds_array(definitions, 1, 8) ||
        !ds_array(gates, json_object_array_length(definitions),
                  json_object_array_length(definitions)))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    for (size_t i = 0; i < json_object_array_length(definitions); ++i) {
        struct json_object *gate = json_object_array_get_idx(gates, i);
        struct json_object *definition = json_object_array_get_idx(definitions, i);
        struct json_object *expected = dw_get(definition, "cases"), *actual = dw_get(gate, "cases");
        if (strcmp(dw_text(gate, "status"), "PASS") ||
            strcmp(dw_text(gate, "gate_id"), dw_text(definition, "id")) ||
            dw_uint(gate, "version") != dw_uint(definition, "version") ||
            !ds_array(expected, 1, 64) ||
            !ds_array(actual, json_object_array_length(expected),
                      json_object_array_length(expected)))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        for (size_t j = 0; j < json_object_array_length(expected); ++j) {
            const char *id = dw_text(json_object_array_get_idx(expected, j), "id");
            size_t found = 0;
            for (size_t k = 0; k < json_object_array_length(actual); ++k) {
                struct json_object *test = json_object_array_get_idx(actual, k);
                if (!strcmp(id, dw_text(test, "id")) && !strcmp(dw_text(test, "status"), "PASS"))
                    ++found;
            }
            if (found != 1)
                return GOLEM_ERR_REQUIREMENTS_UNMET;
        }
    }
    return GOLEM_OK;
}

static golem_status observed(golem_document_store *s, dw_entry *e, const char *predicate, bool live)
{
    golem_digest key, checkpoint;
    if (dw_uint(e->meta, "schema_version") != 5 || !dw_digest(e->meta, "execution_receipt", &key))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    bool qa = !strcmp(predicate, "QA_PASS");
    struct json_object *r = NULL, *cp = NULL;
    golem_status st = ex_load(s, &key, qa ? "qa" : "development", &r);
    if (st == GOLEM_OK && !dw_digest(r, "checkpoint", &checkpoint))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = ex_load(s, &checkpoint, "checkpoint", &cp);
    if (st == GOLEM_OK && !qa && dw_uint(cp, "schema_version") < 4)
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK && !qa)
        st = ex_inventory_check(s, cp, dw_get(r, "snapshot"), false);
    if (st == GOLEM_OK && !strcmp(predicate, "NO_CHANGE") &&
        !json_object_equal(dw_get(cp, "baseline"), dw_get(r, "snapshot")))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK && qa)
        st = rc_qa_cases(r, cp);
    if (st == GOLEM_OK && live)
        st = ex_live(s, e->meta);
    json_object_put(r);
    json_object_put(cp);
    return st;
}

static golem_status review(golem_document_store *s, dw_entry *e, struct json_object *v,
                           bool development, bool live)
{
    if (!v)
        return GOLEM_ERR_NOT_FOUND;
    if (wf_resolve(s, dw_get(v, "document")) != e)
        return GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *targets = dw_get(v, "targets"),
                       *inputs = dw_get(dw_get(e->meta, "input_manifest"), "documents");
    if (json_object_array_length(targets) != json_object_array_length(inputs))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    bool qa_seen = !development;
    for (size_t i = 0; i < json_object_array_length(inputs); ++i) {
        struct json_object *in = json_object_array_get_idx(inputs, i);
        dw_entry *entry = dw_find(s, dw_text(in, "document_id"), (uint32_t)dw_uint(in, "revision"));
        golem_digest digest;
        if (!entry || !dw_digest(in, "digest", &digest) ||
            !dw_equal(&digest, &entry->result.manifest_digest))
            return GOLEM_ERR_IDENTITY_MISMATCH;
        bool found = false;
        for (size_t j = 0; j < json_object_array_length(targets); ++j)
            if (wf_resolve(s, json_object_array_get_idx(targets, j)) == entry && entry)
                found = true;
        if (!found)
            return GOLEM_ERR_IDENTITY_MISMATCH;
        uint64_t bytes;
        golem_status st = wf_integrity(s, (size_t)(entry - s->entries), &bytes);
        if (st != GOLEM_OK)
            return st;
        if (!strcmp(dw_text(entry->meta, "kind"), "qa-result") && development) {
            if (strcmp(dw_text(entry->meta, "execution_receipt"), dw_text(v, "qa_receipt")))
                return GOLEM_ERR_IDENTITY_MISMATCH;
            st = observed(s, entry, "QA_PASS", live);
            if (st != GOLEM_OK)
                return st;
            qa_seen = true;
        }
        if (development && !strcmp(dw_text(entry->meta, "kind"), "development-result")) {
            st = observed(s, entry, "DEVELOPMENT", live);
            if (st != GOLEM_OK)
                return st;
        }
    }
    if (!qa_seen || (!development && strcmp(dw_text(v, "qa_receipt"), "")) ||
        strcmp(dw_text(v, "decision"), "ACCEPT"))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *findings = dw_get(v, "findings");
    for (size_t i = 0; i < json_object_array_length(findings); ++i)
        if (json_object_get_boolean(dw_get(json_object_array_get_idx(findings, i), "blocking")))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
    return GOLEM_OK;
}

golem_status rc_assess(golem_document_store *s, struct json_object *r, bool live,
                       struct json_object *historical, struct json_object **out)
{
    struct json_object *enrollment = rc_enrollment(s, dw_text(r, "selection_id"));
    if (!enrollment)
        return GOLEM_ERR_NOT_FOUND;
    struct json_object *contract = dw_get(dw_get(enrollment, "request"), "contract");
    if (historical &&
        !ds_array(dw_get(historical, "rules"), json_object_array_length(dw_get(contract, "rules")),
                  json_object_array_length(dw_get(contract, "rules"))))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    dw_entry *plan = dw_find(s, dw_text(r, "selection_id"), 0);
    if (!plan || dw_uint(r, "expected_generation") != s->count + 1)
        return GOLEM_ERR_STALE_RESULT;
    wf_graph graph = {0};
    golem_status st = wf_graph_make(s, &graph);
    if (st == GOLEM_OK &&
        (graph.states[plan - s->entries] != GOLEM_DOCUMENT_CURRENT ||
         strcmp(dw_text(dw_get(plan->meta, "selection"), "mode"), dw_text(contract, "mode"))))
        st = GOLEM_ERR_STALE_RESULT;
    struct json_object *a = json_object_new_object(), *rows = json_object_new_array(),
                       *affected = json_object_new_array();
    if (!a || !rows || !affected)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    bool impact[GOLEM_DOCUMENT_MAX_REVISIONS] = {false};
    bool satisfied = true;
    const char *next_kind = "", *next_action = "NONE";
    struct json_object *rules = dw_get(contract, "rules");
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(rules); ++i) {
        struct json_object *rule = json_object_array_get_idx(rules, i),
                           *row = json_object_new_object();
        dw_entry *e = NULL;
        golem_status check = wf_role_pick(s, plan, wf_kind(dw_text(rule, "kind")), &graph, &e);
        uint64_t bytes;
        if (check == GOLEM_OK)
            check = wf_integrity(s, (size_t)(e - s->entries), &bytes);
        const char *p = dw_text(rule, "predicate");
        if (check == GOLEM_OK && strcmp(p, "MARKDOWN") && strcmp(p, "REVIEW"))
            check = observed(s, e, p, live);
        if (check == GOLEM_OK && !strcmp(p, "REVIEW"))
            check = review(s, e, dw_get(r, "review"),
                           !strcmp(dw_text(contract, "mode"), "development"), live);
        if (check == GOLEM_OK && json_object_get_boolean(dw_get(rule, "independent_review")))
            check = GOLEM_ERR_APPROVAL_REQUIRED;
        if (check == GOLEM_ERR_OUT_OF_MEMORY || check == GOLEM_ERR_IO) {
            json_object_put(row);
            st = check;
            break;
        }
        /* Replay preserves a past live failure without observing today's source.
         * A historical success still must pass all prefix-local checks. */
        if (historical) {
            struct json_object *old = json_object_array_get_idx(dw_get(historical, "rules"), i);
            if (!json_object_is_type(dw_get(old, "verification_status"), json_type_int) ||
                dw_uint(old, "verification_status") > GOLEM_ERR_QUEUE_FULL) {
                json_object_put(row);
                st = GOLEM_ERR_CORRUPT_JOURNAL;
                break;
            }
            golem_status recorded = (golem_status)dw_uint(old, "verification_status");
            if (check == GOLEM_OK)
                check = recorded;
            else if (recorded != check) {
                json_object_put(row);
                st = GOLEM_ERR_CORRUPT_JOURNAL;
                break;
            }
        }
        if (check != GOLEM_OK) {
            if (satisfied) {
                next_kind = dw_text(rule, "kind");
                next_action = !strcmp(state(check), "BLOCKED") ? "BLOCKED"
                              : e                              ? "REVISE_DOCUMENT"
                                                               : "AUTHOR_DOCUMENT";
            }
            satisfied = false;
            if (e)
                impact[e - s->entries] = true;
        }
        golem_digest input_digest;
        char input_hex[GOLEM_DIGEST_HEX_CAPACITY] = "";
        size_t required;
        if (e && dw_get(e->meta, "input_manifest")) {
            st = ex_hash(dw_get(e->meta, "input_manifest"), &input_digest);
            if (st == GOLEM_OK)
                st = golem_digest_format(&input_digest, input_hex, sizeof(input_hex), &required);
        }
        if (st != GOLEM_OK) {
            json_object_put(row);
            break;
        }
        if (!row || !dw_add(row, "rule", json_object_get(rule)) ||
            !ex_text(row, "state", state(check)) || !ex_uint(row, "verification_status", check) ||
            !dw_add(row, "document", e ? wf_ref(e) : json_object_new_object()) ||
            !ex_text(row, "execution_receipt", e ? dw_text(e->meta, "execution_receipt") : "") ||
            !ex_text(row, "producer_attempt", e ? dw_text(e->meta, "producer_attempt") : "") ||
            !ex_text(row, "input_digest", input_hex)) {
            json_object_put(row);
            st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (!wf_append(rows, row))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    for (size_t pass = 0; st == GOLEM_OK && pass < s->count; ++pass) {
        bool changed = false;
        for (size_t i = 0; i < s->count; ++i)
            if (!impact[i])
                for (size_t j = 0; j < graph.nodes[i].parent_count; ++j)
                    if (impact[graph.nodes[i].parents[j]]) {
                        impact[i] = true;
                        changed = true;
                        break;
                    }
        if (!changed)
            break;
    }
    for (size_t i = 0; st == GOLEM_OK && i < s->count; ++i)
        if (impact[i] && graph.states[i] != GOLEM_DOCUMENT_SUPERSEDED &&
            !wf_append(affected, wf_ref(&s->entries[i])))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_digest digest;
    if (st == GOLEM_OK)
        st = ex_hash(contract, &digest);
    if (st == GOLEM_OK &&
        (!ex_uint(a, "schema_version", 1) || !ex_text(a, "type", "DeliverableAssessmentV1") ||
         !ex_text(a, "work_id", dw_text(s->spec, "work_id")) ||
         !ex_uint(a, "generation", s->count + 1) || !dw_add(a, "selection", wf_ref(plan)) ||
         !dw_add_digest(a, "contract_digest", &digest) ||
         !ex_text(a, "state", satisfied ? "SATISFIED" : "UNSATISFIED") ||
         !ex_text(a, "next_action", next_action) || !ex_text(a, "target_kind", next_kind) ||
         !dw_add(a, "rules", json_object_get(rows)) ||
         !dw_add(a, "affected", json_object_get(affected)) ||
         !ex_text(a, "assurance", "LOCAL_STRUCTURAL_AND_OBSERVED_EVIDENCE") ||
         !dw_add(a, "execution_authorized", json_object_new_boolean(false))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        *out = a;
    else
        json_object_put(a);
    json_object_put(rows);
    json_object_put(affected);
    wf_graph_free(s, &graph);
    return st;
}
