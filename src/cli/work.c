#define _POSIX_C_SOURCE 200809L
#include "work.h"
#include "../evidence/internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

golem_status cli_replay_file(const char *path, const golem_replay_options *options,
    golem_work_run **out, golem_replay_report *report)
{
    cli_blob b = {0}; golem_replay *replay = NULL;
    golem_status s = cli_read(path, CLI_BUNDLE_MAX, &b);
    if (s == GOLEM_OK) s = golem_replay_create(options, NULL, &replay, NULL);
    if (s == GOLEM_OK) s = golem_replay_feed(replay, (golem_bytes){b.data, b.size}, NULL);
    if (s == GOLEM_OK) s = golem_replay_finish(replay, out, report, NULL);
    golem_replay_free(replay); free(b.data); return s;
}
static int usage(void)
{
    fputs("Usage: golem init DIRECTORY | capsule validate FILE | run --noop CAPSULE --output RUN_DIR | replay RUN_DIR_OR_JOURNAL [--require-terminal] | cost report RUN_DIR\n", stderr);
    return 2;
}
int golem_cli_work(int argc, char **argv)
{
    golem_status s = GOLEM_OK; struct json_object *out = NULL;
    if (strcmp(argv[1], "init") == 0) {
        if (argc != 3) return usage();
        struct json_object *capsule = cli_capsule_template(); int dir = -1;
        s = capsule == NULL ? GOLEM_ERR_OUT_OF_MEMORY : cli_mkdir_new(argv[2], &dir);
        if (s == GOLEM_OK) s = cli_json_write(dir, "capsule.json", capsule);
        if (dir >= 0 && close(dir) != 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
        json_object_put(capsule); out = json_object_new_object();
        if (!cli_json_add(out, "initialized", json_object_new_boolean(true))) s = GOLEM_ERR_OUT_OF_MEMORY;
    } else if (strcmp(argv[1], "capsule") == 0) {
        if (argc != 4 || strcmp(argv[2], "validate") != 0) return usage();
        cli_blob b = {0}; golem_work_capsule *capsule = NULL;
        s = cli_read(argv[3], CLI_CAPSULE_MAX, &b);
        if (s == GOLEM_OK) s = cli_capsule_decode((golem_bytes){b.data, b.size}, &capsule);
        golem_work_capsule_free(capsule); free(b.data); out = json_object_new_object();
        if (!cli_json_add(out, "valid", json_object_new_boolean(true))) s = GOLEM_ERR_OUT_OF_MEMORY;
    } else if (strcmp(argv[1], "run") == 0) {
        if (argc != 6 || strcmp(argv[2], "--noop") != 0 || strcmp(argv[4], "--output") != 0) return usage();
        s = cli_noop_run(argv[3], argv[5], &out);
    } else if (strcmp(argv[1], "cost") == 0) {
        if (argc != 4 || strcmp(argv[2], "report") != 0) return usage();
        struct json_object *summary = NULL; s = cli_bundle_verify(argv[3], &summary, &out); json_object_put(summary);
    } else if (strcmp(argv[1], "replay") == 0) {
        if ((argc != 3 && argc != 4) || (argc == 4 && strcmp(argv[3], "--require-terminal") != 0)) return usage();
        int dir = golem_evidence_path_open(argv[2], true);
        char path[CLI_PATH_MAX]; const char *journal = argv[2]; bool complete = false;
        if (dir >= 0) {
            struct stat st;
            s = cli_path(argv[2], "complete.json", path);
            if (s == GOLEM_OK && lstat(path, &st) == 0) complete = true;
            if (complete) { struct json_object *cost = NULL; s = cli_bundle_verify(argv[2], &out, &cost); json_object_put(cost); }
            else { s = cli_path(argv[2], "journal.bin", path); journal = path; }
            if (close(dir) != 0 && s == GOLEM_OK) s = GOLEM_ERR_IO;
        }
        if (!complete && s == GOLEM_OK) {
            golem_work_run *run = NULL; golem_replay_report report;
            golem_replay_options options = {.require_terminal = argc == 4};
            s = cli_replay_file(journal, &options, &run, &report);
            if (s == GOLEM_OK) { out = cli_run_projection(run, &report, false); if (out == NULL) s = GOLEM_ERR_OUT_OF_MEMORY; }
            golem_work_run_free(run);
        }
    } else return usage();
    return cli_emit(s, out);
}
