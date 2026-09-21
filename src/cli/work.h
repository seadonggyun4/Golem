#ifndef GOLEM_CLI_WORK_H
#define GOLEM_CLI_WORK_H
#include "golem/adapter_protocol.h"
#include "golem/journal.h"
#include "golem/replay.h"
#include <json-c/json.h>
#define CLI_PATH_MAX 4096
#define CLI_CAPSULE_MAX 131072
#define CLI_BUNDLE_MAX 2097152
typedef struct cli_blob { uint8_t *data; size_t size; } cli_blob;
/* CLI-private ownership: read/parse/load outputs owned by caller. All other
 * inputs borrowed. No partial output publication. json_add/append consume the
 * value on both success and failure, but never consume the parent. */
golem_status cli_read(const char *path, size_t limit, cli_blob *out);
golem_status cli_write_new(int dir, const char *name, golem_bytes data);
golem_status cli_mkdir_new(const char *path, int *out);
golem_status cli_path(const char *root, const char *name, char out[CLI_PATH_MAX]);
golem_status cli_json_parse(golem_bytes data, struct json_object **out);
bool cli_json_keys(struct json_object *o, const char *const *keys, size_t count);
const char *cli_json_text(struct json_object *o);
bool cli_json_add(struct json_object *o, const char *key, struct json_object *value);
bool cli_json_append(struct json_object *o, struct json_object *value);
struct json_object *cli_json_u64(uint64_t value);
golem_status cli_json_write(int dir, const char *name, struct json_object *o);
int cli_emit(golem_status status, struct json_object *o);
golem_status cli_capsule_decode(golem_bytes data, golem_work_capsule **out);
struct json_object *cli_capsule_template(void);
struct json_object *cli_cost_projection(const golem_work_run *run);
struct json_object *cli_run_projection(const golem_work_run *run, const golem_replay_report *report, bool complete);
golem_status cli_noop_run(const char *capsule_path, const char *output, struct json_object **out);
golem_status cli_bundle_verify(const char *root, struct json_object **summary, struct json_object **cost);
golem_status cli_replay_file(const char *path, const golem_replay_options *options,
    golem_work_run **out, golem_replay_report *report);
int golem_cli_work(int argc, char **argv);
#endif
