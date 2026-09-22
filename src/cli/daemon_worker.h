#ifndef GOLEM_CLI_DAEMON_WORKER_H
#define GOLEM_CLI_DAEMON_WORKER_H
#include "golem/daemon.h"
#include <signal.h>
typedef struct cli_daemon_host {
    const char *worker;
    volatile sig_atomic_t *stop;
} cli_daemon_host;
golem_status cli_daemon_execute(void *context, golem_runtime *runtime, golem_work_run *run,
    const char *directory, const golem_stage_snapshot *stage, uint64_t deadline,
    golem_runtime_result *out);
#endif
