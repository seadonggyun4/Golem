#include "work.h"
#include "golem/adapter_descriptor.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int emit(golem_status status, const void *data, size_t n)
{
    if (n && (fwrite(data, 1, n, stdout) != n || fputc('\n', stdout) == EOF || fflush(stdout)))
        return 1;
    if (status != GOLEM_OK)
        fprintf(stderr, "golem: %s\n", golem_status_string(status));
    return status == GOLEM_OK ? 0 : 1;
}
static int probe(int argc, char **argv)
{
    if (argc != 8 || strcmp(argv[7], "--allow-process")) {
        fputs(
            "usage: golem adapter probe ABS_EXECUTABLE SHA256 ABS_CWD TIMEOUT_MS --allow-process\n",
            stderr);
        return 2;
    }
    uint64_t ms = 0;
    for (const char *p = argv[6]; *p; ++p) {
        if (*p < '0' || *p > '9' || ms > 30000)
            return 2;
        ms = ms * 10 + (unsigned)(*p - '0');
    }
    if (!ms || ms > 30000)
        return 2;
    golem_harness_probe_options options = {0};
    options.size = sizeof(options);
    options.version = 1;
    options.allow_process = true;
    options.executable = argv[3];
    options.cwd = argv[5];
    options.timeout_ns = ms * UINT64_C(1000000);
    golem_status s = golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])},
                                        &options.expected_executable);
    if (s != GOLEM_OK)
        return emit(s, NULL, 0);
    golem_harness_probe_result result = {0};
    s = golem_harness_probe(&options, &result);
    /* Preflight errors publish no receipt; no subprocess invocation is implied. */
    if (!result.duration_ns)
        return emit(s, NULL, 0);
    char buffer[GOLEM_DESCRIPTOR_MAX_BYTES];
    size_t n = 0;
    golem_status encoded = golem_harness_probe_encode(&result, buffer, sizeof(buffer), &n);
    return encoded == GOLEM_OK ? emit(s, buffer, n) : emit(encoded, NULL, 0);
}
int golem_cli_adapter_descriptor(int argc, char **argv)
{
    if (argc > 2 && !strcmp(argv[2], "probe"))
        return probe(argc, argv);
    golem_adapter_descriptor descriptor;
    golem_status s = GOLEM_ERR_INVALID_ARGUMENT;
    if ((argc == 5 || argc == 6) && !strcmp(argv[3], "--current")) {
        s = golem_adapter_descriptor_current(argv[4], argc == 6 ? argv[5] : "", &descriptor);
    } else if (argc == 4 && !strcmp(argv[3], "noop")) {
        golem_adapter *adapter = NULL;
        golem_adapter_capability capability;
        s = golem_adapter_noop_create(NULL, &adapter);
        if (s == GOLEM_OK)
            s = golem_adapter_probe(adapter, &capability, NULL);
        if (s == GOLEM_OK)
            s = golem_adapter_descriptor_from_v1(&capability, &descriptor);
        golem_adapter_free(adapter);
    } else if (argc == 4) {
        cli_blob blob = {0};
        s = cli_read(argv[3], GOLEM_DESCRIPTOR_MAX_BYTES, &blob);
        if (s == GOLEM_OK)
            s = golem_adapter_descriptor_decode((golem_bytes){blob.data, blob.size}, &descriptor);
        free(blob.data);
    } else {
        fputs("usage: golem adapter describe DESCRIPTOR.json|noop\n"
              "       golem adapter describe --current ADAPTER_ID [SESSION_ID]\n",
              stderr);
        return 2;
    }
    char buffer[GOLEM_DESCRIPTOR_MAX_BYTES];
    size_t n = 0;
    if (s == GOLEM_OK)
        s = golem_adapter_descriptor_encode(&descriptor, buffer, sizeof(buffer), &n);
    return emit(s, buffer, s == GOLEM_OK ? n : 0);
}
