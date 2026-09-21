#include "internal.h"
#include "golem/adapter_protocol.h"
#include <stdio.h>
#include <string.h>

static golem_status read_envelope(bool packed, golem_adapter_envelope *out)
{
    uint8_t input[GOLEM_ADAPTER_JSON_MAX + 1];
    size_t limit = packed ? GOLEM_ADAPTER_MSGPACK_MAX : GOLEM_ADAPTER_JSON_MAX;
    size_t n = fread(input, 1, limit + 1, stdin);
    if (ferror(stdin)) return GOLEM_ERR_IO;
    golem_bytes bytes = {input, n};
    return packed ? golem_adapter_msgpack_decode(bytes, out, NULL) : golem_adapter_envelope_decode(bytes, out, NULL);
}
static int emit(golem_status s, bool packed, const golem_adapter_envelope *e)
{
    uint8_t output[GOLEM_ADAPTER_JSON_MAX + 1]; size_t n;
    if (s == GOLEM_OK) s = packed ? golem_adapter_msgpack_encode(e, output, sizeof(output), &n, NULL) :
        golem_adapter_envelope_encode(e, (char *)output, sizeof(output), &n, NULL);
    if (s != GOLEM_OK) { fprintf(stderr, "golem: %s\n", golem_status_string(s)); return 1; }
    if (!packed) output[n - 1] = '\n';
    if (fwrite(output, 1, n, stdout) != n) return 1;
    return fflush(stdout) == 0 && !ferror(stdout) ? 0 : 1;
}
static bool format(const char *name) { return strcmp(name, "json") == 0 || strcmp(name, "msgpack") == 0; }

int golem_cli_adapter(int argc, char **argv)
{
    if (argc == 5 && strcmp(argv[2], "convert") == 0 && format(argv[3]) && format(argv[4])) {
        golem_adapter_envelope e;
        golem_status s = read_envelope(strcmp(argv[3], "msgpack") == 0, &e);
        return emit(s, strcmp(argv[4], "msgpack") == 0, &e);
    }
    bool packed = false;
    if (argc >= 6 && strcmp(argv[argc - 2], "--format") == 0 && format(argv[argc - 1])) {
        packed = strcmp(argv[argc - 1], "msgpack") == 0; argc -= 2;
    }
    bool probe = argc == 4 && strcmp(argv[3], "probe") == 0;
    bool run = argc == 5 && strcmp(argv[3], "run") == 0;
    if (argc < 4 || strcmp(argv[2], "noop") != 0 || (!probe && !run)) {
        fputs("Usage: golem adapter noop probe | run STORE [--format json|msgpack]\n"
              "       golem adapter convert json|msgpack json|msgpack < envelope\n", stderr); return 2;
    }
    golem_adapter_envelope response = {0};
    golem_status s;
    if (probe) {
        golem_adapter *adapter = NULL;
        s = golem_adapter_noop_create(NULL, &adapter);
        response.type = GOLEM_ADAPTER_CAPABILITY;
        if (s == GOLEM_OK) s = golem_adapter_probe(adapter, &response.data.capability, NULL);
        golem_adapter_free(adapter);
    } else {
        golem_adapter_envelope request;
        s = read_envelope(packed, &request);
        if (s == GOLEM_OK && request.type != GOLEM_ADAPTER_RUN_STAGE) s = GOLEM_ERR_INVALID_ARGUMENT;
        golem_evidence_store *store = NULL;
        if (s == GOLEM_OK) s = golem_evidence_open(argv[4], true, NULL, &store, NULL);
        response.type = GOLEM_ADAPTER_STAGE_RESULT;
        if (s == GOLEM_OK) s = golem_adapter_noop_run_stage(&request.data.request, store, &response.data.result, NULL);
        golem_status closed = golem_evidence_close(store);
        if (s == GOLEM_OK) s = closed;
    }
    return emit(s, packed, &response);
}
