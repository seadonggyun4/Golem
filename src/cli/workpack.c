#include "work.h"
#include "golem/workpack.h"
#include "golem/version.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Full bounded JSON to stdout only: no automatic output-store publication.
 * The existing top-level explicitly configured recording contract still applies. */
int golem_cli_workpack(int argc, char **argv)
{
    if (argc < 4) return 2;
    if (!strcmp(argv[2], "resolve") || !strcmp(argv[2], "bind") || !strcmp(argv[2], "explain")) {
        bool bind = !strcmp(argv[2], "bind"), explain = !strcmp(argv[2], "explain");
        if ((explain && argc != 4) || (!explain && argc != 5 && !(bind && argc == 7 && !strcmp(argv[5], "--approve-binding")))) return 2;
        cli_blob input = {0}; golem_document_store *store = NULL;
        golem_execution_reply reply = {0}; golem_digest approval;
        golem_status status = explain ? GOLEM_OK : cli_read(argv[4], 131072, &input);
        if (status == GOLEM_OK && argc == 7) status = golem_digest_parse((golem_string_view){argv[6], strlen(argv[6])}, &approval);
        if (status == GOLEM_OK) status = golem_document_store_open(argv[3], bind, NULL, &store, NULL);
        if (status == GOLEM_OK && explain) status = golem_workpack_explain(store, &reply, NULL);
        if (status == GOLEM_OK && !explain && bind) status = golem_workpack_bind(store, (golem_bytes){input.data,input.size}, argc == 7 ? &approval : NULL, &reply, NULL);
        if (status == GOLEM_OK && !explain && !bind) status = golem_workpack_resolve(store, (golem_bytes){input.data,input.size}, &reply, NULL);
        golem_status closed = golem_document_store_close(store);
        if (status == GOLEM_OK) status = closed;
        if (status == GOLEM_OK && (fwrite(reply.data, 1, reply.size, stdout) != reply.size || puts("") == EOF || fflush(stdout))) status = GOLEM_ERR_IO;
        free(input.data); golem_execution_reply_free(&reply);
        cli_error_note(status, "pack.binding", NULL);
        return status == GOLEM_OK ? 0 : 1;
    }
    if (!strcmp(argv[2], "list") || !strcmp(argv[2], "search")) {
        bool search = !strcmp(argv[2], "search");
        if ((!search && (argc != 5 || strcmp(argv[3], "--catalog"))) ||
            (search && (argc != 6 || strcmp(argv[4], "--catalog")))) return 2;
        const char *path = argv[search ? 5 : 4];
        golem_string_view query = search ? (golem_string_view){argv[3], strlen(argv[3])} : (golem_string_view){NULL, 0};
        char *output = malloc(GOLEM_WORKPACK_CATALOG_REPORT_MAX); size_t required = 0;
        golem_diagnostic diagnostic;
        golem_status status = output ? golem_workpack_catalog(path, query, output, GOLEM_WORKPACK_CATALOG_REPORT_MAX, &required, &diagnostic) : GOLEM_ERR_OUT_OF_MEMORY;
        if (status != GOLEM_OK) { cli_error_note(status, "pack.catalog", output ? &diagnostic : NULL); free(output); return 1; }
        int failed = puts(output) == EOF || fflush(stdout) || ferror(stdout);
        free(output);
        if (failed) { cli_error_note(GOLEM_ERR_IO, "pack.stdout", NULL); return 1; }
        return 0;
    }
    bool inspect = !strcmp(argv[2], "inspect"), compatibility = !strcmp(argv[2], "compatibility");
    if (!inspect && !compatibility && strcmp(argv[2], "validate")) return 2;
    if (argc != 4 && !(compatibility && argc == 6 && !strcmp(argv[4], "--core-version"))) return 2;
    const char *core = argc == 6 ? argv[5] : GOLEM_VERSION_STRING;
    uint8_t input[GOLEM_WORKPACK_MAX_JSON]; size_t size = 0;
    golem_diagnostic diagnostic;
    golem_status status = golem_workpack_read(argv[3], input, sizeof(input), &size, &diagnostic);
    golem_digest digest; char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t required = 0;
    golem_bytes bytes = {input, size}; bool compatible = false;
    if (status == GOLEM_OK) status = golem_workpack_validate(bytes, &digest, &diagnostic);
    if (status == GOLEM_OK && compatibility)
        status = golem_workpack_compatibility(bytes, (golem_string_view){core, strlen(core)}, &compatible, &diagnostic);
    char *metadata = NULL;
    if (status == GOLEM_OK && inspect) {
        status = golem_workpack_inspect(bytes, NULL, 0, &required, &diagnostic);
        if (status == GOLEM_ERR_BUFFER_TOO_SMALL) {
            metadata = malloc(required);
            status = metadata ? golem_workpack_inspect(bytes, metadata, required, &required, &diagnostic) : GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    if (status == GOLEM_OK) status = golem_digest_format(&digest, hex, sizeof(hex), &required);
    if (status != GOLEM_OK) {
        free(metadata); cli_error_note(status, "pack.read_validate", &diagnostic); return 1;
    }
    int failed = printf("{\"schema\":\"golem.workpack.report.v0\",\"operation\":\"%s\",\"exact_digest\":\"%s\",\"size\":%zu,\"structurally_valid\":true,\"authorized\":false,\"bound\":false,\"work_done\":false", argv[2], hex, size) < 0;
    if (inspect && printf(",\"manifest\":%s", metadata) < 0) failed = 1;
    /* core is validated ASCII numeric x.y.z before interpolation. */
    if (compatibility && printf(",\"core_version\":\"%s\",\"declared_compatible\":%s,\"runtime_availability\":\"NOT_EVALUATED\"", core, compatible ? "true" : "false") < 0) failed = 1;
    if (puts("}") == EOF || fflush(stdout) || ferror(stdout)) failed = 1;
    free(metadata);
    if (failed) { cli_error_note(GOLEM_ERR_IO, "pack.stdout", NULL); return 1; }
    if (compatibility && !compatible) { cli_error_note(GOLEM_ERR_UNSUPPORTED_VERSION, "pack.compatibility", NULL); return 1; }
    return 0;
}
