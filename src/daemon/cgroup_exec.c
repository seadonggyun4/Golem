#define _GNU_SOURCE
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <sys/vfs.h>
#include <linux/magic.h>
#include <stdbool.h>
#include "cgroup_exec_internal.h"
extern char **environ;

static int verify_cgroup(int fd)
{
    struct statfs fs;
    if (fstatfs(fd, &fs) != 0) { gc_exec_error("fstatfs", errno); return -1; }
    if (fs.f_type != CGROUP2_SUPER_MAGIC) { gc_exec_error("filesystem_type", 0); return -1; }
    return 0;
}

/* Trusted trampoline: no user executable runs before kernel membership. */
int main(int argc, char **argv)
{
    return gc_exec_run(argc, argv, environ, verify_cgroup);
}
