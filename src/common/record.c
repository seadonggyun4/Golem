#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/record.h"
#include "record_internal.h"
#include "golem/system_error.h"
#include "../evidence/internal.h"
#include <json-c/json.h>
#include <openssl/rand.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

#define RECORD_LIMIT UINT64_C(67108864)
struct golem_record {
    int directory, logs[2];
    uint64_t bytes[2];
    char id[33];
    char *executable, *source, *root;
    struct timespec started;
    struct json_object *intent;
    golem_status failure;
    struct golem_record *parent;
};
static _Thread_local golem_record *active;
static _Thread_local const gr_context *inherited;

golem_status gr_context_capture(gr_context *out)
{
    if (!out) return GOLEM_ERR_INVALID_ARGUMENT;
    const char *root = active ? active->root : inherited ? inherited->root : getenv("GOLEM_RECORD_ROOT");
    const char *source = active ? active->source : inherited ? inherited->source : getenv("GOLEM_RECORD_SOURCE_MANIFEST");
    gr_context value = {0};
    if (root && *root) {
        value.root = strdup(root);
        if (!value.root) return GOLEM_ERR_OUT_OF_MEMORY;
        if (source && !(value.source = strdup(source))) {
            free(value.root);
            return GOLEM_ERR_OUT_OF_MEMORY;
        }
        if (active) memcpy(value.parent, active->id, sizeof(value.parent));
        else if (inherited) memcpy(value.parent, inherited->parent, sizeof(value.parent));
    }
    *out = value;
    return GOLEM_OK;
}
void gr_context_dispose(gr_context *context)
{
    if (!context) return;
    free(context->root);
    free(context->source);
    *context = (gr_context){0};
}
golem_status gr_context_attach(const gr_context *context)
{
    if (!context) return GOLEM_ERR_INVALID_ARGUMENT;
    if (active || inherited) return GOLEM_ERR_INVALID_STATE;
    inherited = context;
    return GOLEM_OK;
}
golem_status gr_context_detach(const gr_context *context)
{
    if (!context || inherited != context || active) return GOLEM_ERR_INVALID_STATE;
    inherited = NULL;
    return GOLEM_OK;
}

