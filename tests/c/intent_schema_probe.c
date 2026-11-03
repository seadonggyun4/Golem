/* Pure stdin probe: no Work, journal, host scope, subprocess or publication. */
#include "../../src/intent/schema.h"
#include "../../src/common/json.h"
#include "golem/completion.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
golem_status qc_schema_policy(struct json_object *value);
golem_status qc_schema_request(struct json_object *value);
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    unsigned char *data = malloc(GI_CONTROL_MAX + 1u);
    if (!data) return 2;
    size_t n = fread(data, 1, GI_CONTROL_MAX + 1u, stdin);
    if (ferror(stdin)) { free(data); return 2; }
    golem_bytes bytes = {data, n};
    struct json_object *value = NULL;
    golem_status st = golem_json_parse(bytes, GI_CONTROL_MAX, &value);
    golem_digest digest = {{0}};
    bool identity = !strcmp(argv[1], "identity");
    if (identity) st = gi_domain_digest(bytes, &digest, NULL);
    else if (!strcmp(argv[1], "completion")) st = golem_completion_validate(bytes, NULL);
    else if (!strcmp(argv[1], "policy")) { if (st == GOLEM_OK) st = qc_schema_policy(value); }
    else if (!strcmp(argv[1], "request")) { if (st == GOLEM_OK) st = qc_schema_request(value); }
    else if (strcmp(argv[1], "json")) { json_object_put(value); free(data); return 2; }
    char hex[65] = {0}; size_t written = 0;
    if (identity && st == GOLEM_OK && golem_digest_format(&digest, hex, sizeof(hex), &written) != GOLEM_OK) {
        json_object_put(value); free(data); return 2;
    }
    printf("{\"accepted\":%s,\"status\":%d,\"digest\":\"%s\"}\n", st == GOLEM_OK ? "true" : "false", (int)st, hex);
    json_object_put(value); free(data); return 0;
}
