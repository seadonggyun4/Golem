#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include "../evidence/internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <openssl/rand.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

golem_status gd_path(const char *root, const char *name, char out[GD_PATH])
{
    int n = snprintf(out, GD_PATH, "%s/%s", root, name);
    return n >= 0 && n < GD_PATH ? GOLEM_OK : GOLEM_ERR_OVERFLOW;
}
golem_status gd_job_path(const char *root, uint64_t ticket, char out[GD_PATH])
{
    char name[32]; (void)snprintf(name, sizeof(name), "jobs/%020" PRIu64, ticket); return gd_path(root, name, out);
}
int gd_lock(int dir, const char *name, bool create, bool exclusive)
{
    int fd = openat(dir, name, O_RDWR | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK | (create ? O_CREAT : 0), 0600);
    struct stat st;
    if (fd < 0) return -1;
    if (fstat(fd, &st) < 0 || !S_ISREG(st.st_mode) || flock(fd, (exclusive ? LOCK_EX : LOCK_SH) | LOCK_NB) < 0) {
        (void)close(fd); return -1;
    }
    return fd;
}
golem_status gd_read(const char *path, size_t limit, gd_blob *out)
{
    int fd = golem_evidence_path_open(path, false);
    if (fd < 0) return errno == ENOENT ? GOLEM_ERR_NOT_FOUND : GOLEM_ERR_IO;
    struct stat st; golem_status s = GOLEM_OK; gd_blob b = {0};
    if (fstat(fd, &st) < 0 || !S_ISREG(st.st_mode) || st.st_size < 0 || (uintmax_t)st.st_size > limit) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK && flock(fd, LOCK_SH | LOCK_NB) < 0) s = GOLEM_ERR_JOURNAL_BUSY;
    if (s == GOLEM_OK) { b.data = malloc((size_t)st.st_size + 1); if (b.data == NULL) s = GOLEM_ERR_OUT_OF_MEMORY; }
    while (s == GOLEM_OK && b.size <= (size_t)st.st_size) {
        ssize_t n = read(fd, b.data + b.size, (size_t)st.st_size + 1 - b.size);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) { s = GOLEM_ERR_IO; break; }
        if (n == 0) break;
        b.size += (size_t)n;
    }
    if (s == GOLEM_OK && b.size != (size_t)st.st_size) s = GOLEM_ERR_IO;
    if (close(fd) < 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK) { b.data[b.size] = 0; *out = b; } else free(b.data);
    return s;
}
golem_status gd_write(int dir, const char *name, golem_bytes bytes)
{
    uint8_t random[8]; char nonce[17], temp[160];
    if (strchr(name, '/') || strlen(name) > 120) return GOLEM_ERR_INVALID_ARGUMENT;
    if (RAND_bytes(random, sizeof(random)) != 1) return GOLEM_ERR_CRYPTO;
    for (size_t i = 0; i < sizeof(random); ++i) (void)snprintf(nonce + 2 * i, 3, "%02x", random[i]);
    if (snprintf(temp, sizeof(temp), ".%s.pending-%s", name, nonce) >= (int)sizeof(temp)) return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = openat(dir, temp, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return GOLEM_ERR_IO;
    size_t offset = 0; golem_status s = GOLEM_OK;
    while (offset < bytes.size) {
        ssize_t n = write(fd, bytes.data + offset, bytes.size - offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { s = GOLEM_ERR_IO; break; }
        offset += (size_t)n;
    }
    if (s == GOLEM_OK && fsync(fd) < 0) s = GOLEM_ERR_IO;
    if (close(fd) < 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK && linkat(dir, temp, dir, name, 0) < 0) s = GOLEM_ERR_IO;
    if (unlinkat(dir, temp, 0) < 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK && fsync(dir) < 0) s = GOLEM_ERR_IO;
    return s;
}
int gd_root(const char *root)
{
    if (root == NULL || root[0] != '/' || strlen(root) > GD_PATH - 180) return -1;
    char path[GD_PATH]; gd_blob b = {0};
    if (gd_path(root, "format", path) != GOLEM_OK || gd_read(path, 32, &b) != GOLEM_OK) return -1;
    bool valid = b.size == 12 && memcmp(b.data, "GolemQueue1\n", 12) == 0; free(b.data);
    return valid ? golem_evidence_path_open(root, true) : -1;
}
static int compare(const void *a, const void *b)
{
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b; return x < y ? -1 : x > y;
}
golem_status gd_list(int root, uint64_t tickets[GOLEM_DAEMON_MAX_JOBS], size_t *count)
{
    int fd = openat(root, "jobs", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return GOLEM_ERR_IO;
    DIR *dir = fdopendir(fd); if (dir == NULL) { (void)close(fd); return GOLEM_ERR_IO; }
    size_t n = 0; golem_status s = GOLEM_OK; struct dirent *entry; errno = 0;
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] == '.') continue;
        if (strlen(entry->d_name) != 20 || n == GOLEM_DAEMON_MAX_JOBS) { s = GOLEM_ERR_OVERFLOW; break; }
        uint64_t value = 0;
        for (size_t i = 0; i < 20; ++i) {
            unsigned digit = (unsigned)(entry->d_name[i] - '0');
            if (digit > 9 || value > (UINT64_MAX - digit) / 10) { s = GOLEM_ERR_PARSE; break; }
            value = value * 10 + digit;
        }
        if (s != GOLEM_OK || value == 0) { s = GOLEM_ERR_PARSE; break; }
        tickets[n++] = value; errno = 0;
    }
    if (errno != 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
    if (closedir(dir) < 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
    if (s == GOLEM_OK) { qsort(tickets, n, sizeof(*tickets), compare); *count = n; }
    return s;
}
