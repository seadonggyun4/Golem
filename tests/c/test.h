#ifndef GOLEM_TEST_H
#define GOLEM_TEST_H
#include <stdio.h>
#include <stdlib.h>
/* Unlike assert(), checks remain active in Release builds. */
#define CHECK(expression) do { \
    if (!(expression)) { \
        fprintf(stderr, "%s:%d: check failed: %s\n", __FILE__, __LINE__, #expression); \
        return EXIT_FAILURE; \
    } \
} while (0)
#endif
