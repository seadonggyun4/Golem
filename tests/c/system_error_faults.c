#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "../../src/document/internal.h"
#include "golem/system_error.h"
#include "test.h"
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static const char *mode;
static int syncs;
static int fault_openat(int dir, const char *name, int flags, ...)
{
    if (!strcmp(mode, "openat")) { errno = EACCES; return -1; }
    if (flags & O_CREAT) {
        va_list args; va_start(args, flags);
        mode_t permissions = (mode_t)va_arg(args, int); va_end(args);
        return openat(dir, name, flags, permissions);
    }
    return openat(dir, name, flags);
}
static ssize_t fault_write(int fd, const void *data, size_t size)
{
    if (!strcmp(mode, "write")) { errno = ENOSPC; return -1; }
    if (!strcmp(mode, "write_no_progress")) { errno = EACCES; return 0; }
    return write(fd, data, size);
}
static int fault_fsync(int fd)
{
    ++syncs;
    if ((!strcmp(mode, "fsync_file") && syncs == 1) ||
        (!strcmp(mode, "fsync_directory") && syncs == 2)) { errno = EIO; return -1; }
    return fsync(fd);
}
static int fault_close(int fd)
{
    int result = close(fd);
    /* Cleanup must not overwrite a previously captured write failure. */
    errno = EBADF;
    return !strcmp(mode, "close") || !strcmp(mode, "write") ? -1 : result;
}
static int fault_fchmod(int fd, mode_t permissions)
{
    if (!strcmp(mode, "fchmod")) { errno = EPERM; return -1; }
    return fchmod(fd, permissions);
}
static int fault_linkat(int a, const char *b, int c, const char *d, int flags)
{
    if (!strcmp(mode, "linkat")) { errno = EROFS; return -1; }
    return linkat(a, b, c, d, flags);
}
static int fault_unlinkat(int dir, const char *name, int flags)
{
    if (!strcmp(mode, "unlinkat")) { errno = EIO; return -1; }
    return unlinkat(dir, name, flags);
}
#define openat fault_openat
#define write fault_write
#define fsync fault_fsync
#define close fault_close
#define fchmod fault_fchmod
#define linkat fault_linkat
#define unlinkat fault_unlinkat
#include "../../src/document/storage.c"
#undef openat
#undef write
#undef fsync
#undef close
#undef fchmod
#undef linkat
#undef unlinkat

int main(int argc, char **argv)
{
    CHECK(argc == 3);
    mode = argv[2];
    int dir = open(argv[1], O_RDONLY | O_DIRECTORY);
    CHECK(dir >= 0);
    golem_system_error_scope scope;
    CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
    golem_status st = dw_publish(dir, "record", (golem_bytes){(const uint8_t *)"test", 4});
    CHECK(golem_system_error_end(&scope) == GOLEM_OK);
    if (!strcmp(mode, "success")) CHECK(st == GOLEM_OK && scope.count == 0);
    else {
        CHECK(st == GOLEM_ERR_IO && scope.count == 1);
        CHECK(!strcmp(scope.entries[0].component, "document.publish"));
        CHECK(!strcmp(scope.entries[0].operation, mode));
        int expected = !strcmp(mode, "write_no_progress") ? 0 :
            !strcmp(mode, "openat") ? EACCES : !strcmp(mode, "write") ? ENOSPC :
            !strcmp(mode, "close") ? EBADF : !strcmp(mode, "fchmod") ? EPERM :
            !strcmp(mode, "linkat") ? EROFS : EIO;
        CHECK(scope.entries[0].error_number == expected);
    }
    struct stat info;
    bool published = !strcmp(mode, "success") || !strcmp(mode, "fsync_directory") || !strcmp(mode, "unlinkat");
    CHECK((fstatat(dir, "record", &info, 0) == 0) == published);
    CHECK(close(dir) == 0);
    return 0;
}
