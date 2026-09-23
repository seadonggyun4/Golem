#ifndef GOLEM_DAEMON_INTERNAL_H
#define GOLEM_DAEMON_INTERNAL_H
#include "golem/daemon.h"
#include "golem/replay.h"
#define GD_PATH 4096
#define GD_LIMIT (16u * 1024u * 1024u)
typedef struct gd_blob { uint8_t *data; size_t size; } gd_blob;
golem_status gd_path(const char *root, const char *name, char out[GD_PATH]);
golem_status gd_read(const char *path, size_t limit, gd_blob *out);
golem_status gd_write(int dir, const char *name, golem_bytes bytes);
int gd_lock(int dir, const char *name, bool create, bool exclusive);
int gd_root(const char *root);
golem_status gd_list(int root, uint64_t tickets[GOLEM_DAEMON_MAX_JOBS], size_t *count);
golem_status gd_job_path(const char *root, uint64_t ticket, char out[GD_PATH]);
golem_status gd_load(const char *path, golem_daemon_job *job, golem_runtime_options *options);
golem_status gd_intent_write(int dir, uint64_t sequence, golem_bytes frame);
golem_status gd_intents_check(const char *path, golem_bytes journal);
golem_status gd_checkpoint(const char *path, golem_journal_checkpoint *out);
golem_status gd_recover_queue(const char *root, golem_daemon_recovery_report *out);
#endif
