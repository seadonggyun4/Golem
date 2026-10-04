#define _POSIX_C_SOURCE 200809L
#include "output.h"
#include "work.h"
#include "golem/evidence.h"
#include "golem/allocator.h"
#include "../evidence/internal.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define COMPACT_THRESHOLD 2048
#define COMPACT_LIMIT 2048
static bool full_output;
static const char *selected_store;
static const char *program = "golem";

int cli_output_options(int *argc, char **argv)
{
    const char *mode = getenv("GOLEM_CLI_OUTPUT");
    selected_store = getenv("GOLEM_CLI_OUTPUT_STORE");
    program = argv[0];
    int count = 1;
    bool mode_seen = false, store_seen = false;
    while (count < *argc) {
        bool output = !strcmp(argv[count], "--output-mode");
        bool store = !strcmp(argv[count], "--output-store");
        if (!output && !store) break;
        if (count + 1 >= *argc || (output && mode_seen) || (store && store_seen)) return 2;
        if (output) { mode = argv[count + 1]; mode_seen = true; }
        else { selected_store = argv[count + 1]; store_seen = true; }
        count += 2;
    }
    if (mode && strcmp(mode, "compact") && strcmp(mode, "full")) return 2;
    if (selected_store && selected_store[0] != '/') return 2;
    full_output = mode && !strcmp(mode, "full");
    if (count > 1) {
        memmove(argv + 1, argv + count, (size_t)(*argc - count + 1) * sizeof(*argv));
        *argc -= count - 1;
    }
    /* Explicit artifacts/templates/reports are already a request for full data. */
    if (*argc >= 3 && (!strcmp(argv[2], "report") || !strcmp(argv[2], "observability") ||
        (!strcmp(argv[1], "context") && !strcmp(argv[2], "read")))) full_output = true;
    return 0;
}

static golem_status store_path(char path[CLI_PATH_MAX])
{
    if (selected_store) {
        if (strlen(selected_store) >= CLI_PATH_MAX) return GOLEM_ERR_OVERFLOW;
        strcpy(path, selected_store);
        return GOLEM_OK;
    }
    const char *home = getenv("HOME");
    if (!home || home[0] != '/') return GOLEM_ERR_INVALID_ARGUMENT;
    return cli_path(home, ".golem-cli-output", path);
}

static golem_status private_store(const char *path, bool create, golem_evidence_store **store)
{
    int fd = golem_evidence_path_open(path, true);
    if (fd < 0 && create && errno == ENOENT) {
        golem_status st = cli_mkdir_new(path, &fd);
        /* Another invocation may have created the private root concurrently. */
        if (st != GOLEM_OK) {
            if (errno != EEXIST) return st;
            fd = golem_evidence_path_open(path, true);
        }
    }
    if (fd < 0) return GOLEM_ERR_IO;
    struct stat info;
    bool safe = fstat(fd, &info) == 0 && info.st_uid == geteuid() && !(info.st_mode & 0077);
    if (close(fd) != 0 || !safe) return GOLEM_ERR_IO;
    return golem_evidence_open(path, create, NULL, store, NULL);
}

static golem_status write_bytes(golem_bytes bytes)
{
    return fwrite(bytes.data, 1, bytes.size, stdout) == bytes.size && !fflush(stdout)
               ? GOLEM_OK : GOLEM_ERR_IO;
}

/* Diagnostic/denial trees stay intact even at exit zero. This is a conservative
 * fallback, not a semantic verdict or an exhaustive classifier of engine states. */
