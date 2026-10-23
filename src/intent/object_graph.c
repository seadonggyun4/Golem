#include "object_graph.h"
#include "object_inventory.h"
#include "../common/json.h"
#include <stdlib.h>
#include <string.h>

static struct json_object *get(struct json_object *o, const char *key)
{
    struct json_object *v = NULL; (void)json_object_object_get_ex(o, key, &v); return v;
}
static golem_status require_object(struct json_object *declared, struct json_object *used,
    gi_object_kind kind, const golem_digest *digest, size_t length)
{
    char path[192]; golem_status st = gi_object_path(kind, digest, path, sizeof(path));
    if (st != GOLEM_OK) return st;
    struct json_object *row = get(declared, path);
    if (!row || json_object_get_uint64(get(row, "byte_length")) != length) return GOLEM_ERR_INVALID_STATE;
    if (!json_object_object_get_ex(used, path, NULL) && json_object_object_add(used, path, NULL) != 0)
        return GOLEM_ERR_OUT_OF_MEMORY;
    return GOLEM_OK;
}
golem_status gi_object_graph_load(int root, golem_bytes preparation, size_t byte_limit, gi_object_graph *out)
{
    if (root < 0 || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    gi_object_preparation_result manifest;
    golem_status st = gi_object_preparation_validate(preparation, &manifest, NULL);
    if (st != GOLEM_OK) return st;
    struct json_object *m = NULL, *b = NULL, *declared = json_object_new_object(), *used = json_object_new_object();
    uint8_t *baseline = NULL; size_t baseline_size = 0, count = 0, total = 0, retained = 0;
    gi_source_input *sources = NULL; gi_baseline_coverage_result result;
    if (!declared || !used) { st = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    st = golem_json_parse(preparation, GI_CONTROL_MAX, &m);
    if (st != GOLEM_OK) goto done;
    struct json_object *objects = get(m, "objects");
    for (size_t i = 0; i < json_object_array_length(objects); ++i) {
        struct json_object *row = json_object_array_get_idx(objects, i);
        if (json_object_object_add(declared, json_object_get_string(get(row, "path")), json_object_get(row)) != 0) {
            json_object_put(row); st = GOLEM_ERR_OUT_OF_MEMORY; goto done;
        }
    }
    st = gi_object_load(root, GI_OBJECT_BASELINE, &manifest.reservation.publication.baseline,
        GI_CONTROL_MAX, &baseline, &baseline_size);
    if (st != GOLEM_OK) goto done;
    if (baseline_size > byte_limit) { st = GOLEM_ERR_OVERFLOW; goto done; }
    retained = baseline_size;
    gi_baseline_result shape;
    st = gi_baseline_validate((golem_bytes){baseline, baseline_size}, &shape, NULL);
    if (st == GOLEM_OK) st = require_object(declared, used, GI_OBJECT_BASELINE,
        &manifest.reservation.publication.baseline, baseline_size);
    if (st == GOLEM_OK) st = golem_json_parse((golem_bytes){baseline, baseline_size}, GI_CONTROL_MAX, &b);
    if (st != GOLEM_OK) goto done;
    count = shape.sources; sources = calloc(count, sizeof(*sources));
    if (!sources) { st = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    struct json_object *refs = get(get(b, "body"), "source_refs");
    for (size_t i = 0; i < count && st == GOLEM_OK; ++i) {
        golem_digest source, raw; uint8_t *control = NULL, *text = NULL; size_t cn = 0, tn = 0;
        const char *hex = json_object_get_string(json_object_array_get_idx(refs, i));
        st = golem_digest_parse((golem_string_view){hex, 64}, &source);
        if (st == GOLEM_OK) st = gi_object_load(root, GI_OBJECT_SOURCE, &source, GI_CONTROL_MAX, &control, &cn);
        sources[i].control = (golem_bytes){control, cn};
        if (st == GOLEM_OK && cn > byte_limit - retained) st = GOLEM_ERR_OVERFLOW;
        if (st == GOLEM_OK) retained += cn;
        if (st == GOLEM_OK) st = require_object(declared, used, GI_OBJECT_SOURCE, &source, cn);
        struct json_object *s = NULL;
        if (st == GOLEM_OK) st = golem_json_parse(sources[i].control, GI_CONTROL_MAX, &s);
        if (st == GOLEM_OK) {
            struct json_object *cas = get(get(s, "body"), "body_cas");
            if (!json_object_is_type(cas, json_type_string) || json_object_get_string_len(cas) != 64) st = GOLEM_ERR_PARSE;
            else st = golem_digest_parse((golem_string_view){json_object_get_string(cas), 64}, &raw);
        }
        json_object_put(s);
        if (st == GOLEM_OK) st = gi_object_load(root, GI_OBJECT_RAW, &raw, GI_BASELINE_SOURCE_MAX - total, &text, &tn);
        sources[i].text = (golem_bytes){text, tn}; total += tn;
        if (st == GOLEM_OK && tn > byte_limit - retained) st = GOLEM_ERR_OVERFLOW;
        if (st == GOLEM_OK) retained += tn;
        if (st == GOLEM_OK) st = require_object(declared, used, GI_OBJECT_RAW, &raw, tn);
    }
    if (st == GOLEM_OK && json_object_object_length(declared) != json_object_object_length(used)) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) st = gi_baseline_coverage_validate((golem_bytes){baseline, baseline_size}, sources, count, &result, NULL);
    if (st == GOLEM_OK) {
        *out = (gi_object_graph){(golem_bytes){baseline, baseline_size}, sources, count, result};
        baseline = NULL; sources = NULL;
    }
done:
    if (sources) for (size_t i = 0; i < count; ++i) { free((void *)sources[i].control.data); free((void *)sources[i].text.data); }
    free(sources); free(baseline); json_object_put(m); json_object_put(b); json_object_put(declared); json_object_put(used);
    return st;
}

void gi_object_graph_dispose(gi_object_graph *graph)
{
    if (!graph) return;
    for (size_t i = 0; i < graph->source_count; ++i) {
        free((void *)graph->sources[i].control.data);
        free((void *)graph->sources[i].text.data);
    }
    free(graph->sources); free((void *)graph->baseline.data);
    memset(graph, 0, sizeof(*graph));
}

golem_status gi_object_graph_validate(int root, golem_bytes preparation, gi_baseline_coverage_result *out)
{
    if (!out) return GOLEM_ERR_INVALID_ARGUMENT;
    gi_object_graph graph = {0};
    golem_status st = gi_object_graph_load(root, preparation, SIZE_MAX, &graph);
    if (st == GOLEM_OK) *out = graph.coverage;
    gi_object_graph_dispose(&graph);
    return st;
}
