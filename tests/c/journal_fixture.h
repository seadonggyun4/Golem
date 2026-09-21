#ifndef GOLEM_TEST_JOURNAL_FIXTURE_H
#define GOLEM_TEST_JOURNAL_FIXTURE_H
#include "test.h"
#include <stdint.h>
#define FIXTURE_CAPACITY 8192
static int load_fixture(const char *name, uint8_t *data, size_t *size)
{
    char path[1024];
    int length = snprintf(path, sizeof(path), "%s/v1_%s.hex", GOLEM_JOURNAL_FIXTURE_DIR, name);
    CHECK(length > 0 && (size_t)length < sizeof(path));
    FILE *file = fopen(path, "r");
    CHECK(file != NULL);
    unsigned value;
    size_t count = 0;
    int result;
    while ((result = fscanf(file, " %2x", &value)) == 1) {
        CHECK(count < FIXTURE_CAPACITY && value <= 255);
        data[count++] = (uint8_t)value;
    }
    CHECK(result == EOF && !ferror(file));
    CHECK(fclose(file) == 0);
    *size = count;
    return EXIT_SUCCESS;
}
#endif
