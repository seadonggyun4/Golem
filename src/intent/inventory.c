#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "inventory.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static bool same(const struct stat *a, const struct stat *b)
{
#ifdef __APPLE__
    if (a->st_mtimespec.tv_nsec != b->st_mtimespec.tv_nsec ||
        a->st_ctimespec.tv_nsec != b->st_ctimespec.tv_nsec) return false;
#else
    if (a->st_mtim.tv_nsec != b->st_mtim.tv_nsec ||
        a->st_ctim.tv_nsec != b->st_ctim.tv_nsec) return false;
#endif
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino &&
        a->st_mode == b->st_mode && a->st_size == b->st_size &&
        a->st_mtime == b->st_mtime && a->st_ctime == b->st_ctime;
}

static golem_status scan(int fd, dev_t device, uint64_t *budget, unsigned depth,
                         unsigned max_depth, gi_inventory *total)
{
    struct stat before, after;
    if (fstat(fd, &before) < 0) return GOLEM_ERR_IO;
    if (!S_ISDIR(before.st_mode) || before.st_dev != device) return GOLEM_ERR_INVALID_STATE;
    /* openat creates an independent directory offset, unlike dup(). */
    int listing = openat(fd, ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (listing < 0) return GOLEM_ERR_IO;
    DIR *dir = fdopendir(listing);
    if (!dir) { close(listing); return GOLEM_ERR_IO; }
    golem_status status = GOLEM_OK;
    for (;;) {
        errno = 0;
        struct dirent *entry = readdir(dir);
        if (!entry) { if (errno) status = GOLEM_ERR_IO; break; }
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
        if (!*budget) { status = GOLEM_ERR_OVERFLOW; break; }
        --*budget;
        struct stat observed, opened, final;
        if (fstatat(fd, entry->d_name, &observed, AT_SYMLINK_NOFOLLOW) < 0) {
            status = GOLEM_ERR_IO; break;
        }
        if ((!S_ISREG(observed.st_mode) && !S_ISDIR(observed.st_mode)) ||
            observed.st_dev != device || observed.st_size < 0) {
            status = GOLEM_ERR_INVALID_STATE; break;
        }
        int child = openat(fd, entry->d_name, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK |
                           (S_ISDIR(observed.st_mode) ? O_DIRECTORY : 0));
        if (child < 0) { status = GOLEM_ERR_IO; break; }
        if (fstat(child, &opened) < 0 || !same(&observed, &opened)) status = GOLEM_ERR_INVALID_STATE;
        if (status == GOLEM_OK && S_ISDIR(opened.st_mode)) {
            if (depth >= max_depth || total->directories == UINT64_MAX) status = GOLEM_ERR_OVERFLOW;
            else {
                ++total->directories;
                status = scan(child, device, budget, depth + 1, max_depth, total);
            }
        } else if (status == GOLEM_OK) {
            uint64_t size = (uint64_t)opened.st_size;
            if (size > UINT64_MAX - total->logical_bytes || total->files == UINT64_MAX)
                status = GOLEM_ERR_OVERFLOW;
            else { total->logical_bytes += size; ++total->files; }
        }
        if (status == GOLEM_OK && (fstatat(fd, entry->d_name, &final, AT_SYMLINK_NOFOLLOW) < 0 ||
                                  !same(&opened, &final))) status = GOLEM_ERR_INVALID_STATE;
        if (close(child) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
        if (status != GOLEM_OK) break;
    }
    if (closedir(dir) < 0 && status == GOLEM_OK) status = GOLEM_ERR_IO;
    if (status == GOLEM_OK && (fstat(fd, &after) < 0 || !same(&before, &after)))
        status = GOLEM_ERR_INVALID_STATE;
    return status;
}

golem_status gi_inventory_scan(int root_fd, uint64_t entry_budget, unsigned max_depth,
    gi_inventory *out)
{
    if (root_fd < 0 || !out || !max_depth || max_depth > 64) return GOLEM_ERR_INVALID_ARGUMENT;
    struct stat root;
    if (fstat(root_fd, &root) < 0) return GOLEM_ERR_IO;
    gi_inventory result = {0};
    golem_status status = scan(root_fd, root.st_dev, &entry_budget, 0, max_depth, &result);
    if (status == GOLEM_OK) *out = result;
    return status;
}
