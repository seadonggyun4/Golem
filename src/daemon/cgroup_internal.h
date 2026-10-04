#ifndef GOLEM_CGROUP_INTERNAL_H
#define GOLEM_CGROUP_INTERNAL_H
#include "golem/supervisor.h"
/* POSIX I/O mechanism only, not proof of a cgroup filesystem or authority.
 * name must be a fixed control-file label, never a user path. */
bool golem_cgroup_write_value(int scope, const char *name, const char *value);
bool golem_cgroup_is_empty(int scope, bool *empty);
golem_status golem_supervisor_run_joined(const char *, char *const[], const char *, char *const[],
                                         golem_bytes, uint64_t, golem_status (*)(void *), void *,
                                         golem_supervisor_result *, int);
#endif
