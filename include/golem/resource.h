#ifndef GOLEM_RESOURCE_H
#define GOLEM_RESOURCE_H
#include "golem/supervisor.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Linux cgroup-v2 managed execution, not a security sandbox. Caller owns an
 * empty, dedicated cgroup directory descriptor and exclusive control of its
 * hierarchy. Must be delegated CPU/memory/pids controllers with no concurrent
 * writers or child migration. No host/global limits are modified. Processes
 * allowed to modify cgroups can escape: use a separate sandbox for hostile code.
 * helper is the installed, trusted golem-cgroup-exec absolute executable.
 * argv/env/cwd follow supervisor rules; reject loader injection variables.
 * Sets hard CPU bandwidth, memory+zero-swap and task limits before user code.
 * No agent/provider approval is implied. Host checks gates before calling.
 * cgroup.kill is attempted after execution; success requires populated=0.
 * Caller retains the scope for evidence/cleanup; this function never removes it.
 * Result is unchanged before spawn; empty is initialized false on every call.
 * Unsupported platforms fail closed with REQUIREMENTS_UNMET. */
typedef struct golem_resource_limits {
    uint64_t cpu_quota_us, cpu_period_us, memory_bytes, tasks;
} golem_resource_limits;
golem_status golem_resource_run(int cgroup_fd, const golem_resource_limits *limits,
                                const char *helper, const char *executable, char *const argv[],
                                const char *cwd, char *const envp[], golem_bytes input,
                                uint64_t timeout_ns, golem_status (*pulse)(void *), void *context,
                                golem_supervisor_result *out, bool *empty);
#ifdef __cplusplus
}
#endif
#endif
