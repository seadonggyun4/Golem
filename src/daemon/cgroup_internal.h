#ifndef GOLEM_CGROUP_INTERNAL_H
#define GOLEM_CGROUP_INTERNAL_H
#include "golem/supervisor.h"
golem_status golem_supervisor_run_joined(const char *, char *const[], const char *, char *const[],
                                         golem_bytes, uint64_t, golem_status (*)(void *), void *,
                                         golem_supervisor_result *, int);
#endif
