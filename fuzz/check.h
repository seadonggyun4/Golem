#ifndef GOLEM_FUZZ_CHECK_H
#define GOLEM_FUZZ_CHECK_H
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
/* Always active, including NDEBUG builds. Compare bytes only for unchanged
 * outputs or canonical wire data, never independently populated struct padding. */
#define REQUIRE(x) do { if (!(x)) { \
    fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #x); abort(); \
} } while (0)
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
#endif
