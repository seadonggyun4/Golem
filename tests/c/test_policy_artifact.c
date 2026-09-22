#include "golem/policy.h"
#include "test.h"
#include <string.h>

int main(void)
{
    golem_policy_artifact artifact = {.revision = UINT64_MAX}, decoded;
    CHECK(golem_policy_spec_init(&artifact.policy) == GOLEM_OK);
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i)
        artifact.policy.permissions[i] = (golem_autonomy)(i % 4);
    const uint8_t golden[32] = {
        'G','P','O','L',1,0,0,0, 255,255,255,255,255,255,255,255,
        0,1,2,3,0,1,0,0, 0,0,0,0,0,0,0,0
    };
    uint8_t wire[33], saved[33]; size_t n = 0;
    CHECK(golem_policy_artifact_encode(&artifact, wire, sizeof(wire), &n) == GOLEM_OK);
    CHECK(n == sizeof(golden) && memcmp(wire, golden, n) == 0);
    CHECK(golem_policy_artifact_decode((golem_bytes){wire, n}, &decoded) == GOLEM_OK);
    CHECK(decoded.revision == artifact.revision && decoded.policy.version == GOLEM_POLICY_VERSION);
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) CHECK(decoded.policy.permissions[i] == artifact.policy.permissions[i]);
    for (size_t capacity = 0; capacity < sizeof(golden); ++capacity) {
        memset(wire, 0xa5, sizeof(wire)); memcpy(saved, wire, sizeof(wire));
        CHECK(golem_policy_artifact_encode(&artifact, wire, capacity, &n) == GOLEM_ERR_BUFFER_TOO_SMALL);
        CHECK(n == sizeof(golden) && memcmp(wire, saved, sizeof(wire)) == 0);
    }
    CHECK(golem_policy_artifact_encode(&artifact, NULL, 0, &n) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(n == sizeof(golden));
    unsigned char before[sizeof(decoded)];
    memset(&decoded, 0xa5, sizeof(decoded)); memcpy(before, &decoded, sizeof(decoded));
    for (size_t length = 0; length <= sizeof(wire); ++length) {
        if (length == sizeof(golden)) continue;
        memcpy(wire, golden, sizeof(golden)); wire[32] = 0;
        CHECK(golem_policy_artifact_decode((golem_bytes){wire, length}, &decoded) != GOLEM_OK);
        CHECK(memcmp(before, &decoded, sizeof(decoded)) == 0);
    }
    for (size_t pos = 0; pos < sizeof(golden); ++pos) {
        if (pos >= 8 && pos < 16) continue;
        memcpy(wire, golden, sizeof(golden)); wire[pos] = 255;
        CHECK(golem_policy_artifact_decode((golem_bytes){wire, sizeof(golden)}, &decoded) != GOLEM_OK);
        CHECK(memcmp(before, &decoded, sizeof(decoded)) == 0);
    }
    memcpy(wire, golden, sizeof(golden)); memset(wire + 8, 0, 8);
    CHECK(golem_policy_artifact_decode((golem_bytes){wire, sizeof(golden)}, &decoded) == GOLEM_ERR_PARSE);
    CHECK(memcmp(before, &decoded, sizeof(decoded)) == 0);
    CHECK(golem_policy_artifact_decode((golem_bytes){NULL, 32}, &decoded) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_policy_artifact_decode((golem_bytes){golden, 32}, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    artifact.revision = 0; n = 123;
    CHECK(golem_policy_artifact_encode(&artifact, wire, sizeof(wire), &n) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(n == 123);
    artifact.revision = 1; artifact.policy.version = 2;
    CHECK(golem_policy_artifact_encode(&artifact, wire, sizeof(wire), &n) != GOLEM_OK);
    artifact.policy.version = 1; artifact.policy.permissions[0] = (golem_autonomy)99;
    CHECK(golem_policy_artifact_encode(&artifact, wire, sizeof(wire), &n) != GOLEM_OK);
    CHECK(n == 123);
    CHECK(golem_policy_artifact_encode(NULL, wire, sizeof(wire), &n) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_policy_artifact_encode(&artifact, NULL, 32, &n) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_policy_artifact_encode(&artifact, wire, sizeof(wire), NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return EXIT_SUCCESS;
}
