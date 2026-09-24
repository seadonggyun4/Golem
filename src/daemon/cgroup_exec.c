#define _GNU_SOURCE
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <sys/vfs.h>
#include <linux/magic.h>
extern char **environ;

/* Trusted trampoline: no user executable runs before kernel membership. */
int main(int argc, char **argv)
{
    struct statfs fs;
    if (argc < 3 || argv[1][0] != '/' || fstatfs(3, &fs) || fs.f_type != CGROUP2_SUPER_MAGIC)
        return 126;
    int fd = openat(3, "cgroup.procs", O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0)
        return 126;
    ssize_t n = write(fd, "0", 1);
    int closed = close(fd);
    if (n != 1 || closed || close(3))
        return 126;
    execve(argv[1], argv + 2, environ);
    return 127;
}