static bool add(struct json_object *o, const char *key, struct json_object *value)
{
    if (!value) return false;
    if (json_object_object_add(o, key, value) == 0) return true;
    json_object_put(value);
    return false;
}
static bool text(struct json_object *o, const char *key, const char *value)
{
    return add(o, key, json_object_new_string(value ? value : ""));
}
static bool number(struct json_object *o, const char *key, int64_t value)
{
    return add(o, key, json_object_new_int64(value));
}
static golem_status record_io(const char *operation, int error_number)
{
    return golem_system_error_note(GOLEM_ERR_IO, "record.storage", operation, error_number);
}
static int record_close(int fd)
{
    int rc = close(fd);
    if (rc < 0) (void)record_io("close", errno);
    return rc;
}
static golem_status write_all(int fd, const void *data, size_t size)
{
    const unsigned char *p = data;
    while (size) {
        ssize_t n = write(fd, p, size);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return record_io(n < 0 ? "write" : "write_zero", n < 0 ? errno : 0);
        p += n; size -= (size_t)n;
    }
    return GOLEM_OK;
}
static golem_status publish(int dir, const char *name, struct json_object *o)
{
    const char *s = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (!s) return GOLEM_ERR_OUT_OF_MEMORY;
    int fd = openat(dir, ".pending", O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return record_io("open_pending", errno);
    golem_status st = write_all(fd, s, strlen(s));
    if (st == GOLEM_OK && fsync(fd) < 0) st = record_io("fsync_pending", errno);
    if (record_close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && linkat(dir, ".pending", dir, name, 0) < 0) st = record_io("link_publish", errno);
    if (st == GOLEM_OK && unlinkat(dir, ".pending", 0) < 0) st = record_io("unlink_pending", errno);
    if (st == GOLEM_OK && fsync(dir) < 0) st = record_io("fsync_directory", errno);
    return st;
}
static struct json_object *identity(const char *path)
{
    struct json_object *o = json_object_new_object();
    if (!o) return NULL;
    golem_receipt receipt;
    golem_status st = path ? golem_digest_file(path, &receipt, NULL) : GOLEM_ERR_NOT_FOUND;
    bool ok = number(o, "status_code", st) && text(o, "path", path);
    if (st == GOLEM_OK) {
        char hex[65]; size_t required;
        st = golem_digest_format(&receipt.digest, hex, sizeof(hex), &required);
        ok = ok && st == GOLEM_OK && text(o, "sha256", hex) && number(o, "size", (int64_t)receipt.size);
    }
    if (!ok) { json_object_put(o); return NULL; }
    return o;
}
static struct json_object *producer_identity(void)
{
    char path[4096];
#ifdef __APPLE__
    uint32_t size = sizeof(path);
    if (_NSGetExecutablePath(path, &size) != 0) return identity(NULL);
#else
    ssize_t size = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if (size < 0 || (size_t)size >= sizeof(path) - 1) return identity(NULL);
    path[size] = '\0';
#endif
    char *resolved = realpath(path, NULL);
    struct json_object *value = identity(resolved);
    free(resolved);
    return value;
}
static golem_status manifest(golem_record *r)
{
    struct json_object *o = json_object_new_object();
    if (!o) return GOLEM_ERR_OUT_OF_MEMORY;
    const char *names[] = {"started.json", "result.json", "stdout.log", "stderr.log"};
    golem_status st = GOLEM_OK;
    for (unsigned i = 0; i < 4 && st == GOLEM_OK; ++i) {
        if (i >= 2 && r->logs[i-2] < 0) continue;
        int fd = openat(r->directory, names[i], O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
        if (fd < 0) { st = record_io("open_manifest_entry", errno); break; }
        golem_receipt receipt;
        st = golem_evidence_scan_fd(fd, -1, &receipt);
        if (record_close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
        char hex[65]; size_t required;
        if (st == GOLEM_OK) st = golem_digest_format(&receipt.digest, hex, sizeof(hex), &required);
        if (st == GOLEM_OK && !text(o, names[i], hex)) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK) st = publish(r->directory, "manifest.json", o);
    json_object_put(o);
    return st;
}
static void release(golem_record *r)
{
    for (unsigned i = 0; i < 2; ++i) if (r->logs[i] >= 0) (void)record_close(r->logs[i]);
    if (r->directory >= 0) (void)record_close(r->directory);
    json_object_put(r->intent);
    free(r->executable); free(r->source); free(r->root); free(r);
}
golem_status golem_record_begin(const golem_record_options *o, golem_record **out)
{
    if (!o || !out || o->struct_size != sizeof(*o) || o->version != 1 ||
        !o->kind || !o->operation) return GOLEM_ERR_INVALID_ARGUMENT;
    const char *root = o->root ? o->root : active ? active->root :
        inherited ? inherited->root : getenv("GOLEM_RECORD_ROOT");
    if (!o->root && (!root || !*root)) { *out = NULL; return GOLEM_OK; }
    if (!root || root[0] != '/') return GOLEM_ERR_INVALID_ARGUMENT;
    int dir = golem_evidence_path_open(root, true);
    if (dir < 0) return record_io("open_root", errno);
    struct stat sb;
    if (fstat(dir, &sb) < 0) {
        (void)record_io("fstat_root", errno);
        (void)record_close(dir); return GOLEM_ERR_IO;
    }
    if (sb.st_uid != geteuid() || (sb.st_mode & 077)) {
        (void)record_io("root_permissions", 0);
        (void)record_close(dir); return GOLEM_ERR_IO;
    }
    golem_record *r = calloc(1, sizeof(*r));
    if (!r) { (void)record_close(dir); return GOLEM_ERR_OUT_OF_MEMORY; }
    r->directory = r->logs[0] = r->logs[1] = -1;
    golem_status st = GOLEM_ERR_IO;
    r->root = strdup(root);
    if (!r->root) { st = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    unsigned char random[16];
    if (RAND_bytes(random, sizeof(random)) != 1) { st = GOLEM_ERR_CRYPTO; goto done; }
    for (unsigned i = 0; i < sizeof(random); ++i) (void)snprintf(r->id + 2*i, 3, "%02x", random[i]);
    if (mkdirat(dir, r->id, 0700) < 0) { (void)record_io("mkdir_scope", errno); goto done; }
    if (fsync(dir) < 0) { (void)record_io("fsync_root", errno); goto done; }
    r->directory = openat(dir, r->id, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (r->directory < 0) { (void)record_io("open_scope", errno); goto done; }
    if (clock_gettime(CLOCK_MONOTONIC, &r->started) < 0) { (void)record_io("clock_start", errno); goto done; }
    const char *source = o->source_manifest ? o->source_manifest : active ? active->source :
        inherited ? inherited->source : getenv("GOLEM_RECORD_SOURCE_MANIFEST");
    if (o->executable && !(r->executable = strdup(o->executable))) { st = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    if (source && !(r->source = strdup(source))) { st = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    r->intent = json_object_new_object();
    struct json_object *args = json_object_new_array();
    if (!r->intent || !args) { json_object_put(args); st = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    size_t total = 0;
    if (o->argv) for (size_t i = 0; o->argv[i]; ++i) {
        size_t n = strlen(o->argv[i]);
        if (i >= 4096 || n > 1048576 - total) { json_object_put(args); st = GOLEM_ERR_OVERFLOW; goto done; }
        total += n;
        struct json_object *arg = json_object_new_string(o->argv[i]);
        if (!arg || json_object_array_add(args, arg) != 0) {
            json_object_put(arg); json_object_put(args); st = GOLEM_ERR_OUT_OF_MEMORY; goto done;
        }
    }
    if (!add(r->intent, "argv", args)) { st = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    char *cwd = o->cwd ? NULL : getcwd(NULL, 0);
    if (!o->cwd && !cwd) (void)record_io("getcwd", errno);
    bool ok = text(r->intent, "schema", "golem.native-record.v1") &&
        text(r->intent, "id", r->id) && text(r->intent, "parent", active ? active->id :
            inherited ? inherited->parent : NULL) &&
        text(r->intent, "kind", o->kind) && text(r->intent, "operation", o->operation) &&
        text(r->intent, "cwd", o->cwd ? o->cwd : cwd) &&
        text(r->intent, "state", "STARTED") && number(r->intent, "pid", getpid()) &&
        text(r->intent, "output_capture", !strcmp(o->kind, "process") ? "SUPERVISOR_PIPE_BYTES" : "EXPLICIT_WRITES_ONLY") &&
        number(r->intent, "started_unix_seconds", (int64_t)time(NULL)) &&
        text(r->intent, "descendant_coverage", "GOLEM_SUPERVISOR_ONLY") &&
        text(r->intent, "source_semantics", "HOST_MANIFEST_BYTES_NOT_SOURCE_ATTESTATION") &&
        add(r->intent, "producer_executable", producer_identity()) &&
        add(r->intent, "executable_before", identity(r->executable)) &&
        add(r->intent, "source_manifest_before", identity(r->source));
    free(cwd);
    if (!ok) { st = GOLEM_ERR_OUT_OF_MEMORY; goto done; }
    st = publish(r->directory, "started.json", r->intent);
    if (st == GOLEM_OK) { r->parent = active; active = r; *out = r; }
done:
    (void)record_close(dir);
    if (st != GOLEM_OK) release(r);
    return st;
}
golem_status golem_record_write(golem_record *r, unsigned stream, golem_bytes bytes)
{
    if (!r) return GOLEM_OK;
    if (active != r || stream > 1 || (bytes.size && !bytes.data)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->failure != GOLEM_OK) return r->failure;
    if (bytes.size > RECORD_LIMIT - r->bytes[stream]) return r->failure = GOLEM_ERR_OVERFLOW;
    if (r->logs[stream] < 0) r->logs[stream] = openat(r->directory,
        stream ? "stderr.log" : "stdout.log", O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (r->logs[stream] < 0) return r->failure = record_io("open_stream", errno);
    golem_status st = write_all(r->logs[stream], bytes.data, bytes.size);
    if (st == GOLEM_OK) r->bytes[stream] += bytes.size;
    return r->failure = st;
}
golem_status golem_record_finish(golem_record *r, const golem_record_result *result)
{
    if (!r) return GOLEM_OK;
    if (active != r || !result || result->struct_size != sizeof(*result) || result->version != 1)
        return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o = json_object_new_object();
    struct timespec now;
    golem_status st = o ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && clock_gettime(CLOCK_MONOTONIC, &now) < 0) st = record_io("clock_finish", errno);
    if (st == GOLEM_OK) {
        int64_t elapsed = (int64_t)(now.tv_sec - r->started.tv_sec) * INT64_C(1000000000) + now.tv_nsec - r->started.tv_nsec;
        bool ok = text(o, "schema", "golem.native-record.v1") && text(o, "id", r->id) &&
            text(o, "state", r->failure == GOLEM_OK ? "FINISHED" : "RECORDING_FAILED") &&
            number(o, "operation_status", result->operation_status) && number(o, "recording_status", r->failure) &&
            number(o, "exit_code", result->exit_code) && number(o, "signal_number", result->signal_number) &&
            number(o, "elapsed_ns", elapsed) &&
            add(o, "spawned", json_object_new_boolean(result->spawned)) &&
            add(o, "reaped", json_object_new_boolean(result->reaped)) &&
            add(o, "timed_out", json_object_new_boolean(result->timed_out)) &&
            add(o, "product_acceptance", json_object_new_boolean(false)) &&
            add(o, "executable_after", identity(r->executable)) &&
            add(o, "source_manifest_after", identity(r->source));
        if (!ok) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    for (unsigned i = 0; i < 2 && st == GOLEM_OK; ++i) {
        if (!add(o, i ? "stderr_eof" : "stdout_eof", json_object_new_boolean(result->eof[i]))) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (r->logs[i] < 0) continue;
        golem_receipt receipt;
        if (fsync(r->logs[i]) < 0) st = record_io("fsync_stream", errno);
        else if (lseek(r->logs[i], 0, SEEK_SET) < 0) st = record_io("seek_stream", errno);
        if (st == GOLEM_OK) st = golem_evidence_scan_fd(r->logs[i], -1, &receipt);
        char hex[65]; size_t required;
        if (st == GOLEM_OK) st = golem_digest_format(&receipt.digest, hex, sizeof(hex), &required);
        if (st == GOLEM_OK && (!text(o, i ? "stderr_sha256" : "stdout_sha256", hex) ||
            !number(o, i ? "stderr_bytes" : "stdout_bytes", (int64_t)receipt.size))) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK) st = publish(r->directory, "result.json", o);
    if (st == GOLEM_OK) st = manifest(r);
    if (st == GOLEM_OK) st = r->failure;
    json_object_put(o);
    active = r->parent;
    if (st != GOLEM_OK && active && active->failure == GOLEM_OK) active->failure = st;
    release(r);
    return st;
}
golem_status golem_record_call(const golem_record_options *o,
    golem_status (*operation)(void *), void *context, golem_status *operation_status)
{
    if (!operation || !operation_status) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_record *r = NULL;
    golem_status st = golem_record_begin(o, &r);
    if (st != GOLEM_OK) return st;
    *operation_status = operation(context);
    golem_record_result result = {.struct_size = sizeof(result), .version = 1,
        .operation_status = *operation_status, .exit_code = -1};
    return golem_record_finish(r, &result);
}

static _Thread_local golem_record_api_outcome api_outcome;
bool golem_record_last_api_outcome(golem_record_api_outcome *out)
{
    if (!out || out->struct_size != sizeof(*out) || out->version != 1 ||
        !api_outcome.operation) return false;
    *out = api_outcome;
    return true;
}
golem_status gr_api_begin(const char *operation, golem_record **record, golem_diagnostic *d)
{
    golem_record_options options = {.struct_size = sizeof(options), .version = 1,
        .kind = "c_api_auto", .operation = operation};
    golem_status st = golem_record_begin(&options, record);
    if (st != GOLEM_OK) {
        api_outcome = (golem_record_api_outcome){.struct_size = sizeof(api_outcome),
            .version = 1, .operation = operation,
            .dispatched = false, .recording_status = st};
        (void)golem_diagnostic_set(d, st, GOLEM_DIAGNOSTIC_NO_OFFSET, "record.begin_dispatch_not_started");
        (void)golem_system_error_note(st, "record.api", "begin", 0);
    }
    return st;
}
golem_status gr_api_finish(const char *name, golem_record *record, golem_status operation, golem_diagnostic *d)
{
    golem_record_result result = {.struct_size = sizeof(result), .version = 1,
        .operation_status = operation, .exit_code = -1};
    golem_status st = golem_record_finish(record, &result);
    api_outcome = (golem_record_api_outcome){.struct_size = sizeof(api_outcome),
        .version = 1, .operation = name, .dispatched = true,
        .operation_status = operation, .recording_status = st};
    if (st != GOLEM_OK) {
        if (active && active->failure == GOLEM_OK) active->failure = st;
        (void)golem_system_error_note(st, "record.api", "finish_effects_uncertain", 0);
        if (operation == GOLEM_OK)
            (void)golem_diagnostic_set(d, st, GOLEM_DIAGNOSTIC_NO_OFFSET, "record.finish_effects_uncertain");
    }
    return operation;
}
golem_status gr_api_rejected(const char *operation)
{
    golem_record *record = NULL;
    golem_status st = gr_api_begin(operation, &record, NULL);
    return st == GOLEM_OK ? gr_api_finish(operation, record, GOLEM_ERR_INVALID_ARGUMENT, NULL) : st;
}
golem_status gr_api_finish_required(const char *name, golem_record *record,
    golem_status started, golem_status operation)
{
    if (started == GOLEM_OK) return gr_api_finish(name, record, operation, NULL);
    api_outcome = (golem_record_api_outcome){.struct_size = sizeof(api_outcome),
        .version = 1, .operation = name, .dispatched = true,
        .operation_status = operation, .recording_status = started};
    if (active && active->failure == GOLEM_OK) active->failure = started;
    return operation;
}
