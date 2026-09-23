#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include "test.h"
static unsigned mode, syncs, writes;
static ssize_t publication_write(int fd, const void *data, size_t size)
{
    ++writes;
    if (mode == 1 && writes > 1) {
        errno = EIO;
        return -1;
    }
    if (mode == 2 && writes == 1) {
        errno = EINTR;
        return -1;
    }
    return write(fd, data, mode == 1 && size > 1 ? 1 : size);
}
static int publication_sync(int fd)
{
    ++syncs;
    if ((mode == 3 && syncs == 1) || (mode == 4 && syncs == 2)) {
        errno = EIO;
        return -1;
    }
    return fsync(fd);
}
static int publication_link(int olddir, const char *old, int newdir, const char *name, int flags)
{
    if (mode == 5) {
        errno = EIO;
        return -1;
    }
    return linkat(olddir, old, newdir, name, flags);
}
#define write publication_write
#define fsync publication_sync
#define linkat publication_link
#include "../../src/cli/io.c"
#undef write
#undef fsync
#undef linkat

int main(void)
{
    for (mode = 1; mode <= 5; ++mode) {
        char root[] = "/tmp/golem-publication-XXXXXX";
        CHECK(mkdtemp(root) != NULL);
        int dir = open(root, O_RDONLY | O_DIRECTORY);
        CHECK(dir >= 0);
        syncs = writes = 0;
        golem_status status =
            cli_write_new(dir, "journal.bin", (golem_bytes){(const uint8_t *)"payload", 7});
        CHECK(status == (mode == 2 ? GOLEM_OK : GOLEM_ERR_IO));
        /* Export may be visible after a directory-fsync failure, but callers
         * must not publish a completion marker after any failed component. */
        if (status == GOLEM_OK)
            CHECK(cli_write_new(dir, "salvage.commit",
                                (golem_bytes){(const uint8_t *)"commit", 6}) == GOLEM_OK);
        struct stat info;
        CHECK((fstatat(dir, "salvage.commit", &info, AT_SYMLINK_NOFOLLOW) == 0) == (mode == 2));
        CHECK((fstatat(dir, "journal.bin", &info, AT_SYMLINK_NOFOLLOW) == 0) ==
              (mode == 2 || mode == 4));
        (void)unlinkat(dir, "journal.bin", 0);
        (void)unlinkat(dir, "salvage.commit", 0);
        CHECK(close(dir) == 0 && rmdir(root) == 0);
    }
    return EXIT_SUCCESS;
}
