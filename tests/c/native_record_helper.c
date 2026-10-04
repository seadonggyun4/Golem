#define _POSIX_C_SOURCE 200809L
#include "golem/record.h"
#include "golem/supervisor.h"
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <stdlib.h>
#include <pthread.h>
#include <dirent.h>
#include <fcntl.h>

static golem_status invoke(void *context)
{
    char *exe = context;
    char *argv[] = {exe, "child", NULL};
    char *env[] = {"LANG=C", NULL};
    golem_supervisor_result out;
    return golem_supervisor_run_at(exe, argv, "/", env, (golem_bytes){0},
        UINT64_C(2000000000), NULL, NULL, &out);
}
static golem_status rejected(void *context) { (void)context; return GOLEM_ERR_INVALID_STATE; }
static golem_status sabotage_finish(void *context)
{
    const char *root = context;
    DIR *dir = opendir(root);
    if (!dir) return GOLEM_ERR_IO;
    struct dirent *entry;
    while ((entry = readdir(dir))) if (strlen(entry->d_name) == 32) {
        int scope = openat(dirfd(dir), entry->d_name, O_RDONLY | O_DIRECTORY);
        if (scope < 0) { closedir(dir); return GOLEM_ERR_IO; }
        int pending = openat(scope, ".pending", O_WRONLY | O_CREAT | O_EXCL, 0600);
        close(scope);
        if (pending < 0) { closedir(dir); return GOLEM_ERR_IO; }
        close(pending);
    }
    closedir(dir);
    return GOLEM_OK;
}
static void *thread_call(void *context)
{
    golem_record_options *options = context;
    golem_status operation;
    return golem_record_call(options, rejected, NULL, &operation) == GOLEM_OK ? NULL : context;
}
int main(int argc, char **argv)
{
    if (argc == 2 && !strcmp(argv[1], "child")) {
        fputs("raw out\n", stdout); fputs("raw error\n", stderr); return 0;
    }
    if (argc != 3) return 2;
    golem_record_options options = {.struct_size = sizeof(options), .version = 1,
        .root = argv[2], .kind = "c_api", .operation = "host-call", .executable = argv[0]};
    golem_status operation = GOLEM_ERR_NOT_FOUND;
    if (!strcmp(argv[1], "finish-fail")) {
        golem_status st = golem_record_call(&options, sabotage_finish, argv[2], &operation);
        printf("%d %d\n", st, operation);
        return st != GOLEM_OK && operation == GOLEM_OK ? 0 : 13;
    }
    if (!strcmp(argv[1], "threads")) {
        pthread_t threads[4];
        for (unsigned i = 0; i < 4; ++i) if (pthread_create(&threads[i], NULL, thread_call, &options)) return 9;
        for (unsigned i = 0; i < 4; ++i) {
            void *result;
            if (pthread_join(threads[i], &result) || result) return 10;
        }
        return 0;
    }
    if (!strcmp(argv[1], "call")) {
        golem_status st = golem_record_call(&options, invoke, argv[0], &operation);
        printf("%d %d\n", st, operation);
        return st != GOLEM_OK || operation != GOLEM_OK;
    }
    if (!strcmp(argv[1], "reject")) {
        golem_status st = golem_record_call(&options, rejected, NULL, &operation);
        printf("%d %d\n", st, operation); return st != GOLEM_OK;
    }
    golem_record *record = NULL;
    if (golem_record_begin(&options, &record) != GOLEM_OK) return 3;
    if (!strcmp(argv[1], "record-fail")) {
        golem_bytes oversized = {(const uint8_t *)"", 67108865};
        if (golem_record_write(record, 0, oversized) != GOLEM_ERR_OVERFLOW) return 11;
        golem_record_result result = {.struct_size = sizeof(result), .version = 1,
            .operation_status = GOLEM_ERR_INVALID_STATE, .exit_code = -1};
        return golem_record_finish(record, &result) == GOLEM_ERR_OVERFLOW ? 0 : 12;
    }
    if (!strcmp(argv[1], "crash")) { raise(SIGKILL); return 4; }
    if (!strcmp(argv[1], "order")) {
        golem_record *nested = NULL;
        if (golem_record_begin(&options, &nested) != GOLEM_OK) return 5;
        golem_record_result result = {.struct_size = sizeof(result), .version = 1, .exit_code = -1};
        if (golem_record_finish(record, &result) != GOLEM_ERR_INVALID_ARGUMENT) return 6;
        if (golem_record_finish(nested, &result) != GOLEM_OK) return 7;
        return golem_record_finish(record, &result) != GOLEM_OK;
    }
    return 8;
}
