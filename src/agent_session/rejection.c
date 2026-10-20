#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include "golem/system_error.h"
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>

static bool same_text(struct json_object *a, const char *ak, struct json_object *b, const char *bk)
{
    return !strcmp(dw_text(a, ak), dw_text(b, bk));
}
bool as_rejected(struct json_object *state, const golem_digest *digest)
{
    struct json_object *list = dw_get(state, "rejected_outputs");
    if (!list)
        return false;
    for (size_t i = 0; i < json_object_array_length(list); ++i) {
        golem_digest found;
        if (dw_digest(dw_get(json_object_array_get_idx(list, i), "output"), "digest", &found) &&
            dw_equal(digest, &found))
            return true;
    }
    return false;
}
golem_status as_rejection_shape(struct json_object *state, struct json_object *data, uint64_t seq)
{
    const char *keys[] = {"token", "output", "evidence", "trust", "approval_digest", "registered_generation", "reason", "outcome"};
    struct json_object *a = dw_get(state, "active"), *evidence = dw_get(data, "evidence");
    golem_digest digest;
    if (!dw_keys(data, keys, 8) || !seq || seq != dw_uint(state, "sequence") + 1 ||
        !as_token(a, dw_get(data, "token")) || strcmp(dw_text(a, "state"), "RECOVERY_REQUIRED") ||
        !wf_reference(dw_get(data, "output")) ||
        dw_uint(data, "registered_generation") <= dw_uint(a, "input_generation") ||
        dw_uint(data, "registered_generation") > GOLEM_DOCUMENT_MAX_REVISIONS + 1 ||
        !dw_digest(data, "approval_digest", &digest) ||
        strcmp(dw_text(data, "trust"), "self_reported") ||
        strcmp(dw_text(data, "outcome"), "REJECTED_UNSUCCESSFUL") ||
        (strcmp(dw_text(data, "reason"), "WRONG_KIND") &&
         strcmp(dw_text(data, "reason"), "PINNED_INPUT_MISMATCH")) ||
        !json_object_is_type(evidence, json_type_array) || !json_object_array_length(evidence) ||
        json_object_array_length(evidence) > 64)
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    for (size_t i = 0; i < json_object_array_length(evidence); ++i) {
        struct json_object *v = json_object_array_get_idx(evidence, i);
        if (!json_object_is_type(v, json_type_string))
            return GOLEM_ERR_PARSE;
        const char *text = json_object_get_string(v);
        if (golem_digest_parse((golem_string_view){text, strlen(text)}, &digest) != GOLEM_OK)
            return GOLEM_ERR_PARSE;
        for (size_t j = 0; j < i; ++j)
            if (json_object_equal(v, json_object_array_get_idx(evidence, j)))
                return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}
struct json_object *as_rejection_summary(struct json_object *data)
{
    struct json_object *summary = json_object_new_object();
    const char *keys[] = {"token", "output", "trust", "approval_digest", "registered_generation", "reason", "outcome"};
    for (size_t i = 0; summary && i < 7; ++i)
        if (!dw_add(summary, keys[i], json_object_get(dw_get(data, keys[i])))) {
            json_object_put(summary);
            return NULL;
        }
    return summary;
}
golem_status as_rejection_validate(golem_document_store *s, struct json_object *state,
                                   struct json_object *data, uint64_t sequence)
{
    golem_status st = as_rejection_shape(state, data, sequence);
    struct json_object *a = dw_get(state, "active"), *approval = NULL, *pinned = NULL;
    golem_digest digest;
    if (st == GOLEM_OK && !dw_digest(data, "approval_digest", &digest))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = dw_cas_json(s, &digest, &approval);
    const char *ak[] = {"schema_version", "domain", "work_id", "work_spec_digest", "expected_sequence", "token", "input_digest",
                        "input_generation", "registered_generation", "source_snapshot", "selection", "output",
                        "evidence", "decision", "external_effects", "reason"};
    if (st == GOLEM_OK && (!dw_keys(approval, ak, 16) || dw_uint(approval, "schema_version") != 1 ||
        strcmp(dw_text(approval, "domain"), "golem.registered-output-rejection.v1") ||
        !same_text(approval, "work_id", s->spec, "work_id") ||
        !same_text(approval, "work_spec_digest", a, "policy_digest") ||
        dw_uint(approval, "expected_sequence") != sequence - 1 ||
        !json_object_equal(dw_get(approval, "token"), dw_get(data, "token")) ||
        !same_text(approval, "input_digest", a, "manifest_digest") ||
        dw_uint(approval, "input_generation") != dw_uint(a, "input_generation") ||
        dw_uint(approval, "registered_generation") != dw_uint(data, "registered_generation") ||
        !same_text(approval, "source_snapshot", a, "source_snapshot") ||
        !wf_reference(dw_get(approval, "selection")) ||
        strcmp(dw_text(dw_get(approval, "selection"), "document_id"), dw_text(state, "selection_id")) ||
        !json_object_equal(dw_get(approval, "output"), dw_get(data, "output")) ||
        !json_object_equal(dw_get(approval, "evidence"), dw_get(data, "evidence")) ||
        !same_text(approval, "reason", data, "reason") ||
        strcmp(dw_text(approval, "decision"), "REJECT_REGISTERED_OUTPUT") ||
        strcmp(dw_text(approval, "external_effects"), "NONE_IDENTIFIED_AFTER_INSPECTION")))
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    dw_entry *output = wf_resolve(s, dw_get(data, "output"));
    uint64_t generation = dw_uint(approval, "registered_generation");
    if (st == GOLEM_OK && (!output ||
        (dw_uint(output->meta, "schema_version") != 4 && dw_uint(output->meta, "schema_version") != 5) ||
        !same_text(output->meta, "producer_attempt", a, "attempt_id") ||
        generation <= dw_uint(a, "input_generation") || generation > s->count + 1 ||
        output->result.generation <= dw_uint(a, "input_generation") ||
        output->result.generation > generation || as_rejected(state, &output->result.manifest_digest)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    size_t attributable = 0;
    for (size_t i = 0; st == GOLEM_OK && i < s->count; ++i)
        attributable += same_text(s->entries[i].meta, "producer_attempt", a, "attempt_id");
    if (st == GOLEM_OK && attributable != 1)
        st = GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK && !dw_digest(a, "manifest_digest", &digest))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = dw_cas_json(s, &digest, &pinned);
    if (st == GOLEM_OK && (!json_object_equal(dw_get(approval, "selection"), dw_get(pinned, "selection")) ||
        !wf_resolve(s, dw_get(approval, "selection"))))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    if (st == GOLEM_OK) {
        const char *reason = !same_text(output->meta, "kind", a, "kind") ? "WRONG_KIND"
            : !json_object_equal(dw_get(output->meta, "input_manifest"), pinned) ? "PINNED_INPUT_MISMATCH" : "";
        if (!reason[0] || strcmp(reason, dw_text(data, "reason")))
            st = GOLEM_ERR_INVALID_STATE;
    }
    struct json_object *evidence = dw_get(data, "evidence");
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(evidence); ++i) {
        const char *v = json_object_get_string(json_object_array_get_idx(evidence, i));
        uint64_t size;
        st = golem_digest_parse((golem_string_view){v, strlen(v)}, &digest);
        if (st == GOLEM_OK)
            st = golem_evidence_verify(s->cas, &digest, &size, NULL);
    }
    json_object_put(approval);
    json_object_put(pinned);
    return st;
}
/* This operation accounts only for document registration, never native execution
 * or an unresolved external-effect set. Replay does not inspect future directories. */
static golem_status effects_guard(golem_document_store *s, struct json_object *active)
{
    if (dw_get(active, "runtime_binding"))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    const char *dirs[] = {"execution-policies", "execution-attempts", "execution-receipts"};
    for (size_t i = 0; i < 3; ++i) {
        struct stat info;
        if (fstatat(s->root, dirs[i], &info, AT_SYMLINK_NOFOLLOW) == 0)
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        if (errno != ENOENT)
            return golem_system_error_note(GOLEM_ERR_IO, "session.reject_output", "fstatat", errno);
    }
    return GOLEM_OK;
}
golem_status as_rejection_prepare(golem_document_store *s, as_log *log,
                                  struct json_object *request, struct json_object *data)
{
    if (dw_uint(request, "expected_generation") != s->count + 1)
        return GOLEM_ERR_STALE_RESULT;
    struct json_object *active = dw_get(log->state, "active");
    golem_status st = effects_guard(s, active);
    dw_entry *output = wf_resolve(s, dw_get(request, "output"));
    if (st == GOLEM_OK && !output)
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    const char *reason = output && !same_text(output->meta, "kind", active, "kind")
        ? "WRONG_KIND" : "PINNED_INPUT_MISMATCH";
    const char *copy[] = {"token", "output", "evidence", "approval_digest"};
    for (size_t i = 0; st == GOLEM_OK && i < 4; ++i)
        if (!dw_add(data, copy[i], json_object_get(dw_get(request, copy[i]))))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK &&
        (!dw_add(data, "registered_generation", json_object_get(dw_get(request, "expected_generation"))) ||
         !dw_add(data, "trust", json_object_new_string("self_reported")) ||
         !dw_add(data, "reason", json_object_new_string(reason)) ||
         !dw_add(data, "outcome", json_object_new_string("REJECTED_UNSUCCESSFUL"))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = as_rejection_validate(s, log->state, data, log->sequence + 1);
    return st;
}
golem_status as_registration_guard(golem_document_store *s, struct json_object *metadata)
{
    as_log log = {.directory = -1};
    golem_status st = as_load(s, NULL, NULL, &log);
    struct json_object *a = dw_get(log.state, "active"), *pinned = NULL,
                       *rejected = dw_get(log.state, "rejected_outputs");
    const char *producer = dw_text(metadata, "producer_attempt");
    for (size_t i = 0; st == GOLEM_OK && rejected && i < json_object_array_length(rejected); ++i)
        if (!strcmp(producer, dw_text(dw_get(json_object_array_get_idx(rejected, i), "token"), "attempt_id")))
            st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK && a && !strcmp(producer, dw_text(a, "attempt_id"))) {
        golem_digest digest;
        if (!same_text(metadata, "kind", a, "kind"))
            st = GOLEM_ERR_IDENTITY_MISMATCH;
        else if (!dw_digest(a, "manifest_digest", &digest))
            st = GOLEM_ERR_PARSE;
        else
            st = dw_cas_json(s, &digest, &pinned);
        if (st == GOLEM_OK && (!json_object_equal(pinned, dw_get(metadata, "input_manifest")) ||
            dw_uint(metadata, "expected_generation") != dw_uint(a, "input_generation")))
            st = GOLEM_ERR_STALE_RESULT;
    }
    json_object_put(pinned);
    as_close(&log);
    return st;
}
golem_status as_rejection_graph(golem_document_store *s, wf_graph *graph)
{
    if (s->replaying)
        return GOLEM_OK;
    as_log log = {.directory = -1};
    golem_status st = as_load(s, NULL, NULL, &log);
    /* Registry parents precede their children. Historical graph evaluation above
     * remains unchanged; this overlay only invalidates current acceptance inputs. */
    for (size_t i = 0; st == GOLEM_OK && i < s->count; ++i) {
        bool invalid = as_rejected(log.state, &s->entries[i].result.manifest_digest);
        for (size_t j = 0; j < graph->nodes[i].parent_count; ++j) {
            size_t p = graph->nodes[i].parents[j];
            if (p >= i) {
                st = GOLEM_ERR_INVALID_GRAPH;
                break;
            }
            invalid |= graph->states[p] != GOLEM_DOCUMENT_CURRENT;
        }
        if (invalid && graph->states[i] == GOLEM_DOCUMENT_CURRENT)
            graph->states[i] = GOLEM_DOCUMENT_STALE;
    }
    as_close(&log);
    return st;
}
