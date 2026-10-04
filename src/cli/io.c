#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "work.h"
#include "golem/system_error.h"
#include "../evidence/internal.h"
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

golem_status cli_path(const char *root, const char *name, char out[CLI_PATH_MAX])
{
    if (root == NULL || root[0] == '\0') return GOLEM_ERR_INVALID_ARGUMENT;
    int n = snprintf(out, CLI_PATH_MAX, "%s/%s", root, name);
    return n >= 0 && n < CLI_PATH_MAX ? GOLEM_OK : GOLEM_ERR_OVERFLOW;
}
golem_status cli_read(const char *path, size_t limit, cli_blob *out)
{
    int fd = golem_evidence_path_open(path, false);
    if (fd < 0) {
        int saved = errno;
        golem_status status = saved == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO;
        cli_error_errno(status, "request_open", saved);
        return status;
    }
    struct stat before, after; golem_status s = GOLEM_OK;
    if (fstat(fd, &before) < 0) {
        s = GOLEM_ERR_IO; cli_error_errno(s, "request_stat", errno);
    } else if (!S_ISREG(before.st_mode) || before.st_size < 0 || (uintmax_t)before.st_size > limit) {
        s = GOLEM_ERR_IO; cli_error_note(s, "request_metadata", NULL);
    }
    if (s == GOLEM_OK && flock(fd, LOCK_SH | LOCK_NB) < 0) {
        s = GOLEM_ERR_JOURNAL_BUSY; cli_error_errno(s, "request_lock", errno);
    }
    cli_blob b = {0};
    if (s == GOLEM_OK) {
        b.data = malloc((size_t)before.st_size + 1);
        if (b.data == NULL) s = GOLEM_ERR_OUT_OF_MEMORY;
    }
    while (s == GOLEM_OK && b.size <= (size_t)before.st_size) {
        ssize_t n = read(fd, b.data + b.size, (size_t)before.st_size + 1 - b.size);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) { s = GOLEM_ERR_IO; cli_error_errno(s, "request_read", errno); break; }
        if (n == 0) break;
        b.size += (size_t)n;
    }
    if (s == GOLEM_OK && fstat(fd, &after) < 0) {
        s = GOLEM_ERR_IO; cli_error_errno(s, "request_restat", errno);
    }
    if (s == GOLEM_OK && (before.st_size != after.st_size || before.st_mtime != after.st_mtime ||
                         b.size != (size_t)before.st_size)) {
        s = GOLEM_ERR_IO; cli_error_note(s, "request_changed", NULL);
    }
    if (close(fd) < 0 && s == GOLEM_OK) {
        s = GOLEM_ERR_IO; cli_error_errno(s, "request_close", errno);
    }
    if (s != GOLEM_OK) free(b.data);
    else { b.data[b.size] = 0; *out = b; }
    return s;
}
golem_status cli_mkdir_new(const char *path, int *out)
{
    if (path == NULL || strlen(path) >= CLI_PATH_MAX) return GOLEM_ERR_INVALID_ARGUMENT;
    char parent[CLI_PATH_MAX]; strcpy(parent, path);
    char *slash = strrchr(parent, '/'); const char *name = parent; const char *directory = ".";
    if (slash != NULL) { *slash = '\0'; name = slash + 1; directory = slash == parent ? "/" : parent; }
    if (name[0] == '\0' || strcmp(name, ".") == 0 || strcmp(name, "..") == 0) return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = golem_evidence_path_open(directory, true);
    if (fd < 0) return GOLEM_ERR_IO;
    golem_status s = GOLEM_OK; int child = -1;
    if (mkdirat(fd, name, 0700) < 0) s = golem_system_error_note(GOLEM_ERR_IO, "cli.directory", "mkdirat", errno);
    if (s == GOLEM_OK) {
        child = openat(fd, name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (child < 0) s = golem_system_error_note(GOLEM_ERR_IO, "cli.directory", "openat", errno);
        else if (fsync(fd) < 0) s = golem_system_error_note(GOLEM_ERR_IO, "cli.directory", "fsync", errno);
    }
    if (close(fd) < 0 && s == GOLEM_OK) s = golem_system_error_note(GOLEM_ERR_IO, "cli.directory", "close", errno);
    if (s == GOLEM_OK) *out = child;
    else if (child >= 0) (void)close(child);
    return s;
}
golem_status cli_write_new(int dir, const char *name, golem_bytes data)
{
    char temp[128];
    if (strchr(name, '/') != NULL || snprintf(temp, sizeof(temp), ".%s.tmp", name) >= (int)sizeof(temp)) return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = openat(dir, temp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return golem_system_error_note(GOLEM_ERR_IO, "cli.publish", "openat", errno);
    golem_status s = GOLEM_OK; size_t offset = 0;
    while (offset < data.size) {
        ssize_t n = write(fd, data.data + offset, data.size - offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) {
            s = golem_system_error_note(GOLEM_ERR_IO, "cli.publish", n < 0 ? "write" : "write_no_progress", n < 0 ? errno : 0);
            break;
        }
        offset += (size_t)n;
    }
    if (s == GOLEM_OK && fsync(fd) < 0) s = golem_system_error_note(GOLEM_ERR_IO, "cli.publish", "fsync_file", errno);
    if (close(fd) < 0 && s == GOLEM_OK) s = golem_system_error_note(GOLEM_ERR_IO, "cli.publish", "close", errno);
    if (s == GOLEM_OK && linkat(dir, temp, dir, name, 0) < 0) s = golem_system_error_note(GOLEM_ERR_IO, "cli.publish", "linkat", errno);
    if (unlinkat(dir, temp, 0) < 0 && s == GOLEM_OK) s = golem_system_error_note(GOLEM_ERR_IO, "cli.publish", "unlinkat", errno);
    if (s == GOLEM_OK && fsync(dir) < 0) s = golem_system_error_note(GOLEM_ERR_IO, "cli.publish", "fsync_directory", errno);
    return s;
}
golem_status cli_json_write(int dir, const char *name, struct json_object *o)
{
    if (o == NULL) return GOLEM_ERR_OUT_OF_MEMORY;
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (text == NULL) return GOLEM_ERR_OUT_OF_MEMORY;
    return cli_write_new(dir, name, (golem_bytes){(const uint8_t *)text, strlen(text)});
}
int cli_emit(golem_status status, struct json_object *o)
{
    if (status == GOLEM_OK && o == NULL) status = GOLEM_ERR_OUT_OF_MEMORY;
    if (status != GOLEM_OK) {
        cli_error_note(status, NULL, NULL);
        fprintf(stderr, "golem: %s\n", golem_status_string(status)); json_object_put(o); return 1;
    }
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    int result = text == NULL || cli_output_write((golem_bytes){(const uint8_t *)text, strlen(text)}) != GOLEM_OK ||
                 fputc('\n', stdout) == EOF || fflush(stdout) != 0 || ferror(stdout) ? 1 : 0;
    json_object_put(o); return result;
}
