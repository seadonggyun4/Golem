#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/system_error.h"
#include "test.h"
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <string.h>
#include <unistd.h>

static int denied_format(int fd, const char *path, struct stat *out, int flags)
{
    if (!strcmp(path, "format")) { errno = EACCES; return -1; }
    return fstatat(fd, path, out, flags);
}
#define fstatat denied_format
#include "../../src/daemon/queue.c"
#undef fstatat

int main(int argc, char **argv)
{
    CHECK(argc == 2);
    golem_system_error_scope scope;
    CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
    CHECK(golem_daemon_init(argv[1]) == GOLEM_ERR_IO);
    CHECK(golem_system_error_end(&scope) == GOLEM_OK);
    bool found = false;
    for (size_t i = 0; i < scope.count; ++i)
        if (!strcmp(scope.entries[i].component, "daemon.queue") &&
            !strcmp(scope.entries[i].operation, "fstatat_format") &&
            scope.entries[i].error_number == EACCES) found = true;
    CHECK(found);
    int fd = open(argv[1], O_RDONLY | O_DIRECTORY);
    CHECK(fd >= 0);
    struct stat out;
    CHECK(fstatat(fd, "format", &out, AT_SYMLINK_NOFOLLOW) < 0 && errno == ENOENT);
    CHECK(fstatat(fd, "jobs", &out, AT_SYMLINK_NOFOLLOW) < 0 && errno == ENOENT);
    CHECK(close(fd) == 0);
    return 0;
}
