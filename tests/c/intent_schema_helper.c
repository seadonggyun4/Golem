#include "../../src/intent/schema.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Test-only stdin protocol: one bounded source control object, fixed abc body.
 * No Work/CAS filesystem, mutation backend, or authority enrollment. */
int main(int argc, char **argv)
{
    if (argc > 2 || (argc == 2 && strcmp(argv[1], "--digest") != 0)) return 2;
    uint8_t *input = malloc(GI_CONTROL_MAX + 1u);
    if (!input) return 2;
    size_t size = fread(input, 1, GI_CONTROL_MAX + 1u, stdin);
    if (ferror(stdin)) { free(input); return 2; }
    gi_source_result result;
    golem_diagnostic diagnostic;
    (void)golem_diagnostic_clear(&diagnostic);
    golem_digest digest;
    golem_status status = argc == 2 ? gi_domain_digest((golem_bytes){input, size}, &digest, &diagnostic) :
        gi_source_validate((golem_bytes){input, size}, (golem_bytes){(const uint8_t *)"abc", 3}, &result, &diagnostic);
    char hex[GOLEM_DIGEST_HEX_CAPACITY] = {0}; size_t required;
    if (argc == 2 && status == GOLEM_OK && golem_digest_format(&digest, hex, sizeof(hex), &required) != GOLEM_OK) {
        free(input); return 2;
    }
    printf("%d %s\n", status, argc == 2 && status == GOLEM_OK ? hex : diagnostic.message);
    free(input);
    return 0;
}
