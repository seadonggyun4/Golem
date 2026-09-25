#include "internal.h"
#include <string.h>

#define DIFF_ROWS 64u
#define DIFF_BYTES 32768u

static bool optional(struct json_object *o, const char *key, struct json_object *value)
{
    struct json_object *owned = json_object_get(value);
    if (!o || json_object_object_add(o, key, owned) != 0) {
        json_object_put(owned);
        return false;
    }
    return true;
}

golem_status cf_diff_inventory(golem_document_store *store, struct json_object *snapshot,
                               struct json_object **out)
{
    struct json_object *repos = dw_get(snapshot, "repositories");
    if (!ds_array(repos, 1, 1))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *repo = json_object_array_get_idx(repos, 0);
    if (dw_get(repo, "inventory_ref"))
        return ex_inventory_load(store, repo, out);
    if (!dw_get(repo, "inventory"))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    *out = json_object_get(dw_get(repo, "inventory"));
    return GOLEM_OK;
}

static struct json_object *find_entry(struct json_object *inventory, const char *path)
{
    struct json_object *entries = dw_get(inventory, "entries");
    for (size_t i = 0; i < json_object_array_length(entries); ++i) {
        struct json_object *entry = json_object_array_get_idx(entries, i);
        if (!strcmp(dw_text(entry, "path_hex"), path))
            return entry;
    }
    return NULL;
}

static bool index_covered(struct json_object *entry)
{
    struct json_object *index = dw_get(entry, "index"), *head = dw_get(entry, "head"),
                       *worktree = dw_get(entry, "worktree");
    return !index || json_object_equal(index, head) ||
           (!strcmp(dw_text(index, "oid"), dw_text(worktree, "oid")) &&
            !strcmp(dw_text(index, "mode"), dw_text(worktree, "mode")));
}

