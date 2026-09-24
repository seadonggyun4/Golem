#define _GNU_SOURCE
#include "golem/resource.h"
#include "cgroup_internal.h"
#ifdef __linux__
#include <errno.h>
#include <fcntl.h>
#include <linux/magic.h>
#include <stdio.h>
#include <string.h>
#include <sys/vfs.h>
#include <time.h>
#include <unistd.h>

static bool write_value(int scope, const char *name, const char *value)
{
    int fd = openat(scope, name, O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0)
        return false;
    size_t size = strlen(value);
    ssize_t written;
    do {
        written = write(fd, value, size);
    } while (written < 0 && errno == EINTR);
    int closed = close(fd);
    return written == (ssize_t)size && !closed;
}

static bool is_empty(int scope, bool *empty)
{
    int fd = openat(scope, "cgroup.events", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0)
        return false;
    char text[1024];
    ssize_t n;
    do {
        n = read(fd, text, sizeof(text) - 1);
    } while (n < 0 && errno == EINTR);
    int closed = close(fd);
    if (n <= 0 || n == (ssize_t)sizeof(text) - 1 || closed)
        return false;
    text[n] = 0;
    if (!strncmp(text, "populated 0\n", 12) || strstr(text, "\npopulated 0\n")) {
        *empty = true;
        return true;
    }
    if (!strncmp(text, "populated 1\n", 12) || strstr(text, "\npopulated 1\n")) {
        *empty = false;
        return true;
    }
    return false;
}
#endif

golem_status golem_resource_run(int cgroup_fd, const golem_resource_limits *limits,
                                const char *helper, const char *executable, char *const argv[],
                                const char *cwd, char *const envp[], golem_bytes input,
                                uint64_t timeout, golem_status (*pulse)(void *), void *context,
                                golem_supervisor_result *out, bool *empty)
{
    if (!empty)
        return GOLEM_ERR_INVALID_ARGUMENT;
    *empty = false;
    if (cgroup_fd < 0 || !limits || !helper || helper[0] != '/' || !executable ||
        executable[0] != '/' || !argv || !argv[0] || !cwd || cwd[0] != '/' || !envp || !out ||
        !timeout || timeout > UINT64_C(3600000000000) || input.size > 16384 ||
        (input.size && !input.data) || limits->cpu_period_us < 1000 ||
        limits->cpu_period_us > 1000000 || limits->cpu_quota_us < 1000 ||
        limits->cpu_quota_us > UINT64_C(1000000000) || limits->memory_bytes < 4096 ||
        limits->memory_bytes > INT64_MAX || !limits->tasks || limits->tasks > 1048576)
        return GOLEM_ERR_INVALID_ARGUMENT;
#ifndef __linux__
    (void)pulse;
    (void)context;
    return GOLEM_ERR_REQUIREMENTS_UNMET;
#else
    struct statfs fs;
    if (fstatfs(cgroup_fd, &fs) || fs.f_type != CGROUP2_SUPER_MAGIC)
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    bool unused = false;
    if (!is_empty(cgroup_fd, &unused) || !unused)
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    for (size_t i = 0; envp[i]; ++i)
        if (!strncmp(envp[i], "LD_", 3) || !strncmp(envp[i], "DYLD_", 5))
            return GOLEM_ERR_POLICY_DENIED;
    char *args[68] = {(char *)helper, (char *)executable};
    size_t count = 0;
    while (argv[count]) {
        if (count >= 64)
            return GOLEM_ERR_BUDGET_EXHAUSTED;
        args[count + 2] = argv[count];
        ++count;
    }
    args[count + 2] = NULL;
    char cpu[64], memory[32], tasks[32];
    (void)snprintf(cpu, sizeof(cpu), "%llu %llu", (unsigned long long)limits->cpu_quota_us,
                   (unsigned long long)limits->cpu_period_us);
    (void)snprintf(memory, sizeof(memory), "%llu", (unsigned long long)limits->memory_bytes);
    (void)snprintf(tasks, sizeof(tasks), "%llu", (unsigned long long)limits->tasks);
    /* Requiring kill support up front avoids launching into an unmanageable scope. */
    if (!write_value(cgroup_fd, "cgroup.kill", "1") || !write_value(cgroup_fd, "cpu.max", cpu) ||
        !write_value(cgroup_fd, "memory.max", memory) ||
        !write_value(cgroup_fd, "memory.swap.max", "0") ||
        !write_value(cgroup_fd, "memory.oom.group", "1") ||
        !write_value(cgroup_fd, "pids.max", tasks))
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    int inherited = fcntl(cgroup_fd, F_DUPFD_CLOEXEC, 64);
    if (inherited < 0)
        return GOLEM_ERR_IO;
    golem_status st = golem_supervisor_run_joined(helper, args, cwd, envp, input, timeout, pulse,
                                                  context, out, inherited);
    (void)close(inherited);
    if (!write_value(cgroup_fd, "cgroup.kill", "1"))
        return GOLEM_ERR_IO;
    /* Kernel termination can lag the leader. Never equate SIGKILL with death. */
    for (unsigned i = 0; i < 500; ++i) {
        if (!is_empty(cgroup_fd, empty))
            return GOLEM_ERR_IO;
        if (*empty)
            return st;
        struct timespec delay = {.tv_nsec = 10000000};
        (void)nanosleep(&delay, NULL);
    }
    return GOLEM_ERR_INCOMPLETE_WORK;
#endif
}
