#include "bundle_internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* All JSON inputs below are produced by bundle(), never raw caller documents.
 * Keep this projection downstream of the single structural redaction boundary. */
static bool push(struct json_object *array, struct json_object *value)
{
    if (array && value && json_object_array_add(array, value) == 0) return true;
    json_object_put(value); return false;
}
static bool attribute(struct json_object *array, const char *key, const char *text)
{
    struct json_object *entry = json_object_new_object(), *value = json_object_new_object();
    bool ok = ex_text(entry, "key", key) && ex_text(value, "stringValue", text) &&
        dw_add(entry, "value", json_object_get(value));
    json_object_put(value);
    if (!ok) { json_object_put(entry); return false; }
    return push(array, entry);
}
static golem_status otlp(struct json_object *files, const char *hash, struct json_object **out)
{
    struct json_object *root = json_object_new_object(), *resources = json_object_new_array(),
        *resource_logs = json_object_new_object(), *resource = json_object_new_object(),
        *attrs = json_object_new_array(), *scopes = json_object_new_array(),
        *scope_logs = json_object_new_object(), *scope = json_object_new_object(),
        *logs = json_object_new_array();
    bool ok = attribute(attrs, "service.name", "golem-derived-export") &&
        attribute(attrs, "golem.mapping.version", "golem.observability.v1") &&
        attribute(attrs, "golem.source.manifest.sha256", hash) &&
        attribute(attrs, "golem.authority", "DERIVED_ONLY") &&
        attribute(attrs, "golem.privacy", "PRIVATE_REVIEW_REQUIRED") &&
        attribute(attrs, "golem.time_basis", "REPLAY_PREFIX_NO_WALL_CLOCK");
    /* One log per redacted snapshot file, not per alleged live execution.
     * Manifest carries policy, omissions and optional source Work head. */
    for (size_t i = 0; ok && i <= RB_PAYLOADS; ++i) {
        struct json_object *record = json_object_new_object(), *body = json_object_new_object(),
            *attributes = json_object_new_array();
        ok = attribute(attributes, "golem.payload.name", rb_names[i]) &&
            ex_text(body, "stringValue", dw_text(files, rb_names[i])) &&
            dw_add(record, "body", json_object_get(body)) &&
            dw_add(record, "attributes", json_object_get(attributes));
        json_object_put(body); json_object_put(attributes);
        if (ok) ok = push(logs, record); else json_object_put(record);
    }
    ok = ok && dw_add(resource, "attributes", json_object_get(attrs)) &&
        dw_add(resource_logs, "resource", json_object_get(resource)) &&
        ex_text(scope, "name", "golem.research.derived") && ex_text(scope, "version", "1") &&
        dw_add(scope_logs, "scope", json_object_get(scope)) &&
        dw_add(scope_logs, "logRecords", json_object_get(logs)) &&
        push(scopes, json_object_get(scope_logs)) &&
        dw_add(resource_logs, "scopeLogs", json_object_get(scopes)) &&
        push(resources, json_object_get(resource_logs)) &&
        dw_add(root, "resourceLogs", json_object_get(resources));
    json_object_put(resources); json_object_put(resource_logs); json_object_put(resource);
    json_object_put(attrs); json_object_put(scopes); json_object_put(scope_logs);
    json_object_put(scope); json_object_put(logs);
    if (ok) *out = root; else json_object_put(root);
    return ok ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
}
static bool relation(struct json_object *group, const char *id,
    const char *key1, const char *value1, const char *key2, const char *value2)
{
    struct json_object *o = json_object_new_object();
    bool ok = ex_text(o, key1, value1) && ex_text(o, key2, value2);
    if (!ok) { json_object_put(o); return false; }
    return dw_add(group, id, o);
}
static golem_status prov(struct json_object *files, const char *hash, struct json_object **out)
{
    const char *inventory = dw_text(files, "evidence-inventory.json");
    struct json_object *inv = NULL;
    golem_status st = golem_json_parse((golem_bytes){(const uint8_t *)inventory, strlen(inventory)},
        GOLEM_RESEARCH_BUNDLE_MAX_JSON, &inv);
    if (st != GOLEM_OK) return st;
    struct json_object *root = json_object_new_object(), *prefix = json_object_new_object(),
        *entities = json_object_new_object(), *activities = json_object_new_object(),
        *used = json_object_new_object(), *generated = json_object_new_object(),
        *derived = json_object_new_object(), *bundle = json_object_new_object(),
        *output = json_object_new_object(), *redact = json_object_new_object(),
        *mapping = json_object_new_object();
    char ns[128]; (void)snprintf(ns, sizeof(ns), "urn:golem:derived:%s:", hash);
    bool ok = ex_text(prefix, "g", ns) && ex_text(prefix, "prov", "http://www.w3.org/ns/prov#") &&
        ex_text(bundle, "prov:label", "Structurally redacted case-study bundle") &&
        ex_text(bundle, "g:manifest_sha256", hash) &&
        ex_text(bundle, "g:manifest", dw_text(files, "manifest.json")) &&
        ex_text(output, "g:mapping", "golem.observability.v1") &&
        ex_text(output, "g:authority", "DERIVED_ONLY") &&
        ex_text(output, "g:privacy", "PRIVATE_REVIEW_REQUIRED") &&
        ex_text(output, "g:scope", "DIRECT_INVENTORY_NO_TRANSITIVE_EXPANSION") &&
        ex_text(output, "g:identity", "CONTENT_PROJECTION_NOT_EXECUTION_IDENTITY") &&
        ex_text(output, "g:time_basis", "REPLAY_PREFIX_NO_WALL_CLOCK") &&
        ex_text(redact, "prov:label", "Structural redaction and direct CAS verification") &&
        ex_text(mapping, "prov:label", "Deterministic PROV mapping") &&
        dw_add(entities, "g:bundle", json_object_get(bundle)) &&
        dw_add(entities, "g:projection", json_object_get(output)) &&
        dw_add(activities, "g:redact", json_object_get(redact)) &&
        dw_add(activities, "g:map", json_object_get(mapping)) &&
        relation(generated, "g:gb", "prov:entity", "g:bundle", "prov:activity", "g:redact") &&
        relation(generated, "g:gp", "prov:entity", "g:projection", "prov:activity", "g:map") &&
        relation(used, "g:ub", "prov:activity", "g:map", "prov:entity", "g:bundle") &&
        relation(derived, "g:db", "prov:generatedEntity", "g:projection", "prov:usedEntity", "g:bundle");
    struct json_object *items = dw_get(inv, "items");
    for (size_t i = 0; ok && i < json_object_array_length(items); ++i) {
        struct json_object *item = json_object_array_get_idx(items, i), *entity = json_object_new_object();
        char id[80], use[80], derivation[80];
        (void)snprintf(id, sizeof(id), "g:%s", dw_text(item, "evidence_id"));
        (void)snprintf(use, sizeof(use), "g:u%zu", i);
        (void)snprintf(derivation, sizeof(derivation), "g:d%zu", i);
        ok = ex_text(entity, "g:disposition", "RAW_OMITTED");
        if (ok && dw_get(item, "source_sha256"))
            ok = ex_text(entity, "g:source_sha256", dw_text(item, "source_sha256"));
        if (ok) ok = dw_add(entities, id, entity); else json_object_put(entity);
        ok = ok && relation(used, use, "prov:activity", "g:redact", "prov:entity", id) &&
            relation(derived, derivation, "prov:generatedEntity", "g:bundle", "prov:usedEntity", id);
    }
    ok = ok && dw_add(root, "prefix", json_object_get(prefix)) &&
        dw_add(root, "entity", json_object_get(entities)) &&
        dw_add(root, "activity", json_object_get(activities)) &&
        dw_add(root, "used", json_object_get(used)) &&
        dw_add(root, "wasGeneratedBy", json_object_get(generated)) &&
        dw_add(root, "wasDerivedFrom", json_object_get(derived));
    json_object_put(inv); json_object_put(prefix); json_object_put(entities); json_object_put(activities);
    json_object_put(used); json_object_put(generated); json_object_put(derived);
    json_object_put(bundle); json_object_put(output); json_object_put(redact); json_object_put(mapping);
    if (ok) *out = root; else json_object_put(root);
    return ok ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
}
golem_status golem_research_observability(golem_document_store *store, const char *case_id,
    golem_bytes policy, golem_research_export_format format,
    golem_execution_reply *out, golem_diagnostic *diag)
{
    if (!store || !case_id || !out || (format != GOLEM_RESEARCH_EXPORT_OTLP_LOGS &&
        format != GOLEM_RESEARCH_EXPORT_PROV_JSON)) return dw_report(diag, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    golem_execution_reply bundle = {0}; struct json_object *parsed = NULL, *mapped = NULL;
    golem_status st = golem_research_bundle(store, case_id, policy, &bundle, diag);
    if (st == GOLEM_OK) st = golem_json_parse((golem_bytes){bundle.data, bundle.size},
        GOLEM_RESEARCH_BUNDLE_MAX_JSON, &parsed);
    struct json_object *files = dw_get(parsed, "files");
    const char *manifest = dw_text(files, "manifest.json"); golem_digest digest; char hex[65];
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){(const uint8_t *)manifest, strlen(manifest)}, &digest);
    size_t required = 0;
    if (st == GOLEM_OK) st = golem_digest_format(&digest, hex, sizeof(hex), &required);
    if (st == GOLEM_OK) st = format == GOLEM_RESEARCH_EXPORT_OTLP_LOGS ? otlp(files, hex, &mapped) : prov(files, hex, &mapped);
    if (st == GOLEM_OK) {
        const char *text = json_object_to_json_string_ext(mapped, JSON_C_TO_STRING_PLAIN);
        if (!text) st = GOLEM_ERR_OUT_OF_MEMORY;
        else if (strlen(text) > GOLEM_RESEARCH_BUNDLE_MAX_JSON) st = GOLEM_ERR_BUDGET_EXHAUSTED;
        else {
            size_t n = strlen(text); uint8_t *data = malloc(n+1);
            if (!data) st = GOLEM_ERR_OUT_OF_MEMORY;
            else { memcpy(data, text, n+1); *out = (golem_execution_reply){data, n}; }
        }
    }
    json_object_put(mapped); json_object_put(parsed); golem_execution_reply_free(&bundle);
    return dw_report(diag, st, NULL);
}