static golem_status row(cf_context *c, const golem_candidate_member *member,
                        struct json_object *before, struct json_object *after, bool content,
                        size_t *budget, struct json_object *rows, bool *complete, bool *truncated)
{
    const char *path = dw_text(after ? after : before, "path_hex");
    struct json_object *o = json_object_new_object(), *a = NULL, *b = NULL;
    bool available = content && index_covered(before) && index_covered(after);
    golem_status st = GOLEM_OK;
    if (content) {
        st = cf_diff_content(c, member, path, before, false, budget, &a);
        if (st == GOLEM_ERR_INCOMPLETE_WORK || st == GOLEM_ERR_OVERFLOW) {
            *truncated = *truncated || st == GOLEM_ERR_OVERFLOW;
            available = false;
            st = GOLEM_OK;
        }
        if (st == GOLEM_OK)
            st = cf_diff_content(c, member, path, after, true, budget, &b);
        if (st == GOLEM_ERR_INCOMPLETE_WORK || st == GOLEM_ERR_OVERFLOW) {
            *truncated = *truncated || st == GOLEM_ERR_OVERFLOW;
            available = false;
            st = GOLEM_OK;
        }
    }
    *complete = *complete && available;
    golem_digest path_key;
    if (st == GOLEM_OK)
        st = golem_digest_bytes((golem_bytes){(const uint8_t *)path, strlen(path)}, &path_key);
    if (st == GOLEM_OK &&
        (!dw_add_digest(o, "path_digest", &path_key) ||
         !ex_text(o, "path_hex", content ? path : "") ||
         !ex_text(o, "change",
                  !dw_get(before, "worktree") && dw_get(after, "worktree")   ? "ADD"
                  : dw_get(before, "worktree") && !dw_get(after, "worktree") ? "DELETE"
                                                                             : "MODIFY") ||
         !optional(o, "before", content ? before : NULL) ||
         !optional(o, "after", content ? after : NULL) || !optional(o, "before_hex", a) ||
         !optional(o, "after_hex", b) ||
         !dw_add(o, "content_complete", json_object_new_boolean(available))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        const char *encoded = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
        const char *previous = json_object_to_json_string_ext(rows, JSON_C_TO_STRING_PLAIN);
        if (!encoded || !previous) {
            json_object_put(o);
            st = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (strlen(encoded) + strlen(previous) > 196608u) {
            *complete = false;
            json_object_put(o);
        } else if (!wf_append(rows, o))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    } else
        json_object_put(o);
    json_object_put(a);
    json_object_put(b);
    return st;
}

static golem_status current(cf_context *c, size_t i, golem_candidate_member *member,
                            struct json_object **qa)
{
    golem_digest key, gates, expected;
    if (strcmp(cf_state(c, i), "FINISHED") ||
        !dw_digest(dw_get(c->members[i], "result"), "qa", &key))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    golem_status st = cf_member(c, i, member);
    if (st == GOLEM_OK)
        st = cf_qa(member->work, &key, member->tree_root, dw_text(c->manifest, "base_commit"),
                   &gates, qa);
    if (st == GOLEM_OK &&
        (!dw_digest(c->manifest, "gates_digest", &expected) || !dw_equal(&gates, &expected)))
        st = GOLEM_ERR_IDENTITY_MISMATCH;
    return st;
}

static golem_status seal(cf_context *c, size_t i, struct json_object **out)
{
    bool content = !strcmp(dw_text(c->request, "redaction"), "source");
    if ((!content && strcmp(dw_text(c->request, "redaction"), "metadata")) || c->selection)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_candidate_member member;
    struct json_object *qa = NULL, *cp = NULL, *before = NULL, *after = NULL;
    struct json_object *projection = json_object_new_object(), *rows = json_object_new_array();
    golem_digest checkpoint, base_key, after_key, manifest_key, qa_copy, enrollment, inputs;
    golem_status st = current(c, i, &member, &qa);
    if (st == GOLEM_OK && !dw_digest(qa, "checkpoint", &checkpoint))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = ex_load(member.work, &checkpoint, "checkpoint", &cp);
    if (st == GOLEM_OK)
        st = cf_diff_inventory(member.work, dw_get(cp, "baseline"), &before);
    if (st == GOLEM_OK)
        st = cf_diff_inventory(member.work, dw_get(qa, "snapshot"), &after);
    if (st == GOLEM_OK)
        st = dw_put_json(c->parent, before, &base_key);
    if (st == GOLEM_OK)
        st = dw_put_json(c->parent, after, &after_key);
    if (st == GOLEM_OK)
        st = ex_hash(c->manifest, &manifest_key);
    if (st == GOLEM_OK)
        st = ex_hash(dw_get(c->members[i], "enrollment"), &enrollment);
    if (st == GOLEM_OK)
        st = ex_hash(dw_get(qa, "manifest"), &inputs);
    /* Copy inventories and the issued QA receipt before publishing the view.
     * Other QA dependencies remain identities, not claims of archival closure. */
    if (st == GOLEM_OK)
        st = dw_put_json(c->parent, qa, &qa_copy);
    bool complete = content, truncated = false;
    size_t budget = DIFF_BYTES, changed = 0;
    for (unsigned pass = 0; st == GOLEM_OK && pass < 2; ++pass) {
        struct json_object *entries = dw_get(pass ? after : before, "entries");
        for (size_t k = 0; st == GOLEM_OK && k < json_object_array_length(entries); ++k) {
            struct json_object *entry = json_object_array_get_idx(entries, k);
            const char *path = dw_text(entry, "path_hex");
            struct json_object *a = find_entry(before, path), *b = find_entry(after, path);
            if ((pass && a) || json_object_equal(a, b))
                continue;
            ++changed;
            if (json_object_array_length(rows) == DIFF_ROWS) {
                complete = false;
                truncated = true;
                continue;
            }
            st = row(c, &member, a, b, content, &budget, rows, &complete, &truncated);
        }
    }
    struct json_object *fresh = NULL;
    if (st == GOLEM_OK)
        st = current(c, i, &member, &fresh);
    if (st == GOLEM_OK && !json_object_equal(qa, fresh))
        st = GOLEM_ERR_STALE_RESULT;
    if (st == GOLEM_OK &&
        (!ex_uint(projection, "schema_version", 1) ||
         !ex_text(projection, "type", "CandidateDiffV1") ||
         !ex_text(projection, "renderer", "full-file-hex-v1") ||
         !ex_text(projection, "observation", "HISTORICAL_NOT_LIVE") ||
         !ex_text(projection, "group_id", dw_text(c->manifest, "group_id")) ||
         !ex_text(projection, "candidate", dw_text(cf_spec(c, i), "id")) ||
         !dw_add_digest(projection, "group_manifest", &manifest_key) ||
         !dw_add_digest(projection, "enrollment_digest", &enrollment) ||
         !dw_add_digest(projection, "qa", &qa_copy) ||
         !dw_add_digest(projection, "checkpoint", &checkpoint) ||
         !dw_add_digest(projection, "input_manifest_digest", &inputs) ||
         !dw_add_digest(projection, "before_inventory", &base_key) ||
         !dw_add_digest(projection, "after_inventory", &after_key) ||
         !ex_text(projection, "redaction", content ? "source" : "metadata") ||
         !ex_uint(projection, "changed_files", changed) ||
         !dw_add(projection, "complete", json_object_new_boolean(complete)) ||
         !dw_add(projection, "truncated",
                 json_object_new_boolean(truncated || changed != json_object_array_length(rows))) ||
         !dw_add(projection, "changes", json_object_get(rows))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    golem_digest digest;
    struct json_object *reference = json_object_new_object();
    if (st == GOLEM_OK)
        st = dw_put_json(c->parent, projection, &digest);
    if (st == GOLEM_OK && !dw_add_digest(reference, "digest", &digest))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK)
        st = c->host->check(c->host->context, c->request_bytes);
    if (st == GOLEM_OK && !json_object_equal(reference, dw_get(c->members[i], "diff")))
        st = cf_append(c, "DIFF", i, reference);
    if (st == GOLEM_OK)
        *out = json_object_get(reference);
    json_object_put(reference);
    json_object_put(projection);
    json_object_put(rows);
    json_object_put(qa);
    json_object_put(cp);
    json_object_put(before);
    json_object_put(after);
    json_object_put(fresh);
    return st;
}

golem_status cf_diff_validate(cf_context *c, size_t i, struct json_object *data)
{
    golem_digest digest, manifest, actual, enrollment, recorded;
    struct json_object *projection = NULL;
    golem_status st = dw_digest(data, "digest", &digest)
                          ? dw_cas_json(c->parent, &digest, &projection)
                          : GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = ex_hash(c->manifest, &actual);
    if (st == GOLEM_OK)
        st = ex_hash(dw_get(c->members[i], "enrollment"), &enrollment);
    const char *keys[] = {"schema_version",
                          "type",
                          "renderer",
                          "observation",
                          "group_id",
                          "candidate",
                          "group_manifest",
                          "enrollment_digest",
                          "qa",
                          "checkpoint",
                          "input_manifest_digest",
                          "before_inventory",
                          "after_inventory",
                          "redaction",
                          "changed_files",
                          "complete",
                          "truncated",
                          "changes"};
    if (st == GOLEM_OK &&
        (!dw_keys(projection, keys, 18) || dw_uint(projection, "schema_version") != 1 ||
         strcmp(dw_text(projection, "type"), "CandidateDiffV1") ||
         strcmp(dw_text(projection, "renderer"), "full-file-hex-v1") ||
         strcmp(dw_text(projection, "group_id"), dw_text(c->manifest, "group_id")) ||
         strcmp(dw_text(projection, "candidate"), dw_text(cf_spec(c, i), "id")) ||
         !dw_digest(projection, "group_manifest", &manifest) || !dw_equal(&manifest, &actual) ||
         !dw_digest(projection, "enrollment_digest", &recorded) ||
         !dw_equal(&enrollment, &recorded) ||
         strcmp(dw_text(projection, "qa"), dw_text(dw_get(c->members[i], "result"), "qa"))))
        st = GOLEM_ERR_CORRUPT_JOURNAL;
    if (st == GOLEM_OK &&
        (!json_object_is_type(dw_get(projection, "complete"), json_type_boolean) ||
         !json_object_is_type(dw_get(projection, "truncated"), json_type_boolean) ||
         !ds_array(dw_get(projection, "changes"), 0, DIFF_ROWS) ||
         (json_object_get_boolean(dw_get(projection, "complete")) &&
          (strcmp(dw_text(projection, "redaction"), "source") ||
           json_object_get_boolean(dw_get(projection, "truncated")) ||
           dw_uint(projection, "changed_files") !=
               json_object_array_length(dw_get(projection, "changes"))))))
        st = GOLEM_ERR_CORRUPT_JOURNAL;
    if (st == GOLEM_OK) {
        uint64_t size;
        const char *references[] = {"qa", "before_inventory", "after_inventory"};
        for (size_t k = 0; st == GOLEM_OK && k < 3; ++k)
            st = dw_digest(projection, references[k], &digest)
                     ? golem_evidence_verify(c->parent->cas, &digest, &size, NULL)
                     : GOLEM_ERR_CORRUPT_JOURNAL;
    }
    json_object_put(projection);
    return st;
}

golem_status cf_review_check(cf_context *c, size_t i)
{
    struct json_object *diff = dw_get(c->members[i], "diff"),
                       *review = dw_get(c->members[i], "review");
    if (!diff)
        return GOLEM_OK; /* Existing v1 groups retain their original contract. */
    if (strcmp(dw_text(review, "diff"), dw_text(diff, "digest")) ||
        strcmp(dw_text(review, "decision"), "PASS"))
        return GOLEM_ERR_APPROVAL_REQUIRED;
    return GOLEM_OK; /* cf_report separately rechecks live QA and document freshness. */
}

golem_status cf_diff_call(cf_context *c, size_t i, struct json_object **out)
{
    const char *op = dw_text(c->request, "operation");
    if (!strcmp(op, "diff-seal"))
        return seal(c, i, out);
    golem_digest key;
    struct json_object *projection = NULL;
    golem_status st = dw_digest(dw_get(c->members[i], "diff"), "digest", &key)
                          ? dw_cas_json(c->parent, &key, &projection)
                          : GOLEM_ERR_NOT_FOUND;
    if (st == GOLEM_OK && !strcmp(op, "diff")) {
        *out = projection;
        return GOLEM_OK; /* Historical observation, deliberately no live resolver. */
    }
    golem_candidate_member member;
    struct json_object *qa = NULL, *target = NULL;
    if (st == GOLEM_OK)
        st = current(c, i, &member, &qa);
    if (st == GOLEM_OK && !strcmp(op, "review-check"))
        st = cf_review_check(c, i);
    if (st == GOLEM_OK && !strcmp(op, "review")) {
        const char *decision = dw_text(c->request, "decision"),
                   *reviewer = dw_text(c->request, "reviewer");
        if (strcmp(dw_text(c->request, "diff"), dw_text(dw_get(c->members[i], "diff"), "digest")) ||
            (!strcmp(decision, "PASS") &&
             !json_object_get_boolean(dw_get(projection, "complete"))) ||
            (strcmp(decision, "PASS") && strcmp(decision, "FAIL")) || !ws_id(reviewer) ||
            strlen(reviewer) > 64 ||
            !json_object_is_type(dw_get(c->request, "qa"), json_type_string))
            st = GOLEM_ERR_REQUIREMENTS_UNMET;
        if (st == GOLEM_OK && *dw_text(c->request, "qa"))
            st = cf_target(c, i, &target);
        if (st == GOLEM_OK)
            st = c->host->check(c->host->context, c->request_bytes);
        if (st == GOLEM_OK)
            st = cf_append(c, "REVIEW", i, c->request);
    }
    if (st == GOLEM_OK)
        *out = json_object_get(dw_get(c->members[i], "review"));
    json_object_put(target);
    json_object_put(qa);
    json_object_put(projection);
    return st;
}