static bool diagnostic(struct json_object *value, unsigned depth)
{
    if (depth > 64) return true;
    if (json_object_is_type(value, json_type_string)) {
        const char *s = cli_json_text(value);
        static const char *const markers[] = {"BLOCKED", "FAIL", "FAILED", "ERROR", "DENIED",
            "RECOVERY_REQUIRED", "NOT_DONE", "SKIPPED", "NOT_EXECUTED", "UNKNOWN", "STALE",
            "REJECTED", "REMEDIATION_REQUIRED", "PARTIALLY_VERIFIED"};
        if (!s) return true;
        for (size_t i = 0; i < sizeof(markers) / sizeof(*markers); ++i)
            if (!strcmp(s, markers[i])) return true;
    } else if (json_object_is_type(value, json_type_array)) {
        for (size_t i = 0; i < json_object_array_length(value); ++i)
            if (diagnostic(json_object_array_get_idx(value, i), depth + 1)) return true;
    } else if (json_object_is_type(value, json_type_object)) {
        json_object_object_foreach(value, key, child) {
            const char *encoded = json_object_to_json_string_ext(child, JSON_C_TO_STRING_PLAIN);
            if (!encoded) return true;
            if ((!strcmp(key, "errors") || !strcmp(key, "failures") || !strcmp(key, "blockers") ||
                 !strcmp(key, "diagnostic") || !strcmp(key, "error") || !strcmp(key, "reason") ||
                 !strcmp(key, "human_approval") || !strcmp(key, "requirements") || !strcmp(key, "denied")) &&
                child && strcmp(encoded, "[]") && strcmp(encoded, "{}") && strcmp(encoded, "\"\"")) return true;
            if ((!strcmp(key, "allowed") || !strcmp(key, "authorized") || !strcmp(key, "lease_valid")) &&
                json_object_is_type(child, json_type_boolean) && !json_object_get_boolean(child)) return true;
            if (diagnostic(child, depth + 1)) return true;
        }
    }
    return false;
}

static bool protected_field(const char *key)
{
    static const char *const names[] = {"status", "state", "action", "reason", "next", "next_action",
        "permissions", "permission", "authorization", "lease", "approval", "human_approval",
        "acceptance", "requirements", "errors", "failures", "blockers", "diagnostic"};
    for (size_t i = 0; i < sizeof(names) / sizeof(*names); ++i)
        if (!strcmp(key, names[i])) return true;
    return false;
}

static struct json_object *projection(struct json_object *source, const char *root,
                                      const char *hex, size_t size)
{
    struct json_object *out = json_object_new_object(), *fields = json_object_new_object();
    struct json_object *omitted = json_object_new_array(), *next = json_object_new_array();
    struct json_object *evidence = json_object_new_object();
    bool ok = out && fields && omitted && next && evidence;
    json_object_object_foreach(source, key, value) {
        if (!ok) break;
        bool scalar = !json_object_is_type(value, json_type_object) && !json_object_is_type(value, json_type_array);
        const char *encoded = json_object_to_json_string_ext(value, JSON_C_TO_STRING_PLAIN);
        if (!encoded) { ok = false; break; }
        size_t length = strlen(encoded);
        if (protected_field(key) || length <= (scalar ? 256u : 512u)) {
            /* json-c represents JSON null by a NULL pointer. */
            if (json_object_object_add(fields, key, json_object_get(value)) != 0) ok = false;
        } else ok = cli_json_append(omitted, json_object_new_string(key));
    }
    const char *args[] = {program, "--output-store", root, "output", "read", hex};
    for (size_t i = 0; ok && i < sizeof(args) / sizeof(*args); ++i)
        ok = cli_json_append(next, json_object_new_string(args[i]));
    ok = ok && cli_json_add(evidence, "sha256", json_object_new_string(hex)) &&
         cli_json_add(evidence, "bytes", cli_json_u64(size)) &&
         cli_json_add(evidence, "store", json_object_new_string(root)) &&
         cli_json_add(out, "schema", json_object_new_string("golem.cli-output.v1")) &&
         cli_json_add(out, "view", json_object_new_string("compact")) &&
         cli_json_add(out, "partial", json_object_new_boolean(true)) &&
         cli_json_add(out, "read_before_action", json_object_new_boolean(true)) &&
         cli_json_add(out, "execution_authority", json_object_new_boolean(false)) &&
         cli_json_add(out, "fields", json_object_get(fields)) &&
         cli_json_add(out, "omitted", json_object_get(omitted)) &&
         cli_json_add(out, "evidence", json_object_get(evidence)) &&
         cli_json_add(out, "next_read_argv", json_object_get(next));
    json_object_put(fields); json_object_put(omitted); json_object_put(next); json_object_put(evidence);
    if (!ok) { json_object_put(out); return NULL; }
    return out;
}

