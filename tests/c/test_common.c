#include "golem/types.h"
#include "golem/version.h"
#include "test.h"
#include <string.h>

int main(void)
{
    const uint8_t input[] = {0, 127, 255};
    golem_bytes bytes = {NULL, 0};
    CHECK(golem_bytes_init(&bytes, input, sizeof(input)) == GOLEM_OK);
    CHECK(bytes.data == input && bytes.size == sizeof(input));
    CHECK(bytes.data[2] == 255);
    CHECK(golem_bytes_init(&bytes, NULL, 1) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(bytes.data == input && bytes.size == sizeof(input));
    CHECK(golem_bytes_init(NULL, input, sizeof(input)) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_bytes_init(&bytes, NULL, 0) == GOLEM_OK);
    CHECK(bytes.data == NULL && bytes.size == 0);
    CHECK(strcmp(golem_status_string(GOLEM_OK), "ok") == 0);
    for (int code = GOLEM_ERR_INVALID_ARGUMENT; code <= GOLEM_ERR_LEASE_BUSY; ++code) {
        CHECK(strcmp(golem_status_string((golem_status)code), "unknown status") != 0);
    }
    CHECK(strcmp(golem_status_string((golem_status)999), "unknown status") == 0);
    CHECK(strcmp(golem_version_string(), GOLEM_VERSION_STRING) == 0);
    return EXIT_SUCCESS;
}
