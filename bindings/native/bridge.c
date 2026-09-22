#include "golem/binding.h"
#include "../../src/cli/work.h"
#include <stdlib.h>
#include <string.h>

uint32_t golem_binding_abi_version(void) { return GOLEM_BINDING_ABI_VERSION; }
void golem_binding_free(void *result) { free(result); }
const char *golem_binding_status_message(int32_t status) { return golem_status_string((golem_status)status); }

static golem_status validate(golem_bytes bytes, struct json_object **out)
{
    golem_work_capsule *capsule = NULL;
    golem_status s = cli_capsule_decode(bytes, &capsule);
    if (s != GOLEM_OK) return s;
    golem_capsule_spec spec; golem_graph_spec graph;
    s = golem_work_capsule_spec_borrow(capsule, &spec);
    if (s == GOLEM_OK) s = golem_stage_graph_spec_get(spec.graph, &graph);
    struct json_object *o = NULL, *stages = NULL;
    if (s == GOLEM_OK) {
        o = json_object_new_object(); stages = json_object_new_array();
        if (o == NULL || stages == NULL) { json_object_put(stages); s = GOLEM_ERR_OUT_OF_MEMORY; }
        else if (!cli_json_add(o, "stages", stages) ||
            !cli_json_add(o, "schema_version", json_object_new_int(1)) ||
            !cli_json_add(o, "valid", json_object_new_boolean(true)) ||
            !cli_json_add(o, "id", json_object_new_string(spec.id))) s = GOLEM_ERR_OUT_OF_MEMORY;
        else for (size_t i = 0; i < graph.count; ++i)
            if (!cli_json_append(stages, json_object_new_string(golem_stage_name(graph.order[i])))) { s = GOLEM_ERR_OUT_OF_MEMORY; break; }
    }
    golem_work_capsule_free(capsule);
    if (s != GOLEM_OK) json_object_put(o);
    else *out = o;
    return s;
}
static golem_status replay(golem_bytes bytes, struct json_object **out)
{
    golem_replay *engine = NULL; golem_work_run *run = NULL; golem_replay_report report;
    golem_status s = golem_replay_create(NULL, NULL, &engine, NULL);
    if (s == GOLEM_OK) s = golem_replay_feed(engine, bytes, NULL);
    if (s == GOLEM_OK) s = golem_replay_finish(engine, &run, &report, NULL);
    if (s == GOLEM_OK) {
        *out = cli_run_projection(run, &report, false);
        if (*out == NULL) s = GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_work_run_free(run); golem_replay_free(engine); return s;
}
int32_t golem_binding_call(uint32_t operation, const uint8_t *data, size_t size, char **out, size_t *out_size)
{
    if (out == NULL || out_size == NULL || data == NULL || size == 0 ||
        (operation != GOLEM_BINDING_VALIDATE && operation != GOLEM_BINDING_REPLAY) ||
        size > (operation == GOLEM_BINDING_VALIDATE ? GOLEM_BINDING_CAPSULE_MAX : GOLEM_BINDING_JOURNAL_MAX))
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *object = NULL;
    golem_status s = operation == GOLEM_BINDING_VALIDATE ? validate((golem_bytes){data, size}, &object) : replay((golem_bytes){data, size}, &object);
    if (s == GOLEM_OK) {
        const char *json = json_object_to_json_string_ext(object, JSON_C_TO_STRING_PLAIN);
        if (json == NULL) s = GOLEM_ERR_OUT_OF_MEMORY;
        else {
            size_t n = strlen(json);
            /* Journal v1 strings are byte strings. Do not let host runtimes
             * disagree by replacing invalid UTF-8 during JSON conversion. */
            struct json_tokener *tok = json_tokener_new_ex(16);
            if (tok == NULL) s = GOLEM_ERR_OUT_OF_MEMORY;
            else {
                json_tokener_set_flags(tok, JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
                struct json_object *checked = json_tokener_parse_ex(tok, json, (int)n);
                if (json_tokener_get_error(tok) != json_tokener_success) s = GOLEM_ERR_PARSE;
                json_object_put(checked); json_tokener_free(tok);
            }
            if (s == GOLEM_OK) {
                char *copy = malloc(n + 1);
                if (copy == NULL) s = GOLEM_ERR_OUT_OF_MEMORY;
                else { memcpy(copy, json, n + 1); *out = copy; *out_size = n; }
            }
        }
    }
    json_object_put(object); return (int32_t)s;
}