golem_status cli_output_write(golem_bytes bytes)
{
    if (full_output || bytes.size <= COMPACT_THRESHOLD) return write_bytes(bytes);
    struct json_object *source = NULL, *view = NULL;
    if (cli_json_parse(bytes, &source) != GOLEM_OK || !json_object_is_type(source, json_type_object) ||
        diagnostic(source, 0)) {
        json_object_put(source);
        return write_bytes(bytes);
    }
    char root[CLI_PATH_MAX], hex[GOLEM_DIGEST_HEX_CAPACITY];
    golem_digest digest; size_t required;
    golem_status st = store_path(root);
    if (st == GOLEM_OK) st = golem_digest_bytes(bytes, &digest);
    if (st == GOLEM_OK) st = golem_digest_format(&digest, hex, sizeof(hex), &required);
    if (st == GOLEM_OK) view = projection(source, root, hex, bytes.size);
    if (st == GOLEM_OK && !view) st = GOLEM_ERR_OUT_OF_MEMORY;
    const char *text = view ? json_object_to_json_string_ext(view, JSON_C_TO_STRING_PLAIN) : NULL;
    if (view && !text) st = GOLEM_ERR_OUT_OF_MEMORY;
    bool smaller = text && strlen(text) < bytes.size && strlen(text) <= COMPACT_LIMIT;
    golem_evidence_store *store = NULL;
    if (st == GOLEM_OK && smaller) st = private_store(root, true, &store);
    golem_receipt receipt;
    if (st == GOLEM_OK && smaller) st = golem_evidence_put(store, bytes, &receipt, NULL);
    golem_status closed = golem_evidence_close(store);
    if (st == GOLEM_OK) st = closed;
    if (st != GOLEM_OK) {
        fprintf(stderr, "{\"schema\":\"golem.cli-output-error.v1\",\"code\":\"OUTPUT_STORE_UNAVAILABLE\","
                        "\"status_code\":%d,\"fallback\":\"full\",\"retry_effect\":false}\n", (int)st);
    }
    golem_status written = st == GOLEM_OK && smaller
        ? write_bytes((golem_bytes){(const uint8_t *)text, strlen(text)}) : write_bytes(bytes);
    json_object_put(view); json_object_put(source);
    return written;
}

int golem_cli_output(int argc, char **argv)
{
    if (argc != 4 || strcmp(argv[2], "read")) {
        fputs("usage: golem [--output-store ABSOLUTE_DIR] output read SHA256\n", stderr);
        return 2;
    }
    char root[CLI_PATH_MAX]; golem_digest digest;
    golem_status st = golem_digest_parse((golem_string_view){argv[3], strlen(argv[3])}, &digest);
    if (st == GOLEM_OK) st = store_path(root);
    golem_evidence_store *store = NULL;
    if (st == GOLEM_OK) st = private_store(root, false, &store);
    uint8_t *data = NULL; size_t size = 0;
    if (st == GOLEM_OK) st = golem_evidence_read(store, &digest, CLI_BUNDLE_MAX, NULL, &data, &size, NULL);
    golem_status closed = golem_evidence_close(store);
    if (st == GOLEM_OK) st = closed;
    if (st == GOLEM_OK) st = write_bytes((golem_bytes){data, size});
    if (st == GOLEM_OK && (fputc('\n', stdout) == EOF || fflush(stdout))) st = GOLEM_ERR_IO;
    golem_allocator_free(NULL, data);
    cli_error_note(st, "output_read", NULL);
    if (st != GOLEM_OK) fprintf(stderr, "golem output read: %s; do not rerun effects to recover output\n", golem_status_string(st));
    return st == GOLEM_OK ? 0 : 1;
}
