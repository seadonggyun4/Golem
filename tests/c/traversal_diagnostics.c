#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/system_error.h"
#include "test.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static const char *fault;
static bool injected;
static int test_openat(int dir, const char *name, int flags, ...)
{
    if (!strcmp(fault, "open")) { errno = EACCES; return -1; }
    return openat(dir, name, flags);
}
static DIR *test_fdopendir(int fd)
{
    if (!strcmp(fault, "fdopendir-close")) { errno = EMFILE; return NULL; }
    return fdopendir(fd);
}
static int test_close(int fd)
{
    int rc = close(fd);
    if (!strcmp(fault, "fdopendir-close")) { errno = EIO; return -1; }
    return rc;
}
static int test_closedir(DIR *dir)
{
    int rc = closedir(dir);
    if (!strcmp(fault, "closedir")) { errno = EIO; return -1; }
    return rc;
}
static struct dirent *test_readdir(DIR *dir)
{
    if (!strcmp(fault, "readdir")) { errno = EIO; return NULL; }
    return readdir(dir);
}
static int test_fstatat(int dir, const char *name, struct stat *out, int flags)
{
    if (!strcmp(fault, "fstatat")) { errno = EACCES; return -1; }
    return fstatat(dir, name, out, flags);
}
static int test_fstat(int fd, struct stat *out)
{
    if (!strcmp(fault, "fstat")) { errno = EBADF; return -1; }
    int rc = fstat(fd, out);
    if (!rc && !strcmp(fault, "identity")) { ++out->st_ino; errno = ENOSPC; }
    return rc;
}
#ifndef TEST_WORKSPACE
static int test_clock(clockid_t clock, struct timespec *out)
{
    if (!strcmp(fault, "clock")) { errno = EPERM; return -1; }
    if (!strcmp(fault, "clock-value")) { *out = (struct timespec){1, -1}; return 0; }
    return clock_gettime(clock, out);
}
static ssize_t test_read(int fd, void *buffer, size_t size)
{
    if (!strcmp(fault, "read")) { errno = EIO; return -1; }
    if (!strcmp(fault, "eintr") && !injected) { injected = true; errno = EINTR; return -1; }
    return read(fd, buffer, size);
}
static ssize_t test_readlinkat(int fd, const char *path, char *buffer, size_t size)
{
    if (!strcmp(fault, "readlink")) { errno = EIO; return -1; }
    return readlinkat(fd, path, buffer, size);
}
#define read test_read
#define readlinkat test_readlinkat
#define clock_gettime test_clock
#endif
#define openat test_openat
#define fdopendir test_fdopendir
#define close test_close
#define closedir test_closedir
#define readdir test_readdir
#define fstatat test_fstatat
#define fstat test_fstat
#ifdef TEST_WORKSPACE
#include "../../src/workspace/git.c"
#else
#include "../../src/inventory/capture.c"
#endif
#undef openat
#undef fdopendir
#undef close
#undef closedir
#undef readdir
#undef fstatat
#undef fstat
#undef read
#undef readlinkat
#undef clock_gettime

#ifdef TEST_WORKSPACE
static golem_status tick(void *context) { (void)context; return GOLEM_OK; }
#endif
int main(int argc, char **argv)
{
    CHECK(argc == 3);
    fault = argv[1];
    int fd = open(argv[2], O_RDONLY | O_DIRECTORY);
    CHECK(fd >= 0);
    golem_system_error_scope scope;
    CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
    errno = EBUSY;
    size_t visited = 0;
    golem_status status;
#ifdef TEST_WORKSPACE
    (void)injected;
    golem_workspace_host host = {.pulse = tick};
    ws_context ctx = {.host = &host};
    status = cleanup_scan(&ctx, fd, 0, &visited);
#else
    in_policy policy = {0};
    if (!strcmp(fault, "clock") || !strcmp(fault, "clock-value")) {
        struct json_object *unchanged = NULL;
        CHECK(in_capture(argv[2], &policy, &unchanged) == GOLEM_ERR_IO && unchanged == NULL);
        CHECK(golem_system_error_end(&scope) == GOLEM_OK);
        CHECK(scope.count == 1 && scope.entries[0].error_number == (!strcmp(fault, "clock") ? EPERM : 0));
        CHECK(close(fd) == 0);
        return 0;
    }
    in_scan scan = {.root = fd, .policy = &policy, .deadline = UINT64_MAX,
                    .head = "0123456789012345678901234567890123456789"};
    scan.entries = calloc(GOLEM_INVENTORY_MAX_PATHS, sizeof(*scan.entries));
    CHECK(scan.entries);
    bool contents = !strcmp(fault, "read") || !strcmp(fault, "eintr") ||
        !strcmp(fault, "readlink") || !strcmp(fault, "identity") || !strcmp(fault, "fstat");
    struct json_object *out = NULL;
    status = contents ? content(&scan, !strcmp(fault, "readlink") ? "link" : "file", &out)
                      : walk(&scan, fd, "", 0, &visited);
    json_object_put(out);
    free(scan.entries);
#endif
    CHECK(golem_system_error_end(&scope) == GOLEM_OK);
    CHECK(close(fd) == 0);
    if (!strcmp(fault, "success") || !strcmp(fault, "eintr")) {
        CHECK(status == GOLEM_OK && scope.count == 0);
    } else {
        CHECK(scope.count >= 1);
        CHECK(scope.entries[0].error_number ==
            (!strcmp(fault, "identity") ? 0 :
             !strcmp(fault, "fdopendir-close") ? EMFILE :
             !strcmp(fault, "open") || !strcmp(fault, "fstatat") ? EACCES :
             !strcmp(fault, "fstat") ? EBADF : EIO));
        if (!strcmp(fault, "fdopendir-close")) {
            CHECK(scope.count == 2 && scope.entries[1].error_number == EIO);
            CHECK(!strcmp(scope.entries[1].operation, "close"));
        }
        for (size_t i = 0; i < scope.count; ++i)
            CHECK(strchr(scope.entries[i].operation, '/') == NULL);
    }
    return 0;
}
