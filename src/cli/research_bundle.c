#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "work.h"
#include "../research/bundle_internal.h"
#include "../evidence/internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Export destinations must not mutate the source Work, including its subtree.
 * The subsequent safe mkdir rejects symlink/.. components and existing paths. */
static golem_status destination(const char *work, const char *output)
{
    if (!output || strlen(output) >= CLI_PATH_MAX) return GOLEM_ERR_INVALID_ARGUMENT;
    char path[CLI_PATH_MAX]; strcpy(path, output);
    char *slash = strrchr(path, '/');
    if (slash) { if (slash == path) slash[1] = '\0'; else *slash = '\0'; }
    else strcpy(path, ".");
    int root = golem_evidence_path_open(work, true), parent = golem_evidence_path_open(path, true);
    struct stat source, current, above;
    golem_status st = root >= 0 && parent >= 0 && fstat(root, &source) == 0 ? GOLEM_OK : GOLEM_ERR_IO;
    for (unsigned depth = 0; st == GOLEM_OK; ++depth) {
        if (depth == 1024 || fstat(parent, &current) != 0) { st = GOLEM_ERR_IO; break; }
        if (source.st_dev == current.st_dev && source.st_ino == current.st_ino) { st = GOLEM_ERR_POLICY_DENIED; break; }
        int up = openat(parent, "..", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (up < 0) { st = GOLEM_ERR_IO; break; }
        if (fstat(up, &above) != 0) st = GOLEM_ERR_IO;
        close(parent); parent = up;
        if (st == GOLEM_OK && current.st_dev == above.st_dev && current.st_ino == above.st_ino) break;
    }
    if (root >= 0) close(root);
    if (parent >= 0) close(parent);
    return st;
}
static golem_status publish(const char *path, struct json_object *bundle)
{
    int dir = -1; golem_status st = cli_mkdir_new(path, &dir);
    struct json_object *files = dw_get(bundle, "files");
    /* The manifest is the final completeness marker. A crash leaves a private,
     * incomplete directory; retries use a fresh destination, never overwrite. */
    for (size_t i = 0; st == GOLEM_OK && i < RB_FILES; ++i) {
        size_t index = i == RB_FILES-2 ? RB_FILES-1 : i == RB_FILES-1 ? RB_FILES-2 : i;
        struct json_object *v = dw_get(files, rb_names[index]);
        st = cli_write_new(dir, rb_names[index], (golem_bytes){(const uint8_t *)json_object_get_string(v),
            (size_t)json_object_get_string_len(v)});
    }
    if (dir >= 0 && close(dir) != 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    return st;
}
static golem_status load(const char *path, struct json_object **out)
{
    int fd = golem_evidence_path_open(path, true);
    if (fd < 0) return GOLEM_ERR_IO;
    DIR *dir = fdopendir(fd);
    if (!dir) { close(fd); return GOLEM_ERR_IO; }
    golem_status st = GOLEM_OK; size_t count = 0, total = 0;
    struct dirent *item;
    errno = 0;
    while ((item = readdir(dir))) {
        if (!strcmp(item->d_name, ".") || !strcmp(item->d_name, "..")) continue;
        size_t i = 0;
        while (i < RB_FILES && strcmp(item->d_name, rb_names[i])) ++i;
        if (i == RB_FILES) { st = GOLEM_ERR_PARSE; break; }
        ++count;
    }
    if (errno && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && count != RB_FILES) st = GOLEM_ERR_MISSING_RECORD;
    struct json_object *o = json_object_new_object(), *files = json_object_new_object();
    if (!o || !files) st = GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < RB_FILES; ++i) {
        uint8_t *data = NULL; size_t n = 0;
        st = dw_read_at(fd, rb_names[i], GOLEM_RESEARCH_BUNDLE_MAX_JSON-total, &data, &n);
        if (st == GOLEM_OK) {
            total += n;
            if (memchr(data, 0, n)) st = GOLEM_ERR_PARSE;
            else if (!dw_add(files, rb_names[i], json_object_new_string_len((const char *)data, (int)n))) st = GOLEM_ERR_OUT_OF_MEMORY;
        }
        free(data);
    }
    if (closedir(dir) != 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && (!ex_uint(o, "schema_version", 1) || !dw_add(o, "files", json_object_get(files)))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) *out = o; else json_object_put(o);
    json_object_put(files); return st;
}
int golem_cli_research_bundle(int argc, char **argv)
{
    bool pinned = argc == 6 && !strcmp(argv[4], "--expect-manifest");
    bool verify = (argc == 4 || pinned) && !strcmp(argv[2], "bundle-verify");
    bool exporting = argc == 10 && !strcmp(argv[2], "export") && !strcmp(argv[4], "--case") &&
        !strcmp(argv[6], "--output") && !strcmp(argv[8], "--redact");
    if (!verify && !exporting) {
        fputs("usage: golem research export WORK --case CASE_ID --output NEW_DIR --redact POLICY.json\n"
              "       golem research bundle-verify DIR [--expect-manifest SHA256]\n", stderr); return 2;
    }
    golem_status st = GOLEM_OK; golem_document_store *s = NULL;
    cli_blob policy = {0}; golem_execution_reply reply = {0}; struct json_object *bundle = NULL;
    if (exporting) {
        st = destination(argv[3], argv[7]);
        if (st == GOLEM_OK) st = cli_read(argv[9], GOLEM_RESEARCH_REDACTION_MAX_JSON, &policy);
        if (st == GOLEM_OK) st = golem_document_store_open(argv[3], false, NULL, &s, NULL);
        if (st == GOLEM_OK) st = golem_research_bundle(s, argv[5], (golem_bytes){policy.data, policy.size}, &reply, NULL);
        if (st == GOLEM_OK) st = golem_json_parse((golem_bytes){reply.data, reply.size}, GOLEM_RESEARCH_BUNDLE_MAX_JSON, &bundle);
    } else st = load(argv[3], &bundle);
    if (st == GOLEM_OK) {
        const char *text = json_object_to_json_string_ext(bundle, JSON_C_TO_STRING_PLAIN);
        st = text ? golem_research_bundle_verify((golem_bytes){(const uint8_t *)text, strlen(text)}, NULL) : GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK && exporting) st = publish(argv[7], bundle);
    if (st == GOLEM_OK) {
        struct json_object *result = json_object_new_object(); golem_digest digest;
        const char *manifest = dw_text(dw_get(bundle, "files"), "manifest.json");
        st = golem_digest_bytes((golem_bytes){(const uint8_t *)manifest, strlen(manifest)}, &digest);
        if (st == GOLEM_OK && verify && pinned) {
            golem_digest expected;
            st = golem_digest_parse((golem_string_view){argv[5], strlen(argv[5])}, &expected);
            if (st == GOLEM_OK && !dw_equal(&expected, &digest)) st = GOLEM_ERR_DIGEST_MISMATCH;
        }
        if (st == GOLEM_OK && (!ex_text(result, "status", exporting ? "EXPORTED" : "INTEGRITY_VERIFIED") ||
            !dw_add_digest(result, "manifest_sha256", &digest) || !ex_text(result, "privacy", "PRIVATE_REVIEW_REQUIRED") ||
            !dw_add(result, "authenticity_verified", json_object_new_boolean(false)) ||
            !dw_add(result, "redaction_verified", json_object_new_boolean(false)))) st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) { if (cli_emit(st, result) != 0) st = GOLEM_ERR_IO; }
        else json_object_put(result);
    }
    golem_status closed = golem_document_store_close(s);
    if (st == GOLEM_OK) st = closed;
    free(policy.data); golem_execution_reply_free(&reply); json_object_put(bundle);
    if (st != GOLEM_OK) fprintf(stderr, "research bundle: %s\n", golem_status_string(st));
    return st == GOLEM_OK ? 0 : 1;
}
