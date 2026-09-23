#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include "../evidence/internal.h"
#include "golem/supervisor.h"
#include <errno.h>
#include <inttypes.h>
#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

extern char **environ;
static uint64_t now(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) < 0)
        return 0;
    return (uint64_t)t.tv_sec * 1000000000u + (uint64_t)t.tv_nsec;
}
static golem_status git(const char *root, const char *command, const char *arg, const char *path,
                        uint64_t deadline, char output[GOLEM_SUPERVISOR_OUTPUT_MAX + 1])
{
    uint64_t t = now();
    if (!t)
        return GOLEM_ERR_IO;
    if (t >= deadline)
        return GOLEM_ERR_INCOMPLETE_WORK;
    char *argv[] = {"/usr/bin/git",
                    "--no-optional-locks",
                    "--no-pager",
                    "--literal-pathspecs",
                    "--no-replace-objects",
                    "-c",
                    "core.fsmonitor=false",
                    "-c",
                    "core.untrackedCache=false",
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-C",
                    (char *)root,
                    (char *)command,
                    (char *)arg,
                    path ? "--" : NULL,
                    (char *)path,
                    NULL};
    golem_supervisor_result r;
    golem_status st =
        golem_supervisor_run(argv[0], argv, (golem_bytes){NULL, 0}, deadline - t, NULL, NULL, &r);
    if (st != GOLEM_OK)
        return st;
    if (memchr(r.output, 0, r.output_size))
        return GOLEM_ERR_PARSE;
    memcpy(output, r.output, r.output_size);
    output[r.output_size] = 0;
    return GOLEM_OK;
}
static bool append(struct json_object *a, struct json_object *v)
{
    if (!a || !v || json_object_array_add(a, v) != 0) {
        json_object_put(v);
        return false;
    }
    return true;
}
static golem_status hash_text(const char *text, golem_digest *out)
{
    return golem_digest_bytes((golem_bytes){(const uint8_t *)text, strlen(text)}, out);
}
static golem_status file_bytes(const char *path, uint8_t **out, size_t *size, mode_t *mode)
{
    int fd = golem_evidence_path_open(path, false);
    if (fd < 0)
        return GOLEM_ERR_IO;
    struct stat before, after;
    golem_status st = GOLEM_OK;
    if (fstat(fd, &before) < 0 || !S_ISREG(before.st_mode) || before.st_size < 0)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && (uint64_t)before.st_size > GOLEM_DISCOVERY_MAX_FILE_BYTES)
        st = GOLEM_ERR_BUDGET_EXHAUSTED;
    size_t n = st == GOLEM_OK ? (size_t)before.st_size : 0, offset = 0;
    uint8_t *p = st == GOLEM_OK ? malloc(n ? n : 1) : NULL;
    if (st == GOLEM_OK && !p)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    while (st == GOLEM_OK && offset < n) {
        ssize_t got = read(fd, p + offset, n - offset);
        if (got < 0 && errno == EINTR)
            continue;
        if (got <= 0) {
            st = GOLEM_ERR_IO;
            break;
        }
        offset += (size_t)got;
    }
    uint8_t tail;
    if (st == GOLEM_OK &&
        (read(fd, &tail, 1) != 0 || fstat(fd, &after) < 0 || before.st_size != after.st_size ||
         before.st_mtime != after.st_mtime || before.st_ctime != after.st_ctime))
        st = GOLEM_ERR_STALE_RESULT;
    if (close(fd) < 0 && st == GOLEM_OK)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK) {
        *out = p;
        *size = n;
        *mode = before.st_mode;
    } else
        free(p);
    return st;
}
/* Git object identity is computed locally: never invoke clean/smudge filters. */
static golem_status blob_hash(golem_bytes b, bool sha256, char out[65])
{
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    if (!ctx)
        return GOLEM_ERR_OUT_OF_MEMORY;
    char header[64];
    int n = snprintf(header, sizeof(header), "blob %zu", b.size);
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned len = 0;
    bool ok = n > 0 && EVP_DigestInit_ex(ctx, sha256 ? EVP_sha256() : EVP_sha1(), NULL) == 1 &&
              EVP_DigestUpdate(ctx, header, (size_t)n + 1) == 1 &&
              EVP_DigestUpdate(ctx, b.data, b.size) == 1 &&
              EVP_DigestFinal_ex(ctx, digest, &len) == 1;
    EVP_MD_CTX_free(ctx);
    if (!ok)
        return GOLEM_ERR_CRYPTO;
    static const char hex[] = "0123456789abcdef";
    for (unsigned i = 0; i < len; ++i) {
        out[i * 2] = hex[digest[i] >> 4];
        out[i * 2 + 1] = hex[digest[i] & 15];
    }
    out[len * 2] = 0;
    return GOLEM_OK;
}
static golem_status capture_file(const char *root, const char *path, uint64_t deadline, bool sha256,
                                 struct json_object **out,
                                 char index[GOLEM_SUPERVISOR_OUTPUT_MAX + 1])
{
    char full[4096], tree[GOLEM_SUPERVISOR_OUTPUT_MAX + 1];
    int n = snprintf(full, sizeof(full), "%s/%s", root, path);
    if (n < 0 || (size_t)n >= sizeof(full))
        return GOLEM_ERR_OVERFLOW;
    uint8_t *p = NULL;
    size_t size = 0;
    mode_t mode = 0;
    golem_status st = file_bytes(full, &p, &size, &mode);
    if (st == GOLEM_OK)
        st = git(root, "ls-files", "--stage", path, deadline, index);
    if (st == GOLEM_OK)
        st = git(root, "ls-tree", "HEAD", path, deadline, tree);
    golem_digest digest;
    char blob[65];
    if (st == GOLEM_OK)
        st = golem_digest_bytes((golem_bytes){p, size}, &digest);
    if (st == GOLEM_OK)
        st = blob_hash((golem_bytes){p, size}, sha256, blob);
    free(p);
    struct json_object *f = NULL;
    if (st == GOLEM_OK) {
        char ih[65] = {0}, th[65] = {0};
        unsigned im = 0, tm = 0, stage = 99;
        bool tracked = *index != 0;
        bool clean_index = sscanf(index, "%o %64s %u", &im, ih, &stage) == 3 && stage == 0;
        bool clean_tree = sscanf(tree, "%o blob %64s", &tm, th) == 2;
        unsigned fm = (mode & 0111) ? 0100755 : 0100644;
        bool dirty = !clean_index || !clean_tree || strcmp(ih, blob) != 0 || strcmp(ih, th) != 0 ||
                     im != tm || im != fm;
        f = json_object_new_object();
        if (!dw_add(f, "path", json_object_new_string(path)) ||
            !dw_add_digest(f, "digest", &digest) ||
            !dw_add(f, "size", json_object_new_uint64(size)) ||
            !dw_add(f, "tracked", json_object_new_boolean(tracked)) ||
            !dw_add(f, "dirty", json_object_new_boolean(dirty)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK)
        *out = f;
    else
        json_object_put(f);
    return st;
}
static golem_status repository(struct json_object *plan, uint64_t deadline, uint64_t *total,
                               struct json_object **out)
{
    const char *keys[] = {"id", "root", "paths", "toolchain", "test_configuration"};
    const char *root = dw_text(plan, "root");
    struct json_object *paths = dw_get(plan, "paths");
    if (!dw_keys(plan, keys, 5) || !dw_id(dw_text(plan, "id")) || root[0] != '/' ||
        strlen(root) > 3000 || !ds_array(paths, 1, 64) || !ds_prose(plan, "toolchain") ||
        !ds_prose(plan, "test_configuration"))
        return GOLEM_ERR_PARSE;
    for (size_t i = 0; i < json_object_array_length(paths); ++i) {
        struct json_object *p = json_object_array_get_idx(paths, i);
        if (!json_object_is_type(p, json_type_string) || !ds_path(json_object_get_string(p)))
            return GOLEM_ERR_POLICY_DENIED;
        for (size_t j = 0; j < i; ++j)
            if (strcmp(json_object_get_string(p),
                       json_object_get_string(json_object_array_get_idx(paths, j))) == 0)
                return GOLEM_ERR_PARSE;
    }
    int fd = golem_evidence_path_open(root, true);
    struct stat before, after;
    if (fd < 0)
        return GOLEM_ERR_IO;
    golem_status st = fstat(fd, &before) == 0 ? GOLEM_OK : GOLEM_ERR_IO;
    char head[GOLEM_SUPERVISOR_OUTPUT_MAX + 1], check[GOLEM_SUPERVISOR_OUTPUT_MAX + 1];
    if (st == GOLEM_OK)
        st = git(root, "rev-parse", "HEAD", NULL, deadline, head);
    if (st == GOLEM_OK) {
        size_t n = strlen(head);
        if (n != 41 && n != 65)
            st = GOLEM_ERR_PARSE;
        else if (head[n - 1] != '\n')
            st = GOLEM_ERR_PARSE;
    }
    struct json_object *files = json_object_new_array(), *indexes = json_object_new_array(),
                       *r = NULL;
    if (!files || !indexes)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(paths); ++i) {
        struct json_object *f = NULL;
        char index[GOLEM_SUPERVISOR_OUTPUT_MAX + 1];
        st = capture_file(root, json_object_get_string(json_object_array_get_idx(paths, i)),
                          deadline, strlen(head) == 65, &f, index);
        if (st == GOLEM_OK) {
            *total += dw_uint(f, "size");
            if (!append(files, f) || !append(indexes, json_object_new_string(index)))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (*total > GOLEM_DISCOVERY_MAX_TOTAL_BYTES)
                st = GOLEM_ERR_BUDGET_EXHAUSTED;
        }
    }
    /* Repeat observations, without refreshing Git's index or invoking filters. */
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(paths); ++i) {
        struct json_object *f = NULL;
        char index[GOLEM_SUPERVISOR_OUTPUT_MAX + 1];
        st = capture_file(root, json_object_get_string(json_object_array_get_idx(paths, i)),
                          deadline, strlen(head) == 65, &f, index);
        if (st == GOLEM_OK &&
            (!json_object_equal(f, json_object_array_get_idx(files, i)) ||
             strcmp(index, json_object_get_string(json_object_array_get_idx(indexes, i))) != 0))
            st = GOLEM_ERR_STALE_RESULT;
        json_object_put(f);
    }
    if (st == GOLEM_OK)
        st = git(root, "rev-parse", "HEAD", NULL, deadline, check);
    if (st == GOLEM_OK && strcmp(head, check) != 0)
        st = GOLEM_ERR_STALE_RESULT;
    int end = golem_evidence_path_open(root, true);
    if (st == GOLEM_OK && (end < 0 || fstat(end, &after) < 0 || before.st_dev != after.st_dev ||
                           before.st_ino != after.st_ino))
        st = GOLEM_ERR_STALE_RESULT;
    if (end >= 0)
        close(end);
    close(fd);
    if (st == GOLEM_OK) {
        char identity[4096];
        int n = snprintf(identity, sizeof(identity), "%s\n%ju:%ju", root, (uintmax_t)before.st_dev,
                         (uintmax_t)before.st_ino);
        golem_digest id, index;
        if (n < 0 || (size_t)n >= sizeof(identity))
            st = GOLEM_ERR_OVERFLOW;
        if (st == GOLEM_OK)
            st = hash_text(identity, &id);
        const char *encoded = json_object_to_json_string_ext(indexes, JSON_C_TO_STRING_PLAIN);
        if (st == GOLEM_OK)
            st = encoded ? hash_text(encoded, &index) : GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) {
            head[strlen(head) - 1] = 0;
            r = json_object_new_object();
            if (!dw_add(r, "id", json_object_new_string(dw_text(plan, "id"))) ||
                !dw_add_digest(r, "root_identity", &id) ||
                !dw_add(r, "head", json_object_new_string(head)) ||
                !dw_add_digest(r, "index_digest", &index) ||
                !dw_add(r, "toolchain", json_object_new_string(dw_text(plan, "toolchain"))) ||
                !dw_add(r, "test_configuration",
                        json_object_new_string(dw_text(plan, "test_configuration"))))
                st = GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK) {
                bool ok = dw_add(r, "files", files);
                files = NULL;
                if (!ok)
                    st = GOLEM_ERR_OUT_OF_MEMORY;
            }
        }
    }
    json_object_put(files);
    json_object_put(indexes);
    if (st == GOLEM_OK)
        *out = r;
    else
        json_object_put(r);
    return st;
}
golem_status golem_discovery_snapshot(golem_bytes b, const golem_allocator *a, uint8_t **out,
                                      size_t *size, golem_diagnostic *d)
{
    if (!out || !size || golem_allocator_validate(a) != GOLEM_OK)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    for (char **p = environ; *p; ++p)
        if (strncmp(*p, "GIT_", 4) == 0)
            return dw_report(d, GOLEM_ERR_POLICY_DENIED,
                             "unset Git environment overrides before discovery");
    struct json_object *plan = NULL, *snapshot = NULL, *repos = NULL;
    golem_status st = golem_json_parse(b, GOLEM_DOCUMENT_MAX_JSON, &plan);
    const char *keys[] = {"schema_version", "timeout_seconds", "repositories"};
    if (st == GOLEM_OK &&
        (!dw_keys(plan, keys, 3) || dw_uint(plan, "schema_version") != 1 ||
         dw_uint(plan, "timeout_seconds") < 1 || dw_uint(plan, "timeout_seconds") > 60 ||
         !ds_array(dw_get(plan, "repositories"), 1, 8)))
        st = GOLEM_ERR_PARSE;
    uint64_t start = now(), total = 0,
             deadline = start + dw_uint(plan, "timeout_seconds") * 1000000000u;
    if (!start)
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK) {
        snapshot = json_object_new_object();
        repos = json_object_new_array();
        if (!snapshot || !repos)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    struct json_object *input = dw_get(plan, "repositories");
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(input); ++i) {
        struct json_object *r = json_object_array_get_idx(input, i), *result = NULL;
        for (size_t j = 0; j < i; ++j)
            if (strcmp(dw_text(r, "id"), dw_text(json_object_array_get_idx(input, j), "id")) == 0)
                st = GOLEM_ERR_PARSE;
        if (st == GOLEM_OK)
            st = repository(r, deadline, &total, &result);
        if (st == GOLEM_OK && !append(repos, result))
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK &&
        (!dw_add(snapshot, "schema_version", json_object_new_int(1)) ||
         !dw_add(snapshot, "capture", json_object_new_string("allowlist-read-only"))))
        st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        bool ok = dw_add(snapshot, "repositories", repos);
        repos = NULL;
        if (!ok)
            st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    if (st == GOLEM_OK) {
        const char *text = json_object_to_json_string_ext(snapshot, JSON_C_TO_STRING_PLAIN);
        size_t n = text ? strlen(text) : 0;
        void *buffer = NULL;
        if (!text)
            st = GOLEM_ERR_OUT_OF_MEMORY;
        else if (n > GOLEM_DOCUMENT_MAX_JSON)
            st = GOLEM_ERR_BUDGET_EXHAUSTED;
        else
            st = golem_allocator_alloc(a, n, &buffer);
        if (st == GOLEM_OK) {
            memcpy(buffer, text, n);
            *out = buffer;
            *size = n;
        }
    }
    json_object_put(plan);
    json_object_put(repos);
    json_object_put(snapshot);
    return dw_report(d, st,
                     st == GOLEM_OK ? "allowlisted snapshot; toolchain declared, tests not run"
                                    : "snapshot incomplete; no project writes performed");
}
