#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "test.h"
#include "golem/system_error.h"
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>

static const char *mode;
static unsigned writes, reads;
static bool is(const char *s) { return !strcmp(mode, s); }
static ssize_t fault_write(int fd, const void *data, size_t size)
{
    if (is("write-close")) { errno = ENOSPC; return -1; }
    if (is("short-write")) { errno = EACCES; return 0; }
    if (is("write-eintr") && writes++ == 0) { errno = EINTR; return -1; }
    return write(fd, data, size);
}
static ssize_t fault_read(int fd, void *data, size_t size)
{
    if (is("read-close")) { errno = EACCES; return -1; }
    if (is("read-eintr") && reads++ == 0) { errno = EINTR; return -1; }
    return read(fd, data, size);
}
static int fault_close(int fd)
{
    int result = close(fd);
    if (is("write-close") || is("read-close") || is("close")) { errno = EIO; return -1; }
    return result;
}
#define write fault_write
#define read fault_read
#define close fault_close
#include "../../src/daemon/resource_io.c"
#undef write
#undef read
#undef close

int main(int argc, char **argv)
{
    CHECK(argc == 3);
    mode = argv[2];
    int root = open(argv[1], O_RDONLY | O_DIRECTORY);
    CHECK(root >= 0);
    if (!is("missing")) {
        int fd = openat(root, "cpu.max", O_CREAT | O_EXCL | O_WRONLY, 0600);
        CHECK(fd >= 0 && close(fd) == 0);
        fd = openat(root, "cgroup.events", O_CREAT | O_EXCL | O_WRONLY, 0600);
        const char *data = is("populated") ? "populated 1\n" :
                           is("malformed") ? "unknown 0\n" :
                           is("empty") ? "" : "frozen 0\npopulated 0\n";
        CHECK(fd >= 0 && write(fd, data, strlen(data)) == (ssize_t)strlen(data));
        CHECK(close(fd) == 0);
    }
    golem_system_error_scope scope;
    CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
    bool empty = false;
    bool writing = is("write-close") || is("short-write") || is("write-eintr");
    errno = EBUSY;
    bool ok = writing ? golem_cgroup_write_value(root, "cpu.max", "1000 10000") :
                        golem_cgroup_is_empty(root, &empty);
    CHECK(golem_system_error_end(&scope) == GOLEM_OK);
    bool success = is("success") || is("populated") || is("write-eintr") || is("read-eintr");
    CHECK(ok == success);
    if (success) {
        CHECK(scope.count == 0);
        CHECK(empty == (!writing && !is("populated")));
    } else {
        CHECK(!empty && scope.count > 0);
        const char *operation = is("missing") ? "open_control" :
            is("write-close") ? "write_control" : is("short-write") ? "short_write_control" :
            is("read-close") ? "read_control" : is("close") ? "close_control" :
            is("empty") ? "read_shape" : "populated_field";
        int error = is("missing") ? ENOENT : is("write-close") ? ENOSPC :
            is("read-close") ? EACCES : is("close") ? EIO : 0;
        CHECK(!strcmp(scope.entries[0].operation, operation));
        CHECK(scope.entries[0].error_number == error);
        if (is("write-close") || is("read-close")) {
            CHECK(scope.count == 2 && scope.entries[1].error_number == EIO);
            CHECK(!strcmp(scope.entries[1].operation, "close_control"));
        }
    }
    CHECK(close(root) == 0);
    return 0;
}
