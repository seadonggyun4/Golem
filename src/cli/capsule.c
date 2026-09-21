#include "work.h"
#include "../adapter_protocol/internal.h"
#include <string.h>

static struct json_object *get(struct json_object *o, const char *key) { return json_object_object_get(o, key); }
static bool list(struct json_object *o, const char **items, golem_string_list *out)
{
    if (!json_object_is_type(o, json_type_array) || json_object_array_length(o) > GOLEM_JOURNAL_MAX_LIST_ITEMS) return false;
    size_t n = json_object_array_length(o);
    for (size_t i = 0; i < n; ++i) {
        items[i] = cli_json_text(json_object_array_get_idx(o, i));
        if (items[i] == NULL || strlen(items[i]) > 4096) return false;
        for (size_t j = 0; j < i; ++j) if (strcmp(items[i], items[j]) == 0) return false;
    }
    *out = (golem_string_list){items, n}; return true;
}
static golem_stage stage(const char *name)
{
    if (name != NULL) for (int i = 0; i < GOLEM_STAGE_COUNT; ++i)
        if (strcmp(name, golem_stage_name((golem_stage)i)) == 0) return (golem_stage)i;
    return GOLEM_STAGE_NONE;
}
static int mode(const char *text)
{
    static const char *const modes[] = {"DENY", "AUTO_LOCAL", "ASK_ON_EXTERNAL_EFFECT", "ASK_ALWAYS"};
    if (text != NULL) for (size_t i = 0; i < 4; ++i) if (strcmp(text, modes[i]) == 0) return (int)i;
    return -1;
}
static bool acceptance(struct json_object *o, const golem_string_list *gates, const char **items,
    golem_string_list *out)
{
    if (!json_object_is_type(o, json_type_array) || json_object_array_length(o) > GOLEM_JOURNAL_MAX_LIST_ITEMS) return false;
    const char *ids[GOLEM_JOURNAL_MAX_LIST_ITEMS] = {0};
    static const char *const keys[] = {"id", "text", "required_gates"};
    size_t n = json_object_array_length(o);
    for (size_t i = 0; i < n; ++i) {
        struct json_object *entry = json_object_array_get_idx(o, i);
        items[i] = cli_json_text(entry);
        if (items[i] == NULL) {
            if (!cli_json_keys(entry, keys, 3) || json_object_object_length(entry) != 3) return false;
            ids[i] = cli_json_text(get(entry, "id")); items[i] = cli_json_text(get(entry, "text"));
            if (!golem_adapter_id_valid(ids[i])) return false;
            const char *gate_items[GOLEM_JOURNAL_MAX_LIST_ITEMS]; golem_string_list required;
            if (!list(get(entry, "required_gates"), gate_items, &required)) return false;
            for (size_t j = 0; j < required.count; ++j) {
                bool found = false;
                for (size_t k = 0; k < gates->count; ++k) if (strcmp(required.items[j], gates->items[k]) == 0) found = true;
                if (!found) return false;
            }
        }
        if (items[i] == NULL || strlen(items[i]) > 4096) return false;
        for (size_t j = 0; j < i; ++j)
            if (strcmp(items[i], items[j]) == 0 || (ids[i] != NULL && ids[j] != NULL && strcmp(ids[i], ids[j]) == 0)) return false;
    }
    *out = (golem_string_list){items, n}; return true;
}
golem_status cli_capsule_decode(golem_bytes data, golem_work_capsule **out)
{
    if (data.size > CLI_CAPSULE_MAX) return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *root = NULL; golem_status s = cli_json_parse(data, &root);
    if (s != GOLEM_OK) return s;
    static const char *const keys[] = {"schema_version", "id", "goal", "scope", "permissions", "stages",
        "acceptance", "expected_artifacts", "required_gates"};
    struct json_object *version = get(root, "schema_version");
    if (json_object_object_get_ex(root, "schema_version", &version) && (!json_object_is_type(version, json_type_int) || json_object_get_int64(version) != 1))
        s = GOLEM_ERR_UNSUPPORTED_VERSION;
    if (!cli_json_keys(root, keys, 9)) s = GOLEM_ERR_INVALID_ARGUMENT;
    golem_capsule_spec spec = {0}; golem_graph_spec gs;
    (void)golem_stage_graph_default_spec(&gs);
    spec.id = cli_json_text(get(root, "id")); spec.goal = cli_json_text(get(root, "goal"));
    if (!golem_adapter_id_valid(spec.id) || spec.goal == NULL || strlen(spec.goal) > 4096) s = GOLEM_ERR_INVALID_ARGUMENT;
    const char *lists[4][GOLEM_JOURNAL_MAX_LIST_ITEMS];
    if (!list(get(root, "scope"), lists[0], &spec.scope) ||
        !list(get(root, "expected_artifacts"), lists[2], &spec.expected_artifacts) ||
        !list(get(root, "required_gates"), lists[3], &spec.required_gates) ||
        !acceptance(get(root, "acceptance"), &spec.required_gates, lists[1], &spec.acceptance)) s = GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *stages = get(root, "stages"), *permissions = get(root, "permissions");
    if (!json_object_is_type(stages, json_type_array) || json_object_array_length(stages) == 0 ||
        json_object_array_length(stages) > GOLEM_STAGE_COUNT || !json_object_is_type(permissions, json_type_object)) s = GOLEM_ERR_INVALID_GRAPH;
    if (s == GOLEM_OK) {
        gs.count = json_object_array_length(stages);
        json_object_object_foreach(permissions, key, value) {
            golem_stage st = stage(key); int permission = mode(cli_json_text(value));
            if (st == GOLEM_STAGE_NONE || permission < 0) { s = GOLEM_ERR_INVALID_ARGUMENT; break; }
            spec.permissions[st] = (golem_autonomy)permission;
        }
        for (size_t i = 0; i < gs.count; ++i) {
            gs.order[i] = stage(cli_json_text(json_object_array_get_idx(stages, i)));
            if (gs.order[i] == GOLEM_STAGE_NONE || get(permissions, golem_stage_name(gs.order[i])) == NULL) s = GOLEM_ERR_INVALID_GRAPH;
        }
    }
    golem_stage_graph *graph = NULL;
    if (s == GOLEM_OK) s = golem_stage_graph_create(&gs, &graph);
    spec.graph = graph;
    if (s == GOLEM_OK) s = golem_work_capsule_create(&spec, out);
    golem_stage_graph_free(graph); json_object_put(root); return s;
}
struct json_object *cli_capsule_template(void)
{
    static const char source[] =
        "{\"schema_version\":1,\"id\":\"local-smoke\",\"goal\":\"Exercise the local simulation cycle\","
        "\"scope\":[\"local simulation\"],\"permissions\":{\"planning\":\"AUTO_LOCAL\",\"ux\":\"AUTO_LOCAL\","
        "\"publishing\":\"AUTO_LOCAL\",\"development\":\"AUTO_LOCAL\",\"qa\":\"AUTO_LOCAL\",\"audit\":\"AUTO_LOCAL\"},"
        "\"stages\":[\"planning\",\"ux\",\"publishing\",\"development\",\"qa\",\"audit\"],"
        "\"acceptance\":[\"Simulation results and evidence verify\"],\"expected_artifacts\":[\"simulation evidence\"],\"required_gates\":[\"audit\"]}";
    struct json_object *o = NULL;
    (void)cli_json_parse((golem_bytes){(const uint8_t *)source, sizeof(source) - 1}, &o); return o;
}
