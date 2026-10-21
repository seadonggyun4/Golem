#ifndef GOLEM_TEST_H
#define GOLEM_TEST_H
#include <stdio.h>
#include <stdlib.h>
#ifdef GOLEM_TEST_RAISE_POSIX_FEATURE_LEVEL
/* Reproduce libc feature-macro promotion before a fault-injected .c include. */
#undef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 202405L
#endif
/* Unlike assert(), checks remain active in Release builds. */
#define CHECK(expression) do { \
    if (!(expression)) { \
        fprintf(stderr, "%s:%d: check failed: %s\n", __FILE__, __LINE__, #expression); \
        return EXIT_FAILURE; \
    } \
} while (0)
#endif
