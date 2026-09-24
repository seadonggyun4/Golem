#define _POSIX_C_SOURCE 200809L
#include "golem/resource.h"
#include "test.h"
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv)
{
    if (argc == 2) {
        if (!strcmp(argv[1], "memory")) {
            volatile unsigned char *memory = malloc(128u * 1024u * 1024u);
            if (!memory)
                return 2;
            for (size_t i = 0; i < 128u * 1024u * 1024u; i += 4096)
                memory[i] = 1;
            free((void *)memory);
            return 0;
        }
        if (!strcmp(argv[1], "cpu")) {
            volatile unsigned value = 0;
            for (;;)
                ++value;
        }
        if (!strcmp(argv[1], "tasks")) {
            unsigned count = 0;
            for (; count < 20; ++count) {
                pid_t pid = fork();
                if (pid < 0)
                    break;
                if (!pid) {
                    for (;;)
                        pause();
                }
            }
            return count > 0 && count < 4 ? 0 : 3;
        }
        return 0;
    }
    golem_resource_limits limits = {10000, 100000, 32u * 1024u * 1024u, 4};
    golem_supervisor_result result = {.exit_code = 42};
    bool empty = true;
    CHECK(golem_resource_run(-1, &limits, "/helper", "/child", NULL, "/", NULL,
                             (golem_bytes){NULL, 0}, 1, NULL, NULL, &result,
                             &empty) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(!empty && result.exit_code == 42);
    int ordinary = open("/", O_RDONLY | O_DIRECTORY);
    CHECK(ordinary >= 0);
    char *probe_args[] = {"/must-not-execute", NULL}, *probe_env[] = {NULL};
    CHECK(golem_resource_run(ordinary, &limits, "/must-not-execute", "/must-not-execute",
                             probe_args, "/", probe_env, (golem_bytes){NULL, 0}, 1, NULL, NULL,
                             &result, &empty) == GOLEM_ERR_REQUIREMENTS_UNMET);
    CHECK(close(ordinary) == 0 && !empty && result.exit_code == 42);
    if (argc == 1)
        return 0;
    CHECK(argc == 4);
    int fd = open(argv[2], O_RDONLY | O_DIRECTORY);
    CHECK(fd >= 0);
    char *args[] = {argv[0], argv[3], NULL}, *env[] = {NULL};
    golem_status st =
        golem_resource_run(fd, &limits, argv[1], argv[0], args, "/", env, (golem_bytes){NULL, 0},
                           UINT64_C(2000000000), NULL, NULL, &result, &empty);
    CHECK(close(fd) == 0);
    CHECK(empty);
    if (!strcmp(argv[3], "memory")) {
        CHECK(st == GOLEM_ERR_INCOMPLETE_WORK && result.signal_number != 0);
    } else if (!strcmp(argv[3], "cpu")) {
        CHECK(st == GOLEM_ERR_INCOMPLETE_WORK && result.timed_out);
    } else {
        CHECK(st == GOLEM_OK && result.exit_code == 0);
    }
    return 0;
}
