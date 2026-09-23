#include "golem/binding.h"
#include "golem/error.h"
#include "../../tests/c/test.h"
#include <string.h>

int main(int argc, char **argv)
{
    CHECK(argc == 3 && golem_binding_abi_version() == 1);
    uint8_t capsule[GOLEM_BINDING_CAPSULE_MAX]; size_t size;
    FILE *f = fopen(argv[1], "rb"); CHECK(f != NULL);
    size = fread(capsule, 1, sizeof(capsule), f); CHECK(feof(f) && !ferror(f) && fclose(f) == 0);
    uint8_t journal[8192]; size_t journal_size = 0; unsigned value;
    f = fopen(argv[2], "r"); CHECK(f != NULL);
    int scanned;
    while ((scanned = fscanf(f, " %2x", &value)) == 1) { CHECK(journal_size < sizeof(journal)); journal[journal_size++] = (uint8_t)value; }
    CHECK(scanned == EOF && !ferror(f) && fclose(f) == 0);
    const char descriptor[] = "{\"adapter_id\":\"local.noop\",\"adapter_version\":\"\",\"current_agent\":0,\"domain\":\"golem.adapter-descriptor.v1\",\"effect\":1,\"features_known\":0,\"features_supported\":0,\"hidden_prompt_known\":0,\"inputs_known\":0,\"inputs_supported\":0,\"protocol_version\":1,\"sandbox\":0,\"schema_version\":1,\"session_id\":\"\",\"simulation\":2,\"stages\":63,\"tools\":[]}";
    for (size_t i = 0; i < 100; ++i) {
        char *out = NULL; size_t n = 0;
        CHECK(golem_binding_call(GOLEM_BINDING_VALIDATE, capsule, size, &out, &n) == 0);
        CHECK(out != NULL && n == strlen(out) && strstr(out, "\"valid\":true") != NULL);
        golem_binding_free(out); out = NULL;
        CHECK(golem_binding_call(GOLEM_BINDING_REPLAY, journal, journal_size, &out, &n) == 0);
        CHECK(strstr(out, "\"state\":\"SUCCEEDED\"") != NULL);
        CHECK(strstr(out, "\"acceptance_verified\":false") != NULL);
        golem_binding_free(out);
        out = NULL;
        CHECK(golem_binding_call(GOLEM_BINDING_DESCRIBE_ADAPTER, (const uint8_t *)descriptor,
            strlen(descriptor), &out, &n) == GOLEM_OK);
        CHECK(n == strlen(descriptor) && !strcmp(out, descriptor));
        golem_binding_free(out);
    }
    char sentinel = 'x', *out = &sentinel; size_t n = 123;
    CHECK(golem_binding_call(99, capsule, size, &out, &n) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(out == &sentinel && n == 123);
    CHECK(golem_binding_call(GOLEM_BINDING_DESCRIBE_ADAPTER, NULL, 1, &out, &n) != GOLEM_OK);
    CHECK(out == &sentinel && n == 123);
    CHECK(golem_binding_call(1, NULL, 1, &out, &n) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_binding_call(1, capsule, GOLEM_BINDING_CAPSULE_MAX + 1u, &out, &n) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_binding_call(2, journal, GOLEM_BINDING_JOURNAL_MAX + 1u, &out, &n) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_binding_call(1, capsule, size, NULL, &n) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_binding_call(1, capsule, size, &out, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_binding_call(2, journal, journal_size - 1, &out, &n) != 0);
    CHECK(out == &sentinel && n == 123);
    journal[0] ^= 1;
    CHECK(golem_binding_call(2, journal, journal_size, &out, &n) != 0);
    CHECK(out == &sentinel && n == 123);
    CHECK(golem_binding_status_message(GOLEM_ERR_INVALID_ARGUMENT) != NULL);
    golem_binding_free(NULL);
    return EXIT_SUCCESS;
}
