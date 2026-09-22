#include "check.h"
#include <dirent.h>

static uint32_t state = 1701;
static uint32_t next(void)
{
    state ^= state << 13; state ^= state >> 17; state ^= state << 5;
    return state;
}
int main(int argc, char **argv)
{
    REQUIRE(argc == 2);
    DIR *dir = opendir(argv[1]); REQUIRE(dir != NULL);
    struct dirent *entry;
    size_t count = 0;
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] == '.') continue;
        char path[4096];
        int written = snprintf(path, sizeof(path), "%s/%s", argv[1], entry->d_name);
        REQUIRE(written > 0 && (size_t)written < sizeof(path));
        FILE *f = fopen(path, "rb"); REQUIRE(f != NULL);
        REQUIRE(fseek(f, 0, SEEK_END) == 0);
        long length = ftell(f); REQUIRE(length >= 0 && length <= 1048609);
        rewind(f); size_t n = (size_t)length;
        uint8_t *seed = malloc(n + 1), *mutated = malloc(n + 1);
        REQUIRE(seed != NULL && mutated != NULL);
        REQUIRE(fread(seed, 1, n, f) == n && fclose(f) == 0);
        REQUIRE(LLVMFuzzerTestOneInput(seed, n) == 0);
        /* Fixed seed per file: filesystem enumeration cannot change mutations. */
        state = 1701;
        for (size_t i = 0; i < 256; ++i) {
            memcpy(mutated, seed, n); size_t length_now = n;
            switch (i % 4) {
            case 0: if (n != 0) mutated[next() % n] ^= (uint8_t)(1u << (next() % 8)); break;
            case 1: if (n != 0) length_now = next() % n; break;
            case 2: mutated[n] = (uint8_t)next(); ++length_now; break;
            default: if (n != 0) mutated[next() % n] = (uint8_t)next(); break;
            }
            REQUIRE(LLVMFuzzerTestOneInput(mutated, length_now) == 0);
        }
        free(seed); free(mutated); ++count;
    }
    REQUIRE(closedir(dir) == 0 && count > 0);
    const size_t boundaries[] = {0, 1, 31, 32, 33, 47, 48, 49, 4096, 4097, 16384, 16385, 1048576, 1048608, 1048609};
    uint8_t *large = calloc(1048609, 1); REQUIRE(large != NULL);
    for (size_t i = 0; i < sizeof(boundaries) / sizeof(boundaries[0]); ++i)
        REQUIRE(LLVMFuzzerTestOneInput(large, boundaries[i]) == 0);
    free(large);
    state = 1701;
    uint8_t noise[4096];
    for (size_t i = 0; i < 2000; ++i) {
        size_t n = next() % sizeof(noise);
        for (size_t j = 0; j < n; ++j) noise[j] = (uint8_t)next();
        REQUIRE(LLVMFuzzerTestOneInput(noise, n) == 0);
    }
    printf("%zu seed files, 256 mutations per seed, 2000 random inputs\n", count);
    return 0;
}
