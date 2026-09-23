#define _POSIX_C_SOURCE 200809L
#include "golem/adapter_descriptor.h"
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
int main(int argc, char **argv)
{
    if (argc != 2 || strcmp(argv[1], "--golem-describe"))
        return 91;
    if (getenv("GOLEM_TEST_SECRET") || getenv("PATH") || getenv("HOME") || !getenv("LANG") ||
        strcmp(getenv("LANG"), "C") || !getenv("LC_ALL") || strcmp(getenv("LC_ALL"), "C"))
        return 92;
    char byte;
    if (read(STDIN_FILENO, &byte, 1) != 0)
        return 93;
    const char *name = strrchr(argv[0], '/');
    name = name ? name + 1 : argv[0];
    if (strstr(name, "hang")) {
        struct timespec delay = {2, 0};
        (void)nanosleep(&delay, NULL);
    }
    if (strstr(name, "overflow")) {
        for (size_t i = 0; i < 65536; ++i)
            if (fputc('x', stdout) == EOF)
                break;
        return 0;
    }
    if (strstr(name, "exit")) {
        fputs("private diagnostic", stderr);
        return 17;
    }
    if (strstr(name, "signal")) {
        (void)raise(SIGTERM);
        return 94;
    }
    if (strstr(name, "bad")) {
        fputs("{}", stdout);
        return 0;
    }
    golem_adapter_descriptor d;
    golem_adapter_capability c = {1, "fixture.metadata", GOLEM_ADAPTER_ALL_STAGES,
                                  GOLEM_EFFECT_LOCAL, true};
    if (golem_adapter_descriptor_from_v1(&c, &d) != GOLEM_OK)
        return 95;
    char buf[GOLEM_DESCRIPTOR_MAX_BYTES];
    size_t n;
    if (golem_adapter_descriptor_encode(&d, buf, sizeof(buf), &n) != GOLEM_OK)
        return 96;
    return fwrite(buf, 1, n, stdout) == n ? 0 : 97;
}
