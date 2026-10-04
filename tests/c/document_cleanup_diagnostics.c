#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
static int mode;
static int fake_open(int fd, const char *name, int flags, ...)
{
    (void)fd; (void)name; (void)flags;
    if (mode == 1) { errno = EACCES; return -1; }
    return 9;
}
static DIR *fake_fdopendir(int fd)
{
    (void)fd;
    if (mode == 2) { errno = EMFILE; return NULL; }
    return (DIR *)(void *)&mode;
}
static int fake_close(int fd) { (void)fd; errno = EIO; return -1; }
static struct dirent *fake_readdir(DIR *d)
{
    (void)d;
    if (mode == 3) errno = EIO;
    return NULL;
}
static int fake_closedir(DIR *d)
{
    (void)d;
    if (mode >= 3) { errno = EBADF; return -1; }
    return 0;
}
#define openat fake_open
#define fdopendir fake_fdopendir
#define close fake_close
#define readdir fake_readdir
#define closedir fake_closedir
#include "../../src/document/registry.c"
#undef openat
#undef fdopendir
#undef close
#undef readdir
#undef closedir
#include "test.h"
int main(void)
{
    for (mode = 0; mode <= 4; ++mode) {
        golem_system_error_scope scope;
        CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
        errno = EDOM;
        CHECK(empty_root(4) == (mode ? GOLEM_ERR_IO : GOLEM_OK));
        CHECK(golem_system_error_end(&scope) == GOLEM_OK);
        CHECK(scope.count == (mode == 0 ? 0u : mode == 2 || mode == 3 ? 2u : 1u));
        if (mode == 2) {
            CHECK(scope.entries[0].error_number == EMFILE);
            CHECK(scope.entries[1].error_number == EIO);
        }
        if (mode == 3) {
            CHECK(!strcmp(scope.entries[0].operation, "readdir"));
            CHECK(!strcmp(scope.entries[1].operation, "closedir"));
        }
    }
    return 0;
}
